"""
Person C — Envelope assembly.

Takes Person A's raw extraction output (and Person B's enrichment output when
it exists) and produces the single response envelope the frontend consumes.

The important property: this module ALWAYS produces a complete, valid envelope.
When Person B is absent it computes stand-in completeness and confidence itself,
so the UI never has to handle a missing key. When B lands, their values win.
"""

import uuid
from datetime import datetime, timezone

SCHEMA_VERSION = "1.0"

# Confidence band thresholds. These MUST match frontend/src/lib/confidence.js.
BAND_HIGH = 0.85
BAND_MEDIUM = 0.60

# Authority ranking, lowest number = most authoritative.
SOURCE_AUTHORITY = {
    "label": 1,
    "manufacturer_site": 2,
    "datasheet_pdf": 3,
    "distributor": 4,
    "generic_web": 5,
    "inferred": 6,
}

IDENTITY_FIELDS = ("brand", "model_number", "serial_number")

# A and B name the same property differently — A reads "rated_voltage" off the
# label (gemini_extract.py), B's scoring.py calls it "voltage_rating". Left
# alone they become two rows for one property and _dedupe never fires, because
# it keys on the name. One canonical spelling per property, applied to every
# field from either of them. Ours matches Person A's, since those names are the
# ones a person sees printed on the nameplate.
FIELD_ALIASES = {
    "voltage_rating": "rated_voltage",
    "voltage": "rated_voltage",
    "rated_volts": "rated_voltage",
    "current_rating": "rated_current",
    "normal_current": "rated_current",
    "rated_amps": "rated_current",
    "power": "power_rating",
    "rated_power": "power_rating",
    "materials": "material",
    "operating_conditions": "operating_temperature",
    "certification": "certifications",
    "manufacturer": "brand",
    "make": "brand",
    "model": "model_number",
    "part_number": "model_number",
    "serial": "serial_number",
    "weight_kg": "weight",
    "enclosure": "enclosure_type",
    "mounting": "mounting_type",
    "ip": "ip_rating",
    "origin": "country_of_origin",
}


def canonical_field_name(name) -> str:
    """One spelling per property, whichever teammate produced the row."""
    key = str(name).strip().lower()
    return FIELD_ALIASES.get(key, key)


# Person B ranks sources with his own four-word vocabulary (scoring.py,
# conflict_resolution.py). Ours is longer because it also covers the photo
# label, which he never sees. Map his onto ours; anything unrecognised lands on
# generic_web rather than being invented.
B_SOURCE_MAP = {
    "manufacturer": "manufacturer_site",
    "datasheet": "datasheet_pdf",
    "distributor": "distributor",
    "generic": "generic_web",
}

# Person B's own expected-field list, lifted from scoring.py so completeness
# means the same thing on both sides of the wire. Ours is the fallback used
# only when his module is absent.
DEFAULT_EXPECTED_FIELDS = [
    "brand",
    "model_number",
    "serial_number",
    "rated_voltage",
    "rated_current",
    "power_rating",
    "frequency",
    "phase",
    "ip_rating",
    "operating_temperature",
    "dimensions",
    "weight",
    "material",
    "certifications",
    "enclosure_type",
    "mounting_type",
    "country_of_origin",
]



def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def band(confidence: float) -> str:
    if confidence >= BAND_HIGH:
        return "high"
    if confidence >= BAND_MEDIUM:
        return "medium"
    return "low"


def _clamp01(value, default=0.5) -> float:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, f))


