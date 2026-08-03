from __future__ import annotations

import hashlib
from dataclasses import replace

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.security import utcnow
from app.db.models import (
    AccountManagerHistory,
    ConnectionStatus,
    ControlCenterEvent,
    ControlCenterProblem,
    CustomerAccount,
    GoogleAccountAccessPath,
    GoogleConnection,
    GoogleConnectionMode,
    MccAccount,
    Notification,
)
from app.google_ads.interface import CustomerAccountInfo
from app.google_ads.service import build_google_ads_adapter

REQUIRED_GOOGLE_TEST_CHILDREN = {
    "3831073849": {"1833869760", "8047280949"},
}


def sync_google_ads_hierarchy(
    db: Session,
    connection: GoogleConnection,
) -> tuple[list[CustomerAccount], list[str]]:
    adapter = build_google_ads_adapter(db, connection)
    discovery = adapter.discover_customer_hierarchy()
    now = utcnow()
    root_id = discovery.root.customer_id
    discovered_accounts = tuple(
        item
        for item in _deduplicate_accounts(discovery.accounts)
        if item.customer_id != root_id
    )
    if connection.connection_mode == GoogleConnectionMode.GOOGLE_TEST.value:
        if root_id != connection.login_customer_id:
            raise ValueError("Google вернул другой корневой MCC для тестового подключения.")
        if not discovery.root.is_test_account:
            raise ValueError("Google API не подтвердил test_account=true для тестового MCC.")
        required_children = REQUIRED_GOOGLE_TEST_CHILDREN.get(root_id, set())
        discovered_children = {item.customer_id for item in discovered_accounts}
        missing_children = sorted(required_children - discovered_children)
        if missing_children:
            raise ValueError(
                "Тестовая иерархия неполна; Google Ads не вернул Customer ID: " + ", ".join(missing_children)
            )

    root_mcc = _upsert_mcc(
        db,
        connection,
        discovery.root,
        root_id=root_id,
        now=now,
        is_root=True,
    )
    manager_nodes = {root_id: root_mcc}
    manager_remotes = [remote for remote in discovered_accounts if remote.can_manage_clients]
    for remote in manager_remotes:
        manager_nodes[remote.customer_id] = _upsert_mcc(
            db,
            connection,
            remote,
            root_id=root_id,
            now=now,
            is_root=False,
        )
    db.flush()

    seen_mcc_ids = set(manager_nodes)
    for mcc in db.scalars(select(MccAccount).where(MccAccount.connection_id == connection.id)):
        if mcc.customer_id in seen_mcc_ids:
            continue
        mcc.detached_at = mcc.detached_at or now

    seen_accounts: set[str] = set()
    seen_paths: set[tuple[str, str]] = set()
    accounts: list[CustomerAccount] = []
    for remote in (item for item in discovered_accounts if not item.can_manage_clients):
        seen_accounts.add(remote.customer_id)
        account = db.scalar(
            select(CustomerAccount).where(
                CustomerAccount.connection_id == connection.id,
                CustomerAccount.customer_id == remote.customer_id,
            )
        )
        if account is None:
            account = CustomerAccount(
                connection_id=connection.id,
                customer_id=remote.customer_id,
                first_seen_at=now,
            )
            db.add(account)
            db.flush()
        was_detached = account.detached_at is not None
        previous_mcc_id = account.primary_mcc_id
        previous_manager_id = account.manager_customer_id
        previous_path = _primary_path(db, account.id) or _latest_path(db, account.id)
        access_paths = _normalized_paths(remote, root_id)
        primary_path = access_paths[0]
        primary_manager_id = primary_path[-2] if len(primary_path) > 1 else root_id
        primary_mcc = manager_nodes.get(primary_manager_id)
        account.manager_customer_id = primary_manager_id
        account.parent_customer_id = primary_manager_id
        account.primary_mcc_id = primary_mcc.id if primary_mcc else None
        account.hierarchy_root_customer_id = root_id
        account.hierarchy_level = len(primary_path) - 1
        account.account_type = remote.account_type
        account.descriptive_name = remote.descriptive_name
        account.currency_code = remote.currency_code
        account.time_zone = remote.time_zone
        account.can_manage_clients = remote.can_manage_clients
        account.is_test_account = remote.is_test_account
        account.is_hidden = remote.is_hidden
        account.status = remote.status
        account.link_status = "ACTIVE"
        account.last_seen_at = now
        account.detached_at = None
        account.last_sync_attempt_at = now
        account.last_sync_success_at = now
        account.sync_error = None
        account.test_account_verified_at = now if remote.is_test_account else None
        account.last_google_request_ids = list(remote.request_ids)
        if account.geo_override_id:
            account.geo_id = account.geo_override_id
        else:
            account.geo_id = primary_mcc.geo_id if primary_mcc else None
        if previous_mcc_id and previous_mcc_id != account.primary_mcc_id:
            db.add(
                AccountManagerHistory(
                    account_id=account.id,
                    previous_mcc_id=previous_mcc_id,
                    current_mcc_id=account.primary_mcc_id,
                    previous_manager_customer_id=previous_manager_id,
                    current_manager_customer_id=primary_manager_id,
                    previous_path=previous_path,
                    current_path=list(primary_path),
                    reason="HIERARCHY_SYNC",
                    changed_at=now,
                    request_id=remote.request_ids[-1] if remote.request_ids else None,
                )
            )
            _record_hierarchy_event(
                db,
                account,
                "ACCOUNT_MANAGER_CHANGED",
                "Основной MCC аккаунта изменён",
                {
                    "previous_mcc_id": str(previous_mcc_id),
                    "current_mcc_id": str(account.primary_mcc_id),
                    "previous_manager_customer_id": previous_manager_id,
                    "current_manager_customer_id": primary_manager_id,
                    "previous_path": previous_path,
                    "current_path": list(primary_path),
                },
                now,
                severity="WARNING",
            )
        if was_detached:
            db.add(
                AccountManagerHistory(
                    account_id=account.id,
                    previous_mcc_id=previous_mcc_id,
                    current_mcc_id=account.primary_mcc_id,
                    previous_manager_customer_id=previous_manager_id,
                    current_manager_customer_id=primary_manager_id,
                    previous_path=previous_path,
                    current_path=list(primary_path),
                    reason="ACCESS_RESTORED",
                    changed_at=now,
                    request_id=remote.request_ids[-1] if remote.request_ids else None,
                )
            )
            _resolve_access_problem(db, account, now)
            _record_hierarchy_event(
                db,
                account,
                "ACCOUNT_ACCESS_RESTORED",
                "Доступ к аккаунту через MCC восстановлен",
                {
                    "manager_customer_id": primary_manager_id,
                    "current_path": list(primary_path),
                },
                now,
                severity="INFO",
            )
        _store_access_paths(
            db,
            connection,
            target_customer_id=remote.customer_id,
            paths=access_paths,
            now=now,
            request_id=remote.request_ids[-1] if remote.request_ids else None,
            account=account,
            mcc=None,
            seen_paths=seen_paths,
        )
        accounts.append(account)

    for remote in [discovery.root, *manager_remotes]:
        paths = ((root_id,),) if remote.customer_id == root_id else _normalized_paths(remote, root_id)
        _store_access_paths(
            db,
            connection,
            target_customer_id=remote.customer_id,
            paths=paths,
            now=now,
            request_id=remote.request_ids[-1] if remote.request_ids else None,
            account=None,
            mcc=manager_nodes[remote.customer_id],
            seen_paths=seen_paths,
        )

    existing_paths = db.scalars(
        select(GoogleAccountAccessPath).where(GoogleAccountAccessPath.connection_id == connection.id)
    )
    for path in existing_paths:
        if (path.target_customer_id, path.path_fingerprint) in seen_paths:
            continue
        path.is_active = False
        path.is_primary = False
        path.lost_at = path.lost_at or now

    existing_accounts = list(db.scalars(select(CustomerAccount).where(CustomerAccount.connection_id == connection.id)))
    for account in existing_accounts:
        if account.customer_id in seen_accounts:
            continue
        if account.detached_at is None:
            previous_path = _primary_path(db, account.id) or _latest_path(db, account.id)
            db.add(
                AccountManagerHistory(
                    account_id=account.id,
                    previous_mcc_id=account.primary_mcc_id,
                    current_mcc_id=None,
                    previous_manager_customer_id=account.manager_customer_id,
                    current_manager_customer_id=None,
                    previous_path=previous_path,
                    current_path=[],
                    reason="ACCESS_LOST",
                    changed_at=now,
                    request_id=(
                        account.last_google_request_ids[-1]
                        if account.last_google_request_ids
                        else None
                    ),
                )
            )
            _upsert_access_problem(db, account, now)
            _record_hierarchy_event(
                db,
                account,
                "ACCOUNT_ACCESS_LOST",
                "Аккаунт больше не доступен через синхронизированную иерархию MCC",
                {
                    "previous_manager_customer_id": account.manager_customer_id,
                    "previous_path": previous_path,
                },
                now,
                severity="ERROR",
            )
        account.link_status = "DETACHED"
        account.detached_at = account.detached_at or now

    connection.test_hierarchy_root_customer_id = (
        root_id
        if connection.connection_mode == GoogleConnectionMode.GOOGLE_TEST.value
        else connection.test_hierarchy_root_customer_id
    )
    connection.hierarchy_verified_at = now
    connection.hierarchy_request_ids = list(discovery.request_ids)
    connection.status = ConnectionStatus.VERIFIED.value
    connection.last_checked_at = now
    connection.last_error = None
    db.flush()
    return accounts, list(discovery.request_ids)


