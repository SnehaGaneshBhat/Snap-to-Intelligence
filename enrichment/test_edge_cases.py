from merge import build_full_profile

# --- Case 1: No web results ---
person_a_output_no_results = {
    "image_filename": "test_img_2.png",
    "brand": "UnknownBrand",
    "model_number": "XYZ999",
    "serial_number": None
}

enrichment_output_no_results = {
    "specs": {},
    "confidence": "unverified",
    "completeness_score": 0,
    "missing_fields": ["voltage", "current"],
    "conflicting_values": []
}

print("Case 1: No web results")
print(build_full_profile(person_a_output_no_results, enrichment_output_no_results))
print("\n")

# --- Case 2: Conflicting sources ---
person_a_output_conflict = {
    "image_filename": "test_img_3.png",
    "brand": "Siemens",
    "model_number": "ABC123",
    "serial_number": "SN12345"
}

enrichment_output_conflict = {
    "specs": {"voltage": "220V"},
    "confidence": "medium",
    "completeness_score": 70,
    "missing_fields": [],
    "conflicting_values": [
        {"field": "voltage", "values": ["220V (manufacturer)", "230V (distributor)"]}
    ]
}

print("Case 2: Conflicting sources")
print(build_full_profile(person_a_output_conflict, enrichment_output_conflict))
