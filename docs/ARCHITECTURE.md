# Architecture and database

```text
CSV upload (spooled file)
  -> SHA-256 and byte limit
  -> UTF-8 CSV validation, UTC normalization, chunks of 400
  -> bounded participant/timestamp query and unique constraint
  -> single transaction (participants, observations, batch, row diagnostics)
  -> FastAPI summaries, quality review, GeoJSON and CSV
  -> Leaflet map and daily research console
```

| Table | Purpose and constraints |
|---|---|
| `participants` | Synthetic pseudonym primary key and creation time |
| `observations` | Participant foreign key, UTC timestamp, WGS84 coordinates, steps, optional heart rate, source. Unique participant and timestamp; time and participant indexes |
| `import_batches` | Filename, UTC creation time, counters, SHA-256, duration, ingestion source and schema version |
| `import_diagnostics` | Batch foreign key, CSV record number, outcome and safe reason. Composite primary key |
| `studies`, `study_participants` | Single synthetic study and its participant assignments |
| `devices` | Participant and declared synthetic source association |
| `observation_provenance` | Accepted observation key, batch ID, source CSV record ordinal, and validated original field text |
| `analysis_runs` | Participant, study date, input fingerprint, algorithm/schema version, parameters and daily result |
| `demo_identity` | Marker for SQLite databases explicitly opted in while empty |
| `alembic_version` | Applied database revision |

The first migration adopts legacy tables and creates the original schema on an empty database. The next revisions add nullable import audit columns, sanitized diagnostics and the demo marker table. Later revisions register existing participants/sources and retain validated raw field text for new observations. MySQL timestamps support microsecond precision. Historical batches have unknown checksum, source and duration; their exact accepted source rows cannot be reconstructed. Invalid CSV records persist a reason and record ordinal, with no submitted field values.

Analysis reads accepted observations directly. Route segments and spatial quality findings are derived when queried. Full-study endpoints still load their matching observations. The observation preview applies SQL date filters and a limit. Single-study and declared-source links are maintained on ingestion. The daily analysis CLI records an input fingerprint and result. Cohort management and historical persistence of derived observation-level flags remain future work.
