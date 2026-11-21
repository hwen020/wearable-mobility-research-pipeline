"""Spatial metrics on WGS84 traces with travel-speed outlier screening."""
from collections import Counter, defaultdict
from datetime import datetime, time, timedelta, timezone
from math import radians, sin, cos, atan2, sqrt, degrees, isfinite
from statistics import mean
from shapely.geometry import MultiPoint, Point, mapping
import geopandas as gpd

EARTH_RADIUS_KM = 6371.0088
MAX_SPEED_KMH = 120.0  # quality flag, not hard rejection
STAY_RADIUS_M = 120.0
MIN_STAY_MINUTES = 15.0
MAX_GAP_HOURS = 2.0
AREA_BUFFER_M = 100
MAX_AREA_EXTENT_KM = 2000
ALGORITHM_VERSION = "1.2"


def analysis_parameters(sampling=None):
    return {"max_speed_kmh": MAX_SPEED_KMH, "max_gap_hours": MAX_GAP_HOURS,
            "stay_radius_m": STAY_RADIUS_M, "min_stay_min": MIN_STAY_MINUTES,
            "area_buffer_m": AREA_BUFFER_M, "max_area_extent_km": MAX_AREA_EXTENT_KM,
            "expected_sampling": sampling.metadata() if sampling else None}


def day_bounds_utc(day, zone):
    def utc_midnight(value):
        return datetime.combine(value, time.min, zone).astimezone(timezone.utc).replace(tzinfo=None)

    return utc_midnight(day), utc_midnight(day + timedelta(days=1))


def study_date(timestamp, zone=timezone.utc):
    return timestamp.replace(tzinfo=timezone.utc).astimezone(zone).date()


def edge_quality(previous, current, zone):
    hours = (current.timestamp_utc - previous.timestamp_utc).total_seconds() / 3600
    if hours <= 0:
        return 0.0, "nonpositive_interval"
    if study_date(previous.timestamp_utc, zone) != study_date(current.timestamp_utc, zone):
        return 0.0, "day_boundary"
    if hours > MAX_GAP_HOURS:
        return 0.0, "sampling_gap"
    length = haversine_km(previous.latitude, previous.longitude, current.latitude, current.longitude)
    if length / hours > MAX_SPEED_KMH:
        return 0.0, "speed_outlier"
    return length, "repeated_coordinate" if length == 0 else None



def haversine_km(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1)*cos(lat2)*sin(dlon/2)**2
    return 2 * EARTH_RADIUS_KM * atan2(sqrt(a), sqrt(max(0, 1-a)))


def serial_time(t):
    # Database stores normalized naive UTC; attach UTC once for client.
    return t.isoformat() + "Z"


def sorted_points(observations):
    return sorted(observations, key=lambda x: x.timestamp_utc)


def quality_distance(observations, zone=timezone.utc):
    points = sorted_points(observations)
    edges = [edge_quality(previous, current, zone) for previous, current in zip(points, points[1:])]
    return round(sum(length for length, _ in edges), 3), sum(flag == "speed_outlier" for _, flag in edges)


def daily_summary(observations, zone=timezone.utc, *, sampling=None, only_day=None):
    groups = defaultdict(list)
    for point in observations:
        groups[study_date(point.timestamp_utc, zone)].append(point)
    if sampling:
        first = study_date(sampling.start, zone)
        last = study_date(sampling.end - timedelta(microseconds=1), zone)
        days = (only_day,) if only_day else (
            first + timedelta(days=i) for i in range((last - first).days + 1)
        )
        for day in days:
            if first <= day <= last:
                start, end = day_bounds_utc(day, zone)
                if max(start, sampling.start) < min(end, sampling.end):
                    groups.setdefault(day, [])

    result = []
    for day, points in sorted(groups.items()):
        points.sort(key=lambda point: point.timestamp_utc)
        edges = [edge_quality(previous, current, zone)
                 for previous, current in zip(points, points[1:])]
        flags = Counter(flag for _, flag in edges if flag)
        distance = round(sum(length for length, _ in edges), 3)
        hr_values = [p.heart_rate_bpm for p in points if p.heart_rate_bpm is not None]
        validity = round(1 - flags["speed_outlier"] / len(points), 4) if points else None
        occupied, expected = None, None
        if sampling:
            valid_stamps = (point.timestamp_utc for i, point in enumerate(points)
                            if not i or edges[i - 1][1] != "speed_outlier")
            occupied, expected = sampling.counts(*day_bounds_utc(day, zone), valid_stamps)
        result.append({"date": day.isoformat(), "samples": len(points), "steps": sum(p.steps for p in points),
                       "distance_km": distance, "speed_outliers": flags["speed_outlier"],
                       "sampling_gaps": flags["sampling_gap"],
                       "repeated_coordinates": flags["repeated_coordinate"],
                       "screened_gps_ratio": validity,
                       "observed_validity_rate": validity,
                       "expected_sampling_coverage": round(occupied / expected, 4) if expected else None,
                       "occupied_sampling_slots": occupied, "expected_sampling_slots": expected,
                       "algorithm_version": ALGORITHM_VERSION,
                       "avg_heart_rate_bpm": round(mean(hr_values), 1) if hr_values else None})
    return result


