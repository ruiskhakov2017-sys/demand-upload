from pathlib import Path
from shutil import copy2

from app.core.config import settings
from app.storage.interface import StoredObject


class FilesystemStorage:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or settings.storage_root

    def put_file(self, source: Path, key: str, content_type: str | None = None) -> StoredObject:
        target = self.open_path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        copy2(source, target)
        return StoredObject(key=key, size_bytes=target.stat().st_size, content_type=content_type)

    def open_path(self, key: str) -> Path:
        normalized = Path(key)
        if normalized.is_absolute() or ".." in normalized.parts:
            raise ValueError("Некорректный storage key")
        return self.root / normalized

