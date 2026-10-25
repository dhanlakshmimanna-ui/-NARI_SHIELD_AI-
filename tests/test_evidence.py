import json

import pytest

from evidence import INCIDENT_CATEGORIES, EvidenceError, EvidenceStore


@pytest.fixture()
def store(tmp_path):
    return EvidenceStore(tmp_path / "records.json")


def test_create_record_with_consent(store):
    rec = store.create_record(INCIDENT_CATEGORIES[3], redacted_text="threat [REDACTED-PHONE]",
                              notes="my note", consent_sensitive=True, redaction_counts={"phone": 1})
    assert rec.id and rec.created_at and rec.category == INCIDENT_CATEGORIES[3]
    saved = store.list_records()
    assert len(saved) == 1 and saved[0]["notes"] == "my note"


def test_original_text_excluded_by_default(store):
    store.create_record("Cat", redacted_text="safe", original_text="SECRET original 9000000000",
                        consent_sensitive=True)
    raw = store.path.read_text(encoding="utf-8")
    assert "SECRET original" not in raw
    assert store.list_records()[0]["original_included"] is False


def test_original_saved_only_when_requested_with_consent(store):
    rec = store.create_record("Cat", original_text="orig", include_original=True, consent_sensitive=True)
    assert rec.original_included and rec.original_text == "orig"


def test_consent_required_for_text_notes_and_original(store):
    with pytest.raises(EvidenceError):
        store.create_record("Cat", redacted_text="x")
    with pytest.raises(EvidenceError):
        store.create_record("Cat", notes="x")
    with pytest.raises(EvidenceError):
        store.create_record("Cat", original_text="x", include_original=True)
    assert store.list_records() == []


def test_metadata_only_record_needs_no_consent(store):
    assert store.create_record("Cat").id


@pytest.mark.parametrize("cat", ["", "  ", None, 5])
def test_invalid_category(store, cat):
    with pytest.raises(EvidenceError):
        store.create_record(cat, consent_sensitive=True)


def test_export_json_valid_and_filterable(store):
    a = store.create_record("A", redacted_text="one", consent_sensitive=True)
    store.create_record("B", redacted_text="two", consent_sensitive=True)
    data = json.loads(store.export_json())
    assert len(data["records"]) == 2 and "Unencrypted" in data["notice"]
    only = json.loads(store.export_json(ids=[a.id]))
    assert [r["id"] for r in only["records"]] == [a.id]


def test_export_empty_store(store):
    assert json.loads(store.export_json())["records"] == []


def test_delete_single_record(store):
    a = store.create_record("A")
    b = store.create_record("B")
    assert store.delete(a.id) is True
    assert [r["id"] for r in store.list_records()] == [b.id]
    assert store.delete("missing") is False
    assert store.get(a.id) is None and store.get(b.id)["category"] == "B"


def test_clear_all(store):
    store.create_record("A")
    store.create_record("B")
    assert store.clear_all() == 2
    assert store.list_records() == []
    assert store.clear_all() == 0


def test_corrupt_file_handled(store):
    store.path.write_text("{not json", encoding="utf-8")
    assert store.list_records() == []
    assert store.load_warning
    store.create_record("A")
    assert len(store.list_records()) == 1


def test_wrong_format_file_handled(store):
    store.path.write_text('{"a": 1}', encoding="utf-8")
    assert store.list_records() == [] and store.load_warning


def test_demo_flag_persisted(store):
    store.create_record("A", redacted_text="x", consent_sensitive=True, is_demo=True)
    assert store.list_records()[0]["is_demo"] is True
