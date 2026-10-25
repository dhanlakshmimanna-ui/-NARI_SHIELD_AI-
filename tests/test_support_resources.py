import json

from support_resources import (
    DEFAULT_RESOURCES, emergency_options, get_resources, is_https_url, is_valid_phone, resources_for,
)


def test_emergency_options_present_by_default():
    nums = [r.number for r in emergency_options()]
    assert "112" in nums


def test_emergency_number_configurable(tmp_path):
    cfg = tmp_path / "c.json"
    cfg.write_text(json.dumps({"resources": {"emergency_112": {"number": "911"}}}))
    assert get_resources(cfg)["emergency_112"].number == "911"
    assert "911" in [r.number for r in emergency_options(cfg)]


def test_invalid_overrides_ignored(tmp_path):
    cfg = tmp_path / "c.json"
    cfg.write_text(json.dumps({"resources": {
        "emergency_112": {"number": "call me!!"},
        "ncw": {"url": "http://not-https.example"},
        "unknown": {"number": "1"}}}))
    res = get_resources(cfg)
    assert res["emergency_112"].number == "112"
    assert res["ncw"].url == DEFAULT_RESOURCES["ncw"].url


def test_missing_or_broken_config(tmp_path):
    assert get_resources(tmp_path / "none.json")["emergency_112"].number == "112"
    bad = tmp_path / "bad.json"
    bad.write_text("nope")
    assert get_resources(bad)["emergency_112"].number == "112"


def test_validators_and_lookup():
    assert is_valid_phone("+91 112") and not is_valid_phone("abc") and not is_valid_phone(None)
    assert is_https_url("https://example.org/x") and not is_https_url("javascript:alert(1)")
    assert [r.key for r in resources_for(["ncw", "bogus"])] == ["ncw"]


def test_every_resource_has_verify_note_and_contact():
    for r in DEFAULT_RESOURCES.values():
        assert r.verify_note and (r.number or r.url)