def _deduplicate_accounts(
    accounts: tuple[CustomerAccountInfo, ...],
) -> tuple[CustomerAccountInfo, ...]:
    by_customer_id: dict[str, CustomerAccountInfo] = {}
    for remote in accounts:
        existing = by_customer_id.get(remote.customer_id)
        if existing is None:
            by_customer_id[remote.customer_id] = remote
            continue
        access_paths = tuple(
            sorted(
                {
                    *existing.access_paths,
                    *remote.access_paths,
                },
                key=lambda path: (len(path), path),
            )
        )
        request_ids = tuple(
            dict.fromkeys([*existing.request_ids, *remote.request_ids])
        )
        can_manage_clients = (
            existing.can_manage_clients or remote.can_manage_clients
        )
        by_customer_id[remote.customer_id] = replace(
            existing,
            manager_customer_id=(
                remote.manager_customer_id or existing.manager_customer_id
            ),
            descriptive_name=(
                remote.descriptive_name or existing.descriptive_name
            ),
            currency_code=remote.currency_code or existing.currency_code,
            time_zone=remote.time_zone or existing.time_zone,
            can_manage_clients=can_manage_clients,
            is_test_account=existing.is_test_account or remote.is_test_account,
            is_hidden=existing.is_hidden and remote.is_hidden,
            status=remote.status or existing.status,
            parent_customer_id=(
                remote.parent_customer_id or existing.parent_customer_id
            ),
            hierarchy_level=min(
                value
                for value in (
                    existing.hierarchy_level,
                    remote.hierarchy_level,
                )
                if value is not None
            )
            if (
                existing.hierarchy_level is not None
                or remote.hierarchy_level is not None
            )
            else None,
            account_type="MANAGER" if can_manage_clients else "CLIENT",
            request_ids=request_ids,
            access_paths=access_paths,
        )
    return tuple(
        by_customer_id[key]
        for key in sorted(by_customer_id)
    )


