#!/usr/bin/env python3
"""
LaVallee Mine — telemetry generator

Modes:
  --live          stream events to Redis every 5 seconds (runs until Ctrl-C)
  --sample        write ~10 000 events to data/sample.jsonl  (default if no flag)
  --load FILE     publish a .jsonl file to Redis (use after --sample)

Usage:
  python generator/generate.py --live
  python generator/generate.py --sample --out data/sample.jsonl
  python generator/generate.py --load data/sample.jsonl
"""

import argparse
import json
import random
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ── constants ─────────────────────────────────────────────────────────────

STREAM  = "minez:events"
SEED    = 42

ZONES   = ["Z-1", "Z-2", "Z-3", "Z-4", "Z-5", "Z-6"]
TRUCKS  = [f"TRK-{i:02d}" for i in range(1, 9)]
AQ      = [f"AQ-{i:02d}" for i in range(1, 7)]
WORKERS = [f"W-{i:03d}" for i in range(1, 11)]

WORKER_NAMES = {
    "W-001": "Pierre Tremblay",
    "W-002": "Marie-Claire Bouchard",
    "W-003": "Jean-François Côté",
    "W-004": "Kevin O'Brien",
    "W-005": "Sylvie Gagnon",
    "W-006": "Marco Arsenault",
    "W-007": "Linda Ouellet",
    "W-008": "Denis Lavoie",
    "W-009": "Ahmed Belkacem",
    "W-010": "Nathalie Fortin",
}

TRUCK_STATES    = ["hauling", "idle", "dumping", "tramming"]
SAFETY_TYPES    = ["near_miss", "gas_exposure", "equipment_contact", "slip_fall", "evacuation"]
SAFE_CITIES     = ["Val-d'Or, QC", "Rouyn-Noranda, QC", "Malartic, QC", "Amos, QC"]

# Traps (injected by generator — candidates must detect them)
TRAP_MEXICO_CITY   = "Monterrey, MX"
TRAP_ONTARIO_CITY  = "Sudbury, ON"
GIBBERISH_POOL     = [
    "x7k9#@! bq2 mfp77 null null 0x00",
    "\\x00\\x00\\x00 ERR SENSOR FAIL 0",
    "???????????????????????????????????",
    "NaN NaN NaN undefined undefined",
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
]
# Readable but physically impossible in an underground mine
UNREALISTIC_POOL   = [
    ("slip_fall",         "{name} jumped out of a plane and landed in {zone}"),
    ("equipment_contact", "{name} got into a fight with sharks in the sump at {zone}"),
    ("near_miss",         "{name} was abducted by aliens during the shift in {zone}"),
    ("equipment_contact", "{name} wrestled a crocodile in the ventilation shaft at {zone}"),
    ("near_miss",         "{name} was chased by a dinosaur through {zone}"),
    ("slip_fall",         "{name} slipped on a banana peel and landed on the moon"),
    ("gas_exposure",      "{name} was struck by lightning 300 m underground in {zone}"),
    ("slip_fall",         "{name} fell off a skyscraper in {zone}"),
    ("equipment_contact", "{name} crashed a jet ski into a haul truck in {zone}"),
    ("near_miss",         "{name} fought off a polar bear near the crusher in {zone}"),
    ("evacuation",        "{name} evacuated {zone} because a volcano erupted"),
    ("slip_fall",         "{name} got a sunburn at the beach in {zone}"),
]

# speed / payload limits per truck state
SPEED_RANGE   = {"hauling": (8.0, 25.0),  "idle": (0.0, 0.0),
                 "dumping": (0.0, 3.0),   "tramming": (5.0, 20.0)}
PAYLOAD_RANGE = {"hauling": (40.0, 95.0), "idle": (0.0, 5.0),
                 "dumping": (10.0, 80.0), "tramming": (0.0, 5.0)}

# CO threshold rules (candidates must enforce these in validate.py)
CO_CRITICAL = 50.0  # co_ppm_at_event >= 50 → severity must be high or critical
CO_HIGH     = 25.0  # co_ppm_at_event >= 25 → severity must be medium, high, or critical


