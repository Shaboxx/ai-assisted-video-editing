import copy
import tempfile
import unittest
from pathlib import Path

from video_edit import media
from video_edit.__main__ import ROOT, approve, export, propose
from video_edit.contracts import digest, file_digest, intervals, read_json, validate_review, write_json
from video_edit.editing import parse_silences, tighten
from video_edit.ingest import normalize


class TimingTests(unittest.TestCase):
    def test_word_boundary_guard(self):
        result = tighten(6, [{"start": 1, "end": 4}],
                         [{"start": 0.8, "end": 1.3}, {"start": 3.7, "end": 4.2}])
        self.assertEqual(result, [{"start": 0, "end": 1.3}, {"start": 3.7, "end": 6}])

    def test_collapsed_removal_is_skipped(self):
        self.assertEqual(tighten(3, [{"start": 1, "end": 2}],
                                 [{"start": 0.8, "end": 1.9}]), [{"start": 0, "end": 3}])

    def test_union_removals(self):
        self.assertEqual(tighten(6, [{"start": 2, "end": 4}, {"start": 1, "end": 3}], []),
                         [{"start": 0, "end": 1}, {"start": 4, "end": 6}])

    def test_sliver_dropped_without_restoring_silence(self):
        result = tighten(5, [{"start": 1, "end": 2}, {"start": 2.1, "end": 3}], [])
        self.assertEqual(result, [{"start": 0, "end": 1}, {"start": 3, "end": 5}])

    def test_short_silence_is_kept(self):
        self.assertEqual(tighten(2, [{"start": 0.5, "end": 0.8}], []), [{"start": 0, "end": 2}])

    def test_all_silence_yields_no_exportable_plan(self):
        keep = tighten(3, [{"start": 0, "end": 3}], [])
        self.assertEqual(keep, [])
        with self.assertRaises(ValueError):
            intervals(keep, 3)

    def test_trailing_silence_parser(self):
        self.assertEqual(parse_silences("silence_start: 1\nsilence_end: 2\nsilence_start: 4", 5),
                         [{"start": 1, "end": 2}, {"start": 4, "end": 5}])

    def test_nonfinite_and_negative_thresholds_rejected(self):
        for value in (float("nan"), float("inf"), -1, True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                tighten(3, [], [], min_silence=value)

    def test_unordered_or_overlapping_intervals_rejected(self):
        for spans in ([{"start": 2, "end": 3}, {"start": 1, "end": 2}],
                      [{"start": 1, "end": 3}, {"start": 2, "end": 4}]):
            with self.assertRaises(ValueError):
                intervals(spans, 5)

    def test_outside_bounds_rejected(self):
        with self.assertRaises(ValueError):
            intervals([{"start": 0, "end": 9}], 5)


class IngestTests(unittest.TestCase):
    def test_fixture_counts_and_field_lineage(self):
        report = normalize(read_json(ROOT / "fixtures" / "observations.json"))
        self.assertEqual((report["input_rows"], report["unique_assets"], report["duplicate_observations"],
                          report["merged_observations"], len(report["rejected_rows"])), (5, 1, 1, 2, 1))
        asset = report["records"][0]
        self.assertEqual(asset["field_sources"], {"title": "manifest", "duration_seconds": "probe"})
        self.assertEqual(len(asset["conflicts"]), 1)
        self.assertEqual(len(asset["observations"]), 3)

    def test_replaying_observations_does_not_duplicate_assets(self):
        rows = read_json(ROOT / "fixtures" / "observations.json")
        self.assertEqual(normalize(rows)["records"], normalize(rows + rows)["records"])

    def test_identity_is_namespace_and_native_id(self):
        row = {"namespace": "local", "native_id": "x", "provider": "test", "title": ""}
        self.assertEqual(normalize([row, {**row, "namespace": "other"}])["unique_assets"], 2)

    def test_missing_identity_and_invalid_numbers_rejected(self):
        row = {"namespace": "local", "native_id": "x", "provider": "test", "duration_seconds": True}
        self.assertEqual(len(normalize([{}, row])["rejected_rows"]), 2)


class MediaIntegrationTests(unittest.TestCase):
    def test_real_media_review_and_stale_approval(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            fixture = read_json(ROOT / "fixtures" / "timing.json")
            write_json(directory / "ingestion.json", normalize(read_json(ROOT / "fixtures" / "observations.json")))
            media.generate_source(directory, fixture)
            before = file_digest(directory / "source.mkv")
            propose(directory)
            report = read_json(directory / "report.json")
            self.assertEqual(report["decoded_output"]["decoded_video_frames"], 72)
            self.assertAlmostEqual(report["decoded_output"]["decoded_video_seconds"], 6, places=2)
            self.assertGreater(report["signal_retention"], 0.999)
            self.assertLess(report["remaining_silence_seconds"], 0.001)
            with self.assertRaisesRegex(ValueError, "approval"):
                export(directory)
            approve(directory, "CI fixture", "Automated wiring check, not human review", fixture_review=True)
            export(directory)
            self.assertTrue((directory / "edited.mp4").is_file())
            self.assertEqual(before, file_digest(directory / "source.mkv"))
            self.assertEqual(read_json(directory / "export.json")["review_kind"], "automated-fixture-approval")
            plan = read_json(directory / "proposal.json")
            changed = copy.deepcopy(plan)
            changed["keep"][0]["end"] -= 0.25
            with self.assertRaisesRegex(ValueError, "stale"):
                validate_review(changed, read_json(directory / "approval.json"))
            with (directory / "source.mkv").open("ab") as handle:
                handle.write(b"changed")
            with self.assertRaisesRegex(ValueError, "Source media changed"):
                export(directory)

    def test_optional_proposal_requires_matching_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            fixture = read_json(ROOT / "fixtures" / "timing.json")
            media.generate_source(directory, fixture)
            suggestions = directory / "external.json"
            write_json(suggestions, {"source_sha256": "0" * 64, "keep": [{"start": 0, "end": 1}]})
            with self.assertRaisesRegex(ValueError, "exact source"):
                propose(directory, suggestions)


if __name__ == "__main__":
    unittest.main()
