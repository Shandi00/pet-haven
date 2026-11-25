"""迷你 Mongoose schema：型別轉換（cast）、strict 移除未知欄位、預設值、驗證，錯誤訊息格式同 Mongoose。"""
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from bson import ObjectId

_UNSET = object()


@dataclass
class F:
    type: str  # str / num / bool / date / oid / mixed
    required: Any = False  # True 或自訂訊息
    default: Any = _UNSET
    enum: tuple | None = None
    enum_msg: str | None = None
    min: tuple | float | None = None  # 數字 min；可為 (值, 訊息)
    max: tuple | float | None = None
    minlength: tuple | int | None = None
    maxlength: tuple | int | None = None
    match: tuple | None = None  # (pattern, 訊息)
    trim: bool = False
    lowercase: bool = False
    validator: Callable[[Any, dict], bool] | None = None
    validator_msg: str = ""


@dataclass
class Arr:
    of: Any  # F 或 dict（子文件，會有 _id）
    default: Any = field(default_factory=list)


class MongooseError(Exception):
    def __init__(self, errors: list[tuple[str, str]], model: str | None = None) -> None:
        self.errors = errors
        prefix = f"{model} validation failed" if model else "Validation failed"
        super().__init__(f"{prefix}: " + ", ".join(f"{p}: {m}" for p, m in errors))


def _split(spec):
    return (spec[0], spec[1]) if isinstance(spec, tuple) else (spec, None)


def _cast_value(f: F, value: Any, path: str, errors: list) -> Any:
    if value is None:
        return None
    try:
        if f.type == "str":
            if isinstance(value, (dict, list)):
                raise ValueError
            s = str(value).lower() if isinstance(value, bool) else str(value)
            if f.trim:
                s = s.strip()
            if f.lowercase:
                s = s.lower()
            return s
        if f.type == "num":
            if isinstance(value, bool):
                return int(value)
            if isinstance(value, (int, float)):
                return value
            s = str(value).strip()
            if s == "":
                return None
            n = float(s)
            return int(n) if n == int(n) else n
        if f.type == "bool":
            if isinstance(value, bool):
                return value
            s = str(value).strip().lower()
            if s in ("true", "1", "yes"):
                return True
            if s in ("false", "0", "no"):
                return False
            raise ValueError
        if f.type == "date":
            if isinstance(value, datetime):
                return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
            if isinstance(value, (int, float)):
                return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
            d = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        if f.type == "oid":
            if isinstance(value, ObjectId):
                return value
            if isinstance(value, dict) and "_id" in value:
                value = value["_id"]
            return ObjectId(str(value))
    except Exception:
        kind = {"str": "string", "num": "Number", "bool": "Boolean", "date": "date", "oid": "ObjectId"}[f.type]
        errors.append((path, f'Cast to {kind} failed for value "{value}" (type {type(value).__name__}) '
                             f'at path "{path}"'))
        return value
    return value


def cast(schema: dict, data: dict, prefix: str = "", errors: list | None = None) -> dict:
    """依 schema 轉型並移除未知欄位（Mongoose strict）。"""
    errors = [] if errors is None else errors
    out: dict = {}
    if not isinstance(data, dict):
        return out
    for key, spec in schema.items():
        if key not in data:
            continue
        path = f"{prefix}{key}"
        value = data[key]
        if isinstance(spec, F):
            out[key] = _cast_value(spec, value, path, errors)
        elif isinstance(spec, Arr):
            if value is None:
                out[key] = []
                continue
            items = value if isinstance(value, list) else [value]
            if isinstance(spec.of, dict):
                subs = []
                for i, item in enumerate(items):
                    sub = cast(spec.of, item if isinstance(item, dict) else {}, f"{path}.{i}.", errors)
                    sub["_id"] = (item.get("_id") if isinstance(item, dict) and item.get("_id") else ObjectId())
                    if isinstance(sub["_id"], str) and ObjectId.is_valid(sub["_id"]):
                        sub["_id"] = ObjectId(sub["_id"])
                    subs.append(sub)
                out[key] = subs
            else:
                out[key] = [_cast_value(spec.of, v, f"{path}.{i}", errors) for i, v in enumerate(items)]
        elif isinstance(spec, dict):
            if isinstance(value, dict):
                out[key] = cast(spec, value, f"{path}.", errors)
    return out


