"""Authenticated uploads and authorized downloads."""
from pathlib import Path
import mimetypes
from fastapi import APIRouter, File, UploadFile, Depends, Request
from starlette.responses import FileResponse
from common.auth import get_current_user
from common.exception_handler import CustomException
from common.result import Result
from models import User
from service import file_service

router = APIRouter(prefix="/files")

async def file_user(request: Request):
    return await get_current_user(request.headers.get("token") or request.cookies.get("file_session"))

@router.post("/upload")
async def upload_file(file: UploadFile = File(...), user: User = Depends(get_current_user)):
    if user.role != "ADMIN" and Path(file.filename or "").suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise CustomException("Only administrators may upload documents", "403")
    return Result.success(file_service.save(file, user.id))

@router.get("/download/{filename}")
async def download_file(filename: str, user: User = Depends(file_user)):
    if user.role != "ADMIN":
        if Path(filename).suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"} or not (filename.startswith(str(user.id) + "-") or (user.avatar and file_service.storage_name(user.avatar) == filename)):
            raise CustomException("No operation permissions", "403")
    return FileResponse(file_service.resolve(filename), filename=filename, media_type=mimetypes.guess_type(filename)[0] or "application/octet-stream",
                        headers={"X-Content-Type-Options": "nosniff"})
