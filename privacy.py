"""Basic privacy redaction using regular expressions.

LIMITATIONS: pattern-based redaction is imperfect. It misses names, addresses,
unusual formats and context that identifies a person, and it can over-redact.
It does NOT guarantee anonymity. Always review the preview. Production systems
should combine reviewed redaction, access control and encryption.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

LIMITATIONS = (
    "Redaction here is simple pattern matching. It can miss names, addresses, nicknames, photos and "
    "details that identify you indirectly, so it does not guarantee anonymity. Always read the "
    "preview before saving or sharing.",
    "Safer production alternatives: reviewed redaction tooling, encrypted storage, access control, "
    "and sharing evidence only with the authority or lawyer handling your case.",
)

_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_OTP_CONTEXT = re.compile(
    r"(?i)\b(otp|one[- ]time (?:password|code)|verification code|security code|code|pin|cvv)\b([^\d\n]{0,20})(\d{3,8})\b"
)
_SECRET = re.compile(r"(?i)\b(password|passcode|pwd|passphrase)\b(\s*(?:is|:|=)\s*)(\S+)")
_LONG_DIGITS = re.compile(r"(?<![\d+])\+?(?:\d[ \-]?){12,19}(?!\d)")
_PHONE = re.compile(r"(?<![\w])\+?\d[\d ()\-]{8,16}\d(?![\w])")
_STANDALONE_CODE = re.compile(r"(?<![\w.])\d{6}(?![\w.])")


@dataclass
class RedactionResult:
    text: str
    counts: dict = field(default_factory=dict)

    @property
    def total(self) -> int:
        return sum(self.counts.values())


def _digits(s: str) -> int:
    return sum(ch.isdigit() for ch in s)


def redact_text(text, extra_terms=None) -> RedactionResult:
    """Redact emails, phone numbers, OTP-like values, secrets, long ID/card numbers
    and optional user-supplied terms. Non-string/empty input returns an empty result."""
    if not isinstance(text, str) or not text:
        return RedactionResult("", {})
    counts: dict[str, int] = {}

    def bump(name: str) -> None:
        counts[name] = counts.get(name, 0) + 1

    out = text

    def sub_email(m):
        bump("email")
        return "[REDACTED-EMAIL]"
    out = _EMAIL.sub(sub_email, out)

    def sub_otp(m):
        bump("otp_like")
        return f"{m.group(1)}{m.group(2)}[REDACTED-OTP]"
    out = _OTP_CONTEXT.sub(sub_otp, out)

    def sub_secret(m):
        bump("secret")
        return f"{m.group(1)}{m.group(2)}[REDACTED-SECRET]"
    out = _SECRET.sub(sub_secret, out)

    def sub_long(m):
        n = _digits(m.group(0))
        if m.group(0).startswith("+") and 12 <= n <= 13:
            bump("phone")  # international format with country code
            return "[REDACTED-PHONE]"
        if 12 <= n <= 19:
            bump("id_or_card_number")
            return "[REDACTED-NUMBER]"
        return m.group(0)
    out = _LONG_DIGITS.sub(sub_long, out)

    def sub_phone(m):
        if 10 <= _digits(m.group(0)) <= 13:
            bump("phone")
            return "[REDACTED-PHONE]"
        return m.group(0)
    out = _PHONE.sub(sub_phone, out)

    def sub_code(m):
        bump("otp_like")
        return "[REDACTED-CODE]"
    out = _STANDALONE_CODE.sub(sub_code, out)

    for term in extra_terms or []:
        if isinstance(term, str) and term.strip():
            pattern = re.compile(re.escape(term.strip()), re.IGNORECASE)
            out, n = pattern.subn("[REDACTED-TERM]", out)
            if n:
                counts["custom_term"] = counts.get("custom_term", 0) + n

    return RedactionResult(out, counts)


def preview(text, extra_terms=None) -> dict:
    """Return original/redacted text and a summary for display before saving."""
    result = redact_text(text, extra_terms)
    return {
        "original": text if isinstance(text, str) else "",
        "redacted": result.text,
        "counts": dict(result.counts),
        "total_redactions": result.total,
        "limitations": LIMITATIONS,
    }
