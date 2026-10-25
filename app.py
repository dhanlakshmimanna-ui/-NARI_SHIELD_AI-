"""NARI SHIELD AI - Streamlit front end.

Run with:  streamlit run app.py
All logic lives in the other modules; this file only renders the interface.
"""
from __future__ import annotations

import json
import re
from datetime import datetime

import pandas as pd
import streamlit as st

try:
    import plotly.express as px
except ImportError:  # plotly is optional for the charts only
    px = None

import safety_rules as sr
from decision_engine import analyze_text, build_recommendation
from demo_data import DEMO_DISCLAIMER, SAMPLE_TEXTS, SCENARIOS
from evidence import INCIDENT_CATEGORIES, STORAGE_NOTICE, EvidenceError, EvidenceStore
from privacy import LIMITATIONS as REDACTION_LIMITS
from privacy import preview as redaction_preview
from support_resources import (
    build_share_draft, confirm_share, cancel_share, emergency_options,
    get_resources, resources_for,
)

TAGLINE = "Understand the situation. Find the next safe step."
PAGES = [
    "Safety Dashboard",
    "Get Situation-Based Help",
    "Online Harassment & Blackmail",
    "Public Safety Assistance",
    "Personal Safety Planning",
    "Privacy & Evidence Vault",
    "Support Resources",
    "Demo Scenarios",
    "About & Limitations",
]

st.set_page_config(page_title="NARI SHIELD AI", page_icon="🛡️", layout="wide")

CSS = """
<style>
:root { --navy:#0a1628; --card:#10213a; --teal:#14b8a6; --cyan:#22d3ee; --amber:#f59e0b; --red:#ef4444; --text:#e6f1ff; }
.stApp { background: var(--navy); color: var(--text); }
section[data-testid="stSidebar"] { background:#07101f; border-right:1px solid #16304f; }
h1,h2,h3,h4 { color: var(--cyan); }
.brand { font-size:1.6rem; font-weight:800; color:var(--cyan); letter-spacing:.04em; }
.tag { color:#9fb7d4; margin-bottom:.8rem; }
.card { background:var(--card); border:1px solid #1d3a5f; border-radius:12px; padding:1rem 1.2rem; margin-bottom:.8rem; }
.card h4 { margin:0 0 .3rem 0; }
.badge { display:inline-block; padding:.15rem .6rem; border-radius:999px; font-weight:700; font-size:.85rem; }
.b-red { background:#7f1d1d; color:#fecaca; border:1px solid var(--red); }
.b-amber { background:#78350f; color:#fde68a; border:1px solid var(--amber); }
.b-teal { background:#134e4a; color:#99f6e4; border:1px solid var(--teal); }
.b-sim { background:#3b2f0b; color:#fde68a; border:1px dashed var(--amber); }
.sos { background:#2a0f14; border:2px solid var(--red); border-radius:12px; padding:.8rem 1rem; margin-bottom:.8rem; }
.sos a.call { display:block; text-align:center; background:var(--red); color:#fff !important; font-weight:800;
  font-size:1.15rem; padding:.8rem; border-radius:10px; text-decoration:none; margin:.4rem 0; }
.sos a.call:hover, .sos a.call:focus { outline:3px solid #fff; }
.step { border-left:4px solid var(--teal); padding:.4rem .8rem; margin:.4rem 0; background:#0d1d33; border-radius:0 8px 8px 0; }
.step.now { border-left-color:var(--red); }
.step.next { border-left-color:var(--amber); }
.demo-ban { background:#3b2f0b; border:1px dashed var(--amber); padding:.5rem .8rem; border-radius:8px; margin-bottom:.8rem; }
.stButton>button, .stDownloadButton>button { min-height:2.8rem; font-weight:600; border-radius:10px; }
@media (max-width: 640px) { .brand { font-size:1.2rem; } .card { padding:.7rem; } }
</style>
"""


