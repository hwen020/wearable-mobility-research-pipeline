"""Deterministic, clearly synthetic GPS/steps/HR rows; never personal data."""
import argparse
import csv
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from .db import engine, upgrade_schema, SessionLocal
from .pipeline import import_csv_stream
from .models import Observation
from .demo_restore import mark_empty_database
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
DEMO_PATH = ROOT / "data" / "synthetic_wearable.csv"


def create_demo_csv(path=DEMO_PATH):
    path = Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    # Two 5-hour UTC observation windows, with stable dwell segments and walking segments.
    # Fictional trajectories roughly around public LA districts; not collected from people.
    centers=[(34.0221,-118.2845),(34.0570,-118.2460),(34.1397,-118.0353)]
    dates=[datetime(2026,11,16,16,0,tzinfo=timezone.utc),datetime(2026,11,17,16,0,tzinfo=timezone.utc)]
    with path.open("w",newline="",encoding="utf-8") as file:
        writer=csv.writer(file)
        writer.writerow(["participant_id","timestamp_utc","latitude","longitude","steps","heart_rate_bpm","source"])
        for k,(lat0,lon0) in enumerate(centers):
            for day,date in enumerate(dates):
                for i in range(61):
                    t=date+timedelta(minutes=5*i)
                    if i<12:
                        x=y=0.0
                        jitter=0.000025*math.sin(i+k)
                    elif i<32:
                        progress=(i-11)/20
                        x=0.015*progress*(1+0.1*k)
                        y=0.009*progress
                        jitter=0.000018*math.sin(i)
                    elif i<46:
                        x=0.015*(1+0.1*k)
                        y=0.009
                        jitter=0.000027*math.cos(i+k)
                    else:
                        progress=(i-45)/15
                        x=0.015*(1+0.1*k)*(1-progress)
                        y=0.009*(1-progress)
                        jitter=0.00002*math.cos(i)
                    lat=lat0+y+jitter+day*0.001
                    lon=lon0+x-jitter+day*0.001
                    steps=(0 if i<12 or 32<=i<46 else 90+((i+k+day)%8)*15)
                    hr=66+(i%6) if steps==0 else 93+(i%7)*3
                    writer.writerow([f"SYN-P{k+1:03d}",t.isoformat().replace("+00:00","Z"),
                                     f"{lat:.6f}",f"{lon:.6f}",steps,hr,"synthetic"])
    return path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mark-demo", action="store_true",
                        help="Mark an empty SQLite database as eligible for demo restoration")
    args = parser.parse_args()
    if args.mark_demo and engine.dialect.name != "sqlite":
        parser.error("--mark-demo requires SQLite")
    upgrade_schema()
    with SessionLocal.begin() as session:
        if args.mark_demo:
            try:
                mark_empty_database(session)
            except ValueError as exc:
                parser.error(str(exc))
        path = create_demo_csv()
        if session.scalar(select(Observation.id).where(Observation.participant_id == "SYN-P001").limit(1)):
            print("Synthetic demo already present; preserving database and import history.")
        else:
            with path.open("rb") as file:
                report = import_csv_stream(session, file, path.name, source="demo_seed")
            print(f"Demo import: {report}")
    print("Open http://127.0.0.1:8000")


if __name__ == "__main__":
    main()
