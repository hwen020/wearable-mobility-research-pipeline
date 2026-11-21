"""Study-wide expected sampling policy, evaluated in UTC elapsed time."""
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True)
class SamplingPolicy:
    start: datetime
    end: datetime
    interval_seconds: int

    @classmethod
    def from_environment(cls):
        names = ("GPS_WINDOW_START", "GPS_WINDOW_END", "GPS_EXPECTED_INTERVAL_SECONDS")
        values = [os.getenv(name) for name in names]
        if all(value is None for value in values):
            return None

        def utc(value):
            instant = datetime.fromisoformat(value)
            if instant.utcoffset() is None:
                raise ValueError
            return instant.astimezone(timezone.utc).replace(tzinfo=None)

        try:
            start, end = map(utc, values[:2])
            seconds = int(values[2])
            if start >= end or seconds < 1:
                raise ValueError
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(
                "Configure GPS_WINDOW_START and GPS_WINDOW_END as ordered offset-aware timestamps "
                "and GPS_EXPECTED_INTERVAL_SECONDS as a positive integer"
            ) from exc
        return cls(start, end, seconds)

    def metadata(self):
        return {"window_start_utc": self.start.isoformat() + "Z",
                "window_end_utc": self.end.isoformat() + "Z",
                "interval_seconds": self.interval_seconds,
                "slot_alignment": "start_of_window_intersection_with_study_day"}

    def counts(self, day_start, day_end, timestamps):
        start, end = max(day_start, self.start), min(day_end, self.end)
        if end <= start:
            return None, None
        duration = end - start
        width = duration if self.interval_seconds >= duration.total_seconds() else timedelta(seconds=self.interval_seconds)
        full_slots, remainder = divmod(end - start, width)
        occupied = {(stamp - start) // width for stamp in timestamps if start <= stamp < end}
        return len(occupied), full_slots + bool(remainder)
