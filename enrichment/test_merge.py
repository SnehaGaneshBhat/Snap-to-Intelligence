from merge import build_full_profile

# Mock Person A output (extraction JSON)
person_a_output = {
    "image_filename": "test_img_1.png",
    "brand": "Siemens",
    "model_number": "ABC123",
    "serial_number": "SN98765"
}

# Mock Person B enrichment output
enrichment_output = {
    "specs": {
        "voltage": "220V",
        "current": "5A",
        "dimensions": "120x80x60 mm"
    },
    "confidence": "high",
    "completeness_score": 85,
    "missing_fields": ["weight"],
    "conflicting_values": [
        {"field": "voltage", "values": ["220V (manufacturer)", "230V (distributor)"]}
    ]
}

# Run merge
merged = build_full_profile(person_a_output, enrichment_output)
print(merged)
