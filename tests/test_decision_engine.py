import pytest

import safety_rules as sr
from decision_engine import analyze_text, build_recommendation, get_emergency_options
from demo_data import SAMPLE_TEXTS, SCENARIOS
from support_resources import (
    ShareDraft, build_share_draft, cancel_share, confirm_share,
)

ALL = list(sr.SITUATIONS)


def test_ten_situations_supported():
    assert len(ALL) == 10


@pytest.mark.parametrize("key", ALL)
def test_every_situation_returns_guidance(key):
    rec = build_recommendation(key, sr.URGENCY_ADVICE, {})
    assert rec.situation == key
    assert rec.steps and rec.rules_matched and rec.reasons
    assert rec.emergency_available is True
    assert len(rec.rules_matched) == len(rec.reasons)
    assert sr.SITUATIONS[key].questions


@pytest.mark.parametrize("key", ALL)
def test_immediate_urgency_puts_emergency_first(key):
    rec = build_recommendation(key, sr.URGENCY_IMMEDIATE, {})
    assert rec.emergency_first
    assert rec.steps[0].when == "Now"
    assert "emergency" in rec.steps[0].text.lower()
    assert "emergency_112" in rec.resource_keys


@pytest.mark.parametrize("key", ALL)
def test_urgent_help_available_without_answers_or_classification(key):
    rec = build_recommendation(key, sr.URGENCY_ADVICE, None)
    assert rec.emergency_available
    assert get_emergency_options()


def test_following_branching_public_place():
    yes = build_recommendation("following", sr.URGENCY_CONCERNING, {"public": "Yes"})
    no = build_recommendation("following", sr.URGENCY_CONCERNING, {"public": "No"})
    assert "FOL-02" in yes.rules_matched and "FOL-03" not in yes.rules_matched
    assert "FOL-03" in no.rules_matched and "FOL-02" not in no.rules_matched
    assert [s.text for s in yes.steps] != [s.text for s in no.steps]


def test_following_danger_answer_triggers_emergency():
    rec = build_recommendation("following", sr.URGENCY_ADVICE, {"danger": "Yes"})
    assert rec.emergency_first and "FOL-01" in rec.rules_matched


def test_following_trust_answer_changes_steps():
    yes = build_recommendation("following", sr.URGENCY_CONCERNING, {"trust": "Yes"})
    no = build_recommendation("following", sr.URGENCY_CONCERNING, {"trust": "No"})
    assert yes.trusted_contact_suggested and not no.trusted_contact_suggested
    assert "FOL-06" in yes.rules_matched


def test_online_path_differs_from_following():
    online = build_recommendation("online", sr.URGENCY_CONCERNING,
                                  {"intimate": "Yes", "money": "Yes", "account": "Yes"})
    text = " ".join(s.text for s in online.steps).lower()
    for word in ("evidence", "report", "two-step", "stopncii"):
        assert word in text
    assert {"ONL-02", "ONL-03", "ONL-04"} <= set(online.rules_matched)
    assert "stopncii" in online.resource_keys


def test_online_account_unsure_still_secures_accounts():
    rec = build_recommendation("online", sr.URGENCY_CONCERNING, {"account": "Not sure"})
    assert "ONL-04" in rec.rules_matched


def test_domestic_is_trauma_informed_and_never_confronts():
    rec = build_recommendation("domestic", sr.URGENCY_CONCERNING,
                               {"private": "No", "device": "Yes", "children": "Yes", "trust": "Yes"})
    blob = (" ".join(s.text for s in rec.steps) + " ".join(rec.alternatives) + " ".join(rec.notes)).lower()
    assert "confront" in blob and "never" in " ".join(rec.notes).lower()
    assert "not connected to the other person" in blob
    assert {"DOM-02", "DOM-03", "DOM-05", "DOM-07"} <= set(rec.rules_matched)
    assert "women_181" in rec.resource_keys
    for bad in ("confront them", "call the abuser", "talk to your partner", "ask them to stop", "contact the other person"):
        assert bad not in blob


