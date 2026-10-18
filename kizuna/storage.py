"""Protected file storage for capture uploads.

Files are stored outside the web root under data/uploads/<org_id>/ with random
names, validated by extension, declared MIME type *and* magic bytes, and only
served through an authenticated, tenant-checked endpoint (with HTTP Range
support so evidence links can seek inside videos).
"""
from __future__ import annotations

import hashlib
import os
import re
import secrets
from pathlib import Path

ALLOWED = {
    "video": {".mp4": "video/mp4", ".webm": "video/webm", ".mov": "video/quicktime", ".m4v": "video/mp4"},
    "image": {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"},
    "document": {".pdf": "application/pdf", ".txt": "text/plain", ".md": "text/markdown"},
    "transcript": {".txt": "text/plain", ".vtt": "text/vtt", ".srt": "application/x-subrip"},
}
SIZE_LIMITS_MB = {"video": None, "image": 15, "document": 25, "transcript": 2}


def _magic_ok(ext: str, head: bytes) -> bool:
    if ext in (".mp4", ".m4v", ".mov"):
        return head[4:8] in (b"ftyp", b"moov", b"mdat", b"wide", b"free")
    if ext == ".webm":
        return head[:4] == b"\x1a\x45\xdf\xa3"
    if ext == ".png":
        return head[:8] == b"\x89PNG\r\n\x1a\n"
    if ext in (".jpg", ".jpeg"):
        return head[:3] == b"\xff\xd8\xff"
    if ext == ".webp":
        return head[:4] == b"RIFF" and head[8:12] == b"WEBP"
    if ext == ".pdf":
        return head[:5] == b"%PDF-"
    # text formats: must decode as UTF-8 and contain no NUL bytes
    try:
        head.decode("utf-8")
    except UnicodeDecodeError:
        try:
            head[:-3].decode("utf-8")
        except UnicodeDecodeError:
            return False
    return b"\x00" not in head


def safe_name(name: str) -> str:
    base = os.path.basename(name or "upload")
    base = re.sub(r"[^\w.\- ()぀-ヿ一-鿿]", "_", base)[:120]
    return base or "upload"


class UploadError(Exception):
    pass


def validate_meta(kind: str, filename: str) -> tuple[str, str]:
    if kind not in ALLOWED:
        raise UploadError(f"Unsupported upload kind '{kind}'")
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED[kind]:
        raise UploadError(f"'{ext or 'no extension'}' is not allowed for {kind}. Allowed: {', '.join(ALLOWED[kind])}")
    return ext, ALLOWED[kind][ext]


def limit_bytes(kind: str, global_mb: int) -> int:
    lim = SIZE_LIMITS_MB.get(kind) or global_mb
    return min(lim, global_mb) * 1024 * 1024


def store(upload_dir: Path, org_id: str, ext: str, writer) -> tuple[str, int, str, Path]:
    """`writer(fh)` streams the body into fh and returns bytes written."""
    folder = upload_dir / org_id
    folder.mkdir(parents=True, exist_ok=True)
    stored = secrets.token_hex(16) + ext
    path = folder / stored
    try:
        with path.open("wb") as fh:
            size = writer(fh)
        with path.open("rb") as fh:
            head = fh.read(64)
        if not _magic_ok(ext, head):
            raise UploadError("File content does not match its extension")
        h = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                h.update(chunk)
        return stored, size, h.hexdigest(), path
    except Exception:
        path.unlink(missing_ok=True)
        raise


def resolve(upload_dir: Path, org_id: str, stored_name: str) -> Path:
    p = (upload_dir / org_id / stored_name).resolve()
    if (upload_dir / org_id).resolve() not in p.parents:
        raise UploadError("Invalid path")
    return p


def parse_range(header: str | None, size: int) -> tuple[int, int] | None:
    if not header or not header.startswith("bytes="):
        return None
    spec = header[6:].split(",")[0].strip()
    start_s, _, end_s = spec.partition("-")
    try:
        if start_s == "":
            n = int(end_s)
            return max(0, size - n), size - 1
        start = int(start_s)
        end = int(end_s) if end_s else size - 1
    except ValueError:
        return None
    if start >= size or start > end:
        return None
    return start, min(end, size - 1)
