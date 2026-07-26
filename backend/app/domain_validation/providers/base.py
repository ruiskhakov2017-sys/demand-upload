from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class ReputationTarget:
    url: str
    domain: str


@dataclass
class ProviderResult:
    provider: str
    verdict: str
    categories: list[str] = field(default_factory=list)
    diagnostics: dict = field(default_factory=dict)
    attempts: int = 1

    def as_dict(self) -> dict:
        return {
            "provider": self.provider,
            "verdict": self.verdict,
            "categories": self.categories,
            "diagnostics": self.diagnostics,
            "attempts": self.attempts,
        }


@dataclass(frozen=True)
class ProviderUnavailable(Exception):
    code: str
    diagnostics: dict = field(default_factory=dict)


class ReputationProvider(Protocol):
    name: str
    enabled: bool

    def check(self, target: ReputationTarget) -> ProviderResult: ...
