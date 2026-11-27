import pytest
from pydantic import ValidationError

from app.config import Settings


def test_settings_ignore_unknown_keys(tmp_path, monkeypatch):
    monkeypatch.delenv("MONGODB_URI", raising=False)
    env = tmp_path / ".env"
    env.write_text("MONGODB_URI=mongodb://x\nJWT_SECRET=abc\nNODE_ENV=development\n", encoding="utf-8")
    s = Settings(_env_file=env)
    assert s.mongodb_uri == "mongodb://x"


def test_settings_require_mongodb_uri(monkeypatch):
    monkeypatch.delenv("MONGODB_URI", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_cors_origin_list_strips_spaces(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "http://a:3000, http://b:3000,")
    assert Settings(_env_file=None).cors_origin_list() == ["http://a:3000", "http://b:3000"]


def test_settings_repr_hides_secrets(monkeypatch):
    # 錯誤訊息或 log 印出設定時，不能露出資料庫連線字串（含密碼）與各種密鑰
    for k, v in {"MONGODB_URI": "mongodb://u:dbpass@h", "JWT_SECRET": "jwtsecret",
                 "GOOGLE_CLIENT_SECRET": "gsecret"}.items():
        monkeypatch.setenv(k, v)
    text = repr(Settings(_env_file=None)) + str(Settings(_env_file=None))
    assert not any(s in text for s in ("dbpass", "jwtsecret", "gsecret"))


def test_settings_reject_empty_mongodb_uri(monkeypatch):
    # .env.example 複製過來後 MONGODB_URI= 留空，要在讀設定時就報錯
    monkeypatch.setenv("MONGODB_URI", "")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_production_requires_long_jwt_secret(monkeypatch):
    # 弱的 HS256 密鑰可以被暴力破解；正式環境要求至少 32 字元，開發與測試不擋（CI 的測試密鑰較短）
    monkeypatch.setenv("MONGODB_URI", "mongodb://x")
    monkeypatch.setenv("JWT_SECRET", "short-secret")
    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)
    monkeypatch.setenv("JWT_SECRET", "x" * 32)
    assert Settings(_env_file=None).app_env == "production"
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("JWT_SECRET", "short-secret")
    assert Settings(_env_file=None).jwt_secret == "short-secret"
