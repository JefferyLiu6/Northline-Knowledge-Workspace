"""Immutable uploads with validated storage keys."""
import os
import shutil
import uuid
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit
from fastapi import UploadFile
from common.exception_handler import CustomException

from settings import UPLOAD_DIR, PUBLIC_API_BASE
DOWNLOAD_PREFIX = PUBLIC_API_BASE + "/files/download/"

def resolve(filename):
    root = Path(UPLOAD_DIR).resolve()
    if not filename or Path(filename).name != filename or "\\" in filename:
        raise CustomException("Invalid filename")
    path = (root / filename).resolve()
    if path.parent != root or not path.is_file():
        raise CustomException("File does not exist")
    return str(path)

def storage_name(url):
    parts = urlsplit(url or "")
    allowed = {"", "127.0.0.1:9090", "localhost:9090", urlsplit(PUBLIC_API_BASE).netloc}
    prefixes = {"/files/download/", urlsplit(DOWNLOAD_PREFIX).path}
    prefix = next((p for p in prefixes if parts.path.startswith(p)), None)
    if parts.netloc not in allowed or prefix is None:
        raise CustomException("Invalid uploaded file URL")
    return unquote(parts.path.removeprefix(prefix))

def save(file: UploadFile, owner_id: int | None = None):
    name = file.filename or ""
    if Path(name).name != name or "\\" in name or name in {"", ".", ".."}:
        raise CustomException("Invalid filename")
    suffix = Path(name).suffix.lower()
    if suffix not in {".pdf", ".docx", ".xlsx", ".md", ".txt", ".png", ".jpg", ".jpeg", ".webp"}:
        raise CustomException("Unsupported file type")
    file.file.seek(0, 2)
    size = file.file.tell()
    file.file.seek(0)
    if size > 50 * 1024 * 1024:
        raise CustomException("Upload must be at most 50 MB")
    if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
        from PIL import Image
        try:
            with Image.open(file.file) as img:
                img.verify()
        except Exception:
            raise CustomException("Invalid image")
        finally:
            file.file.seek(0)
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    key = (str(owner_id) + "-" if owner_id is not None else "") + uuid.uuid4().hex + suffix
    with open(Path(UPLOAD_DIR) / key, "xb") as target:
        shutil.copyfileobj(file.file, target)
    return DOWNLOAD_PREFIX + quote(key)

def public_url(url):
    if not url:
        return url
    try:
        return DOWNLOAD_PREFIX + quote(storage_name(url))
    except CustomException:
        return url
