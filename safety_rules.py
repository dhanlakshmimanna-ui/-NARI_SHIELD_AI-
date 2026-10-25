"""Static content and text-signal rules for NARI SHIELD AI.

Everything here is deterministic and inspectable: situation definitions,
follow-up questions, and regular-expression indicators for pasted text.
Nothing in this module predicts violence or identifies offenders.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# --------------------------------------------------------------------------
# Urgency levels (user selected)
# --------------------------------------------------------------------------
URGENCY_IMMEDIATE = "immediate_danger"
URGENCY_CONCERNING = "concerning_situation"
URGENCY_ADVICE = "advice_needed"

URGENCY_LABELS = {
    URGENCY_IMMEDIATE: "Immediate danger",
    URGENCY_CONCERNING: "Concerning situation",
    URGENCY_ADVICE: "Advice needed",
}
VALID_URGENCIES = tuple(URGENCY_LABELS)

ANSWER_OPTIONS = ["Yes", "No", "Not sure"]
ANSWER_MAP = {
    "yes": "yes", "y": "yes",
    "no": "no", "n": "no",
    "not sure": "unsure", "unsure": "unsure", "unknown": "unsure",
}


@dataclass(frozen=True)
class Question:
    id: str
    text: str


@dataclass(frozen=True)
class SituationDef:
    key: str
    letter: str
    label: str
    explanation: str
    questions: tuple = field(default_factory=tuple)


def _q(qid: str, text: str) -> Question:
    return Question(qid, text)


SITUATIONS: dict[str, SituationDef] = {
    "following": SituationDef(
        "following", "A", "Someone is following me",
        "Being followed can be frightening. The goal is to move toward people and "
        "staffed, well-lit places and to get support, without confronting the person.",
        (
            _q("danger", "Do you feel in immediate danger?"),
            _q("public", "Can you safely reach a staffed public place (shop, petrol station, hospital, police station)?"),
            _q("trust", "Would you like to contact someone you trust?"),
            _q("vehicle", "Is the person following you in a vehicle?"),
        ),
    ),
    "harassment": SituationDef(
        "harassment", "B", "Public harassment or unwanted contact",
        "Unwanted comments, touching, photographing or persistent approaches in public are "
        "never your fault. Options range from leaving the interaction to reporting it.",
        (
            _q("danger", "Do you feel in immediate danger?"),
            _q("continuing", "Is the person still near you or still approaching you?"),
            _q("witnesses", "Are there other people or staff nearby who could help?"),
            _q("known", "Do you know this person (colleague, neighbour, acquaintance)?"),
            _q("trust", "Would you like to contact someone you trust?"),
        ),
    ),
    "threats": SituationDef(
        "threats", "C", "Threats, coercion or intimidation",
        "Threats and pressure aim to make you feel unsafe or compelled. Your safety comes "
        "before arguing, bargaining or confronting the person.",
        (
            _q("danger", "Do you feel in immediate danger?"),
            _q("explicit", "Has someone threatened to physically harm you or someone close to you?"),
            _q("known", "Is the person known to you?"),
            _q("demand", "Are you being pressured to do something or hand something over?"),
            _q("trust", "Would you like to contact someone you trust?"),
        ),
    ),
    "online": SituationDef(
        "online", "D", "Online harassment, cyberstalking or blackmail",
        "Online abuse and blackmail often rely on fear and urgency. Preserving evidence, "
        "securing your accounts and using platform and official reporting channels are "
        "the main levers.",
        (
            _q("danger", "Do you feel physically unsafe because of these messages?"),
            _q("intimate", "Are they threatening to share private or intimate images or information?"),
            _q("money", "Are they demanding money, images or other things from you?"),
            _q("account", "Do you think this person may have access to your accounts or device?"),
            _q("continues", "Is the person still contacting you?"),
        ),
    ),
    "domestic": SituationDef(
        "domestic", "E", "Domestic abuse or danger from a known person",
        "What is happening is not your fault. You do not have to decide everything today. "
        "This guidance avoids confrontation and assumes your phone or home may not be private.",
        (
            _q("danger", "Do you feel in immediate danger right now?"),
            _q("private", "Are you able to speak or use this device privately right now?"),
            _q("device", "Do you think your phone, accounts or location may be monitored?"),
            _q("children", "Are children involved or with you?"),
            _q("injury", "Do you or anyone else need medical attention?"),
            _q("trust", "Would you like to contact someone you trust?"),
        ),
    ),
    "transport": SituationDef(
        "transport", "F", "Unsafe public transport experience",
        "Unwanted touching, staring, following or an unsafe driver on a bus, train, taxi or "
        "ride-hailing trip. You can seek help from staff, other passengers and authorities.",
        (
            _q("danger", "Do you feel in immediate danger?"),
            _q("staff", "Is there a driver, conductor, guard or other staff member you can reach?"),
            _q("moving", "Is the vehicle currently moving?"),
            _q("ridehail", "Is this a taxi or ride-hailing trip?"),
            _q("trust", "Would you like to contact someone you trust?"),
        ),
    ),
    "otp": SituationDef(
        "otp", "G", "Suspicious requests for OTPs, passwords or personal information",
        "Scammers pretend to be banks, couriers or officials and create urgency to get "
        "codes or passwords. Genuine institutions do not ask you to read out OTPs.",
        (
            _q("shared", "Have you already shared an OTP, password or card/bank details?"),
            _q("money", "Has money left your account or have you seen unfamiliar transactions?"),
            _q("pressure", "Is the person pressuring or threatening you?"),
            _q("claims", "Did they claim to be a bank, courier, company or authority?"),
        ),
    ),
    "unsure": SituationDef(
        "unsure", "H", "I am unsure what is happening but I feel unsafe",
        "You do not need to name or classify what is happening. Feeling unsafe is reason "
        "enough to look for support and move toward people.",
        (
            _q("danger", "Do you feel in immediate danger?"),
            _q("place", "Are you in a public place with other people around?"),
            _q("trust", "Would you like to contact someone you trust?"),
            _q("specific", "Is something specific making you uneasy (a person, a place, a message)?"),
        ),
    ),
    "after": SituationDef(
        "after", "I", "I need help after an incident",
        "Support after an incident can include medical care, emotional support, "
        "documentation and, if you choose, reporting. You decide the pace.",
        (
            _q("medical", "Do you or anyone else need medical attention?"),
            _q("safe", "Are you in a safe place now?"),
            _q("trust", "Would you like to contact someone you trust?"),
            _q("report", "Are you considering reporting what happened?"),
            _q("evidence", "Do you still have messages, photos or other material related to it?"),
        ),
    ),
    "other": SituationDef(
        "other", "J", "Other situation / custom description",
        "Describe your situation in your own words (optional). Text is analysed only on "
        "this device. General safety options are always available.",
        (
            _q("danger", "Do you feel in immediate danger?"),
            _q("safe", "Are you in a safe place now?"),
            _q("trust", "Would you like to contact someone you trust?"),
        ),
    ),
}
SITUATION_KEYS = tuple(SITUATIONS)
FALLBACK_SITUATION = "unsure"


# --------------------------------------------------------------------------
# Text signal rules (pasted-text analysis)
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class SignalDef:
    key: str
    label: str
    patterns: tuple
    reason: str


_FLAGS = re.IGNORECASE

SIGNAL_DEFS: tuple[SignalDef, ...] = (
    SignalDef(
        "threat", "Possible threat",
        (
            r"\b(i|i'll|i will|we will|we'll|gonna|going to)\b[^.\n]{0,25}\b(hurt|kill|harm|destroy|ruin|beat|find you|come for you)\b",
            r"\byou('ll| will)\s+(regret|pay for)\b",
            r"\bwatch your back\b",
            r"\bi know where you (live|work|study)\b",
        ),
        "Wording that states or implies harm, ruin or knowing where you are.",
    ),
    SignalDef(
        "repeated_contact", "Possible repeated unwanted contact",
        (
            r"\bwhy (are you|aren't you|didn't you|did you)\s+(ignoring|ignore|reply|replying|answer|answering|block)",
            r"\b(answer|pick up)\s+(my|the)\s+(calls?|phone|messages?)\b",
            r"\b(\d+|many|so many|ten|twenty)\s+(missed\s+)?(calls?|messages?|texts?)\b",
            r"\b(new|another)\s+(number|account|profile)\b",
            r"\byou blocked me\b",
        ),
        "Wording about ignored messages, many calls, or contacting you from new accounts.",
    ),
    SignalDef(
        "coercive_pressure", "Possible coercive pressure",
        (
            r"\bor else\b",
            r"\bif you (don't|do not|dont|won't|wont|refuse)\b[^.\n]{0,50}\b(i will|i'll|then)\b",
            r"\bdo what i (say|tell you)\b",
            r"\byou (have to|must|better)\b",
            r"\b(send|transfer|pay)\b[^.\n]{0,25}\b(money|rs\.?|rupees|amount|\d{3,})\b",
            r"\b(last|final) chance\b",
        ),
        "Wording that demands compliance, sets ultimatums or asks for payment under pressure.",
    ),
    SignalDef(
        "expose_private", "Possible threat to expose private information",
        (
            r"\b(leak|post|share|upload|publish|expose|send)\b[^.\n]{0,40}\b(photos?|pics?|pictures?|videos?|screenshots?|chats?|nudes?|secrets?|private)\b",
            r"\bexpose you\b",
            r"\beveryone (will|is going to) (see|know)\b",
            r"\btell (your|ur) (family|parents|husband|boss|friends)\b",
        ),
        "Wording about publishing, leaking or telling others private material.",
    ),
    SignalDef(
        "credential_request", "Possible request for OTP, password or sensitive data",
        (
            r"\b(share|send|tell|give|read out|read|forward|enter)\b[^.\n]{0,30}\b(otp|one[- ]time (password|code)|verification code|password|passcode|pin|cvv|card number|aadhaar|upi pin)\b",
            r"\b(otp|one[- ]time (password|code)|verification code|password|pin|cvv|upi pin)\b[^.\n]{0,20}\b(share|send|tell|give)\b",
            r"\bconfirm your (account|card|bank|identity) details\b",
        ),
        "Wording that asks you to hand over a code, password, PIN or similar secret.",
    ),
)

SIGNAL_LABELS = {s.key: s.label for s in SIGNAL_DEFS}


@dataclass(frozen=True)
class SignalMatch:
    key: str
    label: str
    snippets: tuple
    reason: str
    rule_ids: tuple


def detect_signals(text) -> list[SignalMatch]:
    """Return matched indicators for ``text``. Empty or invalid input returns []."""
    if not isinstance(text, str) or not text.strip():
        return []
    matches: list[SignalMatch] = []
    for sd in SIGNAL_DEFS:
        snippets: list[str] = []
        rule_ids: list[str] = []
        for idx, pattern in enumerate(sd.patterns, start=1):
            for m in re.finditer(pattern, text, _FLAGS):
                snippet = m.group(0).strip()
                if snippet and snippet not in snippets:
                    snippets.append(snippet[:120])
                if f"{sd.key}#{idx}" not in rule_ids:
                    rule_ids.append(f"{sd.key}#{idx}")
        if snippets:
            matches.append(
                SignalMatch(sd.key, sd.label, tuple(snippets[:3]), sd.reason, tuple(rule_ids))
            )
    return matches


# --------------------------------------------------------------------------
# Guidance snippets reused by the engine and UI
# --------------------------------------------------------------------------
ACCOUNT_SECURITY_ACTIONS = (
    "Change important passwords (email first) from a device you trust, using unique passphrases.",
    "Turn on two-step verification for email, social media and banking apps.",
    "Review logged-in devices and recovery email/phone on each account and remove anything you do not recognise.",
    "Check app permissions and tighten profile privacy (who can see photos, friends, location).",
    "Never share OTPs, PINs or passwords with anyone, even someone claiming to be support staff.",
    "If you suspect your phone is compromised, avoid resetting it until you have preserved evidence; seek trusted technical help.",
)

EVIDENCE_GUIDANCE = (
    "Take screenshots that show the username, date/time and the full message thread before blocking or deleting anything.",
    "Save links (URLs), profile names and phone numbers as text in a note, in your own words if you prefer.",
    "Keep originals where they are; do not edit or crop in ways that remove dates or context.",
    "Store copies somewhere only you can access. Redact sensitive details before sharing with anyone you do not fully trust.",
    "Write a short timeline: what happened, when, and how you responded.",
)

FALSE_POSITIVE_NOTE = (
    "False positives: ordinary messages can match. For example, a friend joking 'I will kill you if you "
    "spoil the movie', or a bank's real notice saying 'never share your OTP', may be flagged. A match "
    "is a prompt to read the text again, not a conclusion about the sender."
)
FALSE_NEGATIVE_NOTE = (
    "False negatives: threats and pressure are often indirect, coded, in another language or spelled "
    "differently, and pattern matching will miss them. No match does NOT mean you are safe. If you "
    "feel unsafe, use the help options regardless of what this tool finds."
)
INDICATOR_DISCLAIMER = (
    "This indicator only counts how many indicator categories matched. It is illustrative, is not a "
    "validated prediction of harm, does not identify any person as an offender, and never limits "
    "your access to emergency help."
)