# --------------------------------------------------------------------------
# State and helpers
# --------------------------------------------------------------------------
def init_state() -> None:
    ss = st.session_state
    ss.setdefault("nav", PAGES[0])
    ss.setdefault("contact", {"name": ""})
    ss.setdefault("plan", {})
    ss.setdefault("scn_reset", {})
    ss.setdefault("vault_input", "")
    ss.setdefault("ol_text", "")


def go_to(page: str) -> None:
    st.session_state["nav"] = page


def send_to_vault(text: str) -> None:
    st.session_state["vault_input"] = text
    st.session_state["nav"] = "Privacy & Evidence Vault"


def load_sample_text() -> None:
    choice = st.session_state.get("ol_sample")
    if choice in SAMPLE_TEXTS:
        st.session_state["ol_text"] = SAMPLE_TEXTS[choice]


def clear_text() -> None:
    st.session_state["ol_text"] = ""


def store() -> EvidenceStore:
    return EvidenceStore()


def tel_href(number: str) -> str:
    return "tel:" + re.sub(r"[^\d+]", "", number)


def emergency_panel(compact: bool = False) -> None:
    opts = emergency_options()
    links = "".join(
        f'<a class="call" href="{tel_href(r.number)}" aria-label="Call {r.name} {r.number}">'
        f'📞 Call {r.number} ({r.name})</a>'
        for r in opts
    )
    note = ("" if compact else
            '<div style="font-size:.85rem;color:#fecaca">The link opens your device\'s dialer. This app does not place '
            'calls or notify anyone. Nothing is contacted until you press call on your device. Numbers are configurable '
            'and must be verified for your area.</div>')
    st.markdown(f'<div class="sos"><b>🚨 Emergency help</b>{links}{note}</div>', unsafe_allow_html=True)


def urgency_badge(urgency: str) -> str:
    cls = {"immediate_danger": "b-red", "concerning_situation": "b-amber"}.get(urgency, "b-teal")
    return f'<span class="badge {cls}">{sr.URGENCY_LABELS.get(urgency, urgency)}</span>'


def card(title: str, body: str) -> None:
    st.markdown(f'<div class="card"><h4>{title}</h4><div>{body}</div></div>', unsafe_allow_html=True)


def sim_banner(text: str) -> None:
    st.markdown(f'<div class="demo-ban">🧪 <b>SIMULATION / DEMO:</b> {text}</div>', unsafe_allow_html=True)


# --------------------------------------------------------------------------
# Reusable components
# --------------------------------------------------------------------------
def question_inputs(sit_key: str, prefix: str, defaults: dict | None = None) -> dict:
    """Optional follow-up questions. Unanswered questions return None and never block help."""
    answers = {}
    defaults = defaults or {}
    for q in sr.SITUATIONS[sit_key].questions:
        default = defaults.get(q.id)
        idx = sr.ANSWER_OPTIONS.index(default) if default in sr.ANSWER_OPTIONS else None
        answers[q.id] = st.radio(q.text, sr.ANSWER_OPTIONS, index=idx, horizontal=True,
                                 key=f"{prefix}_{sit_key}_{q.id}")
    return {k: v for k, v in answers.items() if v is not None}


