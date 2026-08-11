def resolve_conflicts(values):
    """
    Resolve conflicts between multiple source values.
    Authority ranking:
    manufacturer > datasheet PDF > distributor/catalog > generic web
    Returns: dict with final_value and conflicting_values[]
    """
    if not values:
        return {"final_value": None, "conflicting_values": []}

    # Authority ranking
    authority_order = {
        "manufacturer": 4,
        "datasheet": 3,
        "distributor": 2,
        "generic": 1
    }

    # Sort values by authority
    sorted_values = sorted(values, key=lambda v: authority_order.get(v["source_type"], 0), reverse=True)

    final_value = sorted_values[0]["value"]
    conflicting_values = [v["value"] for v in sorted_values[1:] if v["value"] != final_value]

    return {
        "final_value": final_value,
        "conflicting_values": conflicting_values
    }
