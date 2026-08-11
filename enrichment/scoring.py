def calculate_confidence(values):
    """
    Calculate confidence score for a field based on source authority and agreement.
    values: list of dicts like {"value": "10 A", "source_type": "manufacturer"}
    """
    if not values:
        return 0.0

    # Authority weighting
    authority_order = {
        "manufacturer": 0.9,
        "datasheet": 0.8,
        "distributor": 0.6,
        "generic": 0.4
    }

    # Highest authority confidence
    base_conf = max([authority_order.get(v["source_type"], 0.3) for v in values])

    # Agreement boost: if 2+ sources agree on the same value
    unique_vals = set([v["value"] for v in values])
    if len(unique_vals) == 1 and len(values) > 1:
        base_conf += 0.1

    return round(min(base_conf, 1.0), 2)


def calculate_completeness(resolved_specs):
    """
    Calculate completeness score and missing fields list for a product.
    resolved_specs: dict of fields with final_value + confidence
    """
    expected_fields = [
        "voltage_rating", "current_rating", "dimensions",
        "materials", "certifications", "operating_conditions",
        "compatible_products", "weight"
    ]

    filled = [f for f in expected_fields if resolved_specs[f]["final_value"]]
    missing = [f for f in expected_fields if not resolved_specs[f]["final_value"]]

    completeness = (len(filled) / len(expected_fields)) * 100

    # Weight by average confidence
    confidences = [resolved_specs[f].get("confidence", 0) for f in expected_fields]
    avg_conf = sum(confidences) / len(expected_fields) if confidences else 0
    completeness = round(completeness * (0.8 + 0.2 * avg_conf), 2)

    return completeness, missing
