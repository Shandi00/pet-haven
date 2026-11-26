import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import db
from app.config import get_settings
from app.core.limits import BodySizeLimitMiddleware
from app.core.logging import RequestContextMiddleware, setup_logging
from app.realtime import sio
from app.responses import register_error_handlers
from app.routers import (adoptions, ai, auth, browsing_history, comments, data_import, health, matching, messages,
                         notifications, pets, posts, recommendations, stats, users)

ROUTERS = [health, auth, pets, adoptions, notifications, matching, recommendations, messages, users,
           browsing_history, stats, posts, comments, data_import, ai]

setup_logging(get_settings().log_level)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.connect(get_settings())
    # 背景建立索引：Atlas 連不上時不擋住啟動，/api/ready 會回 503
    index_task = asyncio.create_task(db.ensure_indexes())
    yield
    index_task.cancel()
    await db.close()


app = FastAPI(
    title="Pet Haven API",
    docs_url="/api-docs",
    openapi_url="/api-docs.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)
app.add_middleware(BodySizeLimitMiddleware)
# 最後加入的在最外層：request id 與存取紀錄涵蓋所有請求（含 CORS 預檢與 413）
app.add_middleware(RequestContextMiddleware)
register_error_handlers(app)
for module in ROUTERS:
    app.include_router(module.router)

_uploads = Path(get_settings().upload_path)
_uploads.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=_uploads), name="uploads")

# uvicorn 啟動的是這個：Socket.IO 處理 /socket.io/，其他請求交給 FastAPI
asgi_app = socketio.ASGIApp(sio, other_asgi_app=app)
