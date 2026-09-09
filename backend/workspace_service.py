"""Serializers and pipeline-to-database mapping for the workspace API."""
from datetime import datetime, timezone

from sqlalchemy import select

import adapters
from database import SessionLocal
from workspace_models import ActivityLog, Field, Item


def iso(value):
    return value.isoformat() if value else None


def field_data(field: Field) -> dict:
    return {"id": field.id, "item_id": field.item_id, "field_name": field.field_name, "value": field.value,
            "unit": field.unit, "confidence": field.confidence, "source_type": field.source_type,
            "source_reference": field.source_reference, "conflicting_values": field.conflicting_values or [],
            "is_user_verified": field.is_user_verified}


def item_data(item: Item, include_fields=False) -> dict:
    data = {"id": item.id, "workspace_id": item.workspace_id, "name": item.name, "image_urls": item.image_urls or [],
            "completeness_score": item.completeness_score, "status": item.status,
            "created_at": iso(item.created_at), "updated_at": iso(item.updated_at)}
    if include_fields:
        data["fields"] = [field_data(field) for field in sorted(item.fields, key=lambda f: f.confidence)]
    return data


def activity_data(log: ActivityLog) -> dict:
    return {"id": log.id, "item_id": log.item_id, "workspace_id": log.workspace_id, "actor": log.actor,
            "action": log.action, "field_name": log.field_name, "old_value": log.old_value,
            "new_value": log.new_value, "timestamp": iso(log.timestamp)}


def source_type(raw: str | None) -> str:
    mapping = {"label": "vision_extraction", "manufacturer_site": "manufacturer_site", "datasheet_pdf": "datasheet_pdf",
               "distributor": "distributor", "generic_web": "generic_web"}
    return mapping.get(raw or "", "vision_extraction")


def update_item_status(item: Item) -> None:
    fields = item.fields
    item.completeness_score = round((len(fields) / 17) * 100) if fields else 0
    item.status = "needs_review" if any(field.confidence < .7 or field.conflicting_values for field in fields) else "ready"
    item.updated_at = datetime.now(timezone.utc)


def run_item_pipeline(item_id: int, image_path: str) -> None:
    """Runs after the upload response; each task creates its own DB session."""
    db = SessionLocal()
    try:
        item = db.get(Item, item_id)
        if item is None:
            return
        extraction = adapters.run_extraction(image_path)
        enriched = adapters.run_enrichment(extraction) if extraction.get("extracted_fields") else None
        raw_fields = list(extraction.get("extracted_fields") or [])
        if enriched:
            if enriched.get("fields"):
                raw_fields.extend(enriched["fields"])
            elif isinstance(enriched.get("specs"), dict):
                for name, value in enriched["specs"].items():
                    if value not in (None, ""):
                        raw_fields.append({"field_name": name, "value": value, "source_type": "generic_web", "confidence": .6})
        for raw in raw_fields:
            name = raw.get("field_name")
            if not name or raw.get("value") in (None, ""):
                continue
            db.add(Field(item_id=item.id, field_name=str(name), value=str(raw["value"]), unit=raw.get("unit"),
                         confidence=max(0, min(1, float(raw.get("confidence", .5)))),
                         source_type=source_type(raw.get("source_type")), source_reference=raw.get("source_reference"),
                         conflicting_values=raw.get("conflicting_values") or []))
        db.flush()
        db.refresh(item)
        update_item_status(item)
        db.commit()
    except Exception:
        # A failed external pipeline leaves a visible item for retry/diagnosis instead of crashing the API server.
        item = db.get(Item, item_id)
        if item:
            item.status = "needs_review"
            item.updated_at = datetime.now(timezone.utc)
            db.commit()
    finally:
        db.close()