def normalize_field(raw: dict) -> dict | None:
    """
    Coerce whatever A or B hands us into a valid field object.

    Anything without a field_name is dropped — a nameless row can't be rendered
    and is more likely a bug than data worth showing.
    """
    if not isinstance(raw, dict):
        return None

    field_name = raw.get("field_name")
    if not field_name or not str(field_name).strip():
        return None

    value = raw.get("value", raw.get("raw_value"))
    raw_value = raw.get("raw_value", value)

    source_type = raw.get("source_type") or "label"
    if source_type not in SOURCE_AUTHORITY:
        source_type = "generic_web"

    conflicts = []
    for c in raw.get("conflicting_values") or []:
        if not isinstance(c, dict):
            continue
        c_type = c.get("source_type") or "generic_web"
        if c_type not in SOURCE_AUTHORITY:
            c_type = "generic_web"
        conflicts.append(
            {
                "value": c.get("value"),
                "source_type": c_type,
                "source_reference": c.get("source_reference") or "",
                "confidence": _clamp01(c.get("confidence"), 0.5),
            }
        )

    field = {
        "field_name": canonical_field_name(field_name),
        "value": value,
        "raw_value": raw_value,
        "source_type": source_type,
        "source_reference": raw.get("source_reference") or "photo label",
        "confidence": _clamp01(raw.get("confidence"), 0.5),
        "conflicting_values": conflicts,
    }

    # Optional enrichment-only keys — carried through when present, never invented.
    for optional in ("display_name", "unit", "normalized_value"):
        if raw.get(optional) is not None:
            field[optional] = raw[optional]

    return field


def _dedupe(fields: list[dict]) -> list[dict]:
    """
    One row per field_name. When A and B both produce a field, keep the more
    authoritative source; on a tie keep the higher confidence. The loser is
    folded into conflicting_values rather than dropped — never silently discard.
    """
    by_name: dict[str, dict] = {}

    for field in fields:
        name = field["field_name"]
        existing = by_name.get(name)
        if existing is None:
            by_name[name] = field
            continue

        new_rank = SOURCE_AUTHORITY.get(field["source_type"], 9)
        old_rank = SOURCE_AUTHORITY.get(existing["source_type"], 9)

        if (new_rank, -field["confidence"]) < (old_rank, -existing["confidence"]):
            winner, loser = field, existing
        else:
            winner, loser = existing, field

        conflicts = winner.setdefault("conflicting_values", [])

        # Only record the loser as a conflict if it actually disagrees.
        if str(loser.get("value")) != str(winner.get("value")):
            conflicts.append(
                {
                    "value": loser.get("value"),
                    "source_type": loser["source_type"],
                    "source_reference": loser["source_reference"],
                    "confidence": loser["confidence"],
                }
            )

        # The loser may itself have carried alternates — B's web sources
        # disagreeing among themselves. Dropping the losing row must not drop
        # those: they are the evidence a human needs to settle the field.
        seen = {str(winner.get("value"))} | {str(c.get("value")) for c in conflicts}
        for extra in loser.get("conflicting_values") or []:
            if str(extra.get("value")) in seen:
                continue
            seen.add(str(extra.get("value")))
            conflicts.append(extra)

        by_name[name] = winner

    return list(by_name.values())


def _identity_from_fields(fields: list[dict]) -> dict:
    identity = {"brand": None, "model_number": None, "serial_number": None, "category": None}
    for field in fields:
        if field["field_name"] in IDENTITY_FIELDS:
            identity[field["field_name"]] = field.get("value")
    return identity


def _completeness(fields: list[dict], expected: list[str] | None = None) -> dict:
    expected = expected or DEFAULT_EXPECTED_FIELDS
    present = {f["field_name"] for f in fields if f.get("value") not in (None, "")}
    missing = [name for name in expected if name not in present]
    filled = len(expected) - len(missing)
    score = round(filled / len(expected) * 100) if expected else 0
    return {
        "score": score,
        "fields_filled": filled,
        "expected_fields": len(expected),
        "missing_fields": missing,
    }


def _confidence_summary(fields: list[dict]) -> dict:
    counts = {"high": 0, "medium": 0, "low": 0}
    for field in fields:
        counts[band(field["confidence"])] += 1
    overall = (
        round(sum(f["confidence"] for f in fields) / len(fields), 3) if fields else 0.0
    )
    return {"overall": overall, **counts}


# Person B reports one confidence word for the whole profile, not per field.
# scoring.py computes a per-field number, but merge.py drops it before we see
# it. Until that changes, an enriched field inherits the profile-level word —
# and inherits it at the BOTTOM of its band, because a profile-wide "high" is
# weaker evidence about one field than a measurement of that field would be.
B_CONFIDENCE_WORD = {
    "high": BAND_HIGH,
    "medium": BAND_MEDIUM,
    "low": 0.3,
    "unverified": 0.3,
}