# ── simulator ─────────────────────────────────────────────────────────────

class Simulator:
    def __init__(self, seed: int = SEED):
        self.rng = random.Random(seed)
        self._total = 0           # total events generated so far
        self._batch_no = 0
        # Separate RNG so this trap doesn't shift the main random sequence
        self._unreal_rng  = random.Random(seed + 1)
        self._unreal_pool = self._unreal_rng.sample(UNREALISTIC_POOL, len(UNREALISTIC_POOL))
        self._init_trucks()
        self._init_aq()

    # ── init ──────────────────────────────────────────────────────────────

    def _init_trucks(self):
        self._trucks = {}
        for i, trk in enumerate(TRUCKS):
            state = self.rng.choice(["hauling", "tramming"])
            self._trucks[trk] = {
                "zone":      ZONES[i % len(ZONES)],
                "state":     state,
                "speed":     self.rng.uniform(*SPEED_RANGE[state]),
                "payload":   self.rng.uniform(*PAYLOAD_RANGE[state]),
                "ticks":     0,
                "max_ticks": self.rng.randint(10, 40),
            }

    def _init_aq(self):
        self._aq = {}
        for i, sensor in enumerate(AQ):
            self._aq[sensor] = {
                "zone":           ZONES[i % len(ZONES)],
                "co":             self.rng.uniform(3.0, 15.0),
                "no2":            self.rng.uniform(0.1, 1.5),
                "o2":             self.rng.uniform(19.8, 20.9),
                "temp":           self.rng.uniform(14.0, 26.0),
                "spike_cd":       self.rng.randint(60, 200),
                "in_spike":       False,
                # AQ-04 freezes after 1 200 events (open trap — repeating values)
                "freeze_after":   1200 if sensor == "AQ-04" else 10**9,
                "frozen_vals":    None,
            }

    # ── truck step ────────────────────────────────────────────────────────

    def _truck_event(self, trk: str, ts: datetime, inject_trap: bool) -> dict:
        t = self._trucks[trk]
        t["ticks"] += 1

        if t["ticks"] >= t["max_ticks"]:
            t["state"]     = self.rng.choice(TRUCK_STATES)
            t["ticks"]     = 0
            t["max_ticks"] = self.rng.randint(10, 40)
            if t["state"] == "tramming":
                t["zone"] = self.rng.choice(ZONES)
            if t["state"] == "hauling":
                t["payload"] = self.rng.uniform(40.0, 95.0)
            elif t["state"] in ("idle", "tramming"):
                t["payload"] = self.rng.uniform(0.0, 5.0)

        lo, hi = SPEED_RANGE[t["state"]]
        speed   = self.rng.uniform(lo, hi)
        payload = t["payload"]

        if inject_trap:
            roll = self.rng.random()
            if roll < 0.33:
                # idle truck with speed > 5 kph
                t["state"] = "idle"
                speed      = round(self.rng.uniform(8.0, 20.0), 1)
            elif roll < 0.66:
                # impossible speed (> 55 kph underground)
                speed = round(self.rng.uniform(56.0, 72.0), 1)
            else:
                # payload over capacity (> 110 t)
                payload = round(self.rng.uniform(111.0, 140.0), 1)

        return self._event("truck_status", trk, ts, {
            "zone_id":    t["zone"],
            "state":      t["state"],
            "speed_kph":  round(speed, 1),
            "payload_t":  round(payload, 1),
        })

    # ── AQ step ───────────────────────────────────────────────────────────

    def _aq_event(self, sensor: str, ts: datetime, inject_trap: bool) -> dict:
        a = self._aq[sensor]
        a["spike_cd"] -= 1

        if a["spike_cd"] <= 0 and not a["in_spike"]:
            a["in_spike"]  = True
            a["spike_cd"]  = self.rng.randint(5, 15)
            a["co"]        = self.rng.uniform(28.0, 65.0)
        elif a["in_spike"] and a["spike_cd"] <= 0:
            a["in_spike"]  = False
            a["spike_cd"]  = self.rng.randint(60, 200)
            a["co"]        = self.rng.uniform(3.0, 15.0)
        else:
            a["co"]  = max(0.5, a["co"]  + self.rng.gauss(0, 0.4))

        a["no2"]  = max(0.0, a["no2"] + self.rng.gauss(0, 0.04))
        a["o2"]   = min(21.5, max(18.5, a["o2"]  + self.rng.gauss(0, 0.015)))
        a["temp"] = min(35.0, max(10.0, a["temp"] + self.rng.gauss(0, 0.08)))

        # Frozen sensor trap (open trap — repeating values)
        if self._total >= a["freeze_after"]:
            if a["frozen_vals"] is None:
                a["frozen_vals"] = {
                    "co":   round(a["co"],   2),
                    "no2":  round(a["no2"],  2),
                    "o2":   round(a["o2"],   2),
                    "temp": round(a["temp"], 1),
                }
            payload = {
                "zone_id": a["zone"],
                "co_ppm":  a["frozen_vals"]["co"],
                "no2_ppm": a["frozen_vals"]["no2"],
                "o2_pct":  a["frozen_vals"]["o2"],
                "temp_c":  a["frozen_vals"]["temp"],
            }
            return self._event("air_quality", sensor, ts, payload)

        payload = {
            "zone_id": a["zone"],
            "co_ppm":  round(a["co"],   2),
            "no2_ppm": round(a["no2"],  2),
            "o2_pct":  round(a["o2"],   2),
            "temp_c":  round(a["temp"], 1),
        }

        if inject_trap:
            roll = self.rng.random()
            if roll < 0.5:
                # missing required field (hardcoded trap)
                del payload[self.rng.choice(["co_ppm", "no2_ppm"])]
            else:
                # location not in Quebec (hardcoded trap)
                payload["site_city"] = TRAP_ONTARIO_CITY

        return self._event("air_quality", sensor, ts, payload)

    # ── safety event ──────────────────────────────────────────────────────

    def _safety_event(self, ts: datetime, inject_trap: bool) -> dict:
        worker     = self.rng.choice(WORKERS)
        zone       = self.rng.choice(ZONES)
        ev_type    = self.rng.choice(SAFETY_TYPES)
        co_at_ev   = self.rng.uniform(2.0, 35.0)

        if co_at_ev >= CO_CRITICAL:
            severity = "critical"
        elif co_at_ev >= CO_HIGH:
            severity = self.rng.choice(["high", "critical"])
        elif co_at_ev >= 10.0:
            severity = self.rng.choice(["medium", "high"])
        else:
            severity = self.rng.choice(["low", "medium"])

        name = WORKER_NAMES[worker]
        desc = self.rng.choice([
            f"{name} reported {ev_type.replace('_', ' ')} in {zone}",
            f"Proximity alert triggered near {self.rng.choice(TRUCKS)} for {name}",
            f"Safety event: {ev_type.replace('_', ' ')} logged at {zone}",
            f"Worker {name}: {ev_type.replace('_', ' ')} event at {zone}",
        ])

        payload = {
            "zone_id":          zone,
            "worker_id":        worker,
            "event_type":       ev_type,
            "severity":         severity,
            "co_ppm_at_event":  round(co_at_ev, 1),
            "description":      desc,
            "location_city":    self.rng.choice(SAFE_CITIES),
        }

        if inject_trap:
            roll = self.rng.random()
            if roll < 0.33:
                # severity contradicts CO level (hardcoded trap)
                payload["co_ppm_at_event"] = round(self.rng.uniform(52.0, 75.0), 1)
                payload["severity"]        = "low"
            elif roll < 0.66:
                # location outside Quebec (hardcoded trap)
                payload["location_city"] = TRAP_MEXICO_CITY
            else:
                # gibberish description (hardcoded trap)
                payload["description"] = self.rng.choice(GIBBERISH_POOL)

        return self._event("health_safety", worker, ts, payload)

    # ── open trap: near-duplicate safety events ───────────────────────────

    def _near_duplicate_pair(self, ts: datetime) -> list[dict]:
        """Two events from the same worker at the same timestamp with slightly
        different descriptions — candidates must detect the near-duplicate."""
        worker  = self.rng.choice(WORKERS)
        zone    = self.rng.choice(ZONES)
        ev_type = "near_miss"
        name    = WORKER_NAMES[worker]

        base_payload = {
            "zone_id":         zone,
            "worker_id":       worker,
            "event_type":      ev_type,
            "severity":        "medium",
            "co_ppm_at_event": round(self.rng.uniform(5.0, 15.0), 1),
            "location_city":   self.rng.choice(SAFE_CITIES),
        }

        p1 = {**base_payload, "description": f"{name} reported near miss at {zone}"}
        p2 = {**base_payload, "description": f"{name} reported a near-miss event in {zone}"}  # slight rewording

        return [
            self._event("health_safety", worker, ts, p1),
            self._event("health_safety", worker, ts + timedelta(seconds=1), p2),
        ]

    # ── open trap: zone contradiction ─────────────────────────────────────

    def _zone_contradiction_event(self, ts: datetime) -> dict:
        """Description mentions a different zone than payload.zone_id."""
        worker  = self.rng.choice(WORKERS)
        actual  = self.rng.choice(ZONES)
        # pick a different zone for the description
        wrong   = self.rng.choice([z for z in ZONES if z != actual])
        name    = WORKER_NAMES[worker]

        payload = {
            "zone_id":         actual,
            "worker_id":       worker,
            "event_type":      "slip_fall",
            "severity":        "low",
            "co_ppm_at_event": round(self.rng.uniform(2.0, 8.0), 1),
            "description":     f"{name} slipped near the crusher in {wrong}",  # wrong zone in text
            "location_city":   self.rng.choice(SAFE_CITIES),
        }
        return self._event("health_safety", worker, ts, payload)

    # ── trap: unrealistic description ─────────────────────────────────────

    def _unrealistic_event(self, ts: datetime) -> dict:
        """Valid in every field, but the description can't happen underground."""
        rng      = self._unreal_rng
        worker   = rng.choice(WORKERS)
        zone     = rng.choice(ZONES)
        ev_type, text = self._unreal_pool[(self._batch_no // 110) % len(self._unreal_pool)]
        payload = {
            "zone_id":         zone,
            "worker_id":       worker,
            "event_type":      ev_type,
            "severity":        rng.choice(["low", "medium"]),
            "co_ppm_at_event": round(rng.uniform(3.0, 9.0), 1),
            "description":     text.format(name=WORKER_NAMES[worker], zone=zone),
            "location_city":   rng.choice(SAFE_CITIES),
        }
        return self._event("health_safety", worker, ts, payload)

    # ── helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _event(ev_type: str, source_id: str, ts: datetime, payload: dict) -> dict:
        return {
            "event_id":  str(uuid.uuid4()),
            "type":      ev_type,
            "source_id": source_id,
            "ts":        ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "payload":   payload,
        }

    # ── batch ─────────────────────────────────────────────────────────────

    def batch(self, ts: datetime) -> list[dict]:
        """Generate one 5-second batch of telemetry events."""
        events = []

        # Truck events (8 trucks × 1 reading per batch)
        for trk in TRUCKS:
            jitter    = timedelta(seconds=self.rng.uniform(0, 4.9))
            inject    = self.rng.random() < 0.003   # ~3 truck traps per 1 000 events
            events.append(self._truck_event(trk, ts + jitter, inject))

        # AQ events (6 sensors × 1 reading per batch)
        for sensor in AQ:
            jitter = timedelta(seconds=self.rng.uniform(0, 4.9))
            inject = self.rng.random() < 0.003   # ~2 AQ traps per 1 000 events
            events.append(self._aq_event(sensor, ts + jitter, inject))

        # Health-safety (Poisson arrival, λ ≈ 0.6 per batch → ~7/min)
        n_safety = 1 if self.rng.random() < 0.6 else 0
        for _ in range(n_safety):
            jitter = timedelta(seconds=self.rng.uniform(0, 4.9))
            inject = self.rng.random() < 0.040   # ~5 safety traps per 1 000 health_safety events
            events.append(self._safety_event(ts + jitter, inject))

        # Inject open traps periodically
        self._total += len(events)
        seq = self._total // 100   # increments roughly every 7 batches

        if seq % 30 == 0 and seq > 0:   # near-dup pair ~every 3 000 events (≈ 3× per sample run)
            jitter = timedelta(seconds=self.rng.uniform(0, 4.9))
            events += self._near_duplicate_pair(ts + jitter)

        if seq % 45 == 1 and seq > 0:   # zone contradiction ~every 4 500 events (≈ 2× per run)
            jitter = timedelta(seconds=self.rng.uniform(0, 4.9))
            events.append(self._zone_contradiction_event(ts + jitter))

        self.rng.shuffle(events)

        # Unrealistic description (~1 every 110 batches). Added after the
        # shuffle with its own RNG so the rest of the feed is unchanged.
        if self._batch_no % 110 == 50:
            jitter = timedelta(seconds=self._unreal_rng.uniform(0, 4.9))
            pos    = self._unreal_rng.randint(0, len(events))
            events.insert(pos, self._unrealistic_event(ts + jitter))
        self._batch_no += 1
        return events


# ── publish helpers ────────────────────────────────────────────────────────

def _connect_redis(url: str):
    import redis as _redis
    return _redis.from_url(url, decode_responses=False)


def _publish(r, events: list[dict]) -> None:
    pipe = r.pipeline()
    for ev in events:
        pipe.xadd(STREAM, {"data": json.dumps(ev)})
    pipe.execute()


# ── modes ──────────────────────────────────────────────────────────────────

def run_live(redis_url: str) -> None:
    from app.config import STREAM as CFG_STREAM
    r   = _connect_redis(redis_url)
    sim = Simulator()
    print(f"Streaming to Redis stream '{CFG_STREAM}' — Ctrl-C to stop", flush=True)
    batch_num = 0
    while True:
        ts     = datetime.now(timezone.utc)
        events = sim.batch(ts)
        _publish(r, events)
        batch_num += 1
        print(f"batch {batch_num:5d}  {ts.strftime('%H:%M:%S')}  +{len(events):3d} events", flush=True)
        time.sleep(5)


def run_sample(out_path: Path, n_batches: int = 700) -> None:
    """Write ~700 batches ≈ 10 000 events covering the first hour of day shift."""
    sim      = Simulator()
    start_ts = datetime(2026, 11, 16, 6, 0, 0, tzinfo=timezone.utc)
    total    = 0
    with out_path.open("w") as fh:
        for i in range(n_batches):
            ts     = start_ts + timedelta(seconds=i * 5)
            events = sim.batch(ts)
            for ev in events:
                fh.write(json.dumps(ev) + "\n")
            total += len(events)
    print(f"wrote {total} events to {out_path}", flush=True)


def run_load(jsonl_path: Path, redis_url: str) -> None:
    r = _connect_redis(redis_url)
    n = 0
    with jsonl_path.open() as fh:
        batch = []
        for line in fh:
            line = line.strip()
            if not line:
                continue
            batch.append(json.loads(line))
            if len(batch) >= 500:
                _publish(r, batch)
                n += len(batch)
                batch = []
        if batch:
            _publish(r, batch)
            n += len(batch)
    print(f"loaded {n} events into Redis stream '{STREAM}'", flush=True)


# ── entry point ────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser()
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--live",   action="store_true",
                      help="stream live events to Redis every 5 s")
    mode.add_argument("--sample", action="store_true",
                      help="write sample data to a .jsonl file (default)")
    mode.add_argument("--load",   metavar="FILE",
                      help="publish a .jsonl file to Redis")
    ap.add_argument("--out", default="data/sample.jsonl",
                    help="output path for --sample (default: data/sample.jsonl)")
    ap.add_argument("--redis", default=None,
                    help="Redis URL (default: from app.config)")
    args = ap.parse_args()

    if args.redis:
        redis_url = args.redis
    else:
        from app.config import REDIS_URL
        redis_url = REDIS_URL

    if args.live:
        run_live(redis_url)
    elif args.load:
        run_load(Path(args.load), redis_url)
    else:
        run_sample(Path(args.out))


if __name__ == "__main__":
    main()
