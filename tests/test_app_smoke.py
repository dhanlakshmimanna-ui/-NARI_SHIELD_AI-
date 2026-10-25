"""Runs every page of the Streamlit app headlessly and fails on any exception."""
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

APP = str(Path(__file__).resolve().parent.parent / "app.py")
PAGES = [
    "Safety Dashboard", "Get Situation-Based Help", "Online Harassment & Blackmail",
    "Public Safety Assistance", "Personal Safety Planning", "Privacy & Evidence Vault",
    "Support Resources", "Demo Scenarios", "About & Limitations",
]


@pytest.mark.parametrize("page", PAGES)
def test_page_renders_without_exception(page):
    at = AppTest.from_file(APP, default_timeout=60).run()
    at.session_state["nav"] = page
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert any("Emergency help" in m.value for m in at.sidebar.markdown)
