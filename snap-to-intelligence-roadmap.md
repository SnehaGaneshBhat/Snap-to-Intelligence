# Snap-to-Intelligence — 15-Day Build Roadmap

**Team:** 3 people
**Person A** — Extraction & Vision Pipeline
**Person B** — Enrichment, Standardization & Conflict Resolution
**Person C** — Frontend (React) + Backend Integration + Demo

**Core principle:** Everyone builds against a shared contract (schema + mock data) from Day 1, so no one blocks anyone until integration on Day 12-13. Each person can develop, test, and demo their own piece in total isolation using mock inputs/outputs.

---

## Day 0 (before Day 1 starts) — Team Setup (1-2 hrs, all together)

1. Agree on the shared JSON schema (product profile object) — lock it, don't revisit unless truly broken.
2. Create the repo with 3 folders: `/extraction`, `/enrichment`, `/frontend`, plus a `/shared` folder for schema + mock data files.
3. Everyone gets their free API keys sorted **today**: Google AI Studio (Gemini), SerpAPI or similar free search API, and any others.
4. Person B and Person C write 5-10 **mock JSON files** matching the shared schema by hand (fake but realistic product profiles) — these mocks are what Person C builds the UI against, and what Person B builds enrichment-output validation against, *before* Person A's real pipeline exists.
5. Agree on the API contract between backend and frontend (simple REST: `POST /scan` → returns product profile JSON). Doesn't need to be built yet — just agreed on paper/README.

**Deliverable by end of Day 0:** `schema.json`, 8-10 mock product profile JSONs in `/shared/mocks/`, API keys working, repo structure created.

---

## PERSON A — Extraction & Vision Pipeline

**Owns:** Turning a photo into raw extracted fields (brand, model, visible specs, serial number) with per-field confidence. Does NOT touch enrichment, standardization, or UI.

**Works entirely standalone**: test images in → JSON out. No dependency on B or C at any point except final integration.

### Day 1-2: Test set + environment
- Collect 20-25 real product/nameplate images (Google Images, manufacturer product pages, screenshots, personal devices as stand-ins). Store in `/extraction/test_images/`.
- For each, manually write the ground-truth values (brand, model, visible specs) into `/extraction/ground_truth.json`. This is your accuracy benchmark for the whole project.
- Set up Gemini API access (Vision + text in one call). Confirm a basic "describe this image" call works end-to-end.

### Day 3-4: Core vision extraction
- Write the core function: `extract_from_image(image) → raw_fields_json`
- Prompt Gemini to return strictly structured JSON: brand, model_number, serial_number, and any specs visibly printed on the label (voltage, amperage, dimensions, certifications visible on label, etc.)
- Force JSON-only output (system prompt instruction + strip markdown fences on parse).
- Test against your 20-25 image set, compare to ground truth, compute raw field-level accuracy.

### Day 5: Confidence scoring for extracted fields
- Assign confidence per field based on: (a) how directly Gemini states it vs. infers it, (b) OCR clarity heuristics (e.g., ask Gemini to self-report certainty per field in the same call), (c) fallback — if using Tesseract as backup, cross-check agreement between Gemini and Tesseract as a confidence signal.
- Output format must match the shared schema exactly (`raw_value`, `confidence`, `source_type: "label"`).

### Day 6: Fallback OCR path (redundancy)
- Add Tesseract/EasyOCR as a secondary path in case Gemini free tier rate-limits during demo.
- Simple logic: if Gemini call fails/errors, fall back to Tesseract + a lighter text-only LLM call to structure the OCR output.

### Day 7-8: Edge case handling
- Blurry/angled images → should output low confidence, not guess.
- Partially visible labels → should only output what's actually visible, mark rest as "not visible" rather than hallucinating.
- Test deliberately with 5 "bad" images (blurry, cropped, glare) and confirm graceful degradation.

