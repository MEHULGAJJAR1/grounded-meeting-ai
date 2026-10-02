"""System timestamps are UTC on both SQLite and PostgreSQL."""

from datetime import datetime, timezone


def iso_utc(value: datetime) -> str:
    # SQLite loses tzinfo on reads; all generated system timestamps are stored UTC.
    aware = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    return aware.astimezone(timezone.utc).isoformat()
