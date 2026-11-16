# MineZ Telemetry v2 — Take-Home Challenge

**Time limit: 3 hours**

---

## Context

The LaVallee Mine is an underground gold mine in Abitibi-Témiscamingue, Quebec.
Every device in the mine — haul trucks, air-quality monitors, and worker wearables —
streams telemetry to a central Redis stream called `minez:events`.

Your job is to build the backend pipeline that ingests this stream, stores it in
PostgreSQL, and exposes a query API for the operations dashboard.

---

## The data

Three event types arrive on the stream, all in the same envelope:

```json
{
  "event_id": "...",
  "type": "truck_status | air_quality | health_safety",
  "source_id": "TRK-01 | AQ-01 | W-001",
  "ts": "2026-11-16T06:30:12Z",
  "payload": { ... }
}
```

### `truck_status`
```json
{
  "zone_id": "Z-3",
  "state": "hauling | idle | dumping | tramming",
  "speed_kph": 18.5,
  "payload_t": 62.0
}
```

### `air_quality`
```json
{
  "zone_id": "Z-1",
  "co_ppm": 12.4,
  "no2_ppm": 0.9,
  "o2_pct": 20.6,
  "temp_c": 19.0
}
```

### `health_safety`
```json
{
  "zone_id": "Z-2",
  "worker_id": "W-003",
  "event_type": "near_miss | gas_exposure | equipment_contact | slip_fall | evacuation",
  "severity": "low | medium | high | critical",
  "co_ppm_at_event": 8.5,
  "description": "...",
  "location_city": "Val-d'Or, QC"
}
```

---

## Reference data

The tables `zones`, `equipment`, `workers`, and `shifts` are pre-loaded by
`db/01_reference_data.sql` and created automatically when Docker starts.

The mine operates two 12-hour shifts on the challenge day:

| Shift ID       | Start (UTC)         | End (UTC)           |
|----------------|---------------------|---------------------|
| 2026-11-16-D   | 2026-11-16 06:00:00 | 2026-11-16 18:00:00 |
| 2026-11-16-N   | 2026-11-16 18:00:00 | 2026-11-17 06:00:00 |

---

## Setup

**Requires Python 3.12.** Some pinned packages (e.g. `psycopg[binary]==3.1.19`)
don't install on Python 3.13 or newer.

```bash
python3.12 -m venv .venv && source .venv/bin/activate
make up          # start Postgres + Redis (Docker)
make install     # pip install -r requirements.txt

# Then choose one:
make load        # publish sample.jsonl to Redis (good for testing)
make live        # replay sample.jsonl in real time, a batch every 5 seconds (runs until Ctrl-C)
```

---

## What to build

### 1. Schema — `db/02_schema.sql`

Design tables to store the three event types and any events your pipeline rejects.

### 2. Worker — `app/worker.py`

Consume `minez:events` from Redis and write valid events to Postgres.
Reject invalid events with a reason code.

### 3. API — `app/api.py`

Implement the five endpoints below. Run with: `make api`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Returns `{"status": "ok"}` |
| `GET` | `/zones/{zone_id}/air-quality` | 5-minute CO/NO₂ averages. Query params: `from`, `to` (ISO 8601). 404 if zone unknown. |
| `GET` | `/shifts/{shift_id}/idle-trucks` | Trucks idle > 10 consecutive minutes in the shift. 404 if shift unknown. |
| `GET` | `/workers/{worker_id}/safety-events` | Safety events for a worker. Query params: `from`, `to`. 404 if worker unknown. |
| `GET` | `/zones/{zone_id}/safety-summary` | Aggregate safety stats for a zone (event counts by severity and type, avg CO at event). 404 if zone unknown. |

---

## Notes on the stream

The feed is real-world messy. Your pipeline should handle it gracefully —
silently dropping data is not acceptable.

Document what you found and how you handled it in `NOTES.md`.

---

## Grading

Your solution is evaluated on:
- **Correctness** (automated): API returns accurate results against the sample dataset
- **Data quality** (automated): pipeline correctly handles bad data in the stream
- **Design** (manual review): schema, worker resilience, validation logic
- **Write-up** (manual review): `NOTES.md` — what you found and why you made your choices

Run `pytest -q` to verify your unit tests pass before submitting.
