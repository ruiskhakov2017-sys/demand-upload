from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class StoredObject:
    key: str
    size_bytes: int
    content_type: str | None = None


class Storage(Protocol):
    def put_file(self, source: Path, key: str, content_type: str | None = None) -> StoredObject:
        """Store a local file under a stable key."""

    def open_path(self, key: str) -> Path:
        """Return a local path for a stored object when using filesystem storage."""

