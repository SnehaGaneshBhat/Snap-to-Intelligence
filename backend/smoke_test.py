"""
Person C — backend smoke test.  Run:  python smoke_test.py

Covers the HTTP surface and, more importantly, the seam between Person A's
output, Person B's merge.py, and our envelope. Every assertion below was
written against B's real code, not against his README — when he changes his
shape, this file is what tells us.
"""
import json
import sys

from fastapi.testclient import TestClient

import adapters
import assemble
import main
import mock_store

client = TestClient(main.app)
failures = []


def check(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {name}" + (f"  — {detail}" if detail and not condition else ""))
    if not condition:
        failures.append(name)


def png_bytes():
    """Minimal valid 1x1 PNG."""
    import base64
    return base64.b64decode(
        b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )


# Person A's real output shape: a LIST of field objects.
FAKE_A = {
    "image_filename": "breaker.jpg",
    "extracted_fields": [
        {"field_name": "brand", "value": "Siemens", "raw_value": "Siemens",
         "source_type": "label", "source_reference": "photo label",
         "confidence": 0.94, "conflicting_values": []},
        {"field_name": "rated_voltage", "value": "48V", "raw_value": "48V",
         "source_type": "label", "source_reference": "photo label",
         "confidence": 0.72, "conflicting_values": []},
        {"field_name": None, "value": "junk", "raw_value": "junk",
         "source_type": "label", "source_reference": "x",
         "confidence": 0.5, "conflicting_values": []},
    ],
    "image_quality_flag": "clear",
    "overall_extraction_confidence": 0.88,
    "error": None,
}


print("\n=== /api/health ===")
r = client.get("/api/health")
check("health returns 200", r.status_code == 200, str(r.status_code))
health = r.json()
print("  " + json.dumps(health, indent=2).replace("\n", "\n  "))
check("reports extraction module", health.get("extraction_module") is True)
check("reports Person B's enrichment module", health.get("enrichment_module") is True)
check("reports Person B's mocks", health.get("mocks_loaded", 0) > 0)


print("\n=== /api/mocks (Person B's shared/mocks/mock_products.json) ===")
r = client.get("/api/mocks")
check("mocks endpoint returns 200", r.status_code == 200)
body = r.json()
check("available flag set", body.get("available") is True)
check("all 8 of his samples loaded", len(body.get("mocks") or []) == 8,
      str(len(body.get("mocks") or [])))
check("no REPLACE_ME template rows leaked",
      all("replace" not in str(m.get("brand", "")).lower() for m in body["mocks"]))
check("summary carries what the picker renders",
      all({"id", "brand", "model_number", "status", "field_count"} <= set(m)
          for m in body["mocks"]))
print("  " + ", ".join(f"{m['id']}={m['brand']}" for m in body["mocks"][:4]) + " …")


print("\n=== /api/mocks/{id} ===")
first_id = body["mocks"][0]["id"]
r = client.get(f"/api/mocks/{first_id}")
check("known id returns 200", r.status_code == 200)
mock_profile = r.json()["profile"]
check("envelope shape intact", set(r.json()) >= {"status", "profile", "error"})
check("sample is labelled a sample, not a live scan",
      mock_profile["stages"]["enrichment"] == "skipped"
      and any("Sample data" in w for w in mock_profile["warnings"]),
      str(mock_profile["warnings"]))
check("label provenance on every sample field",
      all(f["source_type"] == "label" for f in mock_profile["fields"]))
# A sample has real fields, so it must carry the same two score blocks a scan
# does — otherwise the meter falls back to its defaults and renders 0% over
# four visible rows.
mc = mock_profile.get("completeness") or {}
check("sample carries a completeness block", bool(mc), str(mock_profile.keys()))
check("sample meter is not a fabricated zero",
      mc.get("score", 0) > 0 and mc.get("fields_filled", 0) == len(mock_profile["fields"]),
      str(mc))
check("sample meter caption adds up",
      mc.get("fields_filled", 0) + len(mc.get("missing_fields") or []) == mc.get("expected_fields"),
      str(mc))
check("no field is both shown and listed missing",
      not ({f["field_name"] for f in mock_profile["fields"]}
           & set(mc.get("missing_fields") or [])),
      str(mc.get("missing_fields")))
check("sample field names use our canonical vocabulary",
      "voltage_rating" not in {f["field_name"] for f in mock_profile["fields"]},
      str([f["field_name"] for f in mock_profile["fields"]]))
check("sample carries a confidence summary",
      bool(mock_profile.get("confidence_summary")))
r = client.get("/api/mocks/does-not-exist")
check("unknown id 404s with an envelope", r.status_code == 404
      and set(r.json()) >= {"status", "profile", "error"})


print("\n=== mode=mock (zero API calls — the demo fallback) ===")
r = client.post("/api/scan", data={"mode": "mock"})
check("returns a profile now that B's file exists", r.status_code == 200, str(r.status_code))
check("envelope shape intact", set(r.json()) >= {"status", "profile", "error"})
check("has renderable fields", len(r.json()["profile"]["fields"]) > 0)


print("\n=== validation ===")
r = client.post("/api/scan", files={"image": ("notes.txt", b"hello", "text/plain")}, data={"mode": "auto"})
check("rejects wrong file type with 400", r.status_code == 400, str(r.status_code))
check("envelope shape intact on error", set(r.json()) >= {"status", "profile", "error"})
r = client.post("/api/scan", files={"image": ("x.png", b"", "image/png")}, data={"mode": "auto"})
check("rejects empty upload", r.status_code == 400, str(r.status_code))


print("\n=== real scan with no API key (degraded path) ===")
r = client.post("/api/scan", files={"image": ("x.png", png_bytes(), "image/png")}, data={"mode": "extract_only"})
check("never 500s", r.status_code in (200, 502), str(r.status_code))
body = r.json()
check("envelope shape intact", set(body) >= {"status", "profile", "error"})
print(f"  status={body['status']}  error={str(body['error'])[:110]}")


print("\n=== adapters: A's list shape -> B's flat shape ===")
flat = adapters._flatten_for_person_b(FAKE_A)
check("brand flattened for B", flat["brand"] == "Siemens", str(flat))
check("image_filename carried", flat["image_filename"] == "breaker.jpg")
check("missing keys are None, not absent",
      "model_number" in flat and flat["model_number"] is None, str(flat))


print("\n=== adapters -> Person B's real build_full_profile() ===")
enriched_live = adapters.run_enrichment(FAKE_A)
check("B's module was importable and ran", isinstance(enriched_live, dict), str(enriched_live))
if isinstance(enriched_live, dict):
    print("  B returned: " + json.dumps(enriched_live, ensure_ascii=False))
    check("his profile carries specs", "specs" in enriched_live)
    check("his identity echoed back", enriched_live.get("brand") == "Siemens")


print("\n=== envelope: B ran but found nothing on the web (his 'unverified' mode) ===")
env = assemble.build_envelope(FAKE_A, enriched_live, "case1", "breaker.jpg", None)
p = env["profile"]
check("drops nameless field", len(p["fields"]) == 2, f"got {len(p['fields'])}")
check("enrichment counted as ok — he ran, he just found nothing",
      p["stages"]["enrichment"] == "ok")
check("says so plainly", any("unverified" in w for w in p["warnings"]), str(p["warnings"]))
c = p["completeness"]
check("meter caption adds up",
      c["fields_filled"] + len(c["missing_fields"]) == c["expected_fields"], str(c))
check("no '0%' beside 'nothing missing'",
      not (c["score"] == 0 and not c["missing_fields"]), str(c))
check("label fields survive an empty enrichment",
      {f["field_name"] for f in p["fields"]} == {"brand", "rated_voltage"})
print(f"  score={c['score']}%  {c['fields_filled']}/{c['expected_fields']} fields")


print("\n=== envelope: B with real specs, his flat merge.py shape ===")
fake_b_flat = {
    "brand": "Siemens",
    "model_number": "3RT2025-1AP00",
    "serial_number": None,
    "image_filename": "breaker.jpg",
    "specs": {
        "voltage_rating": "220V",
        "current_rating": "17A",
        "dimensions": "45 x 58 x 92 mm",
        "weight": None,
    },
    "confidence": "high",
    "completeness_score": 85,
    "missing_fields": ["weight"],
    "conflicting_values": [
        {"field": "voltage_rating", "values": ["220V (manufacturer)", "230V (distributor)"]}
    ],
}
env = assemble.build_envelope(FAKE_A, fake_b_flat, "case2", "breaker.jpg", None)
p = env["profile"]
names = [f["field_name"] for f in p["fields"]]
# His "voltage_rating" is our "rated_voltage" — one property, one spelling, so
# A's label row and B's spec row collide on purpose instead of rendering twice.
check("his specs became renderable rows", "rated_voltage" in names, str(names))
check("his vocabulary canonicalized, not duplicated",
      "voltage_rating" not in names and "current_rating" not in names, str(names))
check("no duplicate rows", len(names) == len(set(names)), str(names))
check("status now ok", env["status"] == "ok")
check("empty spec dropped, not rendered blank", "weight" not in names)
check("his model_number filled our blank identity",
      p["identity"]["model_number"] == "3RT2025-1AP00")
check("label brand outranks his echo",
      next(f for f in p["fields"] if f["field_name"] == "brand")["source_type"] == "label")
c = p["completeness"]
check("his completeness score is used, not recomputed", c["score"] == 85, str(c))
check("captioned against HIS 8 expected fields", c["expected_fields"] == 8, str(c))
check("caption adds up", c["fields_filled"] + len(c["missing_fields"]) == c["expected_fields"], str(c))
check("no unverified warning when he is confident",
      not any("unverified" in w for w in p["warnings"]), str(p["warnings"]))

# A spec of his that A never saw: this row is purely his, so it shows what he
# contributes unopposed — including the confidence we inherit from his one word.
dims = next(f for f in p["fields"] if f["field_name"] == "dimensions")
check("inherited confidence sits at the band floor, not invented",
      dims["confidence"] == 0.85, str(dims["confidence"]))
check("his rows say enrichment, not a fabricated URL",
      dims["source_reference"] == "enrichment", str(dims["source_reference"]))

# The collision: A read 48V off the label, he found 220V on the web, and his own
# sources split 220V/230V. The label wins, and every disagreement stays visible.
volt = next(f for f in p["fields"] if f["field_name"] == "rated_voltage")
check("label value wins the collision", volt["value"] == "48V", str(volt["value"]))
check("label provenance kept", volt["source_type"] == "label")
check("winner is not listed as a conflict with itself",
      all(cv["value"] != volt["value"] for cv in volt["conflicting_values"]),
      str(volt["conflicting_values"]))
alternates = {cv["value"] for cv in volt["conflicting_values"]}
check("his value survives as a conflict", "220V" in alternates, str(alternates))
check("his sources' own disagreement survives too", "230V" in alternates, str(alternates))
by_value = {cv["value"]: cv for cv in volt["conflicting_values"]}
check("alternate's source recovered from his display string",
      by_value.get("230V", {}).get("source_type") == "distributor", str(by_value))
print(f"  rated_voltage = {volt['value']} ({volt['source_type']}) vs "
      + ", ".join(f"{cv['value']} ({cv['source_type']})" for cv in volt["conflicting_values"]))


print("\n=== envelope: B's module absent entirely (stage skipped) ===")
env = assemble.build_envelope(FAKE_A, None, "case3", "breaker.jpg", "/api/uploads/case3.jpg")
p = env["profile"]
check("status is partial, not failed", env["status"] == "partial")
check("enrichment marked skipped", p["stages"]["enrichment"] == "skipped")
check("warned", any("Enrichment unavailable" in w for w in p["warnings"]))
check("falls back to our own completeness", 0 <= p["completeness"]["score"] <= 100)
check("confidence bands counted",
      p["confidence_summary"]["high"] == 1 and p["confidence_summary"]["medium"] == 1)


print("\n=== envelope: a future B who speaks our list shape ===")
fake_b_rich = {
    "fields": [
        {"field_name": "rated_voltage", "value": "50 V", "raw_value": "50V",
         "source_type": "distributor", "source_reference": "https://d.example/p/1",
         "confidence": 0.71, "conflicting_values": []},
        {"field_name": "ip_rating", "value": "IP54", "raw_value": "IP54",
         "source_type": "manufacturer_site", "source_reference": "https://m.example/x",
         "confidence": 0.9, "conflicting_values": []},
    ],
    "completeness": {"score": 65, "fields_filled": 11, "expected_fields": 17,
                     "missing_fields": ["weight"]},
    "identity": {"category": "circuit_breaker"},
}
env = assemble.build_envelope(FAKE_A, fake_b_rich, "case4", "breaker.jpg", None)
p = env["profile"]
names = [f["field_name"] for f in p["fields"]]
check("no duplicate rows", len(names) == len(set(names)), str(names))
check("his completeness block passes through", p["completeness"]["score"] == 65)
check("his category merged", p["identity"]["category"] == "circuit_breaker")
voltage = next(f for f in p["fields"] if f["field_name"] == "rated_voltage")
check("label beats distributor", voltage["value"] == "48V", str(voltage["value"]))
check("loser kept as a conflict", len(voltage["conflicting_values"]) == 1)
check("conflict value recorded", voltage["conflicting_values"][0]["value"] == "50 V")


print("\n" + "=" * 52)
if failures:
    print(f"  {len(failures)} FAILURE(S): {', '.join(failures)}")
    sys.exit(1)
print("  All backend checks passed.")
