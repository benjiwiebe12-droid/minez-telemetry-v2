"""
Telemetry pipeline worker.

Reads from the Redis stream and writes valid events to Postgres.
Rejected events (malformed, unknown source, out-of-range, bad data quality)
go to the rejected_messages table.

Run: python -m app.worker
"""
import os

from app.config import DATABASE_URL, REDIS_URL, STREAM


GROUP    = "pipeline"
CONSUMER = os.getenv("CONSUMER", "worker-1")
BATCH    = 500


def main() -> None:
    raise NotImplementedError("implement me")


if __name__ == "__main__":
    main()
