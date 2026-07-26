from __future__ import annotations

import json
import subprocess
from pathlib import Path

from PIL import Image

IMAGE_MAX_BYTES = 5 * 1024 * 1024
VIDEO_MAX_BYTES = 5 * 1024 * 1024 * 1024


def inspect_media(path: Path, content_type: str | None) -> dict:
    if _looks_like_image(path, content_type):
        return _inspect_image(path)
    if _looks_like_video(path, content_type):
        return _inspect_video(path)
    raise ValueError("Поддерживаются изображения JPEG/PNG и видео MP4/MOV/WebM")


def _looks_like_image(path: Path, content_type: str | None) -> bool:
    return (content_type or "").startswith("image/") or path.suffix.lower() in {".jpg", ".jpeg", ".png"}


def _looks_like_video(path: Path, content_type: str | None) -> bool:
    return (content_type or "").startswith("video/") or path.suffix.lower() in {".mp4", ".mov", ".webm"}


def _inspect_image(path: Path) -> dict:
    size = path.stat().st_size
    with Image.open(path) as image:
        image.verify()
    with Image.open(path) as image:
        width, height = image.size
        image_format = image.format
    errors: list[str] = []
    warnings: list[str] = []
    if image_format not in {"JPEG", "PNG"}:
        errors.append("Google Ads принимает JPEG и PNG")
    if size > IMAGE_MAX_BYTES:
        errors.append("Размер изображения превышает 5 МБ")
    if width < 128 or height < 128:
        errors.append("Минимальный размер изображения — 128 x 128")
    ratio = round(width / height, 4) if height else None
    known_ratios = {"SQUARE": 1.0, "LANDSCAPE": 1.91, "PORTRAIT": 0.8, "TALL": 0.5625}
    closest_role, closest_ratio = min(known_ratios.items(), key=lambda item: abs(item[1] - (ratio or 0)))
    if ratio is not None and abs(closest_ratio - ratio) > 0.08:
        warnings.append("Соотношение сторон не совпадает с основными форматами Demand Gen")
    return {
        "kind": "IMAGE",
        "width": width,
        "height": height,
        "duration_seconds": None,
        "aspect_ratio": ratio,
        "validation": {
            "valid": not errors,
            "errors": errors,
            "warnings": warnings,
            "suggested_role": closest_role,
            "format": image_format,
        },
    }


def _inspect_video(path: Path) -> dict:
    size = path.stat().st_size
    if size > VIDEO_MAX_BYTES:
        raise ValueError("Размер видео превышает 5 ГБ")
    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,codec_name:format=duration,format_name",
        "-of",
        "json",
        str(path),
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True, timeout=30)
        payload = json.loads(result.stdout)
        stream = payload.get("streams", [{}])[0]
        file_format = payload.get("format", {})
        width = int(stream.get("width") or 0)
        height = int(stream.get("height") or 0)
        duration = float(file_format.get("duration") or 0)
    except (subprocess.SubprocessError, ValueError, KeyError, json.JSONDecodeError) as exc:
        raise ValueError("Видео не удалось прочитать через FFmpeg") from exc
    errors: list[str] = []
    if not width or not height or not duration:
        errors.append("В видео не найден корректный видеопоток")
    return {
        "kind": "VIDEO",
        "width": width or None,
        "height": height or None,
        "duration_seconds": round(duration, 3) if duration else None,
        "aspect_ratio": round(width / height, 4) if height else None,
        "validation": {
            "valid": not errors,
            "errors": errors,
            "warnings": [],
            "codec": stream.get("codec_name"),
            "format": file_format.get("format_name"),
        },
    }