def trusted_contact_flow(prefix: str, situation_label: str, expanded: bool = False) -> None:
    with st.expander("Contact someone you trust (simulation)", expanded=expanded):
        sim_banner("No messaging integration exists. You will see a preview and can confirm or cancel, "
                   "but nothing will actually be sent.")
        default_name = st.session_state.get("contact", {}).get("name", "")
        name = st.text_input("Contact name or nickname", value=default_name, key=f"{prefix}_tc_name", max_chars=60)
        include_cat = st.checkbox("Include the situation category in the message", value=False, key=f"{prefix}_tc_cat")
        loc = st.text_input("Optional: location text you type yourself (no GPS is used)", key=f"{prefix}_tc_loc", max_chars=200)
        note = st.text_input("Optional short note", key=f"{prefix}_tc_note", max_chars=200)

        if st.button("Preview message", key=f"{prefix}_tc_preview"):
            try:
                st.session_state[f"{prefix}_draft"] = build_share_draft(
                    name, situation_label if include_cat else "", loc, note)
                st.session_state.pop(f"{prefix}_share_result", None)
            except ValueError as exc:
                st.session_state.pop(f"{prefix}_draft", None)
                st.error(str(exc))

        draft = st.session_state.get(f"{prefix}_draft")
        if draft and not st.session_state.get(f"{prefix}_share_result"):
            st.markdown("**Preview of what would be shared**")
            st.code(draft.message, language=None)
            st.markdown("Data included: " + ", ".join(draft.data_shared) + ".")
            st.caption("Not included: your GPS location, contacts, files, microphone or camera.")
            c1, c2 = st.columns(2)
            if c1.button("Confirm (simulated)", key=f"{prefix}_tc_confirm", type="primary"):
                st.session_state[f"{prefix}_share_result"] = confirm_share(draft, True)
                st.rerun()
            if c2.button("Cancel", key=f"{prefix}_tc_cancel"):
                st.session_state[f"{prefix}_share_result"] = cancel_share(draft)
                st.session_state.pop(f"{prefix}_draft", None)
                st.rerun()
        result = st.session_state.get(f"{prefix}_share_result")
        if result:
            (st.info if result.status == "cancelled" else st.warning)(result.message)
            if st.button("Start over", key=f"{prefix}_tc_reset"):
                st.session_state.pop(f"{prefix}_share_result", None)
                st.session_state.pop(f"{prefix}_draft", None)
                st.rerun()


def resource_lines(resources) -> None:
    for r in resources:
        bits = [f"**{r.name}**"]
        if r.number:
            bits.append(f"[{r.number}]({tel_href(r.number)})")
        if r.url:
            bits.append(f"[{r.url}]({r.url})")
        st.markdown(" · ".join(bits) + f"  \n{r.description}  \n_{r.verify_note}_")


def render_recommendation(rec, prefix: str) -> None:
    st.markdown(f"### Guidance for: {rec.situation_label} &nbsp; {urgency_badge(rec.urgency)}", unsafe_allow_html=True)
    for n in rec.notes[:-1]:
        st.info(n)
    if rec.situation == "domestic":
        st.markdown('<div class="card">💙 <b>You are not to blame.</b> Take only what feels safe. '
                    'This tool does not contact anyone automatically.<br>'
                    '<a href="https://www.wikipedia.org" style="color:#22d3ee">Quick exit (opens a neutral site; '
                    'does not erase your browser history)</a></div>', unsafe_allow_html=True)
    if rec.emergency_first:
        st.error("Emergency help comes first. Use the call option below if you can do so safely.")
        emergency_panel()

    st.markdown("#### Prioritized next steps")
    css = {"Now": "now", "Next": "next", "Later": ""}
    for when, items in rec.steps_by_priority().items():
        for text in items:
            st.markdown(f'<div class="step {css[when]}"><b>{when}:</b> {text}</div>', unsafe_allow_html=True)

    if rec.alternatives:
        st.markdown("#### Alternatives")
        for alt in rec.alternatives:
            st.markdown(f"- {alt}")

    trusted_contact_flow(f"{prefix}_{rec.situation}", rec.situation_label, expanded=rec.trusted_contact_suggested)

    if rec.documentation:
        st.markdown("#### Privacy-preserving documentation")
        for d in rec.documentation:
            st.markdown(f"- {d}")
        st.button("Open the Privacy & Evidence Vault", key=f"{prefix}_vault", on_click=go_to,
                  args=("Privacy & Evidence Vault",))

    st.markdown("#### Relevant resources")
    resource_lines(rec.resources())

    if rec.signals:
        st.markdown("#### Text indicators in your description (illustrative)")
        for s in rec.signals:
            st.markdown(f"- {s}")

    with st.expander("Why am I seeing this? (explanation)"):
        st.markdown(f"**Situation category:** {rec.situation_label}  \n**Urgency you selected:** {rec.urgency_label}")
        if rec.relevant_answers:
            st.markdown("**Your answers:**")
            for q, a in rec.relevant_answers.items():
                st.markdown(f"- {q} → **{a}**")
        else:
            st.markdown("No follow-up answers given. General guidance is shown. Answers are optional.")
        st.markdown("**Rules matched and reasons:**")
        st.dataframe(pd.DataFrame({"Rule": rec.rules_matched, "Reason": rec.reasons}), hide_index=True,
                     use_container_width=True)
        st.caption(rec.confidence_note)
        st.caption(rec.notes[-1])


