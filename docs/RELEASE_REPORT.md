# Wearable Mobility Research Pipeline v1.0.0 release report


## Final local acceptance for the v1.0.0 tag

The workspace was clean at `d88f89c` with no staged or unstaged changes. The original release commit `30378f1` remains an ancestor.

| Check | Final result |
|---|---|
| Full regression | PASS. `python -m pytest -q` passed 44 tests in 26.33 seconds with SQLite, temporary MySQL 9.0.1 and Edge enabled. One upstream Starlette TestClient deprecation warning. |
| Public mutation guard | PASS. POST, PUT, PATCH and DELETE returned 403 before parsing. Public GET requests for health, maps, analytics, exports, diagnostics, assets and docs left the SQLite dump unchanged. GET on the import and restore paths did not execute mutations. |
| Local full functionality | PASS. Edge exercised CSV upload, ingestion, duplicate feedback and confirmed demo restore with `DEMO_PUBLIC_READONLY=false`. |
| Render configuration and native smoke | PASS. Blueprint and startup shell syntax were checked. Native Uvicorn bound to `0.0.0.0` on a supplied port. Two seed runs retained 366 observations. HTTP health, maps, analytics, export and public mutation checks passed. |
| Privacy and fixture integrity | PASS. Review of 77 candidate files found no recognized credentials, personal absolute paths or versioned database/cache artifacts. The synthetic fixture is byte-identical to the baseline. |
| Docker runtime and Render Free capacity | NOT VERIFIED. A single bounded engine probe timed out. The candidate image runtime and memory/CPU behavior remain unverified. |
| Hosted Actions, public HTTPS and provider logs | NOT VERIFIED. No remote publication or deployment was performed. |

**GitHub-ready: YES for local source publication.** External publication still requires authorization. Docker runtime, hosted CI and public ingress remain verification gates. Start locally with `.\scripts\start_windows.bat` and open `http://127.0.0.1:8000/`.


## GitHub and Render publication preparation

The existing `30378f1` release is retained in local Git history. Publication preparation adds a Render Free Docker Blueprint, an environment-driven listener, and a public read-only mode. The original synthetic dataset checksum is unchanged.

| Check | Result |
|---|---|
| Original release regression | PASS. 41 tests passed with SQLite, disposable MySQL 9.0.1 and Edge. |
| Updated candidate regression | PASS. 43 tests passed with SQLite, MySQL 9.0.1 and Edge in 40.80 seconds. The suite includes the new public mutation guard and mobile browser checks for maps, filtering, CSV download and hidden write controls. |
| Public-mode native HTTP smoke | PASS. Seeding twice retained 366 observations; a custom-port Uvicorn process served health, map data, daily analysis and exports. Import, reset, update and delete requests returned 403. |
| Render Blueprint, Docker startup shell and GitHub Actions configuration | PASS. Verified locally against the documented Render fields and checked shell syntax. The Docker workflow exercises port 10000 and the Free-tier CPU and RAM limits. |
| Local Render candidate Docker build | FAILED. Both the local Docker engine query and build attempt timed out. |
| Render candidate container and Free-tier GeoPandas capacity | NOT VERIFIED. The earlier v1.0.0 in-container result below covers the previous image only. |
| Privacy and Git | PASS. Candidate file scan found no recognized credentials, personal absolute paths or tracked database/cache artifacts. Canonical synthetic fixture bytes match the released checksum. |
| GitHub repository, hosted CI, Render deployment and logs | NOT VERIFIED. No configured remote or usable account connector was available. Publication requires explicit authorization. |
| Real public HTTPS browser acceptance | NOT VERIFIED. No public endpoint exists. |

