"""Stream from an audio source for N seconds and print stats.

    python -m backend.audio.demo [--source laptop|file|wearable] [--file PATH] [--seconds 5]
    python -m backend.audio.demo --make-test-wav PATH
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import math
import sys
import time
import wave

import numpy as np

from .base import SAMPLE_RATE, rms_dbfs
from .factory import open_audio_source


def make_test_wav(path: str, seconds: float = 3.0, freq: float = 440.0) -> None:
    n = int(SAMPLE_RATE * seconds)
    t = np.arange(n) / SAMPLE_RATE
    tone = (0.5 * np.sin(2 * math.pi * freq * t) * 32767).astype("<i2")
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(tone.tobytes())


def _fmt_db(db: float) -> str:
    return "-inf" if db == float("-inf") else f"{db:6.1f}"


async def run(source: str | None, file: str | None, seconds: float) -> int:
    kwargs = {}
    if file:
        kwargs["path"] = file
    src = await open_audio_source(source, **kwargs)
    label = src.source_label
    print(f"source_label : {label}")
    if source == "wearable" and label != "wearable":
        print("NOTE         : wearable requested but unavailable -> audio is NOT the wearable "
              f"(using {label})")
    elif label != "wearable":
        print(f"NOTE         : audio is NOT the wearable ({label})")
    print(f"format       : {src.sample_rate} Hz, {src.channels} ch, {src.encoding}, "
          f"{src.frame_ms} ms frames")

    frames = 0
    nbytes = 0
    sq_sum = 0.0
    samples = 0
    win_sq = 0.0
    win_n = 0
    t_start = time.monotonic()
    t_first = None
    t_last = None
    next_print = t_start + 0.5
    deadline = t_start + seconds

    async def consume():
        nonlocal frames, nbytes, sq_sum, samples, win_sq, win_n, next_print, t_first, t_last
        async for frame in src:
            if t_first is None:
                t_first = time.monotonic()
            frames += 1
            nbytes += len(frame.data)
            a = np.frombuffer(frame.data, dtype="<i2").astype(np.float64)
            s = float(np.sum(a * a))
            sq_sum += s
            samples += a.size
            win_sq += s
            win_n += a.size
            now = time.monotonic()
            t_last = now
            if now >= next_print:
                db = 20 * math.log10(math.sqrt(win_sq / win_n) / 32768) if win_sq > 0 else float("-inf")
                print(f"  t={now - t_start:5.2f}s frames={frames:5d} rms={_fmt_db(db)} dBFS")
                win_sq, win_n = 0.0, 0
                next_print += 0.5
            if now >= deadline:
                break

    try:
        await asyncio.wait_for(consume(), timeout=seconds + 5)
    except asyncio.TimeoutError:
        print("WARNING: timed out waiting for frames", file=sys.stderr)
    finally:
        await src.stop()

    elapsed = time.monotonic() - t_start
    avg_db = 20 * math.log10(math.sqrt(sq_sum / samples) / 32768) if sq_sum > 0 else float("-inf")
    fps = frames / elapsed if elapsed > 0 else 0.0
    print(f"frames       : {frames}")
    print(f"elapsed      : {elapsed:.2f} s")
    stream_s = (t_last - t_first) if (t_first is not None and t_last is not None) else 0.0
    stream_fps = (frames - 1) / stream_s if stream_s > 0 else 0.0
    print(f"frames/sec   : {fps:.1f} overall, {stream_fps:.1f} after first frame "
          f"(expected {1000 / src.frame_ms:.0f})")
    print(f"bytes        : {nbytes}")
    print(f"avg rms      : {_fmt_db(avg_db)} dBFS")
    if frames == 0:
        print("ERROR: zero frames captured", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m backend.audio.demo", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--source", choices=["laptop", "file", "wearable"], default=None,
                   help="audio source (default: env AUDIO_SOURCE or laptop)")
    p.add_argument("--file", help="WAV path for --source file (or env AUDIO_FILE_PATH)")
    p.add_argument("--seconds", type=float, default=5.0)
    p.add_argument("--make-test-wav", metavar="PATH",
                   help="write a 3 s 440 Hz 16 kHz mono test WAV and exit")
    args = p.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    if args.make_test_wav:
        make_test_wav(args.make_test_wav)
        print(f"wrote test wav: {args.make_test_wav} (3 s, 440 Hz, 16 kHz mono 16-bit)")
        return 0
    try:
        return asyncio.run(run(args.source, args.file, args.seconds))
    except (ValueError, FileNotFoundError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
