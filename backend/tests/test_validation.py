import pytest

from app.core.validation import A, B, N, O, S, validate
from app.responses import RawError

SCHEMA = O({
    "username": S(required=True, alphanum=True, min=3, msgs={"any.required": "使用者名稱為必填欄位"}),
    "age": N(integer=True, min=0),
    "page": N(default=1),
    "tags": A(S(valid=("a", "b"))),
    "flag": B(),
    "note": S(allow=("",)),
})


def errors(data):
    with pytest.raises(RawError) as e:
        validate(SCHEMA, data)
    assert e.value.status_code == 400 and e.value.body["error"]["code"] == "VALIDATION_ERROR"
    return {d["field"]: d["message"] for d in e.value.body["error"]["details"]}


def test_valid_input_converts_strips_and_defaults():
    out = validate(SCHEMA, {"username": "abc1", "age": "3", "flag": "true", "note": "", "extra": 1})
    assert out == {"username": "abc1", "age": 3, "page": 1, "flag": True, "note": ""}


def test_reports_all_errors_with_custom_messages():
    errs = errors({"age": -1, "tags": ["c"], "flag": "x"})
    assert errs["username"] == "使用者名稱為必填欄位"
    assert set(errs) == {"username", "age", "tags.0", "flag"}


def test_alphanum_rejects_non_ascii_and_symbols():
    assert "username" in errors({"username": "ab_c"})
    assert "username" in errors({"username": "測試帳號"})


def test_null_and_empty_string_rejected_unless_allowed():
    errs = errors({"username": None, "age": None})
    assert set(errs) == {"username", "age"}
