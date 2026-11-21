# Product Specification — Wearable Mobility Research Pipeline

## Origin and positioning

This is a portfolio project scoped from a discussion about improving geospatial research-programmer readiness, including fit with the USC Research Programmer II (REQ20182164) profile. It is **not** affiliated with USC, Fitbit, a hospital, or a research study. Official posting: https://usccareers.usc.edu/en/job/los-angeles/research-programmer-ii/1209/102774489040

**Users** (demo): research software engineers, data analysts, geospatial/health activity researchers reviewing simulated location and activity data.

## Core user journeys v0.1

1. Open app with no credentials; view 3 fictitious participant IDs, 366 observations and map.
2. Choose participant and UTC day; map shows routes, two or more stay clusters, area footprint and start/end markers.
3. Inspect steps, distance, quality anomaly counts, UTC day-level metrics.
4. Upload sample CSV, receive accepted/duplicate/rejected counts with row-level diagnostics. Uploading same file again creates no new observation rows.
5. Download a participant's synthetic rows as CSV and inspect Swagger endpoints.

## Logical design

- Entity `Participant`: synthetic pseudonym only, created time.
- Entity `Observation`: participant ID, normalized UTC timestamp, WGS84 lat/lon, interval steps, heart rate, declared synthetic source. Unique `(participant_id,timestamp_utc)`.
- Entity `ImportBatch`: file name, accepted, rejected, duplicate counters and time.
- GeoJSON: EPSG:4326 output with properties to label start, end, route, dwell, projected activity area.
- UI: server-rendered static JS, Leaflet; FastAPI; GeoPandas and SQLAlchemy; SQLite by default.

## Statistical method disclosure

- Distance: pairwise Haversine across consecutive points <=2 hours apart; segments implying speed >120 km/h are flagged and excluded.
- Stay points: contiguous points within 120 m of an anchor for at least 15 minutes. This is a rule-based detector, not statistically calibrated.
- Area: form 100 m buffers around WGS84 coordinates after transforming them into local UTM meters, union, convex hull, transform back to WGS84, report km². It is an illustrative activity-area proxy.
- Heart rate: unweighted arithmetic mean of available readings per UTC day. No inference about health.
- Steps: sum of independent per-record interval counts, not Fitbit daily-cumulative counts.

## Quality and limits

v0.1 upload is local-only, <=5 MB <=50,000 rows, first 20 error details returned. It validates timestamp timezone, geographic coordinate bounds, steps, plausible HR, synthetic source and deduplicates observations. No longitudinal device sync, clinical validation or auth. Large-scale ingestion and research-level privacy controls are future work.

## Academic and hiring integrity

A demonstrated project can substantiate coding familiarity with geospatial data, but **cannot substitute for 3 years of professional experience, proven actual Fitbit integration or prior paid research-project participation**. Resume bullets must match passing functionality.
