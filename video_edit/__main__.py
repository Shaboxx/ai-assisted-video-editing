"""Run with `python -m video_edit --help`."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from .contracts import digest, file_digest, read_json, validate_plan, validate_review, write_json
from .editing import overlap, parse_silences, tighten
from .ingest import normalize
from . import media
from .report import write_page

ROOT = Path(__file__).resolve().parent.parent


def evaluate(plan: dict, fixture: dict, decoded: dict) -> dict:
    duration = fixture["duration_seconds"]
    signal_seconds = sum(span["end"] - span["start"] for span in fixture["signal"])
    kept_duration = sum(span["end"] - span["start"] for span in plan["keep"])
    signal_retention = overlap(plan["keep"], fixture["signal"]) / signal_seconds
    remaining_silence = overlap(plan["keep"], fixture["silence"])
    return {"evaluation_kind": "synthetic timing integration check; not model quality",
            "fixture_id": fixture["fixture_id"], "source_seconds": duration,
            "baseline": {"policy": "no cuts", "output_seconds": duration,
                         "signal_retention": 1.0, "remaining_silence_seconds": duration - signal_seconds},
            "policy": plan["proposer"], "planned_output_seconds": round(kept_duration, 6),
            "signal_retention": round(signal_retention, 6),
            "remaining_silence_seconds": round(remaining_silence, 6),
            "duration_reduction_fraction": round(1 - kept_duration / duration, 6),
            "decoded_output": decoded,
            "timing_tolerance_seconds": 1 / fixture["fps"],
            "status": "proposed; no approval claimed", "trained_model": "none selected",
            "ffmpeg": media.version(), "imageio_ffmpeg": "0.6.0"}


def propose(directory: Path, suggestions: Path | None = None) -> None:
    fixture = read_json(ROOT / "fixtures" / "timing.json")
    silences = parse_silences(media.detect_silence(directory / "source.mkv"), fixture["duration_seconds"])
    plan = {"schema_version": 1, "status": "proposed", "source_asset_id": "signal-demo",
            "source_sha256": file_digest(directory / "source.mkv"),
            "source_duration_seconds": fixture["duration_seconds"],
            "fixture_sha256": digest(fixture), "proposer": "deterministic-pause-tightening",
            "parameters": {"noise_db": -35, "min_silence_seconds": 0.6, "min_keep_seconds": 0.25},
            "detected_silences": silences,
            "keep": tighten(fixture["duration_seconds"], silences, fixture["word_spans"])}
    if suggestions:
        external = read_json(suggestions)
        if external.get("source_sha256") != plan["source_sha256"]:
            raise ValueError("External proposal must reference the exact source SHA-256")
        plan["keep"] = external["keep"]
        plan["proposer"] = "external-proposal; unverified model or human input"
        plan["parameters"] = {}
    validate_plan(plan)
    media.render(directory / "source.mkv", plan["keep"], directory / "preview.mp4")
    decoded = media.inspect_output(directory / "preview.mp4")
    report = evaluate(plan, fixture, decoded)
    expected_duration = report["planned_output_seconds"]
    if abs(decoded["decoded_video_seconds"] - expected_duration) > 1 / fixture["fps"] + 0.001:
        raise ValueError("Rendered duration differs from the edit plan by more than one frame")
    if decoded["decoded_audio_samples"] == 0:
        raise ValueError("Rendered output has no decoded audio")
    write_json(directory / "proposal.json", plan)
    write_json(directory / "report.json", report)
    write_page(directory, plan, report, read_json(directory / "ingestion.json"))
    print(f"PROPOSED: {fixture['duration_seconds']:.2f}s -> {expected_duration:.2f}s; {len(plan['keep'])} kept intervals")
    print(f"Review {directory / 'review.html'} before approving and exporting.")


def approve(directory: Path, reviewer: str, note: str, fixture_review: bool = False) -> None:
    plan = read_json(directory / "proposal.json")
    validate_plan(plan)
    if not reviewer.strip() or not note.strip():
        raise ValueError("Reviewer and review note must be non-empty")
    if file_digest(directory / "source.mkv") != plan["source_sha256"]:
        raise ValueError("Source media changed; generate and review a new proposal")
    receipt = {"schema_version": 1, "decision": "approved", "reviewer": reviewer.strip(), "note": note.strip(),
               "review_kind": "automated-fixture-approval" if fixture_review else "operator-attestation",
               "plan_sha256": digest(plan), "reviewed_at": datetime.now(timezone.utc).isoformat()}
    write_json(directory / "approval.json", receipt)
    print("Approval recorded for this exact proposal. " + receipt["review_kind"])


def export(directory: Path) -> None:
    plan = read_json(directory / "proposal.json")
    if not (directory / "approval.json").is_file():
        raise ValueError("Final export requires an explicit approval; inspect review.html first")
    review = read_json(directory / "approval.json")
    validate_review(plan, review)
    if file_digest(directory / "source.mkv") != plan["source_sha256"]:
        raise ValueError("Source media changed; approval is no longer valid")
    destination = directory / "edited.mp4"
    media.render(directory / "source.mkv", plan["keep"], destination)
    write_json(directory / "export.json", {"file": destination.name, "sha256": file_digest(destination),
               "plan_sha256": digest(plan), "review_kind": review["review_kind"],
               "decoded_output": media.inspect_output(destination)})
    print(f"EXPORTED: {destination}; review kind: {review['review_kind']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline, review-gated pause-tightening demonstration")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("demo", "propose", "approve", "export"):
        command = commands.add_parser(name)
        command.add_argument("--workdir", type=Path, default=Path("output"))
        if name == "propose":
            command.add_argument("--suggestions", type=Path, help="Optional externally authored JSON proposal; no service is called")
        if name == "approve":
            command.add_argument("--reviewer", required=True)
            command.add_argument("--note", required=True)
            command.add_argument("--fixture-review", action="store_true", help="Label CI/testing approval as automated, not human review")
    args = parser.parse_args()
    try:
        if args.command == "demo":
            args.workdir.mkdir(parents=True, exist_ok=True)
            write_json(args.workdir / "ingestion.json", normalize(read_json(ROOT / "fixtures" / "observations.json")))
            media.generate_source(args.workdir, read_json(ROOT / "fixtures" / "timing.json"))
            propose(args.workdir)
        elif args.command == "propose":
            propose(args.workdir, args.suggestions)
        elif args.command == "approve":
            approve(args.workdir, args.reviewer, args.note, args.fixture_review)
        else:
            export(args.workdir)
    except (ValueError, FileNotFoundError, KeyError, RuntimeError) as error:
        parser.exit(2, f"error: {error}\n")


if __name__ == "__main__":
    main()
