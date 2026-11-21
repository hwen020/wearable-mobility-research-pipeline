# GIS methods and limitations

| Method | Parameters and units |
|---|---|
| Screened Haversine segments | Mean Earth radius 6,371.0088 km. Reject edges faster than 120 km/h, longer than two hours, or crossing study dates. Sum valid edges in km |
| Anchor-radius stay detection | 120 m from anchor for at least 15 minutes. A route discontinuity breaks a stay. Each interval is a separately indexed visit with centroid, UTC arrival/departure, minutes and sample count |
| Projected activity area | Estimate local UTM with GeoPandas; use local equal-area projection outside UTM coverage. Omit the polygon with a warning for unsupported projected extents over 2,000 km across either axis. Buffer by 100 m, union, take the convex hull, and measure km² before reprojecting to EPSG:4326 |
| Segment quality counts | Count excessive sampling gaps, identical consecutive coordinates, and implausible speed edges within each study day |
| Observed Validity Rate | Accepted samples that do not end a speed-flagged edge divided by stored sample count for the study day |

Algorithm version 1.2 is reported with exports. GeoJSON uses longitude/latitude order. The polygon reports its analysis CRS separately. Day boundaries are obtained in the configured IANA zone and filtered against UTC timestamps. Fall-back times with explicit offsets are separate instants.

These methods illustrate local simulated trajectories. The hull can include places outside the route and is sensitive to outliers, projection area and antimeridian crossing. Adjacent-edge screening cannot identify which sample caused a jump. The screened ratio does not estimate adherence to a sampling schedule or count rejected rows as observed samples. Steps and heart rate describe simulated activities.

## Expected Sampling Coverage

Set all three process variables together. The interval is measured in seconds, and window endpoints are offset-aware ISO 8601 instants. Configuration applies to each participant in the synthetic study.

```powershell
$env:GPS_WINDOW_START = "2026-11-16T16:00:00Z"
$env:GPS_WINDOW_END = "2026-11-17T21:05:00Z"
$env:GPS_EXPECTED_INTERVAL_SECONDS = "300"
```

Intersect the half-open observation window with each local study day. Starting at that intersection's start, divide actual elapsed UTC time into successive half-open slots of the expected interval. Count a shortened final slot. Each slot contributes at most one eligible fix. Fixes outside the window and fixes terminating speed-outlier edges cannot fill a slot. Report occupied slots divided by all expected slots. A day with no fixes has zero coverage if scheduled and null observed validity. A day with no expected slots shows N/A.

Slots are elapsed-time intervals. A full spring-forward day in America/Los_Angeles has 23 hourly slots; the fall-back day has 25. The repeated local hour has two distinct UTC slots. This metric measures expected slot occupancy and does not infer device wear-time.
