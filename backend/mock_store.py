"""
Person C — Mock profile store.

Person B owns the files in /shared/mocks/. This module only READS them — it
never authors mock data. If the directory is empty, every function here
degrades to empty and the UI hides its sample row rather than inventing data.

Two layouts are supported, because B shipped the second one:

  1. One profile per file — {"profile": {...}} or a bare profile object.
  2. One file holding many records under "entries" — this is
     shared/mocks/mock_products.json, whose records look like:

        {"image_filename": "breaker_01.jpg", "brand": "Siemens",
         "model_number": "QP120", "serial_number": null,
         "specs": {"voltage_rating": "120/240V", "current_rating": "20A"}}

Those records are ground truth, not enriched profiles: they carry no
confidence, no source reference, and no conflicts. We surface exactly that —
see _entry_to_profile.
"""

import json
import pathlib

import assemble

MOCKS_DIR = pathlib.Path(__file__).resolve().parent.parent / "shared" / "mocks"

# A ground-truth record is a transcription of what is printed on the label.
# That is a real provenance claim and it is the strongest one in the system —
# but it says nothing about the fields nobody transcribed. So: label source,
# and a confidence that reads "medium" rather than a fabricated "high".
GROUND_TRUTH_CONFIDENCE = 0.6

IDENTITY_KEYS = ("brand", "model_number", "serial_number")


def _field(name, value, confidence=GROUND_TRUTH_CONFIDENCE):
    return {
        "field_name": assemble.canonical_field_name(name),
        "value": value,
        "raw_value": value,
        "source_type": "label",
        "source_reference": "sample data",
        "confidence": confidence,
        "conflicting_values": [],
    }


def _entry_to_profile(entry: dict, mock_id: str) -> dict:
    """
    Turn one of B's ground-truth records into a profile the UI can render.

    Deliberately minimal. These records have no enrichment attached, so the
    profile reports enrichment as "skipped" and carries a warning saying so.
    Showing a sample as though it were a fully enriched result would misrepresent
    what the pipeline actually produced.
    """
    fields = [
        _field(key, entry[key])
        for key in IDENTITY_KEYS
        if entry.get(key) not in (None, "")
    ]

    specs = entry.get("specs")
    if isinstance(specs, dict):
        fields.extend(
            _field(name, value)
            for name, value in specs.items()
            if value not in (None, "")
        )

    # Same scoring path a scanned profile takes, so the meter and the confidence
    # strip render for a sample too. The score will be modest — a label carries
    # a handful of the seventeen fields we expect — and that is the true answer
    # for un-enriched ground truth, not a flaw to paper over.
    completeness, confidence_summary = assemble.score_fields(fields)

    return {
        "profile_id": mock_id,
        "identity": {
            "brand": entry.get("brand"),
            "model_number": entry.get("model_number"),
            "serial_number": entry.get("serial_number"),
            "category": None,
        },
        "image": {
            "filename": entry.get("image_filename"),
            "url": None,
            "quality_flag": "unknown",
        },
        "fields": fields,
        "completeness": completeness,
        "confidence_summary": confidence_summary,
        "stages": {"extraction": "ok", "enrichment": "skipped"},
        "warnings": ["Sample data — label values only, not enriched."],
        "error": None,
    }


def _slug(entry: dict, index: int) -> str:
    """Stable, readable id: the image filename's stem, else the position."""
    name = entry.get("image_filename")
    if name:
        return pathlib.Path(str(name)).stem
    model = entry.get("model_number")
    if model:
        return str(model).lower().replace(" ", "-").replace("/", "-")
    return f"sample-{index + 1}"


def _to_envelope(data: dict, mock_id: str) -> dict:
    if "profile" in data and "status" in data:
        envelope = data
    elif "profile" in data:
        envelope = {"status": "ok", "profile": data["profile"], "error": None}
    else:
        envelope = {"status": "ok", "profile": data, "error": None}

    profile = envelope.get("profile")
    if isinstance(profile, dict):
        profile.setdefault("profile_id", mock_id)
    envelope["mock_id"] = mock_id
    return envelope


def _load_all() -> dict[str, dict]:
    """
    Read every JSON file in the mocks directory into {id: envelope}.

    Re-read on each call rather than cached at import: B can drop a new file in
    during the demo and it appears on the next request, no server restart.
    """
    out: dict[str, dict] = {}
    if not MOCKS_DIR.is_dir():
        return out

    for path in sorted(MOCKS_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            out[path.stem] = {
                "status": "failed",
                "profile": None,
                "error": f"Mock '{path.stem}' is not valid JSON: {e}",
                "mock_id": path.stem,
            }
            continue

        if not isinstance(data, dict):
            out[path.stem] = {
                "status": "failed",
                "profile": None,
                "error": f"Mock '{path.stem}' is not a JSON object",
                "mock_id": path.stem,
            }
            continue

        entries = data.get("entries")
        if isinstance(entries, list) and entries:
            # B's multi-record layout. One entry becomes one selectable sample.
            for index, entry in enumerate(entries):
                if not isinstance(entry, dict):
                    continue
                # His files carry an "_instructions" key and placeholder rows
                # left over from the template. Skip anything unfilled rather
                # than offering the judges a product called REPLACE_ME.
                if str(entry.get("brand", "")).upper() == "REPLACE_ME":
                    continue
                mock_id = _slug(entry, index)
                out[mock_id] = {
                    "status": "partial",
                    "profile": _entry_to_profile(entry, mock_id),
                    "error": None,
                    "mock_id": mock_id,
                }
        else:
            out[path.stem] = _to_envelope(data, path.stem)

    return out


def available() -> bool:
    return bool(_load_all())


def list_ids() -> list[str]:
    return sorted(_load_all())


def summaries() -> list[dict]:
    """Lightweight list for the frontend's sample picker."""
    out = []
    for mock_id, envelope in sorted(_load_all().items()):
        profile = envelope.get("profile") or {}
        identity = profile.get("identity") or {}
        completeness = profile.get("completeness") or {}
        out.append(
            {
                "id": mock_id,
                "brand": identity.get("brand"),
                "model_number": identity.get("model_number"),
                "status": envelope.get("status"),
                "score": completeness.get("score"),
                "field_count": len(profile.get("fields") or []),
            }
        )
    return out


def get(mock_id: str) -> dict | None:
    return _load_all().get(mock_id)


def first() -> dict | None:
    ids = list_ids()
    return get(ids[0]) if ids else None


def count() -> int:
    return len(_load_all())
