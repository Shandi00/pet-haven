from datetime import datetime, timezone

import bcrypt
from bson import ObjectId

from app.core.ids import same_id
from app.core.security import create_token, decode_token, hash_password, verify_password
from app.core.serialize import to_json


def test_to_json_matches_mongoose_format():
    oid = ObjectId()
    doc = {"_id": oid, "password": "x", "createdAt": datetime(2026, 1, 2, 3, 4, 5, 678000, tzinfo=timezone.utc),
           "photos": [{"_id": oid, "url": "/a.jpg"}]}
    out = to_json(doc)
    assert out["_id"] == str(oid) and out["id"] == str(oid)
    assert "password" not in out
    assert out["createdAt"] == "2026-01-02T03:04:05.678Z"
    assert out["photos"][0]["id"] == str(oid)


def test_verify_bcryptjs_hash():
    # bcryptjs 產生的 $2a$ 雜湊要能驗證，舊帳號才不用重設密碼
    legacy = bcrypt.hashpw(b"secret123", bcrypt.gensalt(4)).decode().replace("$2b$", "$2a$", 1)
    assert verify_password("secret123", legacy)
    assert not verify_password("wrong", legacy)
    assert not verify_password("secret123", None)


def test_hash_password_uses_cost_12():
    assert hash_password("abc123").startswith("$2b$12$")


def test_token_payload_matches_node():
    uid = ObjectId()
    payload = decode_token(create_token(uid, "shelter"))
    assert payload["userId"] == str(uid) and payload["role"] == "shelter"
    assert payload["exp"] - payload["iat"] == 7 * 24 * 3600


def test_same_id_accepts_mixed_types():
    oid = ObjectId()
    assert same_id(oid, str(oid)) and same_id({"_id": oid}, oid)
    assert not same_id(oid, ObjectId()) and not same_id(None, oid)
