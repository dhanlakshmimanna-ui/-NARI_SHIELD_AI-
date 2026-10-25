"""Deterministic, explainable decision engine for NARI SHIELD AI.

Design principles
-----------------
* Rules only. No machine-learning prediction, no hidden scores.
* Emergency options are ALWAYS available (``Recommendation.emergency_available``
  is True for every input, including invalid or missing input).
* Every recommendation lists the rules that fired and the reason for each.
* The engine never predicts violence or labels any person as dangerous.
* Optional NLP can be plugged in via ``TextAnalyzer`` (see bottom of file);
  the default implementation is regex based.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import safety_rules as sr
from support_resources import emergency_options, resources_for

NOW, NEXT, LATER = "Now", "Next", "Later"
_WHEN_ORDER = {NOW: 0, NEXT: 1, LATER: 2}

NOT_PREDICTIVE_NOTE = (
    "This guidance comes from fixed rules. It does not predict violence or judge whether any "
    "person is dangerous, and emergency help does not depend on it."
)


@dataclass(frozen=True)
class Step:
    when: str
    text: str


@dataclass
class Recommendation:
    situation: str
    situation_label: str
    urgency: str
    urgency_label: str
    relevant_answers: dict
    reasons: list
    rules_matched: list
    steps: list
    alternatives: list
    documentation: list
    resource_keys: list
    trusted_contact_suggested: bool
    emergency_first: bool
    signals: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    emergency_available: bool = True
    confidence_note: str = "Rule-based match. No probability or prediction is involved."

    def explanation(self) -> str:
        lines = [f"Situation: {self.situation_label}", f"Urgency you selected: {self.urgency_label}"]
        if self.relevant_answers:
            lines.append("Your answers: " + "; ".join(f"{q} -> {a}" for q, a in self.relevant_answers.items()))
        else:
            lines.append("No follow-up answers were given; general guidance is shown.")
        lines += [f"Why: {r}" for r in self.reasons]
        lines.append("Rules matched: " + ", ".join(self.rules_matched))
        return "\n".join(lines)

    def steps_by_priority(self) -> dict:
        grouped: dict[str, list[str]] = {NOW: [], NEXT: [], LATER: []}
        for s in self.steps:
            grouped.setdefault(s.when, []).append(s.text)
        return grouped

    def resources(self):
        return resources_for(self.resource_keys)


class _Builder:
    def __init__(self) -> None:
        self.reasons: list[str] = []
        self.rules: list[str] = []
        self.steps: list[Step] = []
        self.alts: list[str] = []
        self.docs: list[str] = []
        self.res: list[str] = []
        self.signals: list[str] = []
        self.notes: list[str] = []
        self.trusted = False
        self.emergency = False

    def rule(self, rid: str, reason: str) -> None:
        self.rules.append(rid)
        self.reasons.append(reason)

    def step(self, when: str, text: str) -> None:
        self.steps.append(Step(when, text))

    def alt(self, text: str) -> None:
        self.alts.append(text)

    def doc(self, text: str) -> None:
        self.docs.append(text)

    def resource(self, *keys: str) -> None:
        for k in keys:
            if k not in self.res:
                self.res.append(k)


# --------------------------------------------------------------------------
# Input normalisation
# --------------------------------------------------------------------------
def normalize_answers(situation: str, answers) -> dict:
    """Map raw answers to yes/no/unsure for known question ids; ignore the rest."""
    if not isinstance(answers, dict):
        return {}
    known = {q.id for q in sr.SITUATIONS[situation].questions}
    out = {}
    for qid, val in answers.items():
        if qid in known and isinstance(val, str) and val.strip().lower() in sr.ANSWER_MAP:
            out[qid] = sr.ANSWER_MAP[val.strip().lower()]
    return out


def _emergency_step(b: _Builder, rid: str, reason: str) -> None:
    b.emergency = True
    b.rule(rid, reason)
    b.step(NOW, "Call your local emergency number now using the call option shown at the top of this page. "
                "If speaking is unsafe, move to a place where you can, or ask someone nearby to call for you.")
    b.resource("emergency_112", "police_100")


def _trust(b: _Builder, a: dict, rid: str, extra: str = "") -> None:
    v = a.get("trust")
    if v == "yes":
        b.trusted = True
        b.rule(rid, "You said you would like to contact someone you trust.")
        b.step(NOW if extra else NEXT,
               "Use the trusted-contact option below. You will see exactly what would be shared and must "
               "confirm first. You can also simply call them yourself. " + extra)
    elif v == "unsure":
        b.alt("You were not sure about contacting someone. The trusted-contact option stays available whenever you want it.")
    elif v == "no":
        b.alt("You chose not to contact anyone for now. You can change your mind at any time.")


# --------------------------------------------------------------------------
# Per-situation decision paths (each is separately testable)
# --------------------------------------------------------------------------
def path_following(a: dict, immediate: bool, b: _Builder) -> None:
    if immediate:
        _emergency_step(b, "FOL-01", "You indicated immediate danger, so emergency help comes first.")
    if a.get("public") == "yes":
        b.rule("FOL-02", "You can safely reach a staffed public place.")
        b.step(NOW, "Walk toward the nearest staffed, well-lit public place (shop, petrol station, hospital, "
                    "police station). Tell staff someone is following you and ask to wait inside.")
    else:
        b.rule("FOL-03", "A staffed public place is not clearly reachable, so the focus is on staying among people.")
        b.step(NOW, "Stay where there are other people. Move toward busy, well-lit areas and avoid shortcuts, "
                    "empty streets and secluded car parks.")
        b.alt("If a staffed place becomes reachable, go there. Calling a trusted person and staying on the line can help.")
    if a.get("vehicle") == "yes":
        b.rule("FOL-04", "The person is in a vehicle.")
        b.step(NOW, "Avoid isolated roads and do not get into any vehicle offered. Where possible, move to a place "
                    "a vehicle cannot easily follow (inside a business, crowded pavement).")
    if not immediate:
        b.rule("FOL-05", "No immediate danger was reported; you can still call emergency services at any time.")
        b.step(NEXT, "If the person keeps following you, treat it as urgent and call the emergency number.")
    b.step(NEXT, "Avoid going straight home if you think you are being followed; go where there are people first.")
    _trust(b, a, "FOL-06")
    b.step(LATER, "Once safe, consider reporting to the police. Staff or security at the place you reached can help.")
    b.doc("When safe, write down time, place and a description of the person or vehicle. Do not take risks to photograph them.")
    b.resource("women_1091", "emergency_112")


def path_harassment(a: dict, immediate: bool, b: _Builder) -> None:
    if immediate:
        _emergency_step(b, "HAR-01", "You indicated immediate danger, so emergency help comes first.")
    if a.get("continuing") == "yes":
        b.rule("HAR-02", "The person is still near you or approaching you.")
        b.step(NOW, "Move away toward other people or staff. If you are comfortable, say clearly and loudly: "
                    "\"Stop. Leave me alone.\" You do not owe them politeness or an explanation.")
    else:
        b.rule("HAR-03", "The person is not currently near you, so you can focus on regaining safety and deciding next steps.")
        b.step(NOW, "Move to a place where you feel safe and take a moment. Your reaction is valid.")
    if a.get("witnesses") == "yes":
        b.rule("HAR-04", "People or staff are nearby.")
        b.step(NOW, "Ask a specific person for help (\"You in the blue jacket, please stay with me\"). "
                    "Specific requests are more likely to get a response than a general call.")
    elif a.get("witnesses") in ("no", "unsure"):
        b.rule("HAR-05", "Nobody helpful is clearly nearby.")
        b.step(NOW, "Head for the nearest place with people (shop, station, bus stop with others waiting).")
    if a.get("known") == "yes":
        b.rule("HAR-06", "The person is known to you, so the pattern may repeat.")
        b.step(NEXT, "Keep a dated record of each incident. If this is a workplace, school or building, "
                     "you can use its complaint process; many places have an internal committee for harassment.")
    _trust(b, a, "HAR-07")
    b.step(LATER, "You may report to the police or the relevant authority whenever you are ready.")
    b.doc("Note date, time, place and what happened, in your own words. CCTV may be overwritten, so request it early if you plan to report.")
    b.resource("women_1091", "women_181", "emergency_112")


def path_threats(a: dict, immediate: bool, b: _Builder) -> None:
    if immediate or a.get("explicit") == "yes":
        reason = ("You reported a threat of physical harm." if a.get("explicit") == "yes"
                  else "You indicated immediate danger.")
        _emergency_step(b, "THR-01", reason + " Emergency help comes first.")
    b.rule("THR-00", "Safety comes before arguing or complying; these steps apply to any threat or intimidation.")
    if a.get("demand") == "yes":
        b.rule("THR-02", "You are being pressured to do or hand over something.")
        b.step(NOW, "You do not have to decide under pressure. It is acceptable to say you need time or to leave. "
                    "Your safety matters more than winning an argument.")
        b.alt("Avoid handing over money, documents or access while pressured; consider getting advice first.")
    if a.get("known") == "yes":
        b.rule("THR-03", "The person is known to you.")
        b.step(NEXT, "Avoid confronting them alone. Consider telling someone you trust and keep a record of each threat.")
    elif a.get("known") in ("no", "unsure"):
        b.rule("THR-04", "The person is not clearly known to you.")
        b.step(NEXT, "Avoid isolated places and consider telling the police, especially if they know where you live or work.")
    _trust(b, a, "THR-05")
    b.step(LATER, "Consider seeking legal advice about protective options, and report the threats when you feel ready.")
    b.doc("Save threatening messages, call logs and voicemails. Record dates and times of in-person threats.")
    b.resource("emergency_112", "police_100", "women_181", "ncw")


def path_online(a: dict, immediate: bool, b: _Builder) -> None:
    if immediate or a.get("danger") == "yes":
        _emergency_step(b, "ONL-01", "You feel physically unsafe, so emergency help comes first.")
    if a.get("intimate") == "yes":
        b.rule("ONL-02", "There is a threat to share private or intimate material.")
        b.step(NOW, "Do not delete the conversation. Preserve evidence first (screenshots showing username and date).")
        b.step(NEXT, "Report the account on the platform and use its non-consensual-image or blackmail reporting option.")
        b.step(NEXT, "Consider StopNCII.org (see resources) and the national cyber crime portal.")
        b.alt("Paying or sending more material often does not end demands and can lead to more. Many experts advise against complying.")
        b.resource("stopncii")
    if a.get("money") == "yes":
        b.rule("ONL-03", "Money, images or other things are being demanded.")
        b.step(NOW, "Pause before sending anything. If you already sent money, note the transaction details and contact your bank.")
    if a.get("account") in ("yes", "unsure"):
        b.rule("ONL-04", "Account or device access by this person is possible or uncertain.")
        b.step(NOW if a.get("account") == "yes" else NEXT,
               "Secure your accounts from a device you trust: change email and social media passwords, turn on "
               "two-step verification and remove unknown logged-in devices.")
    if a.get("continues") == "yes":
        b.rule("ONL-05", "The person is still contacting you.")
        b.step(NEXT, "Avoid engaging or arguing. After preserving evidence, consider blocking and restricting your profile privacy.")
    b.step(NEXT, "Understand platform reporting: most platforms have a report option on the profile and on individual messages.")
    b.step(LATER, "Report to the cyber crime portal or helpline, and speak to someone you trust or a counsellor. This is not your fault.")
    if not b.rules or all(r == "ONL-01" for r in b.rules):
        b.rule("ONL-06", "General online harassment guidance applies.")
    b.doc("Preserve relevant messages safely: screenshots with timestamps and usernames, profile links, payment details. "
          "Use the Evidence Vault to save a redacted record if you choose.")
    b.resource("cyber_portal", "cyber_1930", "telemanas")
    b.alt("You can ask someone you trust to sit with you while you preserve evidence and report. The trusted-contact option is below.")


def path_domestic(a: dict, immediate: bool, b: _Builder) -> None:
    b.notes.append("This tool never contacts anyone automatically and never recommends confronting the other person.")
    if immediate:
        _emergency_step(b, "DOM-01", "You said you are in immediate danger. Your safety comes first.")
    if a.get("private") in ("no", "unsure"):
        b.rule("DOM-02", "You may not be able to use this device privately.")
        b.step(NOW, "You do not have to read or do everything now. Choose only what feels safe. If someone may see your "
                    "screen, you can switch to another page. Closing this tab may not erase browser history.")
    if a.get("device") in ("yes", "unsure"):
        b.rule("DOM-03", "Your phone, accounts or location may be monitored.")
        b.step(NEXT, "If you can, use a device the other person cannot access (a trusted friend's phone, a library, a "
                     "workplace) to look for help. Sudden changes such as deleting apps or resetting may be noticed, so "
                     "move carefully.")
    if a.get("injury") == "yes":
        b.rule("DOM-04", "Someone needs medical attention.")
        b.step(NOW, "Seek medical care. Medical records can also document injuries if you decide to take legal steps later.")
        b.resource("emergency_112")
    if a.get("children") == "yes":
        b.rule("DOM-05", "Children are involved.")
        b.step(NEXT, "Include children in any safety plan: an agreed safe place or word, and knowing how to call for help.")
    b.rule("DOM-06", "Trauma-informed support options are shown regardless of how the questions were answered.")
    b.step(NEXT, "Think about a safer place to go (a trusted person's home or a shelter) and an exit route you could use. "
                 "Keep ID, money and important documents where you can reach them or with someone you trust.")
    b.step(LATER, "A helpline or counsellor can talk through options with you, at your pace, without pressure to leave or report.")
    if a.get("trust") == "yes":
        b.trusted = True
        b.rule("DOM-07", "You would like to contact someone you trust.")
        b.step(NEXT, "Choose someone who is not connected to the other person and who will not tell them. "
                     "The trusted-contact option only shows a preview; you confirm everything.")
    b.alt("You may choose to do nothing today. Being ready to act later is still a form of safety planning.")
    b.doc("If it is safe, keep dated notes or photos where the other person cannot find them (for example with a "
          "trusted person). Do not keep evidence on a shared or monitored device.")
    b.resource("emergency_112", "women_181", "women_1091", "telemanas", "ncw")


def path_transport(a: dict, immediate: bool, b: _Builder) -> None:
    if immediate:
        _emergency_step(b, "TRA-01", "You indicated immediate danger, so emergency help comes first.")
    if a.get("staff") == "yes":
        b.rule("TRA-02", "Staff are reachable.")
        b.step(NOW, "Tell the driver, conductor or guard clearly what is happening and ask them to intervene or stop.")
    else:
        b.rule("TRA-03", "Staff are not clearly reachable.")
        b.step(NOW, "Move closer to other passengers or the driver's area, or to a crowded part of the vehicle.")
    if a.get("moving") == "yes":
        b.rule("TRA-04", "The vehicle is moving.")
        b.step(NEXT, "If you need to get off, do so at a busy, well-lit stop rather than an isolated one.")
    else:
        b.rule("TRA-05", "The vehicle is stopped.")
        b.step(NOW, "If you feel unsafe, you can step off now toward people or staff.")
    if a.get("ridehail") == "yes":
        b.rule("TRA-06", "This is a taxi or ride-hailing trip.")
        b.step(NOW, "If your app has a safety or share-trip feature, use it. Do not share an OTP or end the trip in an isolated place.")
        b.doc("Save the booking details, driver name, vehicle number and trip time from the app.")
    _trust(b, a, "TRA-07")
    b.step(LATER, "Report to the transport authority, the operator's helpline or the police. Include route, time and vehicle number.")
    b.doc("Note the vehicle number, route, time and a description in your own words once you are safe.")
    b.resource("women_1091", "emergency_112", "police_100")


def path_otp(a: dict, immediate: bool, b: _Builder) -> None:
    if immediate:
        _emergency_step(b, "OTP-01", "You indicated immediate danger, so emergency help comes first.")
    if a.get("shared") == "yes" or a.get("money") == "yes":
        b.rule("OTP-02", "Information may already have been shared or money may have left your account.")
        b.step(NOW, "Contact your bank immediately using the number on your card or the official website, not a number "
                    "from the message, and ask to block cards or UPI access.")
        b.step(NOW, "Change passwords and PINs from a trusted device.")
        b.step(NEXT, "Report quickly to the national cyber crime helpline or portal; fast reporting is generally advised.")
        b.resource("cyber_1930", "cyber_portal")
    else:
        b.rule("OTP-03", "Nothing has been shared yet.")
        b.step(NOW, "Do not share any OTP, PIN, CVV or password. Hang up or stop replying. Genuine banks do not ask you to read out OTPs.")
    if a.get("claims") == "yes":
        b.rule("OTP-04", "The person claimed to be an institution or authority.")
        b.step(NEXT, "Verify independently: contact the institution through its official app, website or number. "
                     "Do not use links or numbers they provided.")
    if a.get("pressure") == "yes":
        b.rule("OTP-05", "Pressure or threats were used.")
        b.step(NEXT, "Urgency and threats are common scam tactics. You can end the conversation. If you feel physically "
                     "threatened, use the emergency options above.")
    b.step(LATER, "Warn family and friends about the scam and consider reporting the number on the cyber crime portal.")
    b.doc("Save the phone number, time, any message screenshots and transaction IDs. Do not store OTPs.")
    b.resource("cyber_1930", "cyber_portal")


def path_unsure(a: dict, immediate: bool, b: _Builder) -> None:
    if immediate:
        _emergency_step(b, "UNS-01", "You indicated immediate danger, so emergency help comes first.")
    b.rule("UNS-02", "You do not need to classify the situation. Feeling unsafe is enough to act.")
    if a.get("place") == "yes":
        b.rule("UNS-03", "You are among other people.")
        b.step(NOW, "Stay near people. Let someone you trust know where you are if that feels right.")
    else:
        b.rule("UNS-04", "You may not be around other people.")
        b.step(NOW, "Move toward a place with people and lighting (shop, station, petrol station, hospital).")
    if a.get("specific") == "yes":
        b.rule("UNS-05", "Something specific is making you uneasy.")
        b.alt("Try the more specific guidance: following, harassment, threats, online blackmail or suspicious OTP requests.")
    _trust(b, a, "UNS-06")
    b.step(NEXT, "Trust your instincts. You can leave, change route or ask someone to walk with you without explaining why.")
    b.step(LATER, "Afterwards, writing down what you noticed can help you decide whether to report anything.")
    b.doc("Optional: note time, place and what felt wrong, in your own words.")
    b.resource("women_1091", "emergency_112")


def path_after(a: dict, immediate: bool, b: _Builder) -> None:
    if immediate or a.get("safe") == "no":
        _emergency_step(b, "AFT-01", "You are not in a safe place or indicated danger, so immediate help comes first.")
    if a.get("medical") == "yes":
        b.rule("AFT-02", "Medical attention is needed.")
        b.step(NOW, "Get medical care. You can receive care first and decide about reporting later. "
                    "If you were assaulted, try to avoid washing or changing clothes before care if you can, but only if it feels okay.")
        b.resource("emergency_112")
    if a.get("report") == "yes":
        b.rule("AFT-03", "You are considering reporting.")
        b.step(NEXT, "You can report to the police. In India, a complaint can usually be registered at any police "
                     "station (zero FIR); confirm locally. A support person can come with you.")
    elif a.get("report") in ("no", "unsure"):
        b.rule("AFT-04", "You are unsure or not ready to report.")
        b.alt("There is no deadline to decide today. Keep any evidence safe so you keep your options open.")
    if a.get("evidence") == "yes":
        b.rule("AFT-05", "You still have related messages or material.")
        b.step(NEXT, "Do not delete it. Save copies somewhere only you can access, or create a redacted record in the Evidence Vault.")
    _trust(b, a, "AFT-06")
    b.step(LATER, "Consider emotional support, such as a counsellor or the helplines below. Reactions after an incident vary and are valid.")
    b.rule("AFT-07", "Support and documentation guidance applies after any incident.")
    b.doc("Write down what you remember when you are ready, with dates, places and people. Keep it private.")
    b.resource("emergency_112", "women_1091", "women_181", "telemanas", "ncw")


def path_other(a: dict, immediate: bool, b: _Builder) -> None:
    if immediate or a.get("safe") == "no":
        _emergency_step(b, "OTH-01", "You indicated danger or that you are not safe, so emergency help comes first.")
    b.rule("OTH-02", "Your situation does not match a specific category, so general safety guidance is shown.")
    b.step(NOW, "Move toward people and a well-lit, staffed place if you can. Keep your phone reachable.")
    _trust(b, a, "OTH-03")
    b.step(NEXT, "If your description matches one of the other situations, select it for more specific guidance.")
    b.step(LATER, "Seek support from a helpline or someone you trust.")
    b.doc("Optional: note what happened and when, in your own words.")
    b.resource("women_1091", "emergency_112")


PATHS = {
    "following": path_following, "harassment": path_harassment, "threats": path_threats,
    "online": path_online, "domestic": path_domestic, "transport": path_transport,
    "otp": path_otp, "unsure": path_unsure, "after": path_after, "other": path_other,
}


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------
def build_recommendation(situation, urgency=sr.URGENCY_CONCERNING, answers=None, description="") -> Recommendation:
    """Return guidance for any input. Invalid input falls back safely."""
    notes: list[str] = []
    if situation not in sr.SITUATIONS:
        notes.append("The situation could not be recognised, so general guidance for 'unsure' situations is shown.")
        situation = sr.FALLBACK_SITUATION
    if urgency not in sr.VALID_URGENCIES:
        notes.append("Urgency was missing or invalid, so 'Concerning situation' was assumed. Emergency help is still available.")
        urgency = sr.URGENCY_CONCERNING

    a = normalize_answers(situation, answers)
    sdef = sr.SITUATIONS[situation]
    immediate = urgency == sr.URGENCY_IMMEDIATE or a.get("danger") == "yes"

    b = _Builder()
    b.notes.extend(notes)
    PATHS[situation](a, immediate, b)

    if isinstance(description, str) and description.strip():
        for m in sr.detect_signals(description):
            b.signals.append(f"{m.label}: matched {', '.join(repr(s) for s in m.snippets)}")
        if b.signals:
            b.rule("TXT-01", "Your description matched some text indicators (illustrative only).")

    if not b.steps:
        b.step(NOW, "Move toward people and a well-lit place, and keep emergency options within reach.")
    b.resource("emergency_112")

    steps = sorted(b.steps, key=lambda s: _WHEN_ORDER[s.when])
    qtext = {q.id: q.text for q in sdef.questions}
    label_for = {"yes": "Yes", "no": "No", "unsure": "Not sure"}
    relevant = {qtext[k]: label_for[v] for k, v in a.items()}
    b.notes.append(NOT_PREDICTIVE_NOTE)

    return Recommendation(
        situation=situation,
        situation_label=sdef.label,
        urgency=urgency,
        urgency_label=sr.URGENCY_LABELS[urgency],
        relevant_answers=relevant,
        reasons=b.reasons,
        rules_matched=b.rules,
        steps=steps,
        alternatives=b.alts,
        documentation=b.docs,
        resource_keys=b.res,
        trusted_contact_suggested=b.trusted,
        emergency_first=immediate or b.emergency,
        signals=b.signals,
        notes=b.notes,
    )


def get_emergency_options():
    """Emergency options for display. Independent of any classification."""
    return emergency_options()


# --------------------------------------------------------------------------
# Text analysis for harassment/blackmail
# --------------------------------------------------------------------------
@dataclass
class TextAnalysis:
    is_empty: bool
    matches: list
    indicator_label: str
    indicator_disclaimer: str
    reasons: list
    security_actions: list
    evidence_guidance: list
    reporting_resource_keys: list
    limitations: list


class TextAnalyzer(Protocol):
    """Interface for an optional NLP backend (not used by default)."""

    def analyze(self, text: str) -> list: ...


def analyze_text(text, extra_analyzer: TextAnalyzer | None = None) -> TextAnalysis:
    """Detect predefined indicators in user-supplied text. Never identifies a person."""
    matches = sr.detect_signals(text)
    if extra_analyzer is not None:
        try:
            matches = list(matches) + list(extra_analyzer.analyze(text))
        except Exception:  # an optional backend must never break the core engine
            pass
    empty = not isinstance(text, str) or not text.strip()
    n = len(matches)
    label = ("No text provided" if empty else
             "No indicators matched" if n == 0 else
             "Some indicators matched" if n <= 2 else "Several indicators matched")
    reasons = [f"{m.label}: {m.reason} Matched text: " + ", ".join(repr(s) for s in m.snippets)
               + f" (rules {', '.join(m.rule_ids)})" for m in matches]
    keys = {m.key for m in matches}
    security = list(sr.ACCOUNT_SECURITY_ACTIONS)
    reporting = ["cyber_portal", "cyber_1930"]
    if "expose_private" in keys:
        reporting.append("stopncii")
    if keys & {"threat"}:
        reporting += ["emergency_112", "police_100"]
    return TextAnalysis(
        is_empty=empty, matches=matches, indicator_label=label,
        indicator_disclaimer=sr.INDICATOR_DISCLAIMER, reasons=reasons,
        security_actions=security, evidence_guidance=list(sr.EVIDENCE_GUIDANCE),
        reporting_resource_keys=reporting,
        limitations=[sr.FALSE_POSITIVE_NOTE, sr.FALSE_NEGATIVE_NOTE],
    )
