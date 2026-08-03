from __future__ import annotations

from datetime import datetime, timedelta

from app.core.security import utcnow
from app.db.models import CustomerAccount, GoogleConnection, GoogleConnectionMode
from app.google_ads.client_factory import normalize_customer_id


class GoogleAdsSafetyError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def normalized_execution_mode(value: str) -> str:
    normalized = str(value or "").upper()
    return "PRODUCTION" if normalized == "LIVE" else normalized


def require_google_test_connection_target(
    connection: GoogleConnection | None,
    account: CustomerAccount | None,
    customer_id: str,
) -> None:
    if connection is None or account is None:
        raise GoogleAdsSafetyError(
            "GOOGLE_TEST_TARGET_NOT_FOUND",
            "Тестовое подключение или аккаунт не найдены.",
        )
    if connection.connection_mode != GoogleConnectionMode.GOOGLE_TEST.value:
        raise GoogleAdsSafetyError(
            "PRODUCTION_MUTATE_BLOCKED",
            "Реальный mutate разрешён только для подключения GOOGLE_TEST.",
        )
    target = normalize_customer_id(customer_id)
    root = normalize_customer_id(
        connection.test_hierarchy_root_customer_id or connection.login_customer_id
    )
    if normalize_customer_id(connection.login_customer_id) != root:
        raise GoogleAdsSafetyError(
            "TEST_HIERARCHY_ROOT_MISMATCH",
            "login_customer_id не совпадает с подтверждённым тестовым MCC.",
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
            "TEST_HIERARCHY_MEMBERSHIP_FAILED",
            "Customer ID не подтверждён внутри тестовой иерархии MCC.",
        )
    if not account.is_test_account:
        raise GoogleAdsSafetyError(
            "TEST_ACCOUNT_NOT_CONFIRMED",
            "Google API ещё не подтвердил customer.test_account=true.",
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
    require_google_test_connection_target(connection, account, customer_id)
    target = normalize_customer_id(customer_id)
    if normalize_customer_id(str(fresh_state.get("customer_id") or "")) != target:
        raise GoogleAdsSafetyError(
            "FRESH_STATE_CUSTOMER_MISMATCH",
            "Google вернул состояние другого Customer ID.",
        )
    if not bool(fresh_state.get("test_account")):
        raise GoogleAdsSafetyError(
            "TEST_ACCOUNT_NOT_CONFIRMED",
            "Свежий ответ Google не подтвердил customer.test_account=true.",
        )
    if bool(fresh_state.get("manager")):
        raise GoogleAdsSafetyError(
            "MANAGER_MUTATE_BLOCKED",
            "Свежий ответ Google показывает управляющий аккаунт; mutate запрещён.",
        )
    now = utcnow()
    verified_at = account.test_account_verified_at
    if verified_at is None or now - verified_at > max_age:
        raise GoogleAdsSafetyError(
            "STALE_TEST_ACCOUNT_STATE",
            "Подтверждение тестового аккаунта устарело; выполните свежее чтение.",
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


def require_execution_mode_for_connection(
    connection: GoogleConnection | None,
    execution_mode: str,
) -> None:
    mode = normalized_execution_mode(execution_mode)
    if mode == "SIMULATION":
        return
    if mode == "PRODUCTION":
        raise GoogleAdsSafetyError(
            "PRODUCTION_MUTATE_BLOCKED",
            "Production mutate полностью заблокирован.",
        )
    if mode != "GOOGLE_TEST":
        raise GoogleAdsSafetyError(
            "UNKNOWN_EXECUTION_MODE",
            f"Неподдерживаемый режим выполнения: {execution_mode}.",
        )
    if connection is None or connection.connection_mode != "GOOGLE_TEST":
        raise GoogleAdsSafetyError(
            "GOOGLE_TEST_CONNECTION_REQUIRED",
            "Для GOOGLE_TEST требуется отдельное подтверждённое тестовое подключение.",
        )
