#!/usr/bin/env python3
"""Build a reproducible, standalone Basel parking decision dashboard.

Usage: python build.py [--refresh]
Source: https://data.bs.ch/explore/dataset/100014/
"""
import argparse
import bisect
import csv
import json
import math
import statistics
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "all_historical.csv"
ZONE = ZoneInfo("Europe/Zurich")
LOOKBACK = timedelta(days=182)
HOLDOUT = timedelta(days=56)
NEAR_FULL = 10  # Below 10 spaces reported free.
MAX_INVALID_SHARE = .01
MAX_OVERNIGHT_ZERO_SHARE = .05
# Verified on the official parking pages, 25 September 2026; linked in the dashboard.
CLEARANCE_M = {"aeschen": 1.90, "badbahnhof": 2.20, "bahnhofsued": 1.95,
               "city": 2.10, "elisabethen": 2.10, "europe": 1.90,
               "kunstmuseum": 2.05, "steinen": 2.10, "storchen": 1.90}
# Coordinates from OpenStreetMap Nominatim, 25 September 2026.
DESTINATIONS = {
    "rathaus": {"label": "Rathaus / Marktplatz", "lat": 47.5582611, "lon": 7.5885155},
    "sbb": {"label": "Gare Basel SBB", "lat": 47.5476225, "lon": 7.5896417},
    "messe": {"label": "Messeplatz", "lat": 47.5640599, "lon": 7.6011041},
    "museum": {"label": "Kunstmuseum", "lat": 47.5539294, "lon": 7.5944513},
}


def refresh():
    """Download a full export atomically so interruptions keep the last good copy."""
    DATA.parent.mkdir(exist_ok=True)
    base = "https://data.bs.ch/api/explore/v2.1/catalog/datasets/100014/exports/csv"
    # Enough history for the 182-day profile plus the 56-day rolling evaluation.
    where = "published >= now(days=-240)"
    url = base + "?" + urllib.parse.urlencode({
        "where": where,
        "select": "published,id2,name,address,free,total,geo_point_2d",
    })
    temporary = DATA.with_suffix(".tmp")
    try:
        with urllib.request.urlopen(url, timeout=180) as response, temporary.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
        if temporary.stat().st_size < 100_000:
            raise RuntimeError("Unexpectedly small API export")
        temporary.replace(DATA)
    finally:
        if temporary.exists():
            temporary.unlink()


def load():
    points = defaultdict(list)
    metadata = {}
    audit = defaultdict(lambda: {"rows": 0, "invalid": 0, "night_count": 0,
                                 "night_zero": 0, "duplicate": 0})
    seen = set()
    with DATA.open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source, delimiter=";"):
            key = row.get("id2", "")
            if not key:
                continue
            counters = audit[key]
            counters["rows"] += 1
            try:
                stamp = datetime.fromisoformat(row["published"]).astimezone(timezone.utc)
                free, total = int(row["free"]), int(row["total"])
            except (ValueError, TypeError, KeyError):
                counters["invalid"] += 1
                continue
            if free < 0 or total <= 0 or free > total:
                counters["invalid"] += 1
                continue
            if (key, stamp) in seen:
                counters["duplicate"] += 1
                continue
            seen.add((key, stamp))
            local = stamp.astimezone(ZONE)
            if local.hour < 6:
                counters["night_count"] += 1
                counters["night_zero"] += int(free == 0)
            points[key].append((stamp, free))
            if key not in metadata:
                try:
                    lat, lon = map(float, row.get("geo_point_2d", "").split(","))
                except (ValueError, TypeError):
                    lat = lon = None
                metadata[key] = {"name": row.get("name") or key,
                                 "address": row.get("address") or "",
                                 "capacity": total, "lat": lat, "lon": lon}
    included = {}
    report = {}
    for key, counters in sorted(audit.items()):
        bad = counters["invalid"] / counters["rows"]
        night = counters["night_zero"] / counters["night_count"] if counters["night_count"] else 1
        reasons = []
        if bad > MAX_INVALID_SHARE:
            reasons.append(f"{bad:.1%} de valeurs impossibles ou sans capacité")
        if night > MAX_OVERNIGHT_ZERO_SHARE:
            reasons.append(f"{night:.1%} de zéros entre 00 h et 06 h : cause incertaine")
        if len(points[key]) < 1000 or not metadata.get(key, {}).get("lat"):
            reasons.append("historique ou localisation insuffisants")
        if key not in CLEARANCE_M:
            reasons.append("hauteur de passage non vérifiée")
        report[key] = {**counters, "name": metadata.get(key, {}).get("name", key),
                       "invalid_pct": round(100 * bad, 1), "night_zero_pct": round(100 * night, 1),
                       "included": not reasons, "reasons": reasons}
        if not reasons:
            points[key].sort()
            included[key] = points[key]
    if len(included) < 3:
        raise RuntimeError("Too few garages passed the data quality checks")
    return included, metadata, report


