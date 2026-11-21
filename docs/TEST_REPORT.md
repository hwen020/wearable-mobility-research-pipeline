# Test report — Windows acceptance, 2026-11-20

## Baseline before changes

- Python 3.12, `python -m pip install -r requirements-dev.txt`, `python -m pytest -q`: 8 passed.
- Isolated SQLite seeding and HTTP smoke tests verified 3 synthetic participants, 366 observations, 6 participant-days and 22.2 km.
- The workspace arrived without Git metadata.

## Final result

`python -m pytest -q` with Edge and MySQL integration enabled yielded **30 passed, 0 failed, 0 skipped** in **15.61 s**. The default run yielded **28 passed, 2 opt-in skips**. The final Edge-only run exercised the start and end markers, speed-jump and repeated-coordinate review, and refreshed the screenshots. It yielded **1 passed** in **5.57 s**. The suite emitted one Starlette TestClient dependency deprecation warning.

## Verification commands

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
$env:RUN_BROWSER = "1"
$env:BROWSER_CHANNEL = "msedge"
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m scripts.benchmark_pipeline
```

The full test run also enables `MOBILITY_MYSQL_TEST_URL` for a disposable, initially empty MySQL database whose name starts with `mobility_test`. It exercised MySQL 9.0.1 with TLS on a temporary loopback listener. Each SQLite test used a separate database. The Edge test blocked external requests and rendered local Leaflet with `?basemap=none`.

- Backend coverage includes fresh and legacy migrations, storage of raw accepted fields, rejection and duplicate diagnostics, rollback, concurrent ingest, offsets and DST, protocol compatibility, spatial edge cases, export formats and metadata, repeatable runs, mock device mapping, and gated synthetic restore.
- Browser coverage includes map and polygon rendering, participant and date selection, layer controls, file preview, accepted and duplicate CSV submission, diagnostics filter, both CSV and GeoJSON downloads, confirmation and cancellation of demo reset, and a 390 px viewport overflow check.
- The Windows launcher seeded a separate database and served the expected summary at port 8000. The canonical CSV SHA-256 remained `f040d7bb224d56bcc6e5e5a2369392c915a282d9448003f43b2958d04234e679`.
- JS syntax, Python compilation and dependency checks passed. Docker Compose configuration validated. Docker image execution and GitHub-hosted CI remain unverified. The default network basemap is outside the offline browser acceptance.

[Dashboard](screenshots/dashboard.png) · [GIS map](screenshots/gis-map.png) · [Data quality](screenshots/data-quality.png) · [Analytics](screenshots/analytics.png)

## Performance

SQLite on Windows, synthetic fixture, Python 3.12. Import timing includes transaction commits and Python allocation tracing. Query timing is the arithmetic mean of 30 warm indexed fetches of 250 coordinate rows. Traced peak is Python allocations, excluding native SQLite and interpreter RSS.

| Observations | Import (s) | Peak Python allocations (MiB) | Query mean (ms) |
|---:|---:|---:|---:|
| 10,000 | 2.893 | 1.67 | 0.520 |
| 50,000 | 16.858 | 1.34 | 0.546 |
| 100,000 | 34.030 | 1.36 | 0.771 |

100,000 records were split into two 50,000-row inputs. The query planner used the participant/timestamp unique index. Numbers are for this run and are not a full dashboard or production capacity claim.

## Original verification report

# Verification record — v0.1 (2026-11-19)

The following was executed in the creation environment (Linux / Python 3.13), not on the user's Windows computer:

- `python -m pytest -q`: **8 passed**; SQLite foreign-key enforcement enabled in the test fixture.
- `node --check static/app.js`: **passed** after fixing an escaped newline in the upload result message.
- `python -m app.demo_seed`: **passed**; generated 3 synthetic participants, 366 observations and six participant-days.
- FastAPI TestClient read requests to `/`, `/api/health`, `/api/summary`, `/api/participants`, participant GeoJSON and static JS/CSS: **HTTP 200**. Summary: 366 observations, six participant-days, 22.2 km of synthetic route-distance.
- Playwright/Chromium browser navigation to localhost was **blocked by the execution environment** (`ERR_BLOCKED_BY_ADMINISTRATOR`); therefore **browser end-to-end UI verification is NOT claimed**.
- The Windows BAT scripts and real MySQL connection have **not** been executed on Windows/MySQL. They are prepared as startup paths and must be validated on the user's environment.
- This package includes only source files and generated synthetic fixture CSV. It excludes `.env`, SQLite runtime database, caches, `.venv` and any credentials.

### How Codex should finish browser acceptance

1. On Windows, run `scripts\start_windows.bat` and visit `http://127.0.0.1:8000`.
2. Confirm 3 participants, 366 observations, 6 participant-days and a rendered map with area, route and stay layers.
3. Switch UTC date and verify selected 61 points; use CSV download.
4. Reimport fixture and verify zero newly accepted observations (duplicate counts only).
5. Upload malformed fixture and verify actionable rejection messages.
6. Run `python -m pytest -q` and add Playwright UI checks with an isolated demo database.
