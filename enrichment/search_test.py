import os
import json
from dotenv import load_dotenv
from serpapi import GoogleSearch

def run_search(query, api_key):
    params = {
        "engine": "google",
        "q": query,
        "api_key": api_key
    }
    search = GoogleSearch(params)
    results = search.get_dict()
    return results.get("organic_results", [])[:3]  # top 3 results

def main():
    # Load keys from .env
    load_dotenv()
    api_key = os.getenv("SERPAPI_KEY")

    if not api_key:
        print("❌ No SERPAPI_KEY found in .env")
        return

    # Load product entries
    json_path = os.path.join("shared", "mocks", "mock_products.json")
    with open(json_path, "r") as f:
        data = json.load(f)

    entries = data["entries"]

    # Loop through all products
    for entry in entries:
        query = f"{entry['brand']} {entry['model_number']} datasheet"
        print(f"\n🔎 {entry['image_filename']} → {entry['brand']} {entry['model_number']} datasheet")
        results = run_search(query, api_key)
        if not results:
            print("❌ No results found")
        else:
            for r in results:
                print("-", r.get("link"))

if __name__ == "__main__":
    main()