def _upsert_mcc(
    db: Session,
    connection: GoogleConnection,
    remote,
    *,
    root_id: str,
    now,
    is_root: bool,
) -> MccAccount:
    mcc = db.scalar(
        select(MccAccount).where(
            MccAccount.connection_id == connection.id,
            MccAccount.customer_id == remote.customer_id,
        )
    )
    if mcc is None:
        mcc = MccAccount(
            connection_id=connection.id,
            customer_id=remote.customer_id,
            first_seen_at=now,
        )
        db.add(mcc)
    mcc.first_seen_at = mcc.first_seen_at or now
    paths = _normalized_paths(remote, root_id)
    primary_path = paths[0]
    mcc.parent_customer_id = primary_path[-2] if len(primary_path) > 1 else None
    mcc.hierarchy_level = len(primary_path) - 1
    mcc.is_root = is_root
    mcc.descriptive_name = remote.descriptive_name
    mcc.currency_code = remote.currency_code
    mcc.time_zone = remote.time_zone
    mcc.is_test_account = remote.is_test_account
    mcc.status = remote.status
    mcc.request_ids = list(remote.request_ids)
    mcc.last_sync_success_at = now
    mcc.last_seen_at = now
    mcc.detached_at = None
    return mcc


def _normalized_paths(remote, root_id: str) -> tuple[tuple[str, ...], ...]:
    paths = tuple(
        sorted(
            {
                tuple(str(item) for item in path)
                for path in (remote.access_paths or ())
                if path and path[0] == root_id and path[-1] == remote.customer_id
            },
            key=lambda item: (len(item), item),
        )
    )
    if paths:
        return paths
    parent = remote.parent_customer_id or remote.manager_customer_id or root_id
    return ((root_id, remote.customer_id),) if parent == root_id else ((root_id, parent, remote.customer_id),)


def _path_fingerprint(path: tuple[str, ...]) -> str:
    return hashlib.sha256(">".join(path).encode("ascii")).hexdigest()


def _primary_path(db: Session, account_id) -> list[str]:
    row = db.scalar(
        select(GoogleAccountAccessPath).where(
            GoogleAccountAccessPath.account_id == account_id,
            GoogleAccountAccessPath.is_primary.is_(True),
            GoogleAccountAccessPath.is_active.is_(True),
        )
    )
    return list(row.customer_path) if row else []


def _latest_path(db: Session, account_id) -> list[str]:
    row = db.scalar(
        select(GoogleAccountAccessPath)
        .where(GoogleAccountAccessPath.account_id == account_id)
        .order_by(desc(GoogleAccountAccessPath.last_seen_at))
    )
    return list(row.customer_path) if row else []


def _access_problem_fingerprint(account: CustomerAccount) -> str:
    return hashlib.sha256(f"{account.id}:ACCESS_LOST".encode()).hexdigest()


def _upsert_access_problem(
    db: Session,
    account: CustomerAccount,
    now,
) -> None:
    fingerprint = _access_problem_fingerprint(account)
    problem = db.scalar(
        select(ControlCenterProblem).where(
            ControlCenterProblem.fingerprint == fingerprint
        )
    )
    if problem is None:
        problem = ControlCenterProblem(
            fingerprint=fingerprint,
            connection_id=account.connection_id,
            account_id=account.id,
            source="HIERARCHY_SYNC",
            problem_type="ACCESS_LOST",
            severity="ERROR",
            title="Потерян доступ через MCC",
            description=(
                "Аккаунт не найден при последней синхронизации иерархии. "
                "Локальные заметки, теги и история сохранены."
            ),
            state="NEW",
            first_seen_at=now,
            last_seen_at=now,
            last_changed_at=now,
            previous_state={"link_status": account.link_status},
            current_state={"link_status": "DETACHED"},
        )
        db.add(problem)
        return
    problem.state = "NEW"
    problem.last_seen_at = now
    problem.last_changed_at = now
    problem.resolved_at = None
    problem.previous_state = {"link_status": account.link_status}
    problem.current_state = {"link_status": "DETACHED"}


def _resolve_access_problem(
    db: Session,
    account: CustomerAccount,
    now,
) -> None:
    problem = db.scalar(
        select(ControlCenterProblem).where(
            ControlCenterProblem.fingerprint
            == _access_problem_fingerprint(account)
        )
    )
    if problem is None or problem.state == "RESOLVED":
        return
    problem.previous_state = problem.current_state or {}
    problem.current_state = {"link_status": "ACTIVE"}
    problem.state = "RESOLVED"
    problem.last_seen_at = now
    problem.last_changed_at = now
    problem.resolved_at = now


def _record_hierarchy_event(
    db: Session,
    account: CustomerAccount,
    event_type: str,
    summary: str,
    details: dict,
    now,
    *,
    severity: str,
) -> None:
    db.add(
        ControlCenterEvent(
            account_id=account.id,
            event_type=event_type,
            source="HIERARCHY_SYNC",
            summary=summary,
            details=details,
            occurred_at=now,
        )
    )
    db.add(
        Notification(
            user_id=None,
            severity=severity,
            title=summary,
            message=(
                f"{account.local_name or account.descriptive_name or account.customer_id} "
                f"({account.customer_id})"
            ),
            entity_type="customer_account",
            entity_id=str(account.id),
        )
    )


def _store_access_paths(
    db: Session,
    connection: GoogleConnection,
    *,
    target_customer_id: str,
    paths: tuple[tuple[str, ...], ...],
    now,
    request_id: str | None,
    account: CustomerAccount | None,
    mcc: MccAccount | None,
    seen_paths: set[tuple[str, str]],
) -> None:
    for index, customer_path in enumerate(paths):
        fingerprint = _path_fingerprint(customer_path)
        seen_paths.add((target_customer_id, fingerprint))
        row = db.scalar(
            select(GoogleAccountAccessPath).where(
                GoogleAccountAccessPath.connection_id == connection.id,
                GoogleAccountAccessPath.target_customer_id == target_customer_id,
                GoogleAccountAccessPath.path_fingerprint == fingerprint,
            )
        )
        if row is None:
            row = GoogleAccountAccessPath(
                connection_id=connection.id,
                target_customer_id=target_customer_id,
                path_fingerprint=fingerprint,
                first_seen_at=now,
                last_seen_at=now,
            )
            db.add(row)
        row.account_id = account.id if account else None
        row.mcc_account_id = mcc.id if mcc else None
        row.root_customer_id = customer_path[0]
        row.manager_customer_id = customer_path[-2] if len(customer_path) > 1 else None
        row.customer_path = list(customer_path)
        row.depth = len(customer_path) - 1
        row.is_primary = index == 0
        row.is_active = True
        row.last_seen_at = now
        row.lost_at = None
        row.last_request_id = request_id