def wilson_interval(successes, n):
    """95% interval for a sample share, not a calibrated forecast interval."""
    z = 1.96
    p = successes / n
    denom = 1 + z * z / n
    midpoint = (p + z * z / (2 * n)) / denom
    half = z / denom * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return round(max(0, midpoint - half), 3), round(min(1, midpoint + half), 3)


def profile(history):
    values = [free for _, free in history]
    if len(values) < 12:
        return None
    values.sort()
    hits = sum(v < NEAR_FULL for v in values)
    low, high = wilson_interval(hits, len(values))
    return {"n": len(values), "median": round(statistics.median(values)),
            "p10": values[int((len(values) - 1) * .1)],
            "near_full_count": hits, "near_full": round(hits / len(values), 3),
            "ci_low": low, "ci_high": high}


def build():
    points, metadata, audit = load()
    cutoff = max(stamp for rows in points.values() for stamp, _ in rows)
    groups = {}
    for garage, rows in points.items():
        for stamp, free in rows:
            local = stamp.astimezone(ZONE)
            groups.setdefault((garage, local.weekday(), local.hour), []).append((stamp, free))
    # UTC ordering handles the repeated local hour when daylight-saving time ends.
    for rows in groups.values():
        rows.sort()
    group_times = {key: [stamp for stamp, _ in series] for key, series in groups.items()}

    def previous(garage, day, hour, at):
        key = (garage, day, hour)
        rows = groups.get(key, [])
        stamps = group_times.get(key, [])
        right = bisect.bisect_left(stamps, at)
        left = bisect.bisect_left(stamps, at - LOOKBACK)
        return rows[left:right]

    profiles = {}
    for garage in points:
        profiles[garage] = {}
        for day in range(7):
            profiles[garage][str(day)] = {}
            for hour in range(24):
                sample = previous(garage, day, hour, cutoff + timedelta(seconds=1))
                profiles[garage][str(day)][str(hour)] = profile(sample)

    evaluation = {}
    for garage, rows in points.items():
        all_times = [stamp for stamp, _ in rows]
        event_prefix = [0]
        for _, free in rows:
            event_prefix.append(event_prefix[-1] + int(free < NEAR_FULL))
        count = model_err = weekly_err = model_brier = global_brier = 0
        event_count = 0
        # Rolling-origin test: for every observation, only earlier data is used.
        for stamp, actual in rows:
            if not (cutoff - HOLDOUT < stamp <= cutoff):
                continue
            local = stamp.astimezone(ZONE)
            sample = previous(garage, local.weekday(), local.hour, stamp)
            estimate = profile(sample)
            if estimate is None:
                continue
            weekly = sample[-1][1]  # The previous occurrence of this local weekday/hour.
            left = bisect.bisect_left(all_times, stamp - LOOKBACK)
            right = bisect.bisect_left(all_times, stamp)
            global_rate = (event_prefix[right] - event_prefix[left]) / (right - left)
            event = int(actual < NEAR_FULL)
            count += 1
            event_count += event
            model_err += abs(estimate["median"] - actual)
            weekly_err += abs(weekly - actual)
            model_brier += (estimate["near_full"] - event) ** 2
            global_brier += (global_rate - event) ** 2
        evaluation[garage] = {
            "n": count, "actual_near_full_pct": round(100 * event_count / count, 1),
            "mae_median": round(model_err / count, 1),
            "mae_previous_week": round(weekly_err / count, 1),
            "brier_slot": round(model_brier / count, 3),
            "brier_garage": round(global_brier / count, 3),
        }

    payload = {
        "asof": cutoff.isoformat(), "lookback_days": LOOKBACK.days,
        "holdout_start": (cutoff - HOLDOUT).isoformat(),
        "threshold": NEAR_FULL, "garages": {}, "profiles": profiles,
        "evaluation": evaluation, "audit": audit, "destinations": DESTINATIONS,
        "quality_rules": {"max_invalid_share": MAX_INVALID_SHARE,
                          "max_overnight_zero_share": MAX_OVERNIGHT_ZERO_SHARE},
    }
    for key in points:
        payload["garages"][key] = {**metadata[key], "valid_rows": len(points[key]),
                                    "clearance_m": CLEARANCE_M[key],
                                    "official_url": f"https://www.parkleitsystem-basel.ch/parkhaus/{key}.html"}
    (ROOT / "results.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    from build_site import build_site
    build_site()
    print(f"Built dashboard; {len(points)} garages included / {len(audit)} audited; last {cutoff.isoformat()}")
    for key, result in evaluation.items():
        print(key, result)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true", help="Fetch a fresh full export from Basel-Stadt")
    args = parser.parse_args()
    if args.refresh or not DATA.exists():
        refresh()
    build()
