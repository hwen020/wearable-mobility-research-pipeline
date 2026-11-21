# Data dictionary

## CSV schema 1

| Field | Meaning |
|---|---|
| `participant_id` | Fabricated pseudonym, 3–32 ASCII letters, digits, hyphens or underscores |
| `timestamp_utc` | ISO 8601 timestamp with Z or an explicit offset, normalized to UTC; imports reject timestamps more than 366 days ahead of the import clock |
| `latitude`, `longitude` | Finite WGS84 decimal degrees, within ±90 / ±180 |
| `steps` | Interval count, integer 0–100,000 |
| `heart_rate_bpm` | Optional integer 30–240 bpm |
| `source` | `synthetic`, `simulated`, or `demo`; omitted values default to `synthetic` for existing callers |

Use a UTF-8 file with the listed column names. The participant/timestamp pair defines identity; duplicate records leave the initially accepted observation unchanged.

## Quality and audit

The batch SHA-256 is computed from the exact uploaded bytes. Duration measures application processing through the database flush, excluding network transfer and commit. The diagnostic row ordinal starts at 2 after the header and counts logical CSV records. Invalid coordinates, malformed values and unsupported sources yield human-readable reasons. Duplicates retain the first accepted observation and record their own audit outcome. Accepted snapshots preserve the original CSV field strings alongside normalized observations. Rejected and duplicate counts describe each attempt independently. Filename and accepted field values are stored, so use fabricated filenames and fixtures.

## Daily GPS metrics

| Field | Definition |
|---|---|
| `observed_validity_rate` | Accepted stored GPS observations that do not terminate a speed-outlier edge, divided by accepted stored GPS observations that day. Null when none exist. `screened_gps_ratio` is the legacy alias. |
| `expected_sampling_coverage` | Occupied eligible sampling slots divided by expected slots. Null when no schedule applies. Zero when scheduled slots exist and none is occupied. |
| `occupied_sampling_slots` | Distinct scheduled slots containing at least one valid observed GPS fix. |
| `expected_sampling_slots` | Number of scheduled time slots in the intersection of the local study day and the configured observation window. |

Rejected CSV rows are outside observed validity. A rejected or missing fix leaves a scheduled slot empty unless another eligible fix fills it.