def _b_confidence(value, default=0.45) -> float:
    """B's confidence is a word ('high'), a number (0.9), or missing."""
    if isinstance(value, str):
        return B_CONFIDENCE_WORD.get(value.strip().lower(), default)
    try:
        return _clamp01(float(value), default)
    except (TypeError, ValueError):
        return default


def _split_annotated(text):
    """
    Split Person B's display strings: "230V (distributor)" → ("230V", "distributor").

    His conflicting_values are pre-formatted for humans rather than structured
    (test_merge.py), and that parenthetical is the only record of which source a
    value came from. Reading it back is recovering data he wrote down — not
    guessing. Anything that doesn't match the pattern is returned unchanged with
    no source, so a value containing ordinary parentheses is never mangled.
    """
    raw = str(text).strip()
    if not raw.endswith(")") or "(" not in raw:
        return raw, None
    head, _, tail = raw.rpartition("(")
    source = tail[:-1].strip().lower()
    if source not in B_SOURCE_MAP:
        return raw, None
    return head.strip(), source



def fields_from_person_b(enriched: dict) -> list[dict]:
    """
    Turn Person B's flat profile into field rows.

    His shape (merge.py):
        {"specs": {"voltage": "220V", ...},
         "confidence": "high",
         "conflicting_values": [{"field": "voltage",
                                 "values": ["220V (manufacturer)", ...]}]}

    Two things this deliberately does NOT do:

      1. Invent per-field confidence. Every enriched row gets the same inherited
         number, so a field is never shown as more certain than B actually said.
      2. Invent a source_reference. B's merge output drops the URL that
         extract_specs.py captured, so the row says "enrichment" rather than
         naming a page we cannot actually cite. The footer promises every value
         is traceable; a fabricated citation would break that promise.
    """
    if not isinstance(enriched, dict):
        return []

    specs = enriched.get("specs")
    if not isinstance(specs, dict):
        return []

    inherited = _b_confidence(enriched.get("confidence"))

    # conflicting_values is a flat list keyed by field name; index it first.
    conflicts_by_field: dict[str, list] = {}
    for entry in enriched.get("conflicting_values") or []:
        if not isinstance(entry, dict):
            continue
        name = entry.get("field")
        if name:
            conflicts_by_field.setdefault(str(name), []).extend(
                entry.get("values") or []
            )

    rows = []
    for name, value in specs.items():
        # B's own resolved shape, if a future version passes it through whole.
        if isinstance(value, dict):
            final_value = value.get("final_value", value.get("value"))
            confidence = _b_confidence(value.get("confidence"), inherited)
            source_type = B_SOURCE_MAP.get(value.get("source_type"), "generic_web")
            reference = value.get("source_reference") or "enrichment"
            raw_conflicts = value.get("conflicting_values") or []
        else:
            final_value = value
            confidence = inherited
            source_type = "generic_web"
            reference = "enrichment"
            raw_conflicts = conflicts_by_field.get(str(name), [])

        if final_value in (None, ""):
            continue

        # B's alternates include the value that WON, formatted for display
        # ("220V (manufacturer)"). Listing the winner as a conflict with itself
        # reads as a disagreement that doesn't exist, so drop it — and recover
        # the source name he wrote in the parentheses while we're here.
        conflicts = []
        for candidate in raw_conflicts:
            if candidate in (None, ""):
                continue
            if isinstance(candidate, dict):
                c_value = candidate.get("value")
                c_source = B_SOURCE_MAP.get(candidate.get("source_type"), "generic_web")
                c_reference = candidate.get("source_reference") or "enrichment"
            else:
                c_value, c_source_word = _split_annotated(candidate)
                c_source = B_SOURCE_MAP.get(c_source_word, "generic_web")
                c_reference = c_source_word or "enrichment"
            if c_value in (None, "") or str(c_value) == str(final_value):
                continue
            conflicts.append(
                {
                    "value": c_value,
                    "source_type": c_source,
                    "source_reference": c_reference,
                    "confidence": confidence,
                }
            )

        rows.append(
            {
                "field_name": str(name),
                "value": final_value,
                "raw_value": final_value,
                "source_type": source_type,
                "source_reference": reference,
                "confidence": confidence,
                "conflicting_values": conflicts,
            }
        )

    return rows


