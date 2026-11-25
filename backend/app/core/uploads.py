"""檔案上傳，限制對應舊版 multer 設定。"""
import os
import random
import time
from pathlib import Path

from fastapi import HTTPException, UploadFile

from app.config import get_settings

IMAGE_EXTS = {".jpeg", ".jpg", ".png", ".gif", ".webp"}
IMAGE_MIME = {"image/jpeg", "image/jpg", "image/png", "image/gif", "image/webp"}
MAX_IMAGE_BYTES = 5 * 1024 * 1024


def upload_root() -> Path:
    return Path(get_settings().upload_path)


async def save_files(files: list[UploadFile], subdir: str, prefix: str, *, allowed_exts: set[str],
                     allowed_mime: set[str] | None, max_bytes: int, max_files: int, type_error: str) -> list[dict]:
    """存到 uploads/<subdir>/，回傳 [{filename, path, originalname, size, mimetype}]，path 為 /uploads/... 網址。"""
    files = [f for f in files if f and f.filename]
    if len(files) > max_files:
        raise HTTPException(400, f"最多只能上傳 {max_files} 個檔案")
    target = upload_root() / subdir
    target.mkdir(parents=True, exist_ok=True)
    saved: list[dict] = []
    for f in files:
        ext = os.path.splitext(f.filename)[1].lower()
        try:
            mime_ok = allowed_mime is None or (f.content_type or "").lower() in allowed_mime
            if ext not in allowed_exts or not mime_ok:
                raise HTTPException(400, type_error)
            data = await f.read()
        finally:
            await f.close()
        if len(data) > max_bytes:
            raise HTTPException(400, "檔案大小超過限制")
        name = f"{prefix}-{int(time.time() * 1000)}-{random.randint(0, 10**9)}{ext}"
        (target / name).write_bytes(data)
        saved.append({"filename": name, "path": f"/uploads/{subdir}/{name}", "originalname": f.filename,
                      "size": len(data), "mimetype": f.content_type})
    return saved


async def save_images(files: list[UploadFile], subdir: str, prefix: str, max_files: int = 10,
                      max_bytes: int = MAX_IMAGE_BYTES) -> list[dict]:
    return await save_files(files, subdir, prefix, allowed_exts=IMAGE_EXTS, allowed_mime=IMAGE_MIME,
                            max_bytes=max_bytes, max_files=max_files,
                            type_error="只允許上傳圖片檔案 (jpeg, jpg, png, gif, webp)")