def apply_defaults(schema: dict, doc: dict) -> dict:
    """套用 Mongoose 建立文件時的預設值（包含巢狀物件與子文件陣列）。"""
    for key, spec in schema.items():
        if isinstance(spec, F):
            if doc.get(key) is None and spec.default is not _UNSET and key not in doc:
                doc[key] = spec.default() if callable(spec.default) else spec.default
        elif isinstance(spec, Arr):
            if key not in doc or doc[key] is None:
                doc[key] = list(spec.default)
            elif isinstance(spec.of, dict):
                for item in doc[key]:
                    apply_defaults(spec.of, item)
        elif isinstance(spec, dict):
            sub = doc.get(key)
            if not isinstance(sub, dict):
                sub = {}
            apply_defaults(spec, sub)
            doc[key] = sub
    return doc


def _check(f: F, value: Any, path: str, root: dict, errors: list, partial: bool) -> None:
    if value is None or value == "" and f.type == "str":
        if f.required and not partial:
            msg = f.required if isinstance(f.required, str) else f"Path `{path}` is required."
            errors.append((path, msg))
        return
    if f.enum is not None and value not in f.enum:
        errors.append((path, f.enum_msg or f"`{value}` is not a valid enum value for path `{path}`."))
    if f.type == "num" and isinstance(value, (int, float)):
        if f.min is not None:
            lim, msg = _split(f.min)
            if value < lim:
                errors.append((path, msg or f"Path `{path}` ({value}) is less than minimum allowed value ({lim})."))
        if f.max is not None:
            lim, msg = _split(f.max)
            if value > lim:
                errors.append((path, msg or f"Path `{path}` ({value}) is more than maximum allowed value ({lim})."))
    if f.type == "str" and isinstance(value, str):
        if f.minlength is not None:
            lim, msg = _split(f.minlength)
            if len(value) < lim:
                errors.append((path, msg or f"Path `{path}` (`{value}`) is shorter than the minimum allowed "
                                            f"length ({lim})."))
        if f.maxlength is not None:
            lim, msg = _split(f.maxlength)
            if len(value) > lim:
                errors.append((path, msg or f"Path `{path}` (`{value}`) is longer than the maximum allowed "
                                            f"length ({lim})."))
        if f.match is not None and not re.search(f.match[0], value):
            errors.append((path, f.match[1]))
    if f.validator is not None and not f.validator(value, root):
        errors.append((path, f.validator_msg))


def validate(schema: dict, doc: dict, prefix: str = "", root: dict | None = None,
             errors: list | None = None, partial: bool = False) -> list:
    """回傳錯誤清單 [(path, msg)]。partial=True 用於 findByIdAndUpdate（不檢查 required）。"""
    errors = [] if errors is None else errors
    root = doc if root is None else root
    for key, spec in schema.items():
        path = f"{prefix}{key}"
        if partial and key not in doc:
            continue
        value = doc.get(key)
        if isinstance(spec, F):
            _check(spec, value, path, root, errors, partial)
        elif isinstance(spec, Arr):
            for i, item in enumerate(value or []):
                if isinstance(spec.of, dict):
                    validate(spec.of, item or {}, f"{path}.{i}.", root, errors, False)
                else:
                    _check(spec.of, item, f"{path}.{i}", root, errors, False)
        elif isinstance(spec, dict):
            validate(spec, value if isinstance(value, dict) else {}, f"{path}.", root, errors, partial)
    return errors


def flatten(data: dict, prefix: str = "") -> dict:
    """{'a': {'b': 1}} -> {'a.b': 1}，讓 $set 只改有傳的欄位，不會整個覆蓋巢狀物件。陣列不展開。"""
    out = {}
    for k, v in data.items():
        if isinstance(v, dict) and v and not isinstance(v, ObjectId):
            out.update(flatten(v, f"{prefix}{k}."))
        else:
            out[f"{prefix}{k}"] = v
    return out


def parse_form(items: list[tuple[str, Any]]) -> dict:
    """把 multipart 的 'age[value]' / 'a[b][c]' 欄位轉成巢狀 dict（同 multer 的 append-field）。"""
    out: dict = {}
    for key, value in items:
        parts = re.findall(r"[^\[\]]+", key) if "[" in key else [key]
        cur = out
        for p in parts[:-1]:
            nxt = cur.get(p)
            if not isinstance(nxt, dict):
                nxt = {}
                cur[p] = nxt
            cur = nxt
        last = parts[-1]
        if last in cur:
            cur[last] = cur[last] + [value] if isinstance(cur[last], list) else [cur[last], value]
        else:
            cur[last] = value
    return out
