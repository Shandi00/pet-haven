"""users collection：預設值與虛擬欄位對應舊版 models/User.js。"""
from datetime import datetime, timezone

from app.core.serialize import to_json

ROLES = ("user", "shelter", "admin")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def new_user_doc(**fields) -> dict:
    """建立新使用者文件，套用 Mongoose 會自動補上的預設值。"""
    now = _now()
    doc = {
        "authProvider": "local",
        "avatar_url": None,
        "role": "user",
        "status": "active",
        "isActive": True,
        "isEmailVerified": False,
        "preferences": {
            "pet_types": [], "sizes": [], "ages": [],
            "notification_preferences": {"email": True, "sms": False, "push": True},
        },
        "recommendationProfile": {
            "species": [], "sizes": [], "ageCategories": [], "personality": [],
            "healthPreferences": {"vaccinated": False, "spayed": False, "microchipped": False},
            "specialNeeds": {"goodWithChildren": False, "goodWithOtherPets": False},
            "lastUpdated": now,
        },
        "lifestyleProfile": {"lastUpdated": now},
        "experienceProfile": {"petOwnershipExperience": "none", "previousPets": [], "lastUpdated": now},
        "environmentProfile": {"childrenAges": [], "otherPets": [], "lastUpdated": now},
        "gameProfile": None,  # 配對小遊戲結果（T10）
        "matchFeedback": [],  # Top 3 適合／不適合回饋（T13）
        "browsingHistory": [],
        "favorites": [],
        "collections": [],
        "adoptionHistory": [],
        "stats": {"posts_count": 0, "pets_count": 0, "adoptions_count": 0,
                  "followers_count": 0, "following_count": 0},
        "createdAt": now,
        "updatedAt": now,
        "__v": 0,
    }
    doc.update({k: v for k, v in fields.items() if v is not None})
    return doc


def user_json(doc: dict | None) -> dict | None:
    """toSafeObject()：移除 password 並加上虛擬欄位。"""
    if doc is None:
        return None
    out = to_json(doc)
    out["fullName"] = f"{doc.get('firstName') or ''} {doc.get('lastName') or ''}".strip()
    addr = doc.get("address") or {}
    if isinstance(addr, dict):
        out["fullAddress"] = (f"{addr.get('zipCode') or ''} "
                              f"{addr.get('city') or ''}{addr.get('district') or ''}{addr.get('street') or ''}").strip()
    return out
