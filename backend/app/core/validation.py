"""Joi 相容的輸入驗證：abortEarly=false、stripUnknown=true、convert=true，錯誤格式同舊版 middleware/validation.js。"""
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.responses import RawError

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_URI = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://\S+$")
_MISSING = object()


@dataclass
class Rule:
    kind: str  # str / num / bool / arr / obj / date / any
    required: bool = False
    default: Any = _MISSING
    min: float | None = None
    max: float | None = None
    integer: bool = False
    pattern: str | None = None
    email: bool = False
    uri: bool = False
    alphanum: bool = False
    valid: tuple | None = None
    allow: tuple = ()
    items: "Rule | None" = None
    keys: dict | None = None
    unknown: bool = False
    min_keys: int | None = None
    msgs: dict = field(default_factory=dict)


def S(**kw) -> Rule: return Rule("str", **kw)  # noqa: E704
def N(**kw) -> Rule: return Rule("num", **kw)  # noqa: E704
def B(**kw) -> Rule: return Rule("bool", **kw)  # noqa: E704
def A(items: Rule | None = None, **kw) -> Rule: return Rule("arr", items=items, **kw)  # noqa: E704
def O(keys: dict | None = None, **kw) -> Rule: return Rule("obj", keys=keys, **kw)  # noqa: E704,E743
def D(**kw) -> Rule: return Rule("date", **kw)  # noqa: E704
def ANY(**kw) -> Rule: return Rule("any", **kw)  # noqa: E704


class _Errors(list):
    def add(self, path: list, rule: Rule, code: str, default_msg: str) -> None:
        self.append({"field": ".".join(str(p) for p in path), "message": rule.msgs.get(code, default_msg)})


def _label(path: list) -> str:
    return f'"{path[-1]}"' if path else '"value"'


def _check(value: Any, rule: Rule, path: list, errs: _Errors) -> Any:
    lab = _label(path)
    if value in rule.allow:
        return value
    if rule.kind == "any":
        return value
    if rule.kind == "str":
        if not isinstance(value, str):
            errs.add(path, rule, "string.base", f"{lab} must be a string")
            return value
        if value == "":
            errs.add(path, rule, "string.empty", f"{lab} is not allowed to be empty")
            return value
        if rule.valid is not None and value not in rule.valid:
            errs.add(path, rule, "any.only", f"{lab} must be one of [{', '.join(map(str, rule.valid))}]")
        if rule.min is not None and len(value) < rule.min:
            errs.add(path, rule, "string.min", f"{lab} length must be at least {int(rule.min)} characters long")
        if rule.max is not None and len(value) > rule.max:
            errs.add(path, rule, "string.max",
                     f"{lab} length must be less than or equal to {int(rule.max)} characters long")
        if rule.alphanum and not (value.isascii() and value.isalnum()):
            errs.add(path, rule, "string.alphanum", f"{lab} must only contain alpha-numeric characters")
        if rule.email and not _EMAIL.match(value):
            errs.add(path, rule, "string.email", f"{lab} must be a valid email")
        if rule.uri and not _URI.match(value):
            errs.add(path, rule, "string.uri", f"{lab} must be a valid uri")
        if rule.pattern and not re.search(rule.pattern, value):
            errs.add(path, rule, "string.pattern.base", f"{lab} fails to match the required pattern")
        return value
    if rule.kind == "num":
        num = value
        if isinstance(value, str):
            try:
                num = float(value)
            except ValueError:
                num = None
        if isinstance(num, bool) or not isinstance(num, (int, float)):
            errs.add(path, rule, "number.base", f"{lab} must be a number")
            return value
        if rule.integer and num != int(num):
            errs.add(path, rule, "number.integer", f"{lab} must be an integer")
        if num == int(num):
            num = int(num)
        if rule.min is not None and num < rule.min:
            errs.add(path, rule, "number.min", f"{lab} must be greater than or equal to {rule.min:g}")
        if rule.max is not None and num > rule.max:
            errs.add(path, rule, "number.max", f"{lab} must be less than or equal to {rule.max:g}")
        return num
    if rule.kind == "bool":
        if isinstance(value, str) and value.lower() in ("true", "false"):
            return value.lower() == "true"
        if not isinstance(value, bool):
            errs.add(path, rule, "boolean.base", f"{lab} must be a boolean")
        return value
    if rule.kind == "date":
        if isinstance(value, datetime):
            return value
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return datetime.fromtimestamp(value / 1000)
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                pass
        errs.add(path, rule, "date.base", f"{lab} must be a valid date")
        return value
    if rule.kind == "arr":
        if not isinstance(value, list):
            errs.add(path, rule, "array.base", f"{lab} must be an array")
            return value
        if rule.min is not None and len(value) < rule.min:
            errs.add(path, rule, "array.min", f"{lab} must contain at least {int(rule.min)} items")
        if rule.max is not None and len(value) > rule.max:
            errs.add(path, rule, "array.max", f"{lab} must contain less than or equal to {int(rule.max)} items")
        if rule.items is None:
            return value
        return [_check(v, rule.items, path + [i], errs) for i, v in enumerate(value)]
    if rule.kind == "obj":
        if not isinstance(value, dict):
            errs.add(path, rule, "object.base", f"{lab} must be of type object")
            return value
        if rule.keys is None:
            return value
        out = _object(value, rule, path, errs)
        if rule.min_keys is not None and len(out) < rule.min_keys:
            errs.add(path, rule, "object.min", f"{lab} must have at least {rule.min_keys} key")
        return out
    return value


def _object(data: dict, rule: Rule, path: list, errs: _Errors) -> dict:
    out: dict = {}
    for key, sub in rule.keys.items():
        if key not in data:
            if sub.required:
                errs.add(path + [key], sub, "any.required", f'"{key}" is required')
            elif sub.default is not _MISSING:
                out[key] = sub.default() if callable(sub.default) else sub.default
            continue
        value = data[key]
        if value is None and None not in sub.allow and sub.kind != "any":
            # Joi 不接受 null，除非 allow(null)
            errs.add(path + [key], sub, f"{sub.kind}.base", f'"{key}" must be a {sub.kind}')
            continue
        out[key] = _check(value, sub, path + [key], errs)
    if rule.unknown:
        for k, v in data.items():
            out.setdefault(k, v)
    return out


def validate(schema: Rule, data: Any) -> Any:
    """驗證失敗時丟 RawError(400)，格式同舊版；成功回傳轉換後、移除未知欄位的資料。"""
    errs = _Errors()
    if schema.kind == "obj" and not isinstance(data, dict):
        data = {} if data is None else data
    value = _check(data, schema, [], errs)
    if errs:
        raise RawError(400, {
            "success": False,
            "error": {"code": "VALIDATION_ERROR", "message": "輸入驗證失敗", "details": list(errs)},
        })
    return value
