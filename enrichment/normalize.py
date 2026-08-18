import re

def normalize_voltage(value):
    if not value: return None
    val = value.upper().replace("VAC", "V AC").replace("VDC", "V DC")
    val = re.sub(r"(\d+)\s*V", r"\1 V", val)
    return val.strip()

def normalize_current(value):
    if not value: return None
    val = value.upper().replace("MA", " mA").replace("A", " A")
    val = re.sub(r"(\d+)\s*A", r"\1 A", val)
    return val.strip()

def normalize_dimensions(value):
    if not value: return None
    val = value.lower().replace("mm", " mm").replace("cm", " cm").replace("in", " in")
    val = re.sub(r"\s*x\s*", " x ", val)
    return val.strip().title()

def normalize_temperature(value):
    if not value: return None
    val = value.replace("°c", "°C").replace("°f", "°F")
    return val.strip()

def normalize_ip(value):
    if not value: return None
    val = value.upper()
    if not val.startswith("IP"):
        val = "IP" + val
    return val.strip()

def normalize_certification(value):
    if not value: return None
    val = value.upper().strip()
    if re.fullmatch(r"IP\d{2}", val):
        return normalize_ip(val)
    return val

def normalize_operating_conditions(value):
    if not value: return None
    val = value.upper().replace("HZ", " Hz").replace("KW", " kW").replace("W", " W")
    return val.strip()

def normalize_weight(value):
    if not value: return None
    val = value.lower().replace("kg", " kg").replace("lbs", " lbs")
    return val.strip()

def normalize_specs(specs):
    """Normalize all fields in a specs dict."""
    return {
        "voltage_rating": normalize_voltage(specs.get("voltage_rating", {}).get("value")) if specs.get("voltage_rating") else None,
        "current_rating": normalize_current(specs.get("current_rating", {}).get("value")) if specs.get("current_rating") else None,
        "dimensions": normalize_dimensions(specs.get("dimensions", {}).get("value")) if specs.get("dimensions") else None,
        "materials": specs.get("materials", {}).get("value") if specs.get("materials") else None,
        "certifications": normalize_certification(specs.get("certifications", {}).get("value")) if specs.get("certifications") else None,
        "operating_conditions": normalize_operating_conditions(specs.get("operating_conditions", {}).get("value")) if specs.get("operating_conditions") else None,
        "compatible_products": specs.get("compatible_products", {}).get("value") if specs.get("compatible_products") else None,
        "weight": normalize_weight(specs.get("weight", {}).get("value")) if specs.get("weight") else None,
    }
