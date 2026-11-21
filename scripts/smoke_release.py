"""Check a fresh synthetic demo served by a release container."""
import argparse
import csv
import io
import json
from time import monotonic, sleep
from urllib.request import urlopen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_url")
    base = parser.parse_args().base_url.rstrip("/")

    def read(path):
        with urlopen(base + path, timeout=4) as response:
            return response.read()

    deadline = monotonic() + 55
    while True:
        try:
            health = json.loads(read("/api/health"))
            break
        except OSError:
            if monotonic() >= deadline:
                raise
            sleep(1)

    assert health["version"] == "1.0.0" and health["data_policy"] == "SYNTHETIC_ONLY"
    assert not health["demo_restore_enabled"]
    summary = json.loads(read("/api/summary"))
    assert summary["participants"] == 3 and summary["observations"] == 366
    assert b"Wearable Mobility Research Pipeline" in read("/")
    assert b"Leaflet" in read("/static/vendor/leaflet/leaflet.js")
    participant = "/api/participants/SYN-P001"
    daily = json.loads(read(participant + "/daily"))
    assert daily[0]["samples"] == 61 and "expected_sampling_coverage" in daily[0]
    date = "?date=2026-11-16"
    geometry = json.loads(read(participant + "/geojson" + date))
    assert {"route", "activity_area", "stay"} <= {f["properties"]["kind"] for f in geometry["features"]}
    exported = csv.DictReader(io.StringIO(read(participant + "/export.csv" + date).decode()))
    assert len(list(exported)) == 61
    print("Release smoke passed: health, seed, dashboard, Leaflet, analytics, GeoJSON and CSV")


if __name__ == "__main__":
    main()