# The eight fields Person B's calculate_completeness() scores against
# (enrichment/scoring.py). His profile reports the resulting percentage and the
# names that came back empty, but not the denominator — so we keep his list here
# to caption his number with the arithmetic he actually did.
B_EXPECTED_FIELDS = (
    "voltage_rating",
    "current_rating",
    "dimensions",
    "materials",
    "certifications",
    "operating_conditions",
    "compatible_products",
    "weight",
)


def completeness_from_person_b(enriched: dict, fields: list[dict]) -> dict | None:
    """
    Use B's completeness_score when he sends a meaningful one.

    His score is already weighted by average confidence (scoring.py), so we do
    not recompute it — we only need the caption underneath it, which his output
    doesn't carry. The denominator has to be HIS eight expected fields, not our
    field list: his percentage counts specs, and our list also holds the identity
    rows Person A read off the label, which his scoring never looked at. Mixing
    the two produced captions like "2 of 2 fields · 0%".

    Returns None when his numbers say nothing at all — score 0 with nothing
    listed as missing, which is what merge.py emits when no enrichment ran. The
    caller then falls back to counting the fields we actually have.
    """
    if not isinstance(enriched, dict):
        return None
    if "completeness_score" not in enriched:
        return None

    try:
        score = round(float(enriched["completeness_score"]))
    except (TypeError, ValueError):
        return None

    missing = [
        canonical_field_name(m) for m in (enriched.get("missing_fields") or [])
    ]
    if not missing and score <= 0:
        return None

    # Union rather than his list alone, so a field he starts scoring tomorrow
    # still lands in the denominator instead of pushing "filled" negative.
    expected = {canonical_field_name(f) for f in B_EXPECTED_FIELDS} | set(missing)

    return {
        "score": max(0, min(100, score)),
        "fields_filled": max(0, len(expected) - len(missing)),
        "expected_fields": len(expected),
        "missing_fields": missing,
    }


def score_fields(fields: list[dict]) -> tuple[dict, dict]:
    """
    Completeness + confidence blocks for an already-normalized field list.

    Public because mock_store needs them: a sample profile has real fields, so
    it should carry the same two blocks a scanned profile does. Without this the
    meter falls back to its zero defaults and renders "0% · 0 of 0 fields" over a
    sample that plainly shows four — a fabricated number, and the one thing this
    UI is supposed to never do.
    """
    return _completeness(fields), _confidence_summary(fields)


