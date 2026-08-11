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
        with open("temp.pdf", "wb") as f:
            f.write(resp.content)
        doc = pymupdf.open("temp.pdf")
        text = "".join([page.get_text() for page in doc])
        return text
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

    urls = [r.get("link") for r in results.get("organic_results", [])[:3]]

    docs = []
    for url in urls:
        if url.endswith(".pdf"):
            text = fetch_pdf(url)
        else:
            text = fetch_html(url)
        docs.append({"url": url, "text": text})
    return docs

if __name__ == "__main__":
    # Load API keys from project root .env
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))
    api_key = os.getenv("SERPAPI_KEY")
    gemini_key = os.getenv("GEMINI_KEY")

    if not api_key:
        print("❌ No SERPAPI_KEY found in .env")
        exit()
    if not gemini_key:
        print("❌ No GEMINI_KEY found in .env")
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
        docs = enrich(brand, model_number, api_key)
        if not docs:
            print("❌ No results found")
        else:
            # Collect normalized specs from all sources
            all_specs = []
            for d in docs:
                print("-", d["url"])
                structured = extract_specs_from_text(d["text"], "manufacturer", d["url"])
                normalized = normalize_specs(structured)
                all_specs.append({"source_type": "manufacturer", "value": normalized})

            # Resolve conflicts across sources
            resolved = {}
            for field in ["voltage_rating", "current_rating", "dimensions",
                          "materials", "certifications", "operating_conditions",
                          "compatible_products", "weight"]:
                values = []
                for spec in all_specs:
                    val = spec["value"].get(field) if spec["value"] else None
                    if val:
                        values.append({"value": val, "source_type": spec["source_type"]})
                resolved[field] = resolve_conflicts(values)

                # ✅ Add confidence scoring per field
                resolved[field]["confidence"] = calculate_confidence(values)

            # ✅ Add completeness scoring for the product
            completeness, missing = calculate_completeness(resolved)
            resolved["completeness_score"] = completeness
            resolved["missing_fields"] = missing

            print(json.dumps(resolved, indent=2))
