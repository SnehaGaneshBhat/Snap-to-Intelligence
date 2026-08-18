import os
import json
import requests
from bs4 import BeautifulSoup
import pymupdf  # modern import for PyMuPDF
from dotenv import load_dotenv
from serpapi import GoogleSearch

from extract_specs import extract_specs_from_text
from normalize import normalize_specs   # ✅ normalization
from conflict_resolution import resolve_conflicts   # ✅ conflict resolution
from scoring import calculate_confidence, calculate_completeness   # ✅ scoring

EXPECTED_FIELDS = [
    "voltage_rating",
    "current_rating",
    "dimensions",
    "materials",
    "certifications",
    "operating_conditions",
    "compatible_products",
    "weight",
]


def fetch_html(url):
    """Fetch and extract text from an HTML page."""
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        return soup.get_text(" ", strip=True)
    except Exception as e:
        return f"❌ Error fetching HTML: {e}"

def fetch_pdf(url):
    """Fetch and extract text from a PDF file."""
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        doc = pymupdf.open(stream=resp.content, filetype="pdf")
        try:
            return "".join(page.get_text() for page in doc)
        finally:
            doc.close()
    except Exception as e:
        return f"❌ Error fetching PDF: {e}"

def enrich(brand, model_number, api_key):
    """
    Given a brand and model number, return a list of source documents (URLs + text).
    """
    query = f"{brand} {model_number} datasheet"
    params = {"engine": "google", "q": query, "api_key": api_key}
    search = GoogleSearch(params)
    results = search.get_dict()

    urls = [
        result.get("link")
        for result in results.get("organic_results", [])[:3]
        if result.get("link")
    ]

    docs = []
    for url in urls:
        if url.endswith(".pdf"):
            text = fetch_pdf(url)
        else:
            text = fetch_html(url)
        docs.append({"url": url, "text": text})
    return docs


def _profile_confidence(field_confidences):
    if not field_confidences:
        return "unverified"

    average = sum(field_confidences) / len(field_confidences)
    if average >= 0.85:
        return "high"
    if average >= 0.60:
        return "medium"
    return "low"


def enrich_from_extraction(person_a_output, api_key=None):
    """
    Run Person B's live enrichment pipeline for Person A's extracted identity.

    Returns the enrichment_output shape consumed by build_full_profile().
    """
    brand = person_a_output.get("brand")
    model_number = person_a_output.get("model_number")

    if not brand or not model_number:
        return {
            "specs": {},
            "confidence": "unverified",
            "completeness_score": 0,
            "missing_fields": list(EXPECTED_FIELDS),
            "conflicting_values": [],
        }

    api_key = api_key or os.getenv("SERPAPI_KEY")
    if not api_key:
        raise RuntimeError("SERPAPI_KEY is required for live enrichment")

    docs = enrich(brand, model_number, api_key)

    # This is the same normalize/resolve/score loop previously trapped in
    # __main__, now returning data instead of only printing it.
    all_specs = []
    for doc in docs:
        structured = extract_specs_from_text(
            doc["text"], "manufacturer", doc["url"]
        )
        normalized = normalize_specs(structured)
        all_specs.append(
            {
                "source_type": "manufacturer",
                "source_reference": doc["url"],
                "value": normalized,
            }
        )

    resolved = {}
    specs = {}
    conflicts = []
    field_confidences = []

    for field in EXPECTED_FIELDS:
        values = []
        for spec in all_specs:
            value = spec["value"].get(field) if spec["value"] else None
            if value:
                values.append(
                    {
                        "value": value,
                        "source_type": spec["source_type"],
                        "source_reference": spec["source_reference"],
                    }
                )

        field_result = resolve_conflicts(values)
        field_result["confidence"] = calculate_confidence(values)
        resolved[field] = field_result

        final_value = field_result["final_value"]
        if not final_value:
            continue

        primary = next(value for value in values if value["value"] == final_value)
        conflicting_values = [
            {
                "value": value["value"],
                "source_type": value["source_type"],
                "source_reference": value["source_reference"],
            }
            for value in values
            if value["value"] != final_value
        ]

        specs[field] = {
            "final_value": final_value,
            "source_type": primary["source_type"],
            "source_reference": primary["source_reference"],
            "confidence": field_result["confidence"],
            "conflicting_values": conflicting_values,
        }
        field_confidences.append(field_result["confidence"])

        if conflicting_values:
            conflicts.append({"field": field, "values": conflicting_values})

    completeness, missing = calculate_completeness(resolved)

    return {
        "specs": specs,
        "confidence": _profile_confidence(field_confidences),
        "completeness_score": completeness,
        "missing_fields": missing,
        "conflicting_values": conflicts,
    }

if __name__ == "__main__":
    # Load API keys from project root .env
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))
    api_key = os.getenv("SERPAPI_KEY")

    if not api_key:
        print("❌ No SERPAPI_KEY found in .env")
        exit()

    # Load product entries
    json_path = os.path.join("shared", "mocks", "mock_products.json")
    with open(json_path, "r") as f:
        data = json.load(f)

    entries = data["entries"]

    # Loop through all products
    for entry in entries:
        brand = entry["brand"]
        model_number = entry["model_number"]
        print(f"\n🔎 {entry['image_filename']} → {brand} {model_number} datasheet")
        result = enrich_from_extraction(entry, api_key=api_key)
        print(json.dumps(result, indent=2))
