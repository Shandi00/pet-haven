import re
import time

import pytest

from app.models.adoption import SCHEMA

EMAIL = SCHEMA["emergencyContact"]["email"].match[0]


@pytest.mark.parametrize("email", ["a@b.co", "first.last@mail.example.com", "a-b@c-d.com.tw", "x_1@y.org"])
def test_valid_emails_still_match(email):
    assert re.search(EMAIL, email)


@pytest.mark.parametrize("email", ["a@b", "a@b.c", "a@b.test", "@b.com", "a b@c.com", "a@b..com"])
def test_invalid_emails_still_rejected(email):
    # 沿用舊版規則：網域結尾只接受 2–3 個字元
    assert not re.search(EMAIL, email)


def test_email_check_does_not_hang_on_long_input():
    # 舊的 (\w+([.-]?\w+)*) 是巢狀量詞，比對失敗時指數級回溯，整個後端會卡住（ReDoS）
    start = time.monotonic()
    assert not re.search(EMAIL, "e2e" + "1" * 40 + "@example.test")
    assert time.monotonic() - start < 0.1