### Day 9-10: Buffer + polish
- Improve prompt engineering based on Day 3-8 accuracy results.
- Re-run full test set, finalize accuracy number for the pitch (e.g., "92% field-level accuracy across 25 real products").
- Package your function as a clean, single callable: `extract_from_image(image_path_or_bytes) → JSON matching schema`. This is the exact interface Person C will call.

### Day 11: Freeze & document
- Write a short README: function signature, input/output format, known limitations, error states.
- No more prompt changes after this unless integration testing reveals a bug.

**Person A's deliverable at integration time:** one clean Python function/module that takes an image and returns a schema-compliant JSON of extracted fields with confidence scores. Fully tested standalone.

---

## PERSON B — Enrichment, Standardization & Conflict Resolution

**Owns:** Taking Person A's extracted fields (brand + model number) and enriching them with missing specs from external sources, normalizing units, resolving conflicts, computing completeness score.

**Works entirely standalone**: uses the mock extraction outputs from Day 0 (not Person A's real pipeline) for the entire build. Only swaps mock input for Person A's real output at integration time.

### Day 1-2: Test set + source strategy
- From the same product list Person A is testing (coordinate model numbers on Day 0/1 so your test sets overlap), manually collect: 1 manufacturer datasheet/product page + 1 distributor listing per product, for 10-15 products. Save URLs + saved HTML/PDF copies in `/enrichment/test_sources/` (don't rely on live scraping during dev — pages change/break).
- Set up web search API (SerpAPI free tier, or Bing/DuckDuckGo alternative) and confirm a basic "search model number → get URLs" call works.

### Day 3-4: Enrichment retrieval
- Write function: `enrich(brand, model_number) → list of source documents (URLs/text)`
- Given a model number, search web → fetch top 2-3 relevant pages (manufacturer site prioritized) → extract raw text (BeautifulSoup for HTML, PyMuPDF for PDFs).
- Test against your 10-15 saved sources first (avoids live-scraping flakiness during dev), then test live search separately.

### Day 5-6: Structured extraction from sources
- Write function: `extract_specs_from_text(raw_text) → structured fields JSON`
- Use a text LLM call (Gemini text or Groq) to pull structured attributes (dimensions, materials, certifications, operating conditions, compatible products) from the fetched page text.
- Each field must carry `source_type` and `source_reference` (URL/document name) per the shared schema.

### Day 7: Unit standardization
- Build a rule-based normalizer (not ML) for common industrial units: amps/volts, mm/inches, kg/lbs, °C/°F, IP ratings format.
- Input: raw value + unit as extracted → output: normalized value + standard unit.
- Keep this scoped to units that actually appear in your test set — don't over-engineer a universal converter.

### Day 8: Conflict resolution
- Write function: `resolve_conflicts(list of field values from different sources) → final_value + conflicting_values[]`
- Simple authority ranking: manufacturer site > official datasheet PDF > distributor/catalog > generic web result.
- When sources disagree, keep the highest-authority value as primary, log the rest in `conflicting_values` per the schema — never silently discard.

### Day 9: Confidence + completeness scoring
- Confidence for enriched fields: based on source authority + agreement across sources (if 2+ independent sources agree, higher confidence).
- Completeness Score: simple aggregate, e.g. `(fields_filled / expected_fields_for_category) * 100`, weighted slightly by average confidence.
- Output `missing_fields` list per schema.

### Day 10: Merge logic
- Write the final function: `build_full_profile(person_a_output, enrichment_output) → complete schema-compliant JSON`
- This is the function that combines A's extracted fields + B's enriched fields into one final object.

### Day 11: Buffer + edge cases
- Test: model number with no web results (should degrade gracefully, mark as "unverified," not hallucinate).
- Test: conflicting sources scenario deliberately (pick a product where you know sources disagree).

**Person B's deliverable at integration time:** one clean function that takes Person A's raw extraction JSON and returns the final, complete, enriched, schema-compliant product profile. Fully tested standalone using mocks.

---

## PERSON C — Frontend (React) + Backend Integration + Demo

**Owns:** The entire UI, the backend API that ties A + B together, and the live demo experience. Builds the UI against **mock JSON** the whole time — never blocked waiting for A or B.

### Day 1-3: UI skeleton + upload flow
- Set up React app (Vite is fastest to bootstrap, free).
- Build: photo upload/capture component → loading state → results view.
- Wire it to return one of your Day 0 mock JSONs (hardcoded, no real backend yet) so you can build the full visual flow immediately.

### Day 4-6: Product profile display
- Build the results screen: product image, extracted fields list, each field showing value + confidence badge (color-coded: green/yellow/red) + source tag.
- Click-to-expand on any field → shows source reference (URL/document) and, if conflicting, the alternate values.
- Completeness Score as a visual meter/gauge at the top (this is your "wow, simple, clear" element for judges).
- Missing fields section, clearly separated.

### Day 7: Backend API skeleton
- Set up a lightweight FastAPI (or Flask) server with one endpoint: `POST /scan` — accepts an image, will eventually call A then B, returns final JSON.
- For now, stub it: endpoint accepts image, ignores it, returns a mock JSON. This lets you build/test the full frontend↔backend wiring (network calls, loading states, error handling) without needing A/B's real code yet.

### Day 8-9: Frontend polish
- Responsive layout, clean visual hierarchy, loading/error states (what does the UI show if the scan fails or confidence is very low across the board?).
- Add a simple "before/after" or side-by-side view if time allows — showing raw label photo next to the structured profile is a strong visual for judges.

### Day 10: Error/edge state UI
- Design what the UI shows for: no results found, low-confidence extraction, conflicting values needing human review (maybe an "approve/edit" button per field — nice touch if time allows, optional).

### Day 11: Demo script draft
- Start writing the actual demo narrative: which product will you scan live, in what order will you show features, what's the 1-sentence framing for judges.

**Person C's deliverable at integration time:** working React frontend + backend API skeleton, fully functional against mock data, ready to swap mock responses for real calls to A's and B's functions.

---

## Days 12-13: Integration (all three together)

1. Person C wires the real `/scan` endpoint: receives image → calls Person A's `extract_from_image()` → passes result to Person B's `build_full_profile()` → returns final JSON to frontend.
2. Run your full test image set through the real, integrated pipeline end-to-end.
3. Fix mismatches between actual outputs and what the UI expects (should be minimal since everyone built against the same locked schema).
4. Re-measure accuracy on the full integrated system, not just each component alone — this is the number you'll actually quote.

## Day 14: Full testing + hardening

- Run the complete test set (20-25 images) through the live integrated app.
- Test deliberately with bad inputs (blurry photo, obscure product with no web presence) — confirm graceful failure, not crashes or hallucination.
- Fix any last bugs. Freeze feature development — no new features from this point.

## Day 15: Demo prep

1. Pick 2-3 physical objects (or high-quality pre-tested images) for the live demo — confirmed working in advance, zero surprises.
2. Record a backup video of a successful full run, in case live wifi/API issues happen on stage.
3. Finalize the pitch: problem (1 sentence) → solution (1 sentence) → live demo → accuracy numbers + completeness score example → business impact (time saved, trust/traceability angle) → close.
4. Rehearse the full demo at least twice as a team, timed.

---

## Key rules to keep the team unblocked

- **No one waits on anyone until Day 12.** A and B build/test against mocks and their own test sets. C builds against hardcoded mock JSON.
- **The schema is locked on Day 0.** If someone wants to change it after Day 1, that requires a quick team sync — don't let one person silently change the contract.
- **Everyone keeps their piece callable as a single clean function/endpoint.** This is what makes Day 12-13 integration fast instead of painful.
- **Track accuracy numbers from Day 1, not just at the end** — you'll want real, defensible numbers for the pitch, not last-minute guesses.
