from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # 舊 .env 還有 Node 用的變數，忽略即可
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mongodb_uri: str = Field(min_length=1)
    mongodb_db: str = "pet_haven"
    cors_origins: str = "http://localhost:3000"

    jwt_secret: str = Field(min_length=1)
    # development 時登入限制較寬鬆；test 時不限制
    app_env: str = "development"
    frontend_url: str = "http://localhost:3000"

    google_client_id: str = ""
    google_client_secret: str = ""
    google_callback_url: str = "http://localhost:5000/api/auth/google/callback"

    upload_path: str = "uploads"
    log_level: str = "INFO"
    # 單一請求上限：寵物最多 10 張 5MB 照片，加上表單欄位
    max_request_bytes: int = 55 * 1024 * 1024

    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
