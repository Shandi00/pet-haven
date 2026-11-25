from fastapi import Request, UploadFile
from starlette.datastructures import UploadFile as StarletteUploadFile

from app.core.schema import parse_form


async def read_body(request: Request, file_field: str | None = None) -> tuple[dict, list[UploadFile]]:
    """讀 multipart（巢狀欄位轉 dict，同 multer）或 JSON body，回傳 (body, files)。"""
    ctype = request.headers.get("content-type", "")
    if ctype.startswith("multipart/form-data") or ctype.startswith("application/x-www-form-urlencoded"):
        form = await request.form()
        items = [(k, v) for k, v in form.multi_items() if not isinstance(v, StarletteUploadFile)]
        files = [v for k, v in form.multi_items() if isinstance(v, StarletteUploadFile) and k == file_field]
        return parse_form(items), files
    try:
        data = await request.json()
    except ValueError:
        data = {}
    return (data if isinstance(data, dict) else {}), []
