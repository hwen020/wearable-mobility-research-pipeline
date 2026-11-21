"""Check a fresh synthetic demo served by a release container."""
import argparse
import csv
import io
import json
from time import monotonic, sleep
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_url")
    parser.add_argument("--public", action="store_true")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    def read(path):
        with urlopen(base + path, timeout=4) as response:
            return response.read()

    deadline = monotonic() + (120 if args.public else 55)
    while True:
        try:
            health = json.loads(read("/api/health"))
            break
        except (OSError, json.JSONDecodeError):
            if monotonic() >= deadline:
                raise
            sleep(1)

    assert health["version"] == "1.0.0" and health["data_policy"] == "SYNTHETIC_ONLY"
    assert not health["demo_restore_enabled"]
    if args.public:
        assert health["public_read_only"]
        for method, path in (("POST", "/api/import"), ("POST", "/api/demo/restore"),
                             ("PUT", "/api/participants"), ("DELETE", "/api/participants/SYN-P001")):
            try:
                with urlopen(Request(base + path, method=method), timeout=4):
                    raise AssertionError(f"{method} {path} was allowed")
            except HTTPError as exc:
                assert exc.code == 403, (method, path, exc.code)
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
