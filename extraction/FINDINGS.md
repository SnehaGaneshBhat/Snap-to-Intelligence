# Extraction Pipeline — Final Findings & Known Limitations

**Status:** Core extraction pipeline complete and tested. Ready for integration.

## Final Accuracy Numbers

| Model | Test Set Size | Field-Level Accuracy |
|---|---|---|
| `gemini-3.5-flash` (best quality, 20 req/day free) | 5 images | 78.4% |
| `gemini-2.5-flash` (balanced, higher quota) | 11 images | 75.0% |

**Headline number for pitch: ~75-78% field-level accuracy**, tested across 11 real product nameplates spanning circuit breakers, motors, transformers, pumps, and consumer electronics (as a stand-in category).

## What the pipeline does well

- Reliably extracts brand, model number, and clearly-printed specs from clean, well-lit label photos
- Handles dense, multi-spec industrial nameplates (20+ fields in a single extraction on transformer/motor labels)
- Correctly reads non-Latin text when present (e.g. Chinese manufacturer text on a charger label)
- Degrades reasonably on moderate blur — tested on a legitimately blurry (but human-readable) photo and extraction quality held up

## Known limitations (documented honestly, not hidden)

1. **Character confusion on alphanumeric codes.** The model occasionally confuses visually similar characters — most notably letter "O" vs digit "0" in model numbers. This is a known limitation of vision-based text extraction generally, not unique to this pipeline.

2. **Inconsistent field coverage on dense labels.** On labels with many small-print fields (20+ specs), the model sometimes omits a subset of fields on a given run rather than extracting all of them — even with deterministic settings (temperature=0). This appears to be a genuine model-level limitation under heavy information density, not simple randomness we could fully engineer around.

3. **Self-reported confidence is not fully reliable.** In one test, the model extracted a serial number from a genuinely illegible, rotated, stamped tag and reported 1.0 (full) confidence — despite the value likely being wrong. This is why the product design treats AI confidence as a signal to prioritize for human review, not a guarantee of correctness.

4. **Model tier affects both quota and quality.** Lighter/cheaper models (`flash-lite`) have much higher free-tier request limits but measurably worse instruction-following (e.g. inconsistently stripping units it was told to keep). Stronger models (`gemini-3.5-flash`) are more accurate but quota-limited on the free tier. Production design implication: use a cost-efficient model by default, with an option to re-process low-confidence extractions on a stronger model.

5. **Unit/formatting consistency.** The model sometimes includes units (e.g. "460 V") and sometimes omits them (e.g. "460") for the same type of field across different images — this is a normalization problem for the downstream enrichment/standardization stage to handle, not something extraction alone should be expected to fully solve.

## Design implications for the rest of the product

- **Confidence scores should be treated as a triage signal, not ground truth.** Fields with lower confidence, or fields that a human reviewer flags as suspicious, should be prioritized for review — this is core to the "explainable and reliable" pitch, not just a nice-to-have.
- **A human-in-the-loop review step is not optional for high-stakes fields** (safety certifications, ratings that affect compatibility) given the demonstrated cases of confident-but-wrong extraction.
- **Multi-run consistency checking** (extracting the same image 2-3 times and comparing) is a stronger reliability signal than any single run's self-reported confidence, and worth considering as a v2 feature if time allows.
