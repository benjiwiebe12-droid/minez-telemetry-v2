#!/usr/bin/env python3
"""
LaVallee Mine — telemetry streamer

Publishes recorded mine telemetry to the Redis stream, the way the on-site
gateway does. The recording (data/sample.jsonl) is one hour of raw messages
captured from the mine, exactly as the devices sent them.

Modes:
  --load [FILE]   publish the whole recording at once (good for testing)
  --live [FILE]   replay the recording in real time: one 5-second batch every
                  5 seconds, with timestamps moved to "now". When the recording
                  ends it starts again (new event_ids, later timestamps).

Usage:
  python -m generator.stream --load
  python -m generator.stream --live
"""
from __future__ import annotations

import argparse
import json
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.config import REDIS_URL, STREAM

DEFAULT_FILE = Path("data/sample.jsonl")
BATCH_SECONDS = 5
TS_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def _connect(url: str):
    import redis
    return redis.from_url(url, decode_responses=False)


def _publish(r, raw_messages: list[str]) -> None:
    pipe = r.pipeline()
    for raw in raw_messages:
        pipe.xadd(STREAM, {"data": raw})
    pipe.execute()


def _parse_ts(s: str) -> datetime:
    return datetime.strptime(s, TS_FORMAT).replace(tzinfo=timezone.utc)


# ── --load ─────────────────────────────────────────────────────────────────

def run_load(path: Path, redis_url: str) -> None:
    r = _connect(redis_url)
    lines = [l.rstrip("\n") for l in path.open(encoding="utf-8") if l.strip()]
    for i in range(0, len(lines), 500):
        _publish(r, lines[i:i + 500])          # raw lines, untouched
    print(f"loaded {len(lines)} events into Redis stream '{STREAM}'", flush=True)


# ── --live ─────────────────────────────────────────────────────────────────

def _batches(path: Path) -> list[list[tuple[int, str]]]:
    """Group the recording into 5-second batches by timestamp.

    Each item is (seconds offset from the batch start, raw line). Lines whose
    timestamp can't be read are kept as-is and sent with their batch.
    """
    lines = [l.rstrip("\n") for l in path.open(encoding="utf-8") if l.strip()]
    parsed = []
    for raw in lines:
        try:
            parsed.append((_parse_ts(json.loads(raw)["ts"]), raw))
        except Exception:
            parsed.append((None, raw))
    times = [t for t, _ in parsed if t is not None]
    start = min(times)
    start -= timedelta(seconds=start.second % BATCH_SECONDS)
    n = int((max(times) - start).total_seconds() // BATCH_SECONDS) + 1
    batches: list[list[tuple[int, str]]] = [[] for _ in range(n)]
    last = 0
    for t, raw in parsed:
        if t is None:
            batches[last].append((0, raw))
            continue
        offset = (t - start).total_seconds()
        last = int(offset // BATCH_SECONDS)
        batches[last].append((int(offset - last * BATCH_SECONDS), raw))
    return batches


def _retime(raw: str, ts: datetime, loop: int) -> str:
    """Move a message to a new timestamp; give it a fresh event_id on replays."""
    try:
        msg = json.loads(raw)
        msg["ts"] = ts.strftime(TS_FORMAT)
        if loop and isinstance(msg.get("event_id"), str):
            msg["event_id"] = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{msg['event_id']}/{loop}"))
        return json.dumps(msg)
    except Exception:
        return raw


def run_live(path: Path, redis_url: str) -> None:
    r = _connect(redis_url)
    batches = _batches(path)
    print(f"Streaming {path} to Redis stream '{STREAM}' — Ctrl-C to stop", flush=True)
    loop, sent = 0, 0
    while True:
        for batch in batches:
            now = datetime.now(timezone.utc).replace(microsecond=0)
            _publish(r, [_retime(raw, now + timedelta(seconds=off), loop) for off, raw in batch])
            sent += 1
            print(f"batch {sent:5d}  {now.strftime('%H:%M:%S')}  +{len(batch):3d} events", flush=True)
            time.sleep(BATCH_SECONDS)
        loop += 1


# ── entry point ────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--load", nargs="?", const=str(DEFAULT_FILE), metavar="FILE",
                      help="publish a .jsonl recording all at once")
    mode.add_argument("--live", nargs="?", const=str(DEFAULT_FILE), metavar="FILE",
                      help="replay a .jsonl recording in real time")
    ap.add_argument("--redis", default=REDIS_URL, help=f"Redis URL (default: {REDIS_URL})")
    args = ap.parse_args()

    if args.load:
        run_load(Path(args.load), args.redis)
    else:
        run_live(Path(args.live), args.redis)


if __name__ == "__main__":
    main()
