"""Small JSON contracts shared by proposals, review, and rendering."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def file_digest(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def number(value, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    return float(value)


def intervals(values, duration: float) -> list[dict]:
    """Validate ordered, non-overlapping source-coordinate intervals."""
    if not isinstance(values, list) or not values or len(values) > 100:
        raise ValueError("Expected 1 to 100 intervals")
    previous_end = 0.0
    clean = []
    for item in values:
        start, end = number(item["start"], "start"), number(item["end"], "end")
        if not (0 <= start < end <= duration) or start < previous_end:
            raise ValueError("Intervals must be ordered, non-overlapping, and inside the source")
        clean.append({"start": start, "end": end})
        previous_end = end
    return clean


def validate_plan(plan: dict) -> None:
    if plan.get("schema_version") != 1 or plan.get("status") != "proposed":
        raise ValueError("Only a version 1 proposed edit can be reviewed")
    duration = number(plan["source_duration_seconds"], "source_duration_seconds")
    if not 0 < duration <= 3600:
        raise ValueError("Source duration must be between 0 and 3600 seconds")
    intervals(plan["keep"], duration)
    if not isinstance(plan.get("source_sha256"), str) or len(plan["source_sha256"]) != 64:
        raise ValueError("Missing source SHA-256")


def validate_review(plan: dict, review: dict) -> None:
    validate_plan(plan)
    if review.get("decision") != "approved" or not str(review.get("reviewer", "")).strip():
        raise ValueError("Export requires an explicit approval and reviewer")
    if review.get("plan_sha256") != digest(plan):
        raise ValueError("Approval is stale: the proposal changed; review it again")
