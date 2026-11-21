# Implementation status (2026-11-20)

The sections beneath this note are the original handoff. The completed and pending work is tracked in [README](../README.md), [architecture](ARCHITECTURE.md), and the [Windows verification report](TEST_REPORT.md).

Windows, SQLite, MySQL and Edge acceptance passed for migration, ingestion, analysis, export and restore workflows. Remaining work includes cohort administration, stored observation-level spatial flags, schedule-based GPS coverage, full-study query scaling, and Docker runtime verification.

# Codex Incremental Handoff — Mobility Lab (2026-11-19)

## FIRST PROMPT (copy into VS Code Codex)

> Continue the existing **Wearable Mobility Research Pipeline** repository in this VS Code workspace. Do **NOT** scaffold a replacement repository. First read `AGENTS.md`, `README.md`, `docs/PROJECT_SPEC.md`, `docs/PRIVACY.md`, and this handoff. Run the existing Windows startup/test paths and inspect baseline functionality. Then implement **Phase P0** below incrementally, keeping all existing functionality, demo records, public APIs, directory paths and tests. Do not include real device/health/location data or require real credentials. Add and pass tests for every algorithm/API, and report exactly what changed, what was tested, what is still missing, and how to verify in the browser. For functionality needing secrets or authorization, provide an adapter interface and documented mock, not a fake integration. Preserve project identity, no duplicate projects.

## Baseline that already exists (do NOT rebuild)

- FastAPI + SQLAlchemy with SQLite, optional MySQL-compatible URL configuration.
- Deterministic synthetic generator (3 pseudonymous people × 2 UTC days × 61 samples = 366 rows).
- CSV import: timezone/coordinate/range validation, declared-synthetic-only source, unique participant/timestamp, first-20 rejected samples, import counts and history.
- Geospatial: Haversine distance, speed outlier filter, anchor-radius contiguous dwell detection (120m/15min), GeoPandas local UTM projected buffers and convex hull, GeoJSON.
- Dashboard: Leaflet map, participant/date selectors, quality indicators, CSV import and export.
- Unit/integration tests; Windows one-script bootstrap.

## P0 — high-impact research readiness (implement in order)

### P0-1: Correct data and import pipeline architecture
- Avoid materializing **all** historic observations to dedupe a single upload. Batch query by imported participant/timestamp (in bounded chunks), DB unique constraint remains source of truth.
- Support `uploaded_at`, file checksum, processing duration and import diagnostics in `ImportBatch`, using Alembic migrations. Record provenance and schema version; do not store raw files in git.
- Add configurable study-level timezone policy with UTC persisted; clearly handle daylight saving and offset; reject invalid or nonfinite floats (including infinity), reject incorrectly formatted headers and future outlier values.
- Streaming/chunked ingest, upload fail-safe rollback, row error records and deterministic fixture-based tests including 10k–50k rows. Keep existing small sample API working.

### P0-2: Reproducible spatial research algorithms
- Separate raw observations, cleaned observations and quality flags. Flag (not silently discard) teleport jumps, missingness, excessive sampling gaps and suspicious duplicate coordinates. Expose exclusion reasons and counts.
- Support projected analysis distances, stay point algorithm with documented parameters, visit segmentation, per-day distance/steps/valid GPS sample ratio. Add reference tests with known coordinates and DST/UTC cases.
- Preserve prior `stay` and `activity_area` API fields or version the endpoint; add algorithm name and version to each result.
- Optional exploratory DBSCAN module **only if implemented and tested**, named distinctly from baseline anchor-radius detector.

### P0-3: Research dashboard usability
- Add data-quality review panel with rejected rows/outlier reason filters, participant-day comparison, time-series for steps/heart rate, and map layer toggles.
- Add GeoJSON/CSV export with metadata (CRS, units, method, pipeline version, synthetic flag).
- Add one-button reset to the canonical synthetic fixture (with explicit UI confirmation, demo only), and an offline-capable leaflet asset option (vendored approved libraries). Do not add real data.
- Browser automation checks (Playwright) for upload, duplicate import, participant/day selection, area rendering, exports, and narrow-screen layouts. Separate DB for test runs.

## P1 — genuine research systems skills, after P0 tests green

- Add relational migration path and MySQL service via Docker Compose as an **optional** profile; ensure SQLite remains default, no external server necessary for demo.
- Add formal study/cohort schema with study, device, observation batch and optional consent state using purely synthetic records. Use pseudonymous IDs and schema versioning.
- Introduce task-queue-compatible ingestion and scheduled validation, backpressure, bounded queries, pagination, indexes, and benchmark cases (e.g. 100k synthetic rows) before any scalability claim.
- Prototype a provider-agnostic wearable adapter interface and a **mock Fitbit-shaped sample adapter**; do not imply real Fitbit API integration or use credentials.
- Add authenticated research roles + institutional access policy **only in an isolated synthetic demo**; don't claim HIPAA or production compliance.

## P2 — extensions (optional, not P0 prerequisites)

- Geospatial clustering alternatives, city/park zones via public reference polygons with proper source/licensing and CRS metadata.
- Offline deployment artifact, optional Docker and inexpensive cloud hosting with configurable privacy-safe tile provider.
- Reproducible notebook showing exploratory hypotheses vs measurements, limitations and methodological caveats; no unsupported causal claims.
- Separate ingestion source adapter for smartwatch exports after a robust privacy review; never include actual human traces in a public repository.

## Acceptance checklist for each phase

1. `scripts/start_windows.bat` starts the existing dashboard at `http://127.0.0.1:8000` without any real credentials.
2. `python -m pytest -q` passes including old tests; no existing endpoint removed or changed silently.
3. Reimporting same canonical synthetic CSV leaves 366 observations; invalid rows rejected with actionable reasons.
4. Date and participant filters render routes and a correctly projected activity-area footprint, including legend; mobile layout usable.
5. Browser tests run using an isolated DB; no actual human traces, private paths, credentials, or generated venv/db in package/repository.
6. Report exactly: code modified, tests passed, screenshots captured (if any), recognized risks, unimplemented next steps.

## DO NOT do

- Do not turn this into Travel Desk, job automation or DMC operations. These are separate repositories.
- Do not replace API with a fully new architecture for aesthetic reasons.
- Do not call demo data "Fitbit integration" or label speed threshold as scientific truth.
- Do not initialize the repo again or delete the original sample data, tests, README or handoff.
