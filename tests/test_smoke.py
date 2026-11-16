"""
Smoke tests for minez-telemetry-v2.

These run against the stub API and your validate module.
No database or Redis required — add your validation logic to app/validate.py.
"""
from fastapi.testclient import TestClient

from app.api import app

client = TestClient(app)


# ── API ────────────────────────────────────────────────────────────────────

def test_health():
    assert client.get("/health").json() == {"status": "ok"}


# Note: 404 behaviour for unknown zone/shift/worker is verified by the grader
# during the full integration run against a live database.


# ── Validation (add these once you implement app/validate.py) ──────────────

# Example tests to guide your implementation — uncomment and adapt as you go.

# def test_valid_truck_accepted():
#     from app.validate import parse
#     raw = '{"event_id":"t1","type":"truck_status","source_id":"TRK-01",' \
#           '"ts":"2026-11-16T06:00:00Z","payload":{"zone_id":"Z-1","state":"hauling",' \
#           '"speed_kph":15.0,"payload_t":50.0}}'
#     ev, reason = parse(raw)
#     assert reason == "ok"
#     assert ev.shift_id == "2026-11-16-D"


# def test_valid_health_safety_accepted():
#     from app.validate import parse
#     raw = '{"event_id":"s1","type":"health_safety","source_id":"W-001",' \
#           '"ts":"2026-11-16T07:00:00Z","payload":{"zone_id":"Z-1",' \
#           '"worker_id":"W-001","event_type":"near_miss","severity":"low",' \
#           '"co_ppm_at_event":4.0,"description":"Worker near miss Z-1",' \
#           '"location_city":"Val-d\'Or, QC"}}'
#     ev, reason = parse(raw)
#     assert reason == "ok"


# def test_non_json_rejected():
#     from app.validate import parse
#     ev, reason = parse("not json }{")
#     assert ev is None
#     assert reason == "malformed_json"


# def test_unknown_source_rejected():
#     from app.validate import parse
#     raw = '{"event_id":"u1","type":"truck_status","source_id":"TRK-99",' \
#           '"ts":"2026-11-16T06:00:00Z","payload":{"zone_id":"Z-1",' \
#           '"state":"hauling","speed_kph":10.0,"payload_t":50.0}}'
#     ev, reason = parse(raw)
#     assert ev is None
#     assert reason == "unknown_source"
