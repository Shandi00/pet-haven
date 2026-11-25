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
