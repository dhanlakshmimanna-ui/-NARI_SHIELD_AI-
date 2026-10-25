"""Local, user-controlled evidence records stored as JSON.

WHAT IS SAVED: only what you choose. By default the original text is NOT saved,
and redacted text/notes need explicit consent.
WHERE: a local JSON file on this computer (default ``data/evidence_records.json``).
THE FILE IS NOT ENCRYPTED. Anyone with access to the computer can read it.
Nothing is uploaded anywhere. Production use needs encrypted storage, access
control and audit logging.
"""
from __future__ import annotations

import json
import os
import tempfile
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from safety_rules import SITUATIONS

DEFAULT_STORE_PATH = Path(__file__).parent / "data" / "evidence_records.json"
INCIDENT_CATEGORIES = tuple(s.label for s in SITUATIONS.values())

STORAGE_NOTICE = (
    "Records are saved only to a local JSON file on this computer. The file is NOT encrypted and "
    "nothing is uploaded. Anyone with access to this computer or file could read it. Delete records "
    "you no longer need."
)


class EvidenceError(ValueError):
    """Raised for invalid evidence input or missing consent."""


@dataclass
class EvidenceRecord:
    id: str
    created_at: str
    category: str
    notes: str = ""
    redacted_text: str = ""
    original_text: str = ""
    original_included: bool = False
    consent_sensitive: bool = False
    redaction_counts: dict = field(default_factory=dict)
    signals: list = field(default_factory=list)
    is_demo: bool = False


class EvidenceStore:
    def __init__(self, path=None):
        self.path = Path(path) if path else DEFAULT_STORE_PATH
        self.load_warning = ""

    # -- persistence -------------------------------------------------------
    def _read(self) -> list[dict]:
        self.load_warning = ""
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return [d for d in data if isinstance(d, dict) and "id" in d]
            self.load_warning = "Evidence file had an unexpected format and was treated as empty."
        except (OSError, ValueError):
            self.load_warning = "Evidence file could not be read and was treated as empty."
        return []

    def _write(self, rows: list[dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(self.path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(rows, fh, indent=2, ensure_ascii=False)
            os.replace(tmp, self.path)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)

    # -- operations --------------------------------------------------------
    def create_record(
        self, category, redacted_text="", notes="", original_text="",
        include_original=False, consent_sensitive=False,
        redaction_counts=None, signals=None, is_demo=False,
    ) -> EvidenceRecord:
        if not isinstance(category, str) or not category.strip():
            raise EvidenceError("An incident category is required.")
        redacted_text = redacted_text if isinstance(redacted_text, str) else ""
        notes = notes if isinstance(notes, str) else ""
        original_text = original_text if isinstance(original_text, str) else ""

        stores_content = bool(redacted_text.strip() or notes.strip())
        wants_original = bool(include_original and original_text.strip())
        if (stores_content or wants_original) and not consent_sensitive:
            raise EvidenceError("Explicit consent is required before storing text or notes.")

        record = EvidenceRecord(
            id=uuid.uuid4().hex[:12],
            created_at=datetime.now().isoformat(timespec="seconds"),
            category=category.strip(),
            notes=notes.strip(),
            redacted_text=redacted_text,
            original_text=original_text if wants_original else "",
            original_included=wants_original,
            consent_sensitive=bool(consent_sensitive),
            redaction_counts=dict(redaction_counts or {}),
            signals=list(signals or []),
            is_demo=bool(is_demo),
        )
        rows = self._read()
        rows.append(asdict(record))
        self._write(rows)
        return record

    def list_records(self) -> list[dict]:
        return self._read()

    def get(self, record_id):
        return next((r for r in self._read() if r.get("id") == record_id), None)

    def delete(self, record_id) -> bool:
        rows = self._read()
        kept = [r for r in rows if r.get("id") != record_id]
        if len(kept) == len(rows):
            return False
        self._write(kept)
        return True

    def clear_all(self) -> int:
        rows = self._read()
        if rows or self.path.exists():
            self._write([])
        return len(rows)

    def export_json(self, ids=None) -> str:
        rows = self._read()
        if ids is not None:
            wanted = set(ids)
            rows = [r for r in rows if r.get("id") in wanted]
        payload = {
            "exported_at": datetime.now().isoformat(timespec="seconds"),
            "notice": "Exported from NARI SHIELD AI prototype. Unencrypted. Handle carefully.",
            "records": rows,
        }
        return json.dumps(payload, indent=2, ensure_ascii=False)
