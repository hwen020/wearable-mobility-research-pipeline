"""Run isolated synthetic import and indexed query benchmarks."""
import argparse
import csv
import tempfile
import tracemalloc
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import perf_counter

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import build_engine, upgrade_schema
from app.pipeline import MAX_ROWS, import_csv_stream


def write_fixture(path, first, count):
    epoch = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(("participant_id", "timestamp_utc", "latitude", "longitude", "steps",
                         "heart_rate_bpm", "source"))
        for row in range(first, first + count):
            writer.writerow((f"SYN-B{row // 1000:04d}", (epoch + timedelta(seconds=row)).isoformat(),
                             34.05, -118.25, 4, 80, "synthetic"))


def benchmark(count):
    with tempfile.TemporaryDirectory(prefix="mobility-benchmark-") as directory:
        root = Path(directory)
        engine = build_engine(f"sqlite:///{root / 'bench.db'}")
        fixtures = []
        for first in range(0, count, MAX_ROWS):
            path = root / f"synthetic-{first}.csv"
            write_fixture(path, first, min(MAX_ROWS, count - first))
            fixtures.append(path)
        try:
            upgrade_schema(engine)
            tracemalloc.start()
            start = perf_counter()
            accepted = 0
            for path in fixtures:
                with Session(engine) as session, session.begin(), path.open("rb") as file:
                    accepted += import_csv_stream(session, file, path.name)["accepted"]
            duration = perf_counter() - start
            _, python_peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            assert accepted == count
            with engine.connect() as connection:
                query = text("SELECT timestamp_utc, latitude, longitude FROM observations "
                             "WHERE participant_id = :pid ORDER BY timestamp_utc LIMIT 250")
                start = perf_counter()
                for _ in range(30):
                    assert len(connection.execute(query, {"pid": "SYN-B0000"}).all()) == 250
                average_query_ms = (perf_counter() - start) / 30 * 1000
                plan = connection.execute(text("EXPLAIN QUERY PLAN " + query.text),
                                          {"pid": "SYN-B0000"}).all()
            print(f"{count:,} rows | {duration:.3f} s | peak Python allocations "
                  f"{python_peak / 1024**2:.2f} MiB | 250-row query {average_query_ms:.3f} ms mean")
            print("Query plan:", plan[-1][-1])
        finally:
            if tracemalloc.is_tracing():
                tracemalloc.stop()
            engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("counts", type=int, nargs="*", default=[10000, 50000, 100000])
    args = parser.parse_args()
    for count in args.counts:
        if not 250 <= count <= 100000:
            parser.error("counts must be between 250 and 100,000")
        benchmark(count)


if __name__ == "__main__":
    main()
