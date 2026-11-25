from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import db
from app.config import get_settings
from app.responses import register_error_handlers
from app.routers import health


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
