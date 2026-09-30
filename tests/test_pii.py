from app.pii import scrub_text


def test_scrub_email() -> None:
    out = scrub_text("Email me at student@vinuni.edu.vn")
    assert "student@" not in out
    assert "REDACTED_EMAIL" in out


def test_scrub_common_vietnamese_phone_formats() -> None:
    phone_numbers = (
        "0901234567",
        "090 123 4567",
        "090.123.4567",
        "090-123-4567",
        "+84 90 123 4567",
    )

    for phone_number in phone_numbers:
        out = scrub_text(f"Contact: {phone_number}")
        assert phone_number not in out
        assert "REDACTED_PHONE_VN" in out


def test_scrub_cccd() -> None:
    out = scrub_text("CCCD: 012345678901")
    assert "012345678901" not in out
    assert "REDACTED_CCCD" in out


def test_scrub_credit_card() -> None:
    out = scrub_text("Card: 1234-5678-9012-3456")
    assert "1234-5678-9012-3456" not in out
    assert "REDACTED_CREDIT_CARD" in out


def test_scrub_event_processor() -> None:
    from app.logging_config import scrub_event

    raw_event = {
        "event": "user contact: 0901234567",
        "payload": {
            "email": "test@vinuni.edu.vn",
            "nested": {
                "cccd": "123456789012",
            },
        },
    }
    cleaned = scrub_event(None, "info", raw_event)
    assert "0901234567" not in cleaned["event"]
    assert "REDACTED_PHONE_VN" in cleaned["event"]
    assert "test@vinuni.edu.vn" not in cleaned["payload"]["email"]
    assert "REDACTED_EMAIL" in cleaned["payload"]["email"]
    assert "123456789012" not in cleaned["payload"]["nested"]["cccd"]
    assert "REDACTED_CCCD" in cleaned["payload"]["nested"]["cccd"]


def test_scrub_passport() -> None:
    out = scrub_text("My passport number is B1234567")
    assert "B1234567" not in out
    assert "REDACTED_PASSPORT" in out


def test_scrub_address() -> None:
    out = scrub_text("Dia chi: Số 12 Đường Giải Phóng, Quận Hai Bà Trưng")
    assert "REDACTED_ADDRESS_VN" in out


def test_summarize_text_scrubs_pii() -> None:
    from app.pii import summarize_text

    raw = "Refund request for email student@vinuni.edu.vn and phone 0901234567"
    summary = summarize_text(raw, max_len=100)
    assert "student@" not in summary
    assert "0901234567" not in summary
    assert "REDACTED_EMAIL" in summary
    assert "REDACTED_PHONE_VN" in summary


def test_hash_user_id() -> None:
    from app.pii import hash_user_id

    hashed = hash_user_id("student-12345")
    assert len(hashed) == 12
    assert hashed == hash_user_id("student-12345")
    assert hashed != "student-12345"


