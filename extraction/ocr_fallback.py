"""
Person A — Fallback OCR Path
Used if Gemini API fails/rate-limits during dev or live demo.
Pulls raw text via Tesseract, then structures it with a lightweight
Gemini text-only call (cheaper/faster than vision, and vision might
be the thing that's failing).

Requires: system tesseract installed (`sudo apt install tesseract-ocr`
on Linux, or `brew install tesseract` on Mac) + pytesseract package.
"""

import json
import re
import os
import pytesseract
from PIL import Image
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

# Windows users: if you skipped adding Tesseract to your system PATH,
# uncomment the line below and point it at your actual install location:
# pytesseract.pytesseract.tesseract_cmd = r"D:\downloads\Tesseract-OCR\tesseract.exe"

STRUCTURE_PROMPT = """Below is raw OCR text extracted from a photo of an industrial product's nameplate/label. The OCR may contain errors, garbled characters, or noise.

Extract only what you can confidently identify as: brand, model_number, serial_number, and any visible specs (voltage, current, dimensions, certifications, etc).

Raw OCR text:
---
{ocr_text}
---

Return ONLY a JSON object, no markdown fences:
{{
  "brand": "string or null",
  "model_number": "string or null",
  "serial_number": "string or null",
  "visible_specs": [
    {{"field_name": "...", "raw_value": "...", "confidence": 0.0-1.0}}
  ]
}}

Since this came from noisy OCR (not direct vision), cap all confidence scores at 0.7 maximum, even for text that looks clear."""


def _strip_json_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def extract_via_ocr_fallback(image_path: str) -> dict:
    """
    Fallback extraction path. Same output shape as gemini_extract.extract_from_image
    so Person C's integration code doesn't need to know which path was used.
    """
    try:
        img = Image.open(image_path)
        raw_text = pytesseract.image_to_string(img)

        if not raw_text.strip():
            return {"extracted_fields": [], "error": "OCR found no text in image"}

        model = genai.GenerativeModel("gemini-flash-lite-latest")
        response = model.generate_content(STRUCTURE_PROMPT.format(ocr_text=raw_text))
        parsed = json.loads(_strip_json_fences(response.text))

        extracted_fields = []
        for key in ["brand", "model_number", "serial_number"]:
            if parsed.get(key):
                extracted_fields.append({
                    "field_name": key,
                    "value": parsed[key],
                    "raw_value": parsed[key],
                    "source_type": "label",
                    "source_reference": "photo label (OCR fallback)",
                    "confidence": 0.6,
                    "conflicting_values": []
                })

        for spec in parsed.get("visible_specs", []):
            extracted_fields.append({
                "field_name": spec.get("field_name"),
                "value": spec.get("raw_value"),
                "raw_value": spec.get("raw_value"),
                "source_type": "label",
                "source_reference": "photo label (OCR fallback)",
                "confidence": min(spec.get("confidence", 0.5), 0.7),
                "conflicting_values": []
            })

        return {"extracted_fields": extracted_fields, "error": None, "used_fallback": True}

    except Exception as e:
        return {"extracted_fields": [], "error": f"OCR fallback failed: {e}"}