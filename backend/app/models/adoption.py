"""adoptions collection：對應舊版 models/Adoption.js。"""
import math
from datetime import datetime, timedelta, timezone

from app.core.schema import Arr, F, MongooseError, apply_defaults, cast, validate
from app.core.serialize import to_json
from app.db import get_db

STATUSES = ("pending", "under-review", "approved", "rejected", "completed", "cancelled")
# rawSubmission 在舊版是 select: false，預設不回傳
DEFAULT_PROJECTION = {"rawSubmission": 0}


def _now():
    return datetime.now(timezone.utc)


def _ad(root):
    return root.get("applicantDetails") or {}


SCHEMA = {
    "applicationId": F("str"),
    "pet": F("oid", required="寵物資訊為必填項目"),
    "applicant": F("oid", required="申請人資訊為必填項目"),
    "status": F("str", enum=STATUSES, enum_msg="請選擇有效的申請狀態", default="pending"),
    "applicantDetails": {
        "housingType": F("str", enum=("apartment", "house", "condo", "other")),
        "hasYard": F("bool", default=False),
        "isRented": F("bool", default=False),
        "landlordApproval": F("bool", required=lambda r: bool(_ad(r).get("isRented"))),
        "householdMembers": {
            "adults": F("num", default=1, min=(1, "至少需要一位成人")),
            "children": F("num", default=0, min=(0, "兒童數量不能為負數")),
            "childrenAges": Arr(F("num", min=(0, "年齡不能為負數"), max=(18, "請輸入 18 歲以下兒童年齡"))),
        },
        "allergies": {
            "hasAllergies": F("bool", default=False),
            "allergyDetails": F("str", required=lambda r: bool((_ad(r).get("allergies") or {}).get("hasAllergies")),
                                maxlength=(500, "過敏詳情不能超過 500 個字元")),
        },
        "petExperience": {
            "hasPrevious": F("bool", default=False),
            "previousPets": Arr({"species": F("str"), "yearsOwned": F("num"), "whatHappened": F("str")}),
            "currentPets": Arr({"species": F("str"), "age": F("num"), "vaccinated": F("bool"), "spayed": F("bool")}),
        },
        "workSchedule": {
            "employmentStatus": F("str", enum=("employed", "unemployed", "retired", "student", "self-employed")),
            "hoursAway": F("num", default=8, min=(0, "離家時間不能為負數"), max=(24, "離家時間不能超過 24 小時")),
            "whoWillCare": F("str", maxlength=(200, "照顧者資訊不能超過 200 個字元")),
        },
        "age": F("num", min=(0, "年齡不能為負數"), max=(120, "請輸入合理的年齡")),
        "occupation": F("str", maxlength=(100, "職業不能超過 100 個字元")),
        "veterinarianInfo": {
            "hasVet": F("bool", default=False),
            "vetName": F("str", required=lambda r: bool((_ad(r).get("veterinarianInfo") or {}).get("hasVet"))),
            "vetPhone": F("str", required=lambda r: bool((_ad(r).get("veterinarianInfo") or {}).get("hasVet"))),
            "vetAddress": F("str", required=lambda r: bool((_ad(r).get("veterinarianInfo") or {}).get("hasVet"))),
        },
        "carePlan": {
            "dailyAvailableHours": F("num", min=(0, "每日可陪伴時間不能為負數"), max=(24, "每日可陪伴時間不可超過 24 小時")),
            "exercisePlan": F("str", maxlength=(1000, "運動/活動計畫過長")),
            "vetCarePlan": F("str", maxlength=(1000, "獸醫照護計畫過長")),
            "financialPlan": F("str", maxlength=(1000, "財務規劃過長")),
            "otherNotes": F("str", maxlength=(1000, "補充說明過長")),
        },
        "address": F("str", maxlength=(300, "地址不能超過 300 個字元")),
        "contactPhone": F("str"),
    },
    "motivation": {
        "reasons": Arr(F("str", maxlength=(200, "認養原因不能超過 200 個字元"))),
        "expectations": F("str", maxlength=(1000, "認養期望不能超過 1000 個字元")),
        "commitment": F("str", maxlength=(500, "承諾聲明不能超過 500 個字元")),
    },
    "rawSubmission": F("mixed"),
    "rawSubmissionMeta": {
        "createdAt": F("date", default=_now),
        "source": F("str", default="web"),
        "backfilledFrom": F("str", default=""),
        "backfilledAt": F("date"),
    },
    "emergencyContact": {
        "name": F("str", required="緊急聯絡人姓名為必填項目", maxlength=(50, "姓名不能超過 50 個字元")),
        "relationship": F("str", maxlength=(50, "關係不能超過 50 個字元")),
        "phone": F("str", required="緊急聯絡人電話為必填項目", match=(r"^09\d{8}$", "請輸入有效的台灣手機號碼格式")),
        "email": F("str", match=(r"^\w+([.-]?\w+)*@\w+([.-]?\w+)*(\.\w{2,3})+$", "請輸入有效的電子郵件格式")),
    },
    "reviewNotes": Arr({
        "reviewer": F("oid", required=True),
        "note": F("str", required=True, maxlength=(1000, "審核備註不能超過 1000 個字元")),
        "createdAt": F("date", default=_now),
    }),
    "reviewDecision": {
        "decision": F("str", enum=("approved", "rejected")),
        "reviewer": F("oid"),
        "reason": F("str", maxlength=(500, "決定原因不能超過 500 個字元")),
        "reviewDate": F("date"),
    },
    "completionInfo": {
        "adoptionDate": F("date"),
        "fee": F("num", min=(0, "費用不能為負數")),
        "microchipTransferred": F("bool", default=False),
        "documentsProvided": Arr(F("str", enum=("vaccination-record", "health-certificate", "microchip-info",
                                                 "care-instructions", "food-info", "other"))),
        "completedBy": F("oid"),
    },
    "followUp": {
        "scheduled": Arr({"date": F("date"), "type": F("str", enum=("phone", "visit", "email")),
                          "completed": F("bool", default=False), "notes": F("str")}),
    },
    "priority": F("str", enum=("low", "normal", "high", "urgent"), default="normal"),
    "agreementAccepted": F("bool", default=True),
    "agreementDate": F("date", default=_now),
}


async def next_application_id() -> str:
    """AD + 今天日期 + 當天第幾筆（伺服器本地時間，同舊版）。"""
    local = datetime.now().astimezone()
    start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    count = await get_db().adoptions.count_documents({"createdAt": {"$gte": start, "$lt": start + timedelta(days=1)}})
    return f"AD{local:%Y%m%d}{count + 1:03d}"


async def prepare_new_adoption(data: dict) -> dict:
    errors: list = []
    doc = cast(SCHEMA, data, errors=errors)
    apply_defaults(SCHEMA, doc)
    errors += validate(SCHEMA, doc)
    if errors:
        raise MongooseError(errors, "Adoption")
    doc["applicationId"] = await next_application_id()
    now = _now()
    doc.update(createdAt=now, updatedAt=now, __v=0)
    return doc


def check_adoption(doc: dict) -> None:
    """adoption.save() 對既有文件做整份驗證。"""
    errors = validate(SCHEMA, doc)
    if errors:
        raise MongooseError(errors, "Adoption")


def adoption_json(doc: dict | None) -> dict | None:
    if doc is None:
        return None
    out = to_json(doc)
    created = doc.get("createdAt")
    if isinstance(created, datetime):
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        out["applicationDuration"] = math.ceil(abs((_now() - created).total_seconds()) / 86400)
    return out