def test_domestic_injury_adds_medical_step():
    rec = build_recommendation("domestic", sr.URGENCY_CONCERNING, {"injury": "Yes"})
    assert "DOM-04" in rec.rules_matched


def test_otp_shared_vs_not_shared():
    shared = build_recommendation("otp", sr.URGENCY_ADVICE, {"shared": "Yes"})
    safe = build_recommendation("otp", sr.URGENCY_ADVICE, {"shared": "No", "money": "No"})
    assert "OTP-02" in shared.rules_matched and "OTP-03" not in shared.rules_matched
    assert "OTP-03" in safe.rules_matched and "OTP-02" not in safe.rules_matched
    assert "cyber_1930" in shared.resource_keys


def test_threats_explicit_threat_triggers_emergency():
    rec = build_recommendation("threats", sr.URGENCY_ADVICE, {"explicit": "Yes"})
    assert rec.emergency_first and "THR-01" in rec.rules_matched


def test_transport_branches():
    a = build_recommendation("transport", sr.URGENCY_CONCERNING, {"staff": "Yes", "moving": "No"})
    b = build_recommendation("transport", sr.URGENCY_CONCERNING, {"staff": "No", "moving": "Yes", "ridehail": "Yes"})
    assert "TRA-02" in a.rules_matched and "TRA-05" in a.rules_matched
    assert {"TRA-03", "TRA-04", "TRA-06"} <= set(b.rules_matched)


def test_after_incident_branches():
    rec = build_recommendation("after", sr.URGENCY_ADVICE,
                               {"medical": "Yes", "report": "Not sure", "evidence": "Yes", "safe": "No"})
    assert {"AFT-01", "AFT-02", "AFT-04", "AFT-05"} <= set(rec.rules_matched)
    assert rec.emergency_first


def test_unsure_path_and_other_path():
    u = build_recommendation("unsure", sr.URGENCY_ADVICE, {"place": "No", "specific": "Yes"})
    assert {"UNS-02", "UNS-04", "UNS-05"} <= set(u.rules_matched)
    o = build_recommendation("other", sr.URGENCY_ADVICE, {}, description="I feel odd. Or else I will hurt you")
    assert "OTH-02" in o.rules_matched and "TXT-01" in o.rules_matched and o.signals


def test_harassment_branches():
    rec = build_recommendation("harassment", sr.URGENCY_CONCERNING,
                               {"continuing": "Yes", "witnesses": "No", "known": "Yes"})
    assert {"HAR-02", "HAR-05", "HAR-06"} <= set(rec.rules_matched)


def test_explanation_contains_required_fields():
    rec = build_recommendation("following", sr.URGENCY_CONCERNING, {"public": "Yes", "trust": "No"})
    text = rec.explanation()
    assert rec.situation_label in text
    assert "Concerning situation" in text
    assert "staffed public place" in text
    assert "Rules matched" in text and "FOL-02" in text
    assert "prediction" in rec.confidence_note.lower()
    assert rec.relevant_answers
    assert any("predict violence" in n for n in rec.notes)


@pytest.mark.parametrize("situation,urgency,answers", [
    (None, None, None), ("nope", "bogus", "not a dict"), ("", "", {"danger": 5}),
    (123, 456, ["x"]), ("online", "bogus", {"intimate": "maybe", "zzz": "Yes"}),
])
def test_invalid_or_missing_input_never_blocks_help(situation, urgency, answers):
    rec = build_recommendation(situation, urgency, answers, description=None)
    assert rec.steps and rec.emergency_available
    assert rec.urgency in sr.VALID_URGENCIES
    assert rec.situation in sr.SITUATIONS