def build_envelope(
    extraction: dict,
    enriched: dict | None,
    profile_id: str,
    filename: str,
    image_url: str | None = None,
) -> dict:
    """
    Build the response envelope.

    extraction — Person A's raw output (required)
    enriched   — Person B's full profile, or None when the stage was skipped
    """
    warnings: list[str] = []

    # --- fields ------------------------------------------------------------
    raw_fields = list(extraction.get("extracted_fields") or [])
    enrichment_ok = False

    if enriched:
        # Person B's real shape is a flat `specs` dict (merge.py). The `fields`
        # / `extracted_fields` keys are checked first only so that a future
        # version of his module that speaks our list shape still works.
        b_fields = enriched.get("fields") or enriched.get("extracted_fields") or []
        if not b_fields:
            b_fields = fields_from_person_b(enriched)
        if b_fields:
            raw_fields = raw_fields + list(b_fields)
            enrichment_ok = True
        # B also ran if he handed back a merge-shaped dict whose specs are
        # empty — his documented "no web results" mode. Empty enrichment is
        # still enrichment: it earns the "unverified" warning below, not the
        # "module missing" one.
        elif isinstance(enriched, dict) and "specs" in enriched:
            enrichment_ok = True

    fields = [f for f in (normalize_field(r) for r in raw_fields) if f]
    fields = _dedupe(fields)

    # --- completeness ------------------------------------------------------
    # Label order matters: the photo label is ground truth for identity, so
    # _dedupe keeps A's row and drops B's when they collide on a field name.
    completeness = None
    if enrichment_ok and isinstance(enriched.get("completeness"), dict):
        completeness = dict(enriched["completeness"])
        completeness.setdefault("missing_fields", [])
    elif enrichment_ok:
        completeness = completeness_from_person_b(enriched, fields)
    if completeness is None:
        completeness = _completeness(fields)

    # --- identity ----------------------------------------------------------
    identity = _identity_from_fields(fields)
    if enrichment_ok:
        if isinstance(enriched.get("identity"), dict):
            for key, val in enriched["identity"].items():
                if val:
                    identity[key] = val
        else:
            # B's flat top-level keys. Only fill blanks: a value read off the
            # label outranks the same value echoed back from a web search.
            for key in IDENTITY_FIELDS:
                if not identity.get(key) and enriched.get(key):
                    identity[key] = enriched[key]

    # --- status ------------------------------------------------------------
    if not enrichment_ok:
        warnings.append("Enrichment unavailable — showing label data only.")
    elif str(enriched.get("confidence", "")).strip().lower() == "unverified":
        # B's documented degraded mode: model number found nothing on the web.
        # He marks it "unverified" rather than hallucinating, so say that.
        warnings.append("No sources found for this model — label data is unverified.")

    if extraction.get("used_fallback"):
        warnings.append("Primary vision model unavailable — used OCR fallback.")

    summary = _confidence_summary(fields)
    if fields and summary["overall"] < 0.5:
        warnings.append("Low confidence across most fields — review before use.")

    status = "ok" if (enrichment_ok and fields) else "partial"
    if not fields:
        status = "partial"
        warnings.insert(0, "No readable fields found in this image.")

    profile = {
        "schema_version": SCHEMA_VERSION,
        "profile_id": profile_id,
        "created_at": _now_iso(),
        "image": {
            "filename": filename,
            "url": image_url,
            "quality_flag": extraction.get("image_quality_flag") or "unknown",
        },
        "identity": identity,
        "fields": fields,
        "completeness": completeness,
        "confidence_summary": summary,
        "stages": {
            "extraction": "ok" if fields else "failed",
            "enrichment": "ok" if enrichment_ok else "skipped",
        },
        "warnings": warnings,
        "error": extraction.get("error"),
    }

    return {"status": status, "profile": profile, "error": None}


def ok(profile: dict) -> dict:
    return {"status": profile.get("_status", "ok"), "profile": profile, "error": None}


# Technical failure signatures → the sentence a person in front of the screen
# actually needs. Ordered: first match wins, so put the specific ones first.
ERROR_HINTS = (
    (
        ("no api_key", "adc found", "google_api_key", "api key not valid", "api_key_invalid"),
        "Extraction isn't configured yet — GEMINI_API_KEY is missing from backend/.env.",
    ),
    (
        ("quota", "rate limit", "resource_exhausted", "429"),
        "Extraction is rate-limited right now. Give it a moment, or open a sample profile.",
    ),
    (
        ("deadline", "timed out", "timeout"),
        "Extraction took too long to answer. Try again.",
    ),
    (
        ("getaddrinfo", "connection", "unreachable", "ssl", "dns"),
        "Couldn't reach the extraction service — check the network.",
    ),
    (
        ("tesseract",),
        "The OCR fallback isn't installed, so there was no second attempt at this image.",
    ),
)


def humanize_error(raw: str) -> tuple[str, str | None]:
    """
    Split a failure into (what the user reads, what the developer reads).

    Person A's SDK raises multi-line setup instructions. Those are genuinely
    useful — to whoever is running the server, not to whoever is watching the
    demo. So the sentence goes on screen and the raw text rides along in
    error_detail, where the UI keeps it behind a disclosure.
    """
    if not raw:
        return "Something went wrong before the label could be read.", None

    lowered = raw.lower()
    for needles, message in ERROR_HINTS:
        if any(needle in lowered for needle in needles):
            return message, raw

    # No known signature. A short single-line message is already fine to show;
    # a wrapped SDK dump is not.
    collapsed = " ".join(raw.split())
    if len(collapsed) > 160 or "\n" in raw:
        return "Extraction failed before it could read the label.", raw
    return collapsed, None


def failed(message: str, detail: str | None = None) -> dict:
    human, auto_detail = humanize_error(message)
    return {
        "status": "failed",
        "profile": None,
        "error": human,
        "error_detail": detail or auto_detail,
    }


def new_profile_id() -> str:
    return uuid.uuid4().hex[:12]
