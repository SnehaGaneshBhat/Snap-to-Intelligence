def build_full_profile(person_a_output, enrichment_output):
    """
    Merge Person A's extracted fields with Person B's enrichment output
    into one schema-compliant JSON.
    """
    return {
        "image_filename": person_a_output.get("image_filename"),
        "brand": person_a_output.get("brand"),
        "model_number": person_a_output.get("model_number"),
        "serial_number": person_a_output.get("serial_number"),
        "specs": enrichment_output.get("specs", {}),
        "confidence": enrichment_output.get("confidence", "unverified"),
        "completeness_score": enrichment_output.get("completeness_score", 0),
        "missing_fields": enrichment_output.get("missing_fields", []),
        "conflicting_values": enrichment_output.get("conflicting_values", [])
    }
