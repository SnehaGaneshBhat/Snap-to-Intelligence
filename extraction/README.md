# Person A — Extraction & Vision Pipeline

**Status: Core pipeline complete, tested across 11 images, ready for integration.**
See `FINDINGS.md` for final accuracy numbers and known limitations — use this for your pitch/demo prep.

## Setup (do this first, ~15 min)

1. Get a free Gemini API key: https://aistudio.google.com/apikey
2. `cp .env.example .env` and paste your key in
3. `pip install -r requirements.txt`
4. Install system Tesseract (for fallback OCR):
   - Ubuntu/Debian: `sudo apt install tesseract-ocr`
   - Mac: `brew install tesseract`
   - Windows: download from https://github.com/UB-Mannheim/tesseract/wiki

## Switching models

Set `GEMINI_MODEL` in `.env`:
- `gemini-flash-lite-latest` — cheap, high daily quota, use for day-to-day dev/testing
- `gemini-2.5-flash` — balanced quality/quota
- `gemini-3.5-flash` — best quality, only 20 free requests/day — use for final validation and demo day

If you hit a `429` quota error, either wait for the daily reset, switch to a lighter model in `.env`, or use a second API key from a different Google account.

## What's done

- [x] Core extraction function (`gemini_extract.py`) — image in, schema-compliant JSON out
- [x] Fallback OCR path (`ocr_fallback.py`) for redundancy if the primary API fails
- [x] Automatic retry with backoff for transient rate-limit/network errors
- [x] Deterministic output settings (temperature=0, top_k=1)
- [x] Prompt tuned for exhaustive extraction + correct unit handling
- [x] Tested across 11 real product images (breakers, motors, transformers, pumps, electronics)
- [x] Accuracy measured and documented (`eval.py` + `FINDINGS.md`)
- [x] Known limitations documented honestly for pitch/demo

## What Person C needs to know for integration

Import and call directly:

```python
from gemini_extract import extract_from_image

result = extract_from_image("path/to/photo.jpg")
# result["extracted_fields"] -> list of fields matching the shared schema
# result["error"] -> None on success, error message string on failure
```

If `result["error"]` is not None, handle gracefully in the UI (show "couldn't process image, try again" rather than crashing). This can happen on quota limits or network issues.

Fallback path (same input/output shape, use if primary fails repeatedly):
```python
from ocr_fallback import extract_via_ocr_fallback
result = extract_via_ocr_fallback("path/to/photo.jpg")
```

## Files in this folder

| File | Purpose |
|---|---|
| `gemini_extract.py` | Main extraction function — what Person C imports |
| `ocr_fallback.py` | Backup path using Tesseract if Gemini fails |
| `eval.py` | Accuracy testing script |
| `ground_truth.json` | Verified test set answers (11 images) |
| `list_available_models.py` | Utility to check which models your API key can access |
| `FINDINGS.md` | **Final accuracy numbers + known limitations — read this for the pitch** |
| `test_images/` | Test photos |
| `results/eval_results.json` | Latest accuracy report, auto-generated |
