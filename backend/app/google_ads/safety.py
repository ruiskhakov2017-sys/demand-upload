from __future__ import annotations

from datetime import datetime, timedelta

from app.core.config import settings
from app.core.security import utcnow
from app.db.models import CustomerAccount, GoogleConnection, GoogleConnectionMode
from app.google_ads.access import get_access_profile, normalize_access_level
from app.google_ads.client_factory import normalize_customer_id


class GoogleAdsSafetyError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def normalized_execution_mode(value: str) -> str:
    normalized = str(value or "").upper()
    return "PRODUCTION" if normalized == "LIVE" else normalized


def require_connection_target(
    connection: GoogleConnection | None,
    account: CustomerAccount | None,
    customer_id: str,
    execution_mode: str,
) -> None:
    mode = normalized_execution_mode(execution_mode)
    if connection is None or account is None:
        raise GoogleAdsSafetyError(
            "GOOGLE_ADS_TARGET_NOT_FOUND",
            "Подключение Google Ads или целевой аккаунт не найдены.",
        )
    if mode not in {
        GoogleConnectionMode.GOOGLE_TEST.value,
        GoogleConnectionMode.PRODUCTION.value,
    }:
        raise GoogleAdsSafetyError(
            "UNKNOWN_EXECUTION_MODE",
            f"Неподдерживаемый режим выполнения: {execution_mode}.",
        )
    if connection.connection_mode != mode:
        raise GoogleAdsSafetyError(
            "GOOGLE_ADS_CONNECTION_MODE_MISMATCH",
            f"Для режима {mode} требуется подключение с тем же режимом.",
        )
    target = normalize_customer_id(customer_id)
    root = normalize_customer_id(
        connection.test_hierarchy_root_customer_id
        if mode == GoogleConnectionMode.GOOGLE_TEST.value
        else connection.login_customer_id
    )
    if normalize_customer_id(connection.login_customer_id) != root:
        raise GoogleAdsSafetyError(
            "HIERARCHY_ROOT_MISMATCH",
            "login_customer_id не совпадает с подтверждённым корнем MCC.",
        )
    if target == root or account.can_manage_clients or account.account_type == "MANAGER":
        raise GoogleAdsSafetyError(
            "MANAGER_MUTATE_BLOCKED",
            "Изменения управляющего MCC запрещены.",
        )
    if account.connection_id != connection.id or normalize_customer_id(account.customer_id) != target:
        raise GoogleAdsSafetyError(
            "TEST_HIERARCHY_MEMBERSHIP_FAILED",
            "Customer ID не принадлежит выбранному тестовому подключению.",
        )
    hierarchy_root = account.hierarchy_root_customer_id
    if not hierarchy_root or normalize_customer_id(hierarchy_root) != root:
        raise GoogleAdsSafetyError(
            "HIERARCHY_MEMBERSHIP_FAILED",
            "Customer ID не подтверждён внутри выбранной иерархии MCC.",
        )
    if mode == GoogleConnectionMode.GOOGLE_TEST.value and not account.is_test_account:
        raise GoogleAdsSafetyError(
            "TEST_ACCOUNT_NOT_CONFIRMED",
            "Google API ещё не подтвердил customer.test_account=true.",
        )
    if mode == GoogleConnectionMode.PRODUCTION.value and account.is_test_account:
        raise GoogleAdsSafetyError(
            "PRODUCTION_ACCOUNT_NOT_CONFIRMED",
            "Для режима PRODUCTION нужен аккаунт с customer.test_account=false.",
        )


def require_google_test_connection_target(
    connection: GoogleConnection | None,
    account: CustomerAccount | None,
    customer_id: str,
) -> None:
    require_connection_target(
        connection,
        account,
        customer_id,
        GoogleConnectionMode.GOOGLE_TEST.value,
    )


def require_fresh_account_state(
    connection: GoogleConnection,
    account: CustomerAccount,
    customer_id: str,
    fresh_state: dict,
    *,
    execution_mode: str,
    confirmed_at: datetime | None = None,
    require_confirmation: bool = True,
    max_age: timedelta = timedelta(minutes=15),
) -> None:
    mode = normalized_execution_mode(execution_mode)
    require_connection_target(connection, account, customer_id, mode)
    target = normalize_customer_id(customer_id)
    if normalize_customer_id(str(fresh_state.get("customer_id") or "")) != target:
        raise GoogleAdsSafetyError(
            "FRESH_STATE_CUSTOMER_MISMATCH",
            "Google вернул состояние другого Customer ID.",
        )
    if mode == GoogleConnectionMode.GOOGLE_TEST.value and not bool(
        fresh_state.get("test_account")
    ):
        raise GoogleAdsSafetyError(
            "TEST_ACCOUNT_NOT_CONFIRMED",
            "Свежий ответ Google не подтвердил customer.test_account=true.",
        )
    if mode == GoogleConnectionMode.PRODUCTION.value and bool(
        fresh_state.get("test_account")
    ):
        raise GoogleAdsSafetyError(
            "PRODUCTION_ACCOUNT_NOT_CONFIRMED",
            "Свежий ответ Google показывает тестовый аккаунт, а не production.",
        )
    if bool(fresh_state.get("manager")):
        raise GoogleAdsSafetyError(
            "MANAGER_MUTATE_BLOCKED",
            "Свежий ответ Google показывает управляющий аккаунт; mutate запрещён.",
        )
    now = utcnow()
    verified_at = (
        account.test_account_verified_at
        if mode == GoogleConnectionMode.GOOGLE_TEST.value
        else account.last_sync_success_at
    )
    if verified_at is None or now - verified_at > max_age:
        raise GoogleAdsSafetyError(
            "STALE_ACCOUNT_STATE",
            "Подтверждение состояния аккаунта устарело; выполните свежее чтение.",
        )
    if require_confirmation and confirmed_at is None:
        raise GoogleAdsSafetyError(
            "ACTION_NOT_CONFIRMED",
            "Реальное действие не подтверждено пользователем.",
        )
    if confirmed_at is not None and confirmed_at > now:
        raise GoogleAdsSafetyError(
            "INVALID_CONFIRMATION_TIME",
            "Время подтверждения действия некорректно.",
        )


def require_fresh_google_test_state(
    connection: GoogleConnection,
    account: CustomerAccount,
    customer_id: str,
    fresh_state: dict,
    *,
    confirmed_at: datetime | None = None,
    require_confirmation: bool = True,
    max_age: timedelta = timedelta(minutes=15),
) -> None:
    require_fresh_account_state(
        connection,
        account,
        customer_id,
        fresh_state,
        execution_mode=GoogleConnectionMode.GOOGLE_TEST.value,
        confirmed_at=confirmed_at,
        require_confirmation=require_confirmation,
        max_age=max_age,
    )


def require_execution_mode_for_connection(
    connection: GoogleConnection | None,
    execution_mode: str,
    access_level: str | None = None,
) -> None:
    mode = normalized_execution_mode(execution_mode)
    if mode == "SIMULATION":
        return
    profile = get_access_profile(access_level or settings.google_ads_access_level)
    if profile is None:
        raise GoogleAdsSafetyError(
            "UNKNOWN_GOOGLE_ADS_ACCESS_LEVEL",
            (
                "Неизвестный уровень Google Ads API: "
                f"{normalize_access_level(access_level or settings.google_ads_access_level) or 'UNKNOWN'}."
            ),
        )
    if mode not in {"GOOGLE_TEST", "PRODUCTION"}:
        raise GoogleAdsSafetyError(
            "UNKNOWN_EXECUTION_MODE",
            f"Неподдерживаемый режим выполнения: {execution_mode}.",
        )
    if connection is None or connection.connection_mode != mode:
        raise GoogleAdsSafetyError(
            "GOOGLE_ADS_CONNECTION_REQUIRED",
            f"Для {mode} требуется активное подключение с тем же режимом.",
        )
    if mode == "GOOGLE_TEST" and not profile.test_mutate_enabled:
        raise GoogleAdsSafetyError(
            "TEST_MUTATE_NOT_ALLOWED",
            f"Уровень {profile.level} не разрешает mutate тестовых аккаунтов.",
        )
    if mode == "PRODUCTION" and not profile.production_mutate_enabled:
        raise GoogleAdsSafetyError(
            "PRODUCTION_MUTATE_ACCESS_DENIED",
            f"Уровень {profile.level} не разрешает mutate production-аккаунтов.",
        )
