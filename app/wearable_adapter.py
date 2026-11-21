"""Synthetic wearable adapter that feeds the existing validated import pipeline."""
import csv
import io
from collections.abc import Iterable
from tempfile import SpooledTemporaryFile
from typing import Protocol

from .db import SessionLocal, upgrade_schema
from .pipeline import import_csv_stream

FIELDS = ("participant_id", "timestamp_utc", "latitude", "longitude", "steps",
          "heart_rate_bpm", "source")


class WearableAdapter(Protocol):
    source: str

    def normalized_records(self) -> Iterable[dict]:
        """Yield canonical synthetic observation fields."""


class MockFitbitAdapter:
    source = "mock_fitbit"

    def normalized_records(self):
        # Location comes from the synthetic fixture, independent of the device-shaped values.
        rows = (
            {"dateTime": "2026-11-16T09:00:00-08:00", "steps": {"value": 12},
             "heartRate": {"bpm": 74}, "location": (34.05, -118.25)},
            {"dateTime": "2026-11-16T09:05:00-08:00", "steps": {"value": 26},
             "heartRate": {"bpm": 82}, "location": (34.051, -118.249)},
        )
        for record in rows:
            latitude, longitude = record["location"]
            yield {"participant_id": "SYN-MOCK-001", "timestamp_utc": record["dateTime"],
                   "latitude": latitude, "longitude": longitude,
                   "steps": record["steps"]["value"], "heart_rate_bpm": record["heartRate"]["bpm"],
                   "source": "synthetic"}


def import_wearable(session, adapter: WearableAdapter):
    with SpooledTemporaryFile(max_size=1024 * 1024, mode="w+b") as body:
        stream = io.TextIOWrapper(body, encoding="utf-8", newline="")
        try:
            writer = csv.DictWriter(stream, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(adapter.normalized_records())
            stream.flush()
        finally:
            stream.detach()
        body.seek(0)
        return import_csv_stream(session, body, f"{adapter.source}.csv", source=adapter.source)


def main():
    upgrade_schema()
    with SessionLocal.begin() as session:
        report = import_wearable(session, MockFitbitAdapter())
    print(report)


if __name__ == "__main__":
    main()