def stays(observations, radius_m=STAY_RADIUS_M, min_minutes=MIN_STAY_MINUTES, *, zone=timezone.utc):
    """Contiguous dwell detection; anchor point and stay centroid, not a DBSCAN claim."""
    points = sorted_points(observations)
    result = []
    i = 0
    while i < len(points) - 1:
        j = i + 1
        while j < len(points):
            _, flag = edge_quality(points[j - 1], points[j], zone)
            if flag not in (None, "repeated_coordinate"):
                break
            if haversine_km(points[i].latitude, points[i].longitude,
                            points[j].latitude, points[j].longitude)*1000 > radius_m:
                break
            j += 1
        end = j - 1
        duration = (points[end].timestamp_utc-points[i].timestamp_utc).total_seconds()/60
        if end > i and duration >= min_minutes:
            cluster = points[i:end+1]
            result.append({"visit_index": len(result) + 1,
                           "latitude": round(mean(p.latitude for p in cluster), 6),
                           "longitude": round(mean(p.longitude for p in cluster), 6),
                           "start_utc": serial_time(points[i].timestamp_utc),
                           "end_utc": serial_time(points[end].timestamp_utc),
                           "duration_minutes": round(duration, 1), "samples": len(cluster),
                           "algorithm": "anchor_radius", "algorithm_version": ALGORITHM_VERSION})
            i = end + 1
        else:
            i += 1
    return result


def activity_area(observations, radius_m=AREA_BUFFER_M):
    """Project GPS into local meter CRS using GeoPandas, buffer observations, then hull."""
    points = sorted_points(observations)
    if not points:
        return None
    anchor = points[0]
    if any(haversine_km(anchor.latitude, anchor.longitude, point.latitude, point.longitude)
           > MAX_AREA_EXTENT_KM for point in points[1:]):
        return None
    gs = gpd.GeoSeries([Point(p.longitude, p.latitude) for p in points], crs="EPSG:4326")
    try:
        analysis_crs = gs.estimate_utm_crs()
    except RuntimeError:
        # UTM does not cover the poles. Use a local equal-area projection there.
        latitude = mean(p.latitude for p in points)
        longitude = degrees(atan2(sum(sin(radians(p.longitude)) for p in points),
                                  sum(cos(radians(p.longitude)) for p in points)))
        analysis_crs = f"+proj=laea +lat_0={latitude} +lon_0={longitude} +datum=WGS84 +units=m"
    projected = gs.to_crs(analysis_crs)
    west, south, east, north = projected.total_bounds
    if not all(isfinite(v) for v in (west, south, east, north)) or max(east - west, north - south) > MAX_AREA_EXTENT_KM * 1000:
        return None
    # Convex hull of 100m buffers for stable visible polygons, including single points.
    geom = projected.buffer(radius_m).union_all().convex_hull
    area_km2 = round(geom.area / 1_000_000, 3)
    result_geom = gpd.GeoSeries([geom], crs=projected.crs).to_crs(epsg=4326).iloc[0]
    return {"type": "Feature", "properties": {"kind": "activity_area",
            "area_km2": area_km2, "method": f"convex hull of {radius_m}m projected buffers",
            "algorithm": "projected_buffer_convex_hull", "algorithm_version": ALGORITHM_VERSION,
            "analysis_crs": projected.crs.to_string(), "crs": "EPSG:4326"}, "geometry": mapping(result_geom)}


def geojson_features(observations, *, include_area=True, zone=timezone.utc):
    points = sorted_points(observations)
    features = []
    if not points:
        return {"type": "FeatureCollection", "features": []}
    # Separate line segments on data gaps or implausible speed, avoids false cross-day path.
    segments = []
    segment = [points[0]]
    for prev, point in zip(points, points[1:]):
        _, flag = edge_quality(prev, point, zone)
        if flag not in (None, "repeated_coordinate"):
            if len(segment) > 1:
                segments.append(segment)
            segment = [point]
        else:
            segment.append(point)
    if len(segment) > 1:
        segments.append(segment)
    for idx, segment in enumerate(segments):
        features.append({"type":"Feature", "properties":{"kind":"route","segment":idx+1,
                         "algorithm":"screened_haversine_segments","algorithm_version":ALGORITHM_VERSION},
                         "geometry":{"type":"LineString","coordinates":[[p.longitude,p.latitude] for p in segment]}})
    for kind, point in [("start", points[0]), ("end", points[-1])]:
        features.append({"type":"Feature", "properties":{"kind":kind,"timestamp_utc":serial_time(point.timestamp_utc)},
                         "geometry":{"type":"Point","coordinates":[point.longitude,point.latitude]}})
    for stay in stays(points, zone=zone):
        features.append({"type":"Feature", "properties":{"kind":"stay",**stay},
                         "geometry":{"type":"Point","coordinates":[stay["longitude"],stay["latitude"]]}})
    collection = {"type": "FeatureCollection", "features": features}
    if include_area:
        area = activity_area(points)
        if area is None:
            collection["warnings"] = ["The trajectory is outside the supported local projection extent."]
        else:
            features.append(area)
    return collection
