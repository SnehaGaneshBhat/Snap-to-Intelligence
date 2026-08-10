"""
Person A — Accuracy Evaluation Script

Runs extract_from_image() against every image in ground_truth.json and
computes field-level accuracy. Run this repeatedly as you tune your
prompt (Day 3-8) to track improvement, and run it one final time on
Day 10-11 to get the number you'll quote in the pitch.

Usage:
    python eval.py
"""

import json
import os
from gemini_extract import extract_from_image

TEST_IMAGES_DIR = "test_images"
GROUND_TRUTH_PATH = "ground_truth.json"
RESULTS_DIR = "results"


def normalize(val):
    """Loose string comparison — strips whitespace/case so '20A' == '20a' matches.
    Doesn't do unit conversion (that's Person B's job) — just fair string matching."""
    if val is None:
        return None
    return str(val).strip().lower().replace(" ", "")


def evaluate():
    with open(GROUND_TRUTH_PATH) as f:
        gt_data = json.load(f)

    entries = gt_data.get("entries", [])
    os.makedirs(RESULTS_DIR, exist_ok=True)

    total_fields_checked = 0
    total_fields_correct = 0
    per_image_results = []

    for entry in entries:
        image_path = os.path.join(TEST_IMAGES_DIR, entry["image_filename"])
        if not os.path.exists(image_path):
            print(f"⚠️  Skipping {entry['image_filename']} — file not found in test_images/")
            continue

        print(f"Testing {entry['image_filename']}...")
        result = extract_from_image(image_path)

        if result.get("error"):
            print(f"   ❌ Extraction error: {result['error']}")
            per_image_results.append({"image": entry["image_filename"], "error": result["error"]})
            continue

        # Build a lookup of what was actually extracted
        extracted_lookup = {f["field_name"]: f["value"] for f in result["extracted_fields"]}

        image_correct = 0
        image_total = 0
        field_details = []

        # Check top-level fields
        for field in ["brand", "model_number", "serial_number"]:
            expected = entry.get(field)
            if expected is None:
                continue
            image_total += 1
            got = extracted_lookup.get(field)
            is_correct = normalize(got) == normalize(expected)
            if is_correct:
                image_correct += 1
            field_details.append({
                "field": field, "expected": expected, "got": got, "correct": is_correct
            })

        # Check specs
        for field_name, expected in entry.get("specs", {}).items():
            image_total += 1
            got = extracted_lookup.get(field_name)
            is_correct = normalize(got) == normalize(expected)
            if is_correct:
                image_correct += 1
            field_details.append({
                "field": field_name, "expected": expected, "got": got, "correct": is_correct
            })

        total_fields_checked += image_total
        total_fields_correct += image_correct

        accuracy = (image_correct / image_total * 100) if image_total > 0 else 0
        print(f"   ✓ {image_correct}/{image_total} fields correct ({accuracy:.0f}%)")

        per_image_results.append({
            "image": entry["image_filename"],
            "accuracy": round(accuracy, 1),
            "field_details": field_details
        })

    overall_accuracy = (total_fields_correct / total_fields_checked * 100) if total_fields_checked > 0 else 0

    summary = {
        "overall_field_accuracy_pct": round(overall_accuracy, 1),
        "total_fields_checked": total_fields_checked,
        "total_fields_correct": total_fields_correct,
        "images_tested": len(per_image_results),
        "per_image_results": per_image_results
    }

    with open(os.path.join(RESULTS_DIR, "eval_results.json"), "w") as f:
        json.dump(summary, f, indent=2)

    print("\n" + "=" * 50)
    print(f"OVERALL FIELD-LEVEL ACCURACY: {overall_accuracy:.1f}%")
    print(f"({total_fields_correct}/{total_fields_checked} fields correct across {len(per_image_results)} images)")
    print("=" * 50)
    print(f"\nFull results saved to {RESULTS_DIR}/eval_results.json")


if __name__ == "__main__":
    evaluate()
