"""One FFmpeg subprocess boundary, always argument arrays and no shell."""
from __future__ import annotations

import math
import struct
import subprocess
import wave
from pathlib import Path

import imageio_ffmpeg


def run(args: list[str], data: bytes | None = None) -> subprocess.CompletedProcess:
    result = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-nostdin", *args],
                            input=data, capture_output=True, timeout=120, check=False)
    if result.returncode:
        raise RuntimeError("FFmpeg failed: " + result.stderr.decode(errors="replace")[-2000:])
    return result


def version() -> str:
    return run(["-version"]).stdout.decode().splitlines()[0].split(" Copyright")[0]


# Minimal original block lettering for the synthetic cards; no font files.
GLYPHS = {
    "A":"01110/10001/10001/11111/10001/10001/10001", "C":"01111/10000/10000/10000/10000/10000/01111",
    "D":"11110/10001/10001/10001/10001/10001/11110", "E":"11111/10000/10000/11110/10000/10000/11111",
    "G":"01111/10000/10000/10111/10001/10001/01111", "H":"10001/10001/10001/11111/10001/10001/10001",
    "I":"11111/00100/00100/00100/00100/00100/11111", "L":"10000/10000/10000/10000/10000/10000/11111",
    "N":"10001/11001/11001/10101/10011/10011/10001", "O":"01110/10001/10001/10001/10001/10001/01110",
    "P":"11110/10001/10001/11110/10000/10000/10000", "R":"11110/10001/10001/11110/10100/10010/10001",
    "S":"01111/10000/10000/01110/00001/00001/11110", "T":"11111/00100/00100/00100/00100/00100/00100",
    "U":"10001/10001/10001/10001/10001/10001/01110", "V":"10001/10001/10001/10001/10001/01010/00100",
    "W":"10001/10001/10001/10101/10101/10101/01010", "Y":"10001/10001/01010/00100/00100/00100/00100",
    "1":"00100/01100/00100/00100/00100/00100/01110", "2":"01110/10001/00001/00010/00100/01000/11111",
    "3":"11110/00001/00001/01110/00001/00001/11110", " ":"00000/00000/00000/00000/00000/00000/00000"
}
WIDTH, HEIGHT = 480, 270


def frame(time: float) -> bytes:
    buffer = bytearray(bytes((13, 24, 40)) * WIDTH * HEIGHT)

    def box(x, y, width, height, color):
        for row in range(max(0, y), min(HEIGHT, y + height)):
            left, right = max(0, x), min(WIDTH, x + width)
            if right > left:
                buffer[(row * WIDTH + left) * 3:(row * WIDTH + right) * 3] = bytes(color) * (right - left)

    def label(text, x, y, scale, color):
        for index, letter in enumerate(text):
            for row, pattern in enumerate(GLYPHS[letter].split("/")):
                for col, pixel in enumerate(pattern):
                    if pixel == "1":
                        box(x + (index * 6 + col) * scale, y + row * scale, scale, scale, color)

    active = int(time // 2) % 2 == 0
    accent = (64, 214, 164) if active else (233, 165, 87)
    label("EDIT REVIEW", 24, 24, 2, (171, 190, 213))
    label("SIGNAL " + str(int(time // 4) + 1) if active else "PAUSE", 24, 70, 5, accent)
    for index in range(24):
        height = int(18 + abs(math.sin(index * 0.75 + time * 3)) * 37) if active else 3
        box(26 + index * 18, 163 - height // 2, 10, height, accent)
    for index in range(6):
        color = (64, 214, 164) if index % 2 == 0 else (61, 74, 95)
        box(24 + index * 73, 207, 66, 8, color)
    box(24 + min(431, int(time / 12 * 431)), 203, 2, 16, (255, 255, 255))
    label("SYNTHETIC INPUT", 24, 240, 2, (171, 190, 213))
    return bytes(buffer)


def generate_source(directory: Path, fixture: dict) -> None:
    sample_rate, duration = fixture["sample_rate"], fixture["duration_seconds"]
    pcm = bytearray()
    for index in range(int(sample_rate * duration)):
        time = index / sample_rate
        signal = next((span for span in fixture["signal"] if span["start"] <= time < span["end"]), None)
        value = int(7500 * math.sin(2 * math.pi * 440 * time)) if signal else 0
        pcm.extend(struct.pack("<h", value))
    with wave.open(str(directory / "fixture.wav"), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(pcm)
    frames = b"".join(frame(index / fixture["fps"]) for index in range(int(duration * fixture["fps"])))
    run(["-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{WIDTH}x{HEIGHT}",
         "-r", str(fixture["fps"]), "-i", "pipe:0", "-i", str(directory / "fixture.wav"),
         "-c:v", "ffv1", "-c:a", "pcm_s16le", "-map_metadata", "-1", "-threads", "1",
         str(directory / "source.mkv")], frames)
    run(["-v", "error", "-y", "-i", str(directory / "source.mkv"), *encoding(),
         str(directory / "source-preview.mp4")])


def encoding() -> list[str]:
    return ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
            "-r", "12", "-fps_mode", "cfr",
            "-c:a", "aac", "-b:a", "64k", "-map_metadata", "-1", "-threads", "1", "-movflags", "+faststart"]


def detect_silence(source: Path, noise_db: float = -35, minimum: float = 0.6) -> str:
    return run(["-i", str(source), "-af", f"silencedetect=noise={noise_db}dB:d={minimum}",
                "-f", "null", "-"]).stderr.decode(errors="replace")


def render(source: Path, keep: list[dict], destination: Path) -> None:
    filters, labels = [], []
    for index, span in enumerate(keep):
        start, end = span["start"], span["end"]
        filters.extend([f"[0:v]trim=start={start:.6f}:end={end:.6f},setpts=PTS-STARTPTS[v{index}]",
                        f"[0:a]atrim=start={start:.6f}:end={end:.6f},asetpts=PTS-STARTPTS[a{index}]"])
        labels.extend([f"[v{index}]", f"[a{index}]"])
    filters.append("".join(labels) + f"concat=n={len(keep)}:v=1:a=1[v][a]")
    run(["-v", "error", "-y", "-i", str(source), "-filter_complex", ";".join(filters),
         "-map", "[v]", "-map", "[a]", *encoding(), str(destination)])


def inspect_output(path: Path) -> dict:
    frames, duration = imageio_ffmpeg.count_frames_and_secs(str(path))
    # Decode the whole audio track too: a readable container alone is insufficient.
    audio = run(["-v", "error", "-i", str(path), "-vn", "-f", "s16le", "-ac", "1", "-ar", "16000", "pipe:1"])
    return {"decoded_video_frames": frames, "decoded_video_seconds": duration,
            "decoded_audio_samples": len(audio.stdout) // 2, "audio_sample_rate": 16000}
