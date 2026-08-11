"""
Person C — Adapter layer.

This is the ONLY file that knows Person A's and Person B's real function
signatures. If either of them changes theirs, this file changes and nothing
else does.

Design rules:
  1. sys.path juggling lives here and nowhere else.
  2. A and B are imported LAZILY, inside the functions. A missing or broken
     module must degrade to a skipped stage, never prevent the server booting.
  3. Neither function ever raises. They return a dict (or None) so main.py has
     no try/except around pipeline calls.
"""

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
EXTRACTION_DIR = ROOT / "extraction"
ENRICHMENT_DIR = ROOT / "enrichment"

for _d in (EXTRACTION_DIR, ENRICHMENT_DIR):
    if _d.is_dir() and str(_d) not in sys.path:
        sys.path.insert(0, str(_d))


def extraction_available() -> bool:
    return (EXTRACTION_DIR / "gemini_extract.py").is_file()


def enrichment_available() -> bool:
    """Person B's entry point. Checked by name so /health can report it."""
    if not ENRICHMENT_DIR.is_dir():
        return False
    return any(
        (ENRICHMENT_DIR / name).is_file()
        for name in ("merge.py", "build_profile.py", "enrich.py", "main.py")
    )


def _import_enrichment_entry():
    """
    Person B's deliverable is `build_full_profile(a_output, enrichment_output)`.
    It lives in merge.py — his README says to import it from there — but the
    other names stay in the list so a rename on his side doesn't break us.
    """
    for module_name in ("merge", "build_profile", "enrich", "main"):
        try:
            module = __import__(module_name)
        except Exception:
            continue
        fn = getattr(module, "build_full_profile", None)
        if callable(fn):
            return fn
    return None


def _flatten_for_person_b(extraction: dict) -> dict:
    """
    Person A returns a LIST of field objects; Person B reads FLAT KEYS:

        A: {"extracted_fields": [{"field_name": "brand", "value": "Siemens"}, ...]}
        B: person_a_output.get("brand")

    Neither of them is wrong — they were built against the same schema doc a
    week apart. Rather than make either rewrite working, tested code, the
    translation lives here, which is the whole reason this file exists.
    """
    flat = {
        "image_filename": extraction.get("image_filename"),
        "brand": None,
        "model_number": None,
        "serial_number": None,
    }
    for field in extraction.get("extracted_fields") or []:
        if not isinstance(field, dict):
            continue
        name = field.get("field_name")
        if name in flat and flat[name] is None:
            flat[name] = field.get("value")
    return flat



def run_extraction(image_path: str) -> dict:
    """
    Call Person A's extract_from_image().

    Person A's function takes a FILESYSTEM PATH (it calls genai.upload_file),
    not bytes — main.py writes the upload to a temp file before calling this.

    If the primary Gemini path fails, automatically try Person A's Tesseract
    fallback. They built it for exactly the demo-day quota scenario, so wire it
    up rather than leaving it unused.

    Always returns a dict shaped like Person A's output. Never raises.
    """
    try:
        from gemini_extract import extract_from_image
    except Exception as e:
        return {
            "extracted_fields": [],
            "error": f"Extraction module unavailable: {e}",
        }

    try:
        result = extract_from_image(image_path)
    except Exception as e:
        result = {"extracted_fields": [], "error": f"Extraction crashed: {e}"}

    if not isinstance(result, dict):
        return {"extracted_fields": [], "error": "Extraction returned a non-dict"}

    # Primary path worked.
    if not result.get("error") and result.get("extracted_fields"):
        return result

    # Primary failed or came back empty — try the OCR fallback.
    try:
        from ocr_fallback import extract_via_ocr_fallback

        fallback = extract_via_ocr_fallback(image_path)
        if isinstance(fallback, dict) and not fallback.get("error") and fallback.get(
            "extracted_fields"
        ):
            fallback["used_fallback"] = True
            return fallback
    except Exception:
        pass  # fallback is best-effort; report the original error below

    return result


def _import_enrichment_producer():
    """
    Find something that turns A's extraction into B's `enrichment_output`.

    B's resolve/score loop currently lives inside enrich.py's `if __name__ ==
    "__main__"` block, so there is no importable function that produces it yet
    (his own build_full_profile is the only exported entry point). We look for
    the likely names anyway: the day he lifts that loop into a function, this
    picks it up with no change here.
    """
    candidates = (
        "enrich_from_extraction",
        "build_enrichment",
        "run_enrichment",
        "enrich_profile",
    )
    for module_name in ("merge", "enrich", "build_profile", "main"):
        try:
            module = __import__(module_name)
        except Exception:
            continue
        for attr in candidates:
            fn = getattr(module, attr, None)
            if callable(fn):
                return fn
    return None


def run_enrichment(extraction_result: dict) -> dict | None:
    """
    Call Person B's build_full_profile().

    Two arguments, per his README:
        build_full_profile(person_a_output, enrichment_output)

    person_a_output is flattened from A's list shape. enrichment_output comes
    from B's producer when one exists, and is `{}` otherwise — NOT None, because
    his merge calls .get() on it directly and None would raise. With `{}` his
    function returns a valid profile whose specs are empty and whose confidence
    reads "unverified", which is the honest description of a scan that never got
    enriched.

    Returns his profile dict, or None if enrichment is unavailable — None means
    "stage skipped" and assemble.py fills the gap.
    """
    fn = _import_enrichment_entry()
    if fn is None:
        return None

    flat = _flatten_for_person_b(extraction_result)

    enrichment_output = {}
    producer = _import_enrichment_producer()
    if producer is not None:
        try:
            produced = producer(flat)
            if isinstance(produced, dict):
                enrichment_output = produced
        except Exception:
            pass  # best-effort; an empty enrichment is still a valid profile

    try:
        result = fn(flat, enrichment_output)
    except TypeError:
        # Tolerate a single-argument signature.
        try:
            result = fn(flat)
        except Exception:
            return None
    except Exception:
        return None

    return result if isinstance(result, dict) else None

