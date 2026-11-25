from contextlib import asynccontextmanager
from pathlib import Path

import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import db
from app.config import get_settings
from app.realtime import sio
from app.responses import register_error_handlers
from app.routers import auth, health, pets


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.connect(get_settings())
    yield
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
)
register_error_handlers(app)
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(pets.router)

_uploads = Path(get_settings().upload_path)
_uploads.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=_uploads), name="uploads")

# uvicorn 啟動的是這個：Socket.IO 處理 /socket.io/，其他請求交給 FastAPI
asgi_app = socketio.ASGIApp(sio, other_asgi_app=app)
