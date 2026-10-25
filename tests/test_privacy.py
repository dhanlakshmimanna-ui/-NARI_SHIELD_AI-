import pytest

from privacy import preview, redact_text


def test_email_redacted():
    r = redact_text("write to jane.doe@example.com now")
    assert "jane.doe@example.com" not in r.text and "[REDACTED-EMAIL]" in r.text
    assert r.counts["email"] == 1


@pytest.mark.parametrize("phone", ["9000000000", "+91 90000 00000", "+91-90000-00000", "090000 00000"])
def test_phone_numbers_redacted(phone):
    r = redact_text(f"call me on {phone} please")
    assert phone not in r.text and "[REDACTED-PHONE]" in r.text


def test_otp_in_context_redacted_and_label_kept():
    r = redact_text("Your OTP is 482913, do not share")
    assert "482913" not in r.text and "OTP" in r.text and "[REDACTED-OTP]" in r.text


def test_standalone_six_digit_code_redacted():
    r = redact_text("code was 123456 ok")
    assert "123456" not in r.text


def test_password_redacted():
    r = redact_text("my password is Hunter2!")
    assert "Hunter2" not in r.text and "[REDACTED-SECRET]" in r.text


def test_card_or_aadhaar_like_numbers_redacted():
    r = redact_text("card 4111 1111 1111 1111 and id 1234 5678 9012")
    assert "4111" not in r.text and "9012" not in r.text
    assert r.counts["id_or_card_number"] == 2


def test_custom_terms_case_insensitive():
    r = redact_text("Ravi and RAVI met", extra_terms=["ravi", "", None])
    assert "ravi" not in r.text.lower() and r.counts["custom_term"] == 2


def test_short_numbers_and_years_untouched():
    r = redact_text("It happened at 7pm on 12 March 2026, bus 45")
    assert r.text == "It happened at 7pm on 12 March 2026, bus 45" and r.total == 0


@pytest.mark.parametrize("bad", ["", None, 12, [], {}])
def test_empty_and_invalid_input(bad):
    r = redact_text(bad)
    assert r.text == "" and r.total == 0
    p = preview(bad)
    assert p["original"] == "" and p["redacted"] == "" and p["total_redactions"] == 0


def test_preview_contains_both_versions_and_limitations():
    p = preview("mail a@b.com", ["mail"])
    assert p["original"] == "mail a@b.com"
    assert "a@b.com" not in p["redacted"]
    assert p["total_redactions"] >= 2
    assert "does not guarantee anonymity" in " ".join(p["limitations"])