def test_unclassifiable_situation_falls_back_with_note():
    rec = build_recommendation("not-a-situation")
    assert rec.situation == sr.FALLBACK_SITUATION
    assert any("could not be recognised" in n for n in rec.notes)


def test_unknown_answer_values_ignored():
    rec = build_recommendation("following", sr.URGENCY_ADVICE, {"danger": "perhaps"})
    assert not rec.emergency_first and rec.relevant_answers == {}


# ---- text signal detection -------------------------------------------------
def test_blackmail_sample_detects_expected_signals():
    res = analyze_text(SAMPLE_TEXTS["Blackmail with threat to leak photos"])
    keys = {m.key for m in res.matches}
    assert {"threat", "repeated_contact", "coercive_pressure", "expose_private"} <= keys
    assert res.reasons and all("Matched text" in r for r in res.reasons)
    assert "stopncii" in res.reporting_resource_keys
    assert res.security_actions and res.evidence_guidance and res.limitations


def test_otp_sample_detects_credential_request():
    res = analyze_text(SAMPLE_TEXTS["Suspicious OTP request"])
    assert "credential_request" in {m.key for m in res.matches}


def test_false_positive_demo_is_flagged_and_documented():
    res = analyze_text(SAMPLE_TEXTS["Harmless message (false-positive demo)"])
    assert res.matches
    assert any("False positives" in n for n in res.limitations)


def test_false_negative_demo_is_missed_and_documented():
    res = analyze_text(SAMPLE_TEXTS["Indirect pressure (false-negative demo)"])
    assert not res.matches
    assert "NOT mean you are safe" in " ".join(res.limitations)


@pytest.mark.parametrize("bad", ["", "   ", None, 42, []])
def test_empty_or_invalid_text(bad):
    res = analyze_text(bad)
    assert res.is_empty and res.matches == [] and res.indicator_label == "No text provided"
    assert sr.detect_signals(bad) == []


def test_indicator_is_illustrative_and_does_not_gate_help():
    res = analyze_text("hello, see you at lunch")
    assert "illustrative" in res.indicator_disclaimer.lower()
    assert "not a validated prediction" in res.indicator_disclaimer.lower()
    assert get_emergency_options()


def test_optional_analyzer_failure_does_not_break_engine():
    class Broken:
        def analyze(self, text):
            raise RuntimeError("boom")
    assert analyze_text("or else", extra_analyzer=Broken()).matches


# ---- demo scenarios --------------------------------------------------------
def test_six_scenarios_each_use_different_paths():
    assert len(SCENARIOS) >= 6
    assert len({s["situation"] for s in SCENARIOS}) == len(SCENARIOS)
    for s in SCENARIOS:
        a = build_recommendation(s["situation"], s["urgency"], s["answers"])
        b = build_recommendation(s["situation"], s["urgency"], s["alt_answers"])
        assert a.rules_matched != b.rules_matched, s["id"]


# ---- cancellation of contact-sharing flows ---------------------------------
def test_share_cancel_sends_nothing():
    draft = build_share_draft("Sister", "Someone is following me", "Near the market", "hi")
    assert isinstance(draft, ShareDraft) and draft.includes_location
    assert "Location text you typed (not GPS)" in draft.data_shared
    res = confirm_share(draft, False)
    assert res.status == "cancelled" and res.delivered is False
    assert cancel_share(draft).delivered is False


def test_share_confirm_is_simulation_only():
    draft = build_share_draft("Sister")
    res = confirm_share(draft, True)
    assert res.status == "simulated_confirmed" and res.delivered is False
    assert "SIMULATION" in res.message and "no message was sent" in res.message.lower()


@pytest.mark.parametrize("bad", ["", "  ", None, 5])
def test_share_requires_contact_name(bad):
    with pytest.raises(ValueError):
        build_share_draft(bad)


def test_confirm_without_draft_is_invalid():
    for draft in (None, "x"):
        res = confirm_share(draft, True)
        assert res.status == "invalid" and res.delivered is False
