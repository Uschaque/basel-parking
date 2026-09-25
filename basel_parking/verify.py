#!/usr/bin/env python3
"""Independent checks of the shipped snapshot and the main decision example."""
import csv
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
result = json.loads((ROOT / "results.json").read_text(encoding="utf-8"))
assert len(result["audit"]) == 16, "The source audit should cover all 16 current garages"
assert len(result["garages"]) == 9, "The nine reviewed garages should pass the gates"
assert all(len(result["profiles"][key]) == 7 for key in result["garages"])
assert all(all(len(day) == 24 for day in result["profiles"][key].values())
           for key in result["garages"])
assert all(result["evaluation"][key]["n"] > 1000 for key in result["garages"])

# Recompute the most revealing Saturday 16:00 scenario from the original CSV,
# independently of build.py and without using its selection/profile functions.
cutoff = datetime.fromisoformat(result["asof"])
values = defaultdict(list)
raw_rows = 0
with (ROOT / "data" / "all_historical.csv").open(encoding="utf-8-sig", newline="") as stream:
    for row in csv.DictReader(stream, delimiter=";"):
        raw_rows += 1
        if row["id2"] not in ("storchen", "kunstmuseum", "steinen"):
            continue
        moment = datetime.fromisoformat(row["published"]).astimezone(timezone.utc)
        if not cutoff - timedelta(days=182) <= moment <= cutoff:
            continue
        local = moment.astimezone(ZoneInfo("Europe/Zurich"))
        if local.weekday() == 5 and local.hour == 16:
            free, capacity = int(row["free"]), int(row["total"])
            if 0 <= free <= capacity:
                values[row["id2"]].append(free)

for key, observations in values.items():
    published = result["profiles"][key]["5"]["16"]
    assert len(observations) == published["n"]
    assert sum(value < 10 for value in observations) == published["near_full_count"]
    assert round(median(observations)) == published["median"]
assert raw_rows > 200_000
assert result["audit"]["centralbahn"]["included"] is False
assert result["audit"]["rebgasse"]["included"] is False
assert "__EMBEDDED_DATA__" not in (ROOT / "dashboard.html").read_text(encoding="utf-8")
print(f"OK: {raw_rows:,} source rows, 16 audits, 9 garages, independent Saturday check")
