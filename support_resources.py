"""Support resources, emergency numbers and the (simulated) trusted-contact flow.

Resource details are defaults for India and MUST be verified locally before
relying on them. They can be overridden without editing code via
``data/config.json``.

No messaging integration exists in this prototype: sharing is always a
simulation and ``ShareResult.delivered`` is always False.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

DEFAULT_CONFIG_PATH = Path(__file__).parent / "data" / "config.json"
VERIFY_NOTE = "Default value for India. Verify with the official source before relying on it."


@dataclass(frozen=True)
class Resource:
    key: str
    name: str
    number: str = ""
    url: str = ""
    description: str = ""
    category: str = "support"
    verify_note: str = VERIFY_NOTE


DEFAULT_RESOURCES: dict[str, Resource] = {
    "emergency_112": Resource(
        "emergency_112", "National emergency number", "112", "",
        "Single emergency number for police, fire and ambulance in India.", "emergency"),
    "police_100": Resource(
        "police_100", "Police", "100", "",
        "Police helpline. May route to 112 in some regions.", "emergency"),
    "women_1091": Resource(
        "women_1091", "Women's helpline", "1091", "",
        "Helpline for women in distress. Availability varies by state.", "support"),
    "women_181": Resource(
        "women_181", "Women's helpline (181)", "181", "",
        "State-run support line for women. Availability varies by state.", "support"),
    "cyber_1930": Resource(
        "cyber_1930", "National cyber crime helpline", "1930", "",
        "Used to report cyber fraud and online financial crime quickly.", "cyber"),
    "cyber_portal": Resource(
        "cyber_portal", "National Cyber Crime Reporting Portal", "", "https://cybercrime.gov.in",
        "Official portal to report cyber crimes, including online harassment and blackmail.", "cyber"),
    "ncw": Resource(
        "ncw", "National Commission for Women", "", "https://ncw.nic.in",
        "Official body with complaint and information channels for women.", "support"),
    "stopncii": Resource(
        "stopncii", "StopNCII.org", "", "https://stopncii.org",
        "Free tool intended to help stop intimate images from being shared online. Read how it works before use.",
        "cyber"),
    "telemanas": Resource(
        "telemanas", "Tele-MANAS mental health helpline", "14416", "https://telemanas.mohfw.gov.in",
        "Free national tele-mental-health support.", "wellbeing"),
}

_PHONE_RE = re.compile(r"^\+?[\d\s\-]{2,16}$")
_URL_RE = re.compile(r"^https://[A-Za-z0-9.\-]+\.[A-Za-z]{2,}(/[^\s]*)?$")


def is_valid_phone(value) -> bool:
    return isinstance(value, str) and bool(_PHONE_RE.match(value.strip()))


def is_https_url(value) -> bool:
    return isinstance(value, str) and bool(_URL_RE.match(value.strip()))


def load_overrides(path=None) -> dict:
    """Read config overrides; malformed or missing files return {}."""
    p = Path(path) if path else DEFAULT_CONFIG_PATH
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data.get("resources", {}) if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def get_resources(config_path=None) -> dict[str, Resource]:
    """Default resources with valid overrides applied. Invalid values are ignored."""
    resources = dict(DEFAULT_RESOURCES)
    overrides = load_overrides(config_path)
    if not isinstance(overrides, dict):
        return resources
    for key, patch in overrides.items():
        if key not in resources or not isinstance(patch, dict):
            continue
        updates = {}
        if "number" in patch and (patch["number"] == "" or is_valid_phone(patch["number"])):
            updates["number"] = patch["number"].strip()
        if "url" in patch and (patch["url"] == "" or is_https_url(patch["url"])):
            updates["url"] = patch["url"].strip()
        if updates:
            updates["verify_note"] = "Overridden in data/config.json. Confirm it is correct."
            resources[key] = replace(resources[key], **updates)
    return resources


def get_resource(key: str, config_path=None):
    return get_resources(config_path).get(key)


def resources_for(keys, config_path=None) -> list[Resource]:
    res = get_resources(config_path)
    return [res[k] for k in keys if k in res]


def emergency_options(config_path=None) -> list[Resource]:
    """Emergency numbers shown everywhere. Never depends on any answer or score."""
    res = get_resources(config_path)
    return [res[k] for k in ("emergency_112", "police_100") if res[k].number]


# --------------------------------------------------------------------------
# Trusted-contact flow (simulation only)
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class ShareDraft:
    contact_name: str
    message: str
    data_shared: tuple
    includes_location: bool
    created_at: str


@dataclass(frozen=True)
class ShareResult:
    status: str          # "simulated_confirmed" | "cancelled" | "invalid"
    delivered: bool      # always False: no real integration exists
    message: str


def build_share_draft(contact_name, situation_label="", location_text="", note="") -> ShareDraft:
    """Build a preview of what WOULD be shared. Raises ValueError on invalid input."""
    if not isinstance(contact_name, str) or not contact_name.strip():
        raise ValueError("Please enter a name or nickname for your trusted contact.")
    name = contact_name.strip()[:60]
    label = situation_label.strip()[:120] if isinstance(situation_label, str) else ""
    loc = location_text.strip()[:200] if isinstance(location_text, str) else ""
    extra = note.strip()[:200] if isinstance(note, str) else ""

    parts = ["[NARI SHIELD demo message] I may need help. Please contact me when you can."]
    data = ["Your chosen contact name", "The message text shown above"]
    if label:
        parts.append(f"Situation type: {label}.")
        data.append("Situation category")
    if loc:
        parts.append(f"Location I typed: {loc}")
        data.append("Location text you typed (not GPS)")
    if extra:
        parts.append(f"Note: {extra}")
        data.append("Your optional note")
    return ShareDraft(
        contact_name=name,
        message=" ".join(parts),
        data_shared=tuple(data),
        includes_location=bool(loc),
        created_at=datetime.now().isoformat(timespec="seconds"),
    )


def confirm_share(draft, user_confirmed: bool) -> ShareResult:
    """Handle the user's decision. Even on confirmation nothing is sent."""
    if not isinstance(draft, ShareDraft):
        return ShareResult("invalid", False, "No message preview exists, so nothing was done.")
    if not user_confirmed:
        return cancel_share(draft)
    return ShareResult(
        "simulated_confirmed", False,
        f"SIMULATION ONLY: no message was sent to {draft.contact_name}. This prototype has no "
        "messaging integration. In a real app, delivery would only be reported after the "
        "provider confirmed it. Use your phone to call or message your contact yourself.",
    )


def cancel_share(draft=None) -> ShareResult:
    return ShareResult("cancelled", False, "Cancelled. Nothing was shared or stored.")
