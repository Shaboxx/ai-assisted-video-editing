"""Normalize observations, deduplicate natural keys, and retain field lineage."""
from __future__ import annotations

import hashlib
import unicodedata

from .contracts import digest, number


def text(value) -> str:
    if not isinstance(value, str):
        raise ValueError("Expected a string")
    return " ".join(unicodedata.normalize("NFKC", value).split())


def normalize(rows: list[dict]) -> dict:
    records, rejected, observations = {}, [], set()
    repeated_observations = 0
    for index, row in enumerate(rows):
        try:
            namespace = text(row["namespace"]).casefold()
            native_id, provider = text(row["native_id"]), text(row["provider"])
            if not namespace or not native_id or not provider:
                raise ValueError("Identity and provider cannot be empty")
            title = text(row.get("title", ""))
            duration = row.get("duration_seconds")
            if duration is not None:
                duration = number(duration, "duration_seconds")
                if duration <= 0:
                    raise ValueError("Duration must be positive")
            clean = {"namespace": namespace, "native_id": native_id, "provider": provider,
                     "title": title, "duration_seconds": duration}
            observation_id = digest(clean)
            if observation_id in observations:
                repeated_observations += 1
                continue
            observations.add(observation_id)
            key = (namespace, native_id)
            record = records.setdefault(key, {
                "asset_id": hashlib.sha256(f"{namespace}\0{native_id}".encode()).hexdigest()[:24],
                "namespace": namespace, "native_id": native_id,
                "title": "", "duration_seconds": None,
                "field_sources": {}, "observations": [], "conflicts": []})
            record["observations"].append({"observation_sha256": observation_id, "provider": provider})
            for field in ("title", "duration_seconds"):
                value = clean[field]
                if value is None or value == "":
                    continue
                if record[field] is None or record[field] == "":
                    record[field] = value
                    record["field_sources"][field] = provider
                elif record[field] != value:
                    record["conflicts"].append({"field": field, "kept": record[field],
                                                "observed": value, "provider": provider})
        except (ValueError, KeyError, TypeError) as error:
            # Reject receipts identify the input row, without echoing an arbitrary payload.
            rejected.append({"row": index + 1, "reason": str(error)})
    result = sorted(records.values(), key=lambda record: record["asset_id"])
    return {"input_rows": len(rows), "unique_assets": len(result),
            "duplicate_observations": repeated_observations,
            "merged_observations": len(observations) - len(result),
            "rejected_rows": rejected, "records": result}