Render is configured to seed a fresh ephemeral SQLite database before opening the port and rejects visitor mutations at the application boundary. See [Render deployment and acceptance](DEPLOYMENT.md#render-free-blueprint). The section below retains the earlier v1.0.0 acceptance history.

Release readiness assessed on 2026-11-20. Scope is a synthetic-only geospatial portfolio demo.

## Changes in this release

- Separated Observed Validity Rate from Expected Sampling Coverage. Accepted daily fixes form the observed denominator. Coverage uses distinct occupied slots within an explicitly configured sampling window. Missing configured days have zero coverage; dates outside the window have an unavailable coverage value.
- Preserved the legacy `screened_gps_ratio` alias and added daily JSON/CSV counts, a reproducible sampling policy in export metadata, and consistent Dashboard labels. See [research methods](RESEARCH_METHODS.md) and the [data dictionary](DATA_DICTIONARY.md).
- Added a read-only hosting option, a release smoke check, a canonical fixture checksum in CI, and a Linux container deployment recipe. The service uses no real wearable account, OAuth, research subject, or external paid API.

## Acceptance

| Check | Result |
|---|---|
| SQLite and coverage unit/API regression | PASS. Default pytest: 38 passed, 3 opt-in skips. |
| Edge Playwright and screenshots | PASS. Two Edge tests covered the upload/download/reset flow and configured coverage versus N/A. |
| Disposable MySQL 9.0.1 regression | PASS. Migration, idempotence, duplicate diagnostics, subsecond UTC timestamps and concurrent import were exercised. |
| Linux image build, container boot and HTTP smoke | PASS. Image built with Docker 24.0.7; the non-root service reported healthy and passed the full HTTP smoke inside the container. |
| Read-only release smoke on isolated Windows SQLite | PASS |
| GitHub workflow structure, Compose configuration, and local README link and image review | PASS |
| Windows-published Docker port | FAILED in this environment. The forwarded connection closed before an HTTP response. |
| Independent Docker network and public ingress | NOT VERIFIED. The local Docker network command stalled; no public service was provisioned. |
| Hosted GitHub Actions, public HTTPS ingress and third-party map tiles | NOT VERIFIED |

The full suite with Edge and disposable MySQL enabled ran **41 tests, 41 passed, 0 failed, 0 skipped in 17.99 seconds**. The runner used a low-memory temporary MySQL configuration and limited BLAS/Node allocations after Windows resource errors in earlier attempts. Pytest reported one upstream Starlette TestClient deprecation warning. The Windows README launcher also passed with a disposable database.

The original 366 observed rows retain SHA-256 `f040d7bb224d56bcc6e5e5a2369392c915a282d9448003f43b2958d04234e679`. Git attributes preserve these bytes across checkouts. The Windows smoke covered health, seed counts, dashboard HTML, Leaflet assets, daily analysis, GeoJSON and CSV exports.

[Dashboard](screenshots/dashboard.png) · [GIS map](screenshots/gis-map.png) · [Data quality](screenshots/data-quality.png) · [Participant analytics](screenshots/analytics.png)

## Release gates

**GitHub-ready: YES.** The source, MIT license, static asset license, workflow, screenshots and documentation were reviewed, with local Git history prepared. **Cloud-demo-ready: local image validated; ingress acceptance remains open.** No resources were purchased or published. Final HTTPS ingress and hosted CI remain unverified. Online deployment should use `DEMO_READ_ONLY=1`, terminate TLS at the host, and serve the synthetic fixture only. See [deployment](DEPLOYMENT.md).

The release tree excludes virtual environments, caches, logs, runtime databases and actual environment files. The release scan found no recognized credential patterns or personal absolute local paths in the candidate files. Only the synthetic fixture and intentional synthetic examples are included.

## Portfolio bullets

- Built a FastAPI and SQLAlchemy pipeline that validates synthetic wearable GPS records and preserves duplicate, rejection, and observation provenance in SQLite and MySQL.
- Implemented DST-aware expected GPS sampling coverage and observed validity metrics with explicit denominators, missing-day handling, and reproducible CSV and GeoJSON outputs.
- Validated Leaflet map interactions, CSV import/export, and synthetic reset in Edge with Playwright and verified a read-only release using a repeatable HTTP smoke suite.