def situation_flow(prefix: str, allowed=None, defaults=None, default_urgency=None) -> None:
    keys = list(allowed or sr.SITUATION_KEYS)
    sel = st.selectbox("What is happening?", keys, key=f"{prefix}_sit",
                       format_func=lambda k: f"{sr.SITUATIONS[k].letter}. {sr.SITUATIONS[k].label}")
    sit = sr.SITUATIONS[sel]
    st.write(sit.explanation)
    urgency = st.radio("How urgent does this feel?", list(sr.VALID_URGENCIES), horizontal=True,
                       index=list(sr.VALID_URGENCIES).index(default_urgency or sr.URGENCY_CONCERNING),
                       format_func=sr.URGENCY_LABELS.get, key=f"{prefix}_urg")
    if urgency == sr.URGENCY_IMMEDIATE:
        emergency_panel()
    description = ""
    if sel == "other":
        description = st.text_area("Describe the situation in your own words (optional, analysed only on this device)",
                                   key=f"{prefix}_desc", max_chars=2000)
    with st.expander("Optional follow-up questions (you can skip all of these)", expanded=True):
        answers = question_inputs(sel, prefix, defaults)
    rec = build_recommendation(sel, urgency, answers, description)
    render_recommendation(rec, prefix)


# --------------------------------------------------------------------------
# Pages
# --------------------------------------------------------------------------
def page_dashboard() -> None:
    st.markdown('<div class="brand">🛡️ NARI SHIELD AI</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="tag">{TAGLINE}</div>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown('<div class="card"><h4>Emergency help</h4><span class="badge b-red">Always available</span></div>',
                unsafe_allow_html=True)
    c2.markdown(f'<div class="card"><h4>Situations</h4><span class="badge b-teal">{len(sr.SITUATIONS)} decision paths</span></div>',
                unsafe_allow_html=True)
    c3.markdown(f'<div class="card"><h4>Demo scenarios</h4><span class="badge b-teal">{len(SCENARIOS)} replayable</span></div>',
                unsafe_allow_html=True)
    n = len(store().list_records())
    c4.markdown(f'<div class="card"><h4>Saved local records</h4><span class="badge b-amber">{n}</span></div>',
                unsafe_allow_html=True)

    emergency_panel()
    st.markdown("### Where would you like to start?")
    b1, b2, b3 = st.columns(3)
    b1.button("I need help now", on_click=go_to, args=("Get Situation-Based Help",), use_container_width=True, type="primary")
    b2.button("Online blackmail or harassment", on_click=go_to, args=("Online Harassment & Blackmail",), use_container_width=True)
    b3.button("Try a demo scenario", on_click=go_to, args=("Demo Scenarios",), use_container_width=True)

    st.markdown("### How the engine behaves across the demo scenarios")
    rows = []
    for s in SCENARIOS:
        rec = build_recommendation(s["situation"], s["urgency"], s["answers"])
        rows.append({"Scenario": s["title"], "Rules matched": len(rec.rules_matched),
                     "Steps": len(rec.steps), "Emergency first": "Yes" if rec.emergency_first else "No"})
    df = pd.DataFrame(rows)
    if px is not None:
        fig = px.bar(df, x="Scenario", y="Rules matched", color_discrete_sequence=["#14b8a6"],
                     title="Rules matched per demo scenario (illustrative of decision paths, not risk)")
        fig.update_layout(paper_bgcolor="#0a1628", plot_bgcolor="#10213a", font_color="#e6f1ff",
                          xaxis_title=None, margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.dataframe(df, hide_index=True, use_container_width=True)
    st.caption("This chart counts which rules fired. It is not a risk score and does not predict harm.")
    plan_state = "configured (kept private, not shown here)" if st.session_state.get("plan") else "not set"
    st.caption(f"Personal safety plan: {plan_state}. Evidence records are local to this computer.")


def page_help() -> None:
    st.header("Get Situation-Based Help")
    st.write("Choose what is happening. Help options appear immediately and update as you answer. "
             "No question is required.")
    emergency_panel(compact=True)
    situation_flow("gh")


def page_online() -> None:
    st.header("Online Harassment & Blackmail")
    tab1, tab2 = st.tabs(["Analyze text (optional)", "Guided workflow"])
    with tab1:
        st.info("Paste text only if you choose to. It is analysed in memory on this computer and is not sent anywhere. "
                "This tool never accesses your messages, accounts, contacts, camera or microphone.")
        c1, c2, c3 = st.columns([3, 1, 1])
        c1.selectbox("Or load a fictional demonstration conversation", list(SAMPLE_TEXTS), key="ol_sample")
        c2.button("Load sample", on_click=load_sample_text, use_container_width=True)
        c3.button("Clear", on_click=clear_text, use_container_width=True)
        text = st.text_area("Text to analyse", key="ol_text", height=180, max_chars=5000)
        if not text.strip():
            st.caption("No text yet. The guided workflow tab works without any text.")
        else:
            res = analyze_text(text)
            st.markdown(f"**Result:** {res.indicator_label}")
            st.caption(res.indicator_disclaimer)
            if res.matches:
                st.dataframe(pd.DataFrame([{
                    "Signal": m.label, "Matched text": "; ".join(m.snippets),
                    "Why it matched": m.reason, "Rules": ", ".join(m.rule_ids)} for m in res.matches]),
                    hide_index=True, use_container_width=True)
                st.caption("Matches describe wording only. They do not identify or accuse any person.")
            else:
                st.success("No predefined indicators matched. This does not mean you are safe; see limits below.")
            with st.expander("Suggested account-security actions", expanded=bool(res.matches)):
                for s in res.security_actions:
                    st.markdown(f"- {s}")
            with st.expander("Evidence-preservation guidance"):
                for s in res.evidence_guidance:
                    st.markdown(f"- {s}")
                st.button("Prepare a redacted record in the Vault", key="ol_to_vault",
                          on_click=send_to_vault, args=(text,))
            with st.expander("Reporting and support options"):
                resource_lines(resources_for(res.reporting_resource_keys + ["telemanas"]))
            with st.expander("False positives and false negatives (please read)", expanded=True):
                for s in res.limitations:
                    st.markdown(f"- {s}")
            if any(m.key == "threat" for m in res.matches):
                st.warning("If you feel physically threatened, emergency help is always available above.")
                emergency_panel(compact=True)
    with tab2:
        situation_flow("ol", allowed=["online"])


def page_public() -> None:
    st.header("Public Safety Assistance")
    st.write("Guidance for being followed, harassment, threats and unsafe transport. "
             "Emergency help does not depend on answering anything.")
    emergency_panel(compact=True)
    situation_flow("ps", allowed=["following", "harassment", "threats", "transport", "unsure"])


PLAN_PREP = [
    "Save the emergency number and a trusted person's number in my phone favourites",
    "Tell one trusted person how I would like them to respond if I ask for help",
    "Keep my phone charged and carry a small power bank when travelling",
    "Know where staffed public places are on my regular routes",
    "Decide on a code word that tells a trusted person I need help",
]
PLAN_FOLLOW = [
    "Write down what happened while I remember it",
    "Preserve messages or evidence before blocking or deleting",
    "Review my account security (passwords, two-step verification)",
    "Choose whether and when to report, and who can support me",
    "Arrange emotional support for myself",
]


def page_planning() -> None:
    st.header("Personal Safety Planning")
    st.info("Optional. You do not need to share sensitive details. This plan is kept only in this browser session "
            "(it is lost when you close the tab) unless you download it. It is not shown on the dashboard.")
    res = get_resources()
    contact_name = st.text_input("Trusted contact nickname (no phone number needed)",
                                 value=st.session_state["contact"].get("name", ""), max_chars=60)
    prefs = st.multiselect("How would you like to be supported?", [
        "Phone call first", "Text message first", "Come and meet me", "Stay on the phone with me",
        "Do not contact me unless I ask", "Help me contact the authorities if I ask"])
    safety_prefs = st.multiselect("General safety preferences", [
        "Share my journey with a trusted person", "Avoid isolated routes", "Prefer travelling in daylight",
        "Prefer licensed or app-booked transport", "Keep my phone charged"])
    chosen = st.multiselect("Resources I want in my plan", list(res), format_func=lambda k: res[k].name)
    emergency_info = st.text_area("Editable emergency information (optional, e.g. medical needs; avoid highly sensitive details)",
                                  max_chars=500)
    st.markdown("#### Preparation checklist")
    prep = [p for p in PLAN_PREP if st.checkbox(p, key=f"prep_{PLAN_PREP.index(p)}")]
    st.markdown("#### Follow-up checklist")
    follow = [p for p in PLAN_FOLLOW if st.checkbox(p, key=f"fol_{PLAN_FOLLOW.index(p)}")]
    done = len(prep) + len(follow)
    total = len(PLAN_PREP) + len(PLAN_FOLLOW)
    st.progress(done / total, text=f"{done} of {total} items ticked")

    plan = {
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "trusted_contact_nickname": contact_name.strip(), "support_preferences": prefs,
        "safety_preferences": safety_prefs, "resources": [res[k].name for k in chosen],
        "emergency_information": emergency_info.strip(), "preparation_done": prep, "followup_done": follow,
    }
    c1, c2 = st.columns(2)
    if c1.button("Save plan for this session", type="primary"):
        st.session_state["plan"] = plan
        st.session_state["contact"] = {"name": contact_name.strip()}
        st.success("Saved in this browser session only. Nothing was written to disk.")
    c2.download_button("Download my plan (JSON)", json.dumps(plan, indent=2), "safety_plan.json", "application/json")
    if st.button("Clear my plan"):
        st.session_state["plan"] = {}
        st.session_state["contact"] = {"name": ""}
        st.success("Plan cleared from this session.")


def page_vault() -> None:
    st.header("Privacy & Evidence Vault")
    st.warning(STORAGE_NOTICE)
    es = store()
    if es.list_records() is not None and es.load_warning:
        st.error(es.load_warning)

    st.subheader("1. Redaction preview")
    category = st.selectbox("Incident category", INCIDENT_CATEGORIES)
    text = st.text_area("Text you want to preserve (optional)", key="vault_input", height=160, max_chars=5000)
    terms_raw = st.text_input("Extra words to redact, separated by commas (e.g. names)")
    terms = [t.strip() for t in terms_raw.split(",") if t.strip()]
    prev = redaction_preview(text, terms)
    c1, c2 = st.columns(2)
    c1.markdown("**Original (shown only here, not saved by default)**")
    c1.code(prev["original"] or "(empty)", language=None)
    c2.markdown("**Redacted preview**")
    c2.code(prev["redacted"] or "(empty)", language=None)
    if prev["counts"]:
        st.caption("Redactions: " + ", ".join(f"{k}: {v}" for k, v in prev["counts"].items()))
    for lim in REDACTION_LIMITS:
        st.caption(lim)

    st.subheader("2. Create a record (optional)")
    notes = st.text_area("Your own notes (optional)", max_chars=1000)
    save_redacted = st.checkbox("Save the redacted text", value=True)
    save_original = st.checkbox("Also save the ORIGINAL text (not recommended)", value=False)
    consent = st.checkbox("I understand this will be saved unencrypted in a local file and I consent to saving what I selected.")
    if st.button("Save record", type="primary"):
        try:
            sig = [m.label for m in analyze_text(text).matches] if text.strip() else []
            rec = es.create_record(
                category, redacted_text=prev["redacted"] if save_redacted else "", notes=notes,
                original_text=text, include_original=save_original, consent_sensitive=consent,
                redaction_counts=prev["counts"], signals=sig)
            st.success(f"Record {rec.id} saved locally to {es.path.name}. It is not encrypted.")
        except EvidenceError as exc:
            st.error(str(exc))

    st.subheader("3. Your saved records")
    rows = es.list_records()
    if not rows:
        st.info("No records saved.")
    else:
        df = pd.DataFrame([{k: r.get(k) for k in ("id", "created_at", "category", "original_included", "is_demo")}
                           for r in rows])
        st.dataframe(df, hide_index=True, use_container_width=True)
        pick = st.selectbox("Select a record", [r["id"] for r in rows])
        with st.expander("View selected record"):
            st.json(es.get(pick))
        d1, d2 = st.columns(2)
        if d1.button("Delete selected record"):
            if es.delete(pick):
                st.success("Record deleted.")
                st.rerun()
        d2.download_button("Export all records (JSON)", es.export_json(), "evidence_export.json", "application/json")
        confirm_clear = st.checkbox("I want to permanently delete ALL records")
        if st.button("Clear all records", disabled=not confirm_clear):
            n = es.clear_all()
            st.success(f"{n} record(s) deleted.")
            st.rerun()

    with st.expander("Limitations and safer production alternatives"):
        st.markdown("- The JSON file is **not encrypted** and sits on this computer only.\n"
                    "- Redaction is pattern based and **does not guarantee anonymity**.\n"
                    "- Deleting a file does not guarantee secure erasure from disk or backups.\n"
                    "- Production alternative: encrypted storage with access control, secure deletion, and audit logs.")


def page_resources() -> None:
    st.header("Support Resources")
    st.info("Defaults are for India and must be verified before you rely on them. They can be changed in "
            "`data/config.json` (see README). No contact details were invented.")
    emergency_panel(compact=True)
    res = get_resources()
    st.dataframe(pd.DataFrame([{
        "Resource": r.name, "Number": r.number, "Website": r.url, "About": r.description,
        "Type": r.category} for r in res.values()]), hide_index=True, use_container_width=True)
    for r in res.values():
        with st.expander(r.name):
            resource_lines([r])


def page_demo() -> None:
    st.header("Demo Scenarios")
    st.markdown(f'<div class="demo-ban">🧪 {DEMO_DISCLAIMER}</div>', unsafe_allow_html=True)
    emergency_panel(compact=True)
    by_title = {s["title"]: s for s in SCENARIOS}
    title = st.selectbox("Choose a scenario", list(by_title))
    s = by_title[title]
    reset_n = st.session_state["scn_reset"].get(s["id"], 0)
    variant = st.radio("Answer set", ["As written", "Alternate answers (shows a different path)"], horizontal=True,
                       key=f"scn_var_{s['id']}_{reset_n}")
    alt = variant != "As written"
    defaults = s["alt_answers"] if alt else s["answers"]
    prefix = f"scn_{s['id']}_{reset_n}_{int(alt)}"

    st.markdown("#### Step 1 - What the user says")
    st.markdown(f"> {s['user_input']}")
    st.markdown("#### Step 2 - Context-specific questions")
    urgency = st.radio("Urgency", list(sr.VALID_URGENCIES), horizontal=True, format_func=sr.URGENCY_LABELS.get,
                       index=list(sr.VALID_URGENCIES).index(s["urgency"]), key=f"{prefix}_urg")
    if urgency == sr.URGENCY_IMMEDIATE:
        emergency_panel()
    answers = question_inputs(s["situation"], prefix, defaults)
    st.markdown("#### Step 3 - Decision path and explanation")
    rec = build_recommendation(s["situation"], urgency, answers, s["user_input"])
    render_recommendation(rec, prefix)

    st.markdown("#### Step 4 - Privacy and evidence options")
    sample = s["sample_text"] or s["user_input"]
    st.caption(s["evidence_note"])
    pv = redaction_preview(sample)
    st.code(pv["redacted"], language=None)
    if s["sample_text"]:
        res = analyze_text(s["sample_text"])
        st.markdown(f"Text indicators in the sample: **{res.indicator_label}** (illustrative only)")
        for r in res.reasons:
            st.markdown(f"- {r}")
    consent = st.checkbox("I consent to saving this fictional redacted sample as a DEMO record (local, unencrypted)",
                          key=f"{prefix}_consent")
    if st.button("Save demo record", key=f"{prefix}_save"):
        try:
            label = sr.SITUATIONS[s["situation"]].label
            r = store().create_record(label, redacted_text=pv["redacted"], consent_sensitive=consent,
                                      redaction_counts=pv["counts"], is_demo=True)
            st.success(f"Demo record {r.id} saved locally (not encrypted). You can delete it in the Vault.")
        except EvidenceError as exc:
            st.error(str(exc))

    if st.button("Reset and replay this scenario", key=f"{prefix}_reset"):
        st.session_state["scn_reset"][s["id"]] = reset_n + 1
        st.rerun()


def page_about() -> None:
    st.header("About & Limitations")
    st.markdown("""
**NARI SHIELD AI** is a situation-aware safety guidance prototype. It helps a user understand options and find
support. It is **not** an emergency service, a legal advisor or a counsellor.

#### Architecture
`app.py` (UI) → `decision_engine.py` (deterministic rules) → `safety_rules.py` (content, signals) ·
`privacy.py` (redaction) · `evidence.py` (local JSON store) · `support_resources.py` (resources, simulated sharing) ·
`demo_data.py` (fictional scenarios).
""")
    st.markdown("#### Working vs simulated")
    st.dataframe(pd.DataFrame([
        ("Situation decision paths (10)", "Working (rule-based)"),
        ("Text indicator detection", "Working (regex), with false positives/negatives"),
        ("Redaction and preview", "Working (pattern based, not guaranteed)"),
        ("Evidence records, export, delete", "Working (local, unencrypted JSON)"),
        ("Emergency call links", "Working as tel: links; your device places the call"),
        ("Trusted-contact alert", "SIMULATED: no message is ever sent"),
        ("Location sharing", "Not implemented"),
        ("Real-time dispatch / police integration", "Not implemented"),
    ], columns=["Feature", "Status"]), hide_index=True, use_container_width=True)
    st.markdown("""
#### Known limitations
- Rules are simple and cannot cover every situation. They do not predict violence or judge any person.
- Pattern matching misses indirect, coded or non-English wording and can flag harmless text.
- Resource numbers are defaults and must be verified locally.
- Local JSON is not encrypted; session data lives in the browser session only.

#### Future development
Encrypted storage and authentication, professionally reviewed content with local-language support, verified
messaging/location providers with delivery confirmation, partnerships with support organisations, accessibility
audits, and expert review for domestic-abuse and survivor-safety flows.
""")


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
PAGE_FUNCS = {
    "Safety Dashboard": page_dashboard,
    "Get Situation-Based Help": page_help,
    "Online Harassment & Blackmail": page_online,
    "Public Safety Assistance": page_public,
    "Personal Safety Planning": page_planning,
    "Privacy & Evidence Vault": page_vault,
    "Support Resources": page_resources,
    "Demo Scenarios": page_demo,
    "About & Limitations": page_about,
}


def main() -> None:
    init_state()
    st.markdown(CSS, unsafe_allow_html=True)
    with st.sidebar:
        st.markdown('<div class="brand">🛡️ NARI SHIELD AI</div>', unsafe_allow_html=True)
        st.caption(TAGLINE)
        emergency_panel(compact=True)
        st.radio("Navigation", PAGES, key="nav")
        st.caption("Prototype. Not an emergency service.")
    PAGE_FUNCS[st.session_state["nav"]]()


main()
