"""Pause-tightening interval math, independent of media and UI."""
from __future__ import annotations

import re

from .contracts import intervals, number


def parse_silences(stderr: str, duration: float) -> list[dict]:
    """Read FFmpeg's paired silence events; close terminal silence at EOF."""
    found, start = [], None
    for match in re.finditer(r"silence_(start|end):\s*(-?\d+(?:\.\d+)?)", stderr):
        time = max(0.0, min(float(match[2]), duration))
        if match[1] == "start":
            start = time
        elif start is not None:
            if time > start:
                found.append({"start": start, "end": time})
            start = None
    if start is not None and start < duration:
        found.append({"start": start, "end": duration})
    return found


def tighten(duration: float, silences: list[dict], words: list[dict],
            min_silence: float = 0.6, min_keep: float = 0.25) -> list[dict]:
    """Remove long pauses without placing either cut edge inside a word.

    Shrink removal boundaries to word gaps, union overlapping removals, and
    drop short kept slivers. Never bridge a removed pause to merge a sliver.
    """
    duration = number(duration, "duration")
    min_silence, min_keep = number(min_silence, "min_silence"), number(min_keep, "min_keep")
    if duration <= 0 or min_silence <= 0 or min_keep <= 0:
        raise ValueError("Duration and thresholds must be positive")
    if words:
        intervals(words, duration)
    removals = []
    for pause in silences:
        start = max(0.0, number(pause["start"], "silence start"))
        end = min(duration, number(pause["end"], "silence end"))
        if end - start < min_silence:
            continue
        for word in words:
            if word["start"] < start < word["end"]:
                start = word["end"]
            if word["start"] < end < word["end"]:
                end = word["start"]
        if end - start >= min_silence / 2:
            removals.append({"start": start, "end": end})
    cursor, kept = 0.0, []
    for removal in sorted(removals, key=lambda span: span["start"]):
        if removal["start"] > cursor:
            kept.append({"start": cursor, "end": removal["start"]})
        cursor = max(cursor, removal["end"])
    if cursor < duration:
        kept.append({"start": cursor, "end": duration})
    return [span for span in kept if span["end"] - span["start"] >= min_keep]


def overlap(a: list[dict], b: list[dict]) -> float:
    return sum(max(0.0, min(x["end"], y["end"]) - max(x["start"], y["start"]))
               for x in a for y in b)
