from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum


class GoogleAdsAccessLevel(StrEnum):
    TEST = "TEST"
    EXPLORER = "EXPLORER"
    BASIC = "BASIC"
    STANDARD = "STANDARD"


@dataclass(frozen=True)
class GoogleAdsAccessProfile:
    level: str
    production_read_enabled: bool
    production_mutate_enabled: bool
    test_mutate_enabled: bool
    production_operation_limit: int | None
    test_operation_limit: int
    basic_access_status: str
    unsupported_operations: tuple[str, ...]

    def public_payload(self) -> dict:
        return {
            **asdict(self),
            "unsupported_operations": list(self.unsupported_operations),
        }


EXPLORER_UNSUPPORTED_OPERATIONS = (
    "CUSTOMER_ACCOUNT_CREATE",
    "CUSTOMER_USER_MANAGEMENT",
    "KEYWORD_PLANNING",
    "BILLING_MUTATE",
    "INVOICE_MUTATE",
)


class GoogleAdsOperationNotSupported(RuntimeError):
    def __init__(self, level: str, operation: str) -> None:
        self.code = f"{level}_OPERATION_UNSUPPORTED"
        self.level = level
        self.operation = operation
        super().__init__(
            f"{self.code}: операция {operation} недоступна при уровне {level}."
        )


_PROFILES = {
    GoogleAdsAccessLevel.TEST: GoogleAdsAccessProfile(
        level=GoogleAdsAccessLevel.TEST.value,
        production_read_enabled=False,
        production_mutate_enabled=False,
        test_mutate_enabled=True,
        production_operation_limit=0,
        test_operation_limit=15_000,
        basic_access_status="NOT_AVAILABLE",
        unsupported_operations=EXPLORER_UNSUPPORTED_OPERATIONS,
    ),
    GoogleAdsAccessLevel.EXPLORER: GoogleAdsAccessProfile(
        level=GoogleAdsAccessLevel.EXPLORER.value,
        production_read_enabled=True,
        production_mutate_enabled=True,
        test_mutate_enabled=True,
        production_operation_limit=2_880,
        test_operation_limit=15_000,
        basic_access_status="PENDING_BRAND_VERIFICATION",
        unsupported_operations=EXPLORER_UNSUPPORTED_OPERATIONS,
    ),
    GoogleAdsAccessLevel.BASIC: GoogleAdsAccessProfile(
        level=GoogleAdsAccessLevel.BASIC.value,
        production_read_enabled=True,
        production_mutate_enabled=True,
        test_mutate_enabled=True,
        production_operation_limit=15_000,
        test_operation_limit=15_000,
        basic_access_status="GRANTED",
        unsupported_operations=(),
    ),
    GoogleAdsAccessLevel.STANDARD: GoogleAdsAccessProfile(
        level=GoogleAdsAccessLevel.STANDARD.value,
        production_read_enabled=True,
        production_mutate_enabled=True,
        test_mutate_enabled=True,
        production_operation_limit=None,
        test_operation_limit=15_000,
        basic_access_status="SUPERSEDED_BY_STANDARD",
        unsupported_operations=(),
    ),
}


def normalize_access_level(value: object) -> str:
    return str(value or "").strip().upper()


def get_access_profile(value: object) -> GoogleAdsAccessProfile | None:
    normalized = normalize_access_level(value)
    try:
        level = GoogleAdsAccessLevel(normalized)
    except ValueError:
        return None
    return _PROFILES[level]


def access_summary(value: object) -> dict:
    profile = get_access_profile(value)
    if profile is None:
        return {
            "level": normalize_access_level(value) or "UNKNOWN",
            "production_read_enabled": False,
            "production_mutate_enabled": False,
            "test_mutate_enabled": False,
            "production_operation_limit": 0,
            "test_operation_limit": 0,
            "basic_access_status": "UNKNOWN",
            "unsupported_operations": [],
        }
    return profile.public_payload()


def operation_is_supported(value: object, operation: str) -> bool:
    profile = get_access_profile(value)
    return bool(profile and operation.strip().upper() not in profile.unsupported_operations)


def require_operation_supported(value: object, operation: str) -> None:
    profile = get_access_profile(value)
    level = profile.level if profile else normalize_access_level(value) or "UNKNOWN"
    if not profile or not operation_is_supported(level, operation):
        raise GoogleAdsOperationNotSupported(level, operation.strip().upper())
