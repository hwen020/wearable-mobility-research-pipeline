# API guide

The browser and API default to `http://127.0.0.1:8000`. Swagger is available at `/docs`.

| Method and path | Contract |
|---|---|
| GET `/api/health` | Service version, synthetic policy, study timezone and demo-restore availability |
| GET `/api/summary` | Counts, range, total distance and rejection count |
| GET `/api/participants` | Participant IDs and study dates |
| GET `/api/participants/{pid}/daily` | Per-study-day metrics and segment quality counts |
| GET `/api/participants/{pid}/observations` | Preview ordered by UTC timestamp. Optional `date`, `limit` (1–2,000), `offset`, and `include_quality=true` for derived incoming-segment flags |
| GET `/api/participants/{pid}/stays` | Anchor-radius stays. Optional `date` |
| GET `/api/participants/{pid}/geojson` | Features and metadata. Optional `date`, `download=true`, and `layer=route\|stay\|activity_area`; `metadata_only=true` returns the JSON manifest |
| GET `/api/participants/{pid}/export.csv` | Observations by default, or `dataset=daily`. Optional `date`; metadata in `X-Research-Metadata` |
| POST `/api/import` | Multipart `file`, maximum 5 MiB by default and up to 50,000 CSV data records. Returns counts and up to 20 row-level rejection reasons |
| GET `/api/imports` | Latest 20 batches; optional `batch_id` switches to diagnostics with `reason`, `outcome=rejected\|duplicate`, `offset`, and `limit` |
| POST `/api/demo/restore` | Opt-in loopback-only mutation for a marked SQLite database. JSON confirmation string must be `RESTORE SYNTHETIC DEMO` |

Dates use `YYYY-MM-DD` in the configured study timezone. A malformed CSV document returns 422 and rolls back the whole upload. Unsupported filenames return 415; oversize uploads return 413. Structurally valid files can return 200 with rejected records.

## GPS sampling fields (v1.0.0)

The daily endpoint adds `observed_validity_rate`, `expected_sampling_coverage`, `occupied_sampling_slots`, and `expected_sampling_slots`. JSON rates are fractions from 0 to 1. The existing `screened_gps_ratio` remains as an alias for observed validity. Daily CSV appends these fields and encodes null values as empty cells. A configured day with no samples appears with zero occupied slots and null observed validity, and the participant date selector includes it. The participant observed-day count keeps its prior meaning. Analysis export metadata records the policy under `parameters.expected_sampling`.
