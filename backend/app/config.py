from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # 舊 .env 還有 Node 用的變數，忽略即可
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # repr=False：錯誤訊息或 log 印出設定時不露出連線字串（含資料庫密碼）與密鑰
    mongodb_uri: str = Field(min_length=1, repr=False)
    mongodb_db: str = "pet_haven"
    cors_origins: str = "http://localhost:3000"

    jwt_secret: str = Field(min_length=1, repr=False)
    # development 時登入限制較寬鬆；test 時不限制
    app_env: str = "development"
    frontend_url: str = "http://localhost:3000"

    google_client_id: str = ""
    google_client_secret: str = Field("", repr=False)
    google_callback_url: str = "http://localhost:5000/api/auth/google/callback"

    # AI（T12）：只在後端讀取；規則見 docs/api/新增API契約.md §0
    gemini_api_key: SecretStr = SecretStr("")  # SecretStr：設定被印出或記錄時不會露出金鑰
    gemini_model: str = "gemini-3.1-flash-lite"
    llm_timeout_seconds: float = 8

    # npm run seed 建立的收容所帳號密碼；沒設定時用 seed.py 的預設值（只能用在本機與 CI）
    seed_shelter_password: SecretStr = SecretStr("")

    upload_path: str = "uploads"
    log_level: str = "INFO"
    # 單一請求上限：寵物最多 10 張 5MB 照片，加上表單欄位
    max_request_bytes: int = 55 * 1024 * 1024

    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
