import os
import re
import json
import requests
from bs4 import BeautifulSoup
import pymupdf  # modern import for PyMuPDF

def wrap_with_metadata(value, source_type, source_reference):
    if value:
        clean_val = (
            value.strip()
            .upper()
            .replace("VDC", "V DC")
            .replace("VAC", "V AC")
            .replace("HZ", "Hz")
        )
        return {
            "value": clean_val,
            "source_type": source_type,
            "source_reference": source_reference
        }
    return None

def fetch_html(url):
    """Fetch and extract text from HTML page, focusing on spec sections."""
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        specs_text = []

        for table in soup.find_all("table"):
            specs_text.append(table.get_text(" ", strip=True))
        for ul in soup.find_all("ul"):
            specs_text.append(ul.get_text(" ", strip=True))
        for div in soup.find_all("div", class_=["product-specs", "specifications", "details"]):
            specs_text.append(div.get_text(" ", strip=True))

        if not specs_text:
            return soup.get_text(" ", strip=True)

        return "\n".join(specs_text)
    except Exception as e:
        return f"❌ Error fetching HTML: {e}"

def fetch_pdf(url):
    """Fetch and extract text from PDF datasheet using PyMuPDF."""
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        with open("temp.pdf", "wb") as f:
            f.write(resp.content)

        doc = pymupdf.open("temp.pdf")
        text = []
        for page in doc:
            text.append(page.get_text())
        doc.close()
        os.remove("temp.pdf")
        return "\n".join(text)
    except Exception as e:
        return f"❌ Error fetching PDF: {e}"

def extract_specs_from_text(raw_text, source_type, source_reference):
    voltage = None
    current = None
    dimensions = None
    materials = None
    certifications = None
    operating_conditions = None
    compatible_products = None

    # Voltage
    v_match = re.search(r"(\d{2,3}(?:/\d{2,3})?\s*V(?:\s*(?:AC|DC))?)", raw_text, re.IGNORECASE)
    if v_match:
        voltage = v_match.group(1)

    # Current
    c_match = re.search(r"(\d{1,3}\s*(?:A|mA))", raw_text, re.IGNORECASE)
    if c_match:
        val = c_match.group(1)
        if not val.startswith("0"):
            current = val

    # Dimensions
    d_match = re.search(r"(\d+\s*x\s*\d+(?:\s*x\s*\d+)?\s*(mm|cm|in))", raw_text, re.IGNORECASE)
    if d_match:
        dimensions = d_match.group(1)

    # Materials
    if "copper" in raw_text.lower():
        materials = "Copper"
    elif "plastic" in raw_text.lower():
        materials = "Plastic"

    # Certifications
    if "UL" in raw_text:
        certifications = "UL"
    elif "CE" in raw_text:
        certifications = "CE"
    ip_match = re.search(r"(IP\d{2})", raw_text)
    if ip_match:
        certifications = ip_match.group(1)

    # Operating conditions
    temp_match = re.search(r"(-?\d+\s*°C\s*to\s*-?\d+\s*°C)", raw_text)
    if temp_match:
        operating_conditions = temp_match.group(1)

    freq_match = re.search(r"(\d{2,3}\s*/\s*\d{2,3}\s*Hz|\d{2,3}\s*Hz)", raw_text, re.IGNORECASE)
    if freq_match:
        operating_conditions = freq_match.group(1)

    power_match = re.search(r"(\d+\s*(?:W|kW))", raw_text, re.IGNORECASE)
    if power_match:
        operating_conditions = power_match.group(1)

    ka_match = re.search(r"(\d+\s*kA)", raw_text, re.IGNORECASE)
    if ka_match:
        operating_conditions = ka_match.group(1)

    # Compatible products
    comp_match = re.search(r"compatible with ([\w\s-]+)", raw_text.lower())
    if comp_match:
        compatible_products = comp_match.group(1)

    specs = {
        "voltage_rating": wrap_with_metadata(voltage, source_type, source_reference),
        "current_rating": wrap_with_metadata(current, source_type, source_reference),
        "dimensions": wrap_with_metadata(dimensions, source_type, source_reference),
        "materials": wrap_with_metadata(materials, source_type, source_reference),
        "certifications": wrap_with_metadata(certifications, source_type, source_reference),
        "operating_conditions": wrap_with_metadata(operating_conditions, source_type, source_reference),
        "compatible_products": wrap_with_metadata(compatible_products, source_type, source_reference),
    }
    return specs

def extract_from_url(url, source_type="manufacturer"):
    """Prefer PDF datasheets over HTML pages."""
    if url.lower().endswith(".pdf"):
        text = fetch_pdf(url)
    else:
        text = fetch_html(url)
    return extract_specs_from_text(text, source_type, url)

def merge_specs(spec_list):
    """
    Merge specs from multiple sources for the same product.
    Prefer the most detailed (e.g. 230/400 V over 400 V).
    """
    merged = {}
    for spec in spec_list:
        for key, val in spec.items():
            if val and (key not in merged or len(val["value"]) > len(merged[key]["value"])):
                merged[key] = val
    return merged
