# Data and review contracts

All times are seconds in the unmodified source. The demo accepts one local source and does not fetch remote media. JSON files use UTF-8; numeric timestamps must be finite.

## Metadata observations

Each row carries `namespace`, immutable `native_id`, and `provider`; `title` and `duration_seconds` are optional. Namespace is Unicode-normalized, whitespace-normalized, and case-folded. Native IDs retain case. Duration must be positive.

Asset identity hashes `(namespace, native_id)`. Observation identity hashes normalized field values plus provider. Replaying observations preserves the asset and observation list. A field's first nonempty value wins in input order, and `field_sources` records its provider. A differing later value produces a conflict receipt. This is deterministic precedence, not a claim that the first source is correct. Unknown fields are omitted from the released contract.

[`observations.json`](../fixtures/observations.json) deliberately contains five observations: an initial manifest, a duration observation, an exact duplicate, a conflicting title, and an invalid negative duration. The providers are fixture labels, not live external services.

## Proposal

`proposal.json` includes schema version 1, `status: proposed`, `source_sha256`, duration, proposer label, detector parameters, and `keep`. Kept intervals must be ordered, non-overlapping, inside the source, and nonempty. At most 100 intervals are accepted. The demonstration caps declared duration at one hour; it is not a general media ingestion tool.

The deterministic proposer stores detected pauses as well as kept ranges. Its synthetic word annotations validate boundary guards without claiming speech recognition. No selection probability or quality score is invented.

## External proposal input

After `python -m video_edit demo`, copy `source_sha256` from `output/proposal.json` into a JSON file containing:

```json
{
  "source_sha256": "<copy the exact source_sha256 from output/proposal.json>",
  "keep": [{"start": 0.0, "end": 2.0}, {"start": 4.0, "end": 6.0}]
}
```

Then run:

```bash
python -m video_edit propose --suggestions suggestion.json
```

The source hash must match. The renderer still checks interval validity, decodes the preview, and requires explicit review before export. The input can come from a person or a separate model experiment. This release supplies neither a model client nor a selected model, and labels the provenance as unverified external input. Imported suggestions can change content; no word guard is promised for them.

## Approval and export

`approval.json` stores the decision, reviewer, note, UTC review time, and a SHA-256 over canonical proposal JSON. `--fixture-review` records `automated-fixture-approval`; normal use records `operator-attestation`. These are local files, not an authenticated multiuser audit log.

Final export checks the approval hash and current source bytes before running FFmpeg. An edited proposal or modified source requires new review. `export.json` stores the output checksum, proposal checksum, review kind, and decoded media counts. Source media is never overwritten.

## Evaluation metrics

Signal retention is the total intersection of kept ranges with annotated signal ranges, divided by total annotated signal duration. Remaining silence is the intersection with annotated silence ranges. Planned output duration is the sum of kept ranges. The no-cut baseline retains the entire source. These are timing metrics on known fixtures, not a benchmark of semantic editing quality.
