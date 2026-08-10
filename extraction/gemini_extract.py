"""
Person A — Core Vision Extraction Pipeline
Turns a product/nameplate photo into structured, schema-compliant JSON.

Usage:
    from gemini_extract import extract_from_image
    result = extract_from_image("test_images/breaker_01.jpg")
"""

import os
import json
import re
import time
from datetime import datetime, timezone
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

# MODEL_NAME is read from .env so you can switch models without editing code.
# Set GEMINI_MODEL=gemini-flash-lite-latest in .env for cheap dev/testing (high daily quota, lower accuracy)
# Set GEMINI_MODEL=gemini-3.5-flash in .env for final validation runs / demo day (better accuracy, only 20/day free)
MODEL_NAME = os.environ.get("GEMINI_MODEL", "gemini-flash-lite-latest")

# The prompt is the most important part of this file. Tune this based on
# accuracy results against your ground_truth.json test set.
EXTRACTION_PROMPT = """You are an expert industrial product data extractor. Look at this photo of a product or its nameplate/label.

CRITICAL: Be exhaustive. Extract EVERY single spec/value printed on the label — every row, every field. Do not skip fields, even ones that seem minor, unfamiliar, or hard to categorize. Scan the entire label systematically, top to bottom, left to right, before producing your answer. Missing a visible field is a serious error — it is far better to include a field with slightly lower confidence than to omit it entirely.

IMPORTANT — value formatting: the "raw_value" must include the actual measurement AND its unit, but NOT the printed field-name/label text next to it.

Examples of CORRECT extraction:
- Label shows "RATED VOLT 48V" → field_name: "rated_voltage", raw_value: "48V" (label text "RATED VOLT" removed, unit "V" KEPT)
- Label shows "FREQUENCY 50 Hz" → field_name: "frequency", raw_value: "50 Hz" (label text "FREQUENCY" removed, unit "Hz" KEPT)
- Label shows "3150 A" (no separate label word) → field_name: "normal_current", raw_value: "3150 A" (nothing to strip, keep as-is including unit)

Examples of INCORRECT extraction (do NOT do this):
- Label shows "RATED VOLT 48V" → raw_value: "RATED VOLT 48V" (WRONG — didn't strip the label text)
- Label shows "3150 A" → raw_value: "3150" (WRONG — stripped the unit "A", should have kept it)

Rule of thumb: only remove words that are clearly a field-name/category label (like "RATED VOLT", "FIELD CURRENT"). NEVER remove units (V, A, Hz, kV, kg, kW, rpm, etc.) — units are always part of the raw_value, not the label.

Extract ONLY information that is ACTUALLY VISIBLE in the image — do not guess or infer specs that aren't printed. But if it IS printed, no matter how minor, include it.

Return ONLY a JSON object (no markdown fences, no explanation text) in this exact structure:

{
  "brand": "manufacturer name as printed, or null if not visible",
  "model_number": "model/part number as printed, or null if not visible",
  "serial_number": "serial number as printed, or null if not visible",
  "visible_specs": [
    {
      "field_name": "e.g. voltage_rating, current_rating, dimensions, weight, ip_rating, material",
      "raw_value": "exactly as printed on label, e.g. '120/240V'",
      "confidence": 0.0 to 1.0,
      "reasoning": "one short phrase, e.g. 'clearly printed, high contrast' or 'partially obscured, inferred from partial text'"
    }
  ],
  "image_quality_flag": "clear | blurry | partially_obscured | glare",
  "overall_extraction_confidence": 0.0 to 1.0
}

Confidence scoring rules:
- 0.9-1.0: text is sharp, unambiguous, fully visible
- 0.6-0.89: text is readable but slightly unclear, angled, or partially obscured
- 0.3-0.59: text is guessed from partial/blurry visibility
- Below 0.3: do not include the field at all — omit it instead of guessing

Return ONLY the JSON object, nothing else."""


def _strip_json_fences(text: str) -> str:
    """Gemini sometimes wraps JSON in ```json ... ``` even when told not to. Strip it."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def extract_from_image(image_path: str) -> dict:
    """
    Core function Person C will call at integration time.

    Args:
        image_path: path to a local image file (jpg/png)

    Returns:
        dict matching the shared schema's "extracted_fields" section,
        plus metadata (image_quality_flag, overall_extraction_confidence).
        On failure, returns a dict with "error" key instead of raising,
        so the API layer can handle it gracefully.
    """
    try:
        image_file = genai.upload_file(image_path)
        model = genai.GenerativeModel(
            MODEL_NAME,
            generation_config=genai.GenerationConfig(
                temperature=0,
                top_p=1,
                top_k=1
            )
        )

        # Retry with backoff for transient rate limits (per-minute caps).
        # Does NOT help if you've hit the per-DAY quota — that only resets
        # at the next day (UTC). If you see the same 429 error repeatedly
        # even after waiting, you've hit the daily cap, not a transient limit.
        max_retries = 3
        response = None
        last_error = None
        for attempt in range(max_retries):
            try:
                response = model.generate_content([EXTRACTION_PROMPT, image_file])
                break
            except Exception as api_err:
                last_error = api_err
                if "429" in str(api_err) and attempt < max_retries - 1:
                    wait_seconds = 15 * (attempt + 1)  # 15s, 30s, 45s
                    print(f"   Rate limited, waiting {wait_seconds}s before retry {attempt + 2}/{max_retries}...")
                    time.sleep(wait_seconds)
                else:
                    raise

        if response is None:
            raise last_error

        raw_text = _strip_json_fences(response.text)
        parsed = json.loads(raw_text)

        # Reshape into schema-compliant "extracted_fields" list
        extracted_fields = []

        if parsed.get("brand"):
            extracted_fields.append({
                "field_name": "brand",
                "value": parsed["brand"],
                "raw_value": parsed["brand"],
                "source_type": "label",
                "source_reference": "photo label",
                "confidence": parsed.get("overall_extraction_confidence", 0.8),
                "conflicting_values": []
            })

        if parsed.get("model_number"):
            extracted_fields.append({
                "field_name": "model_number",
                "value": parsed["model_number"],
                "raw_value": parsed["model_number"],
                "source_type": "label",
                "source_reference": "photo label",
                "confidence": parsed.get("overall_extraction_confidence", 0.8),
                "conflicting_values": []
            })

        if parsed.get("serial_number"):
            extracted_fields.append({
                "field_name": "serial_number",
                "value": parsed["serial_number"],
                "raw_value": parsed["serial_number"],
                "source_type": "label",
                "source_reference": "photo label",
                "confidence": parsed.get("overall_extraction_confidence", 0.8),
                "conflicting_values": []
            })

        for spec in parsed.get("visible_specs", []):
            extracted_fields.append({
                "field_name": spec.get("field_name"),
                "value": spec.get("raw_value"),
                "raw_value": spec.get("raw_value"),
                "source_type": "label",
                "source_reference": "photo label",
                "confidence": spec.get("confidence", 0.5),
                "conflicting_values": []
            })

        return {
            "extracted_fields": extracted_fields,
            "image_quality_flag": parsed.get("image_quality_flag", "unknown"),
            "overall_extraction_confidence": parsed.get("overall_extraction_confidence", 0.5),
            "extracted_at": datetime.now(timezone.utc).isoformat(),
            "error": None
        }

    except json.JSONDecodeError as e:
        return {"extracted_fields": [], "error": f"JSON parse failure: {e}", "raw_response": raw_text if 'raw_text' in dir() else None}
    except Exception as e:
        return {"extracted_fields": [], "error": f"Extraction failed: {e}"}


if __name__ == "__main__":
    # Quick manual test — run: python gemini_extract.py test_images/your_image.jpg
    import sys
    if len(sys.argv) < 2:
        print("Usage: python gemini_extract.py <image_path>")
        sys.exit(1)
    result = extract_from_image(sys.argv[1])
    print(json.dumps(result, indent=2))