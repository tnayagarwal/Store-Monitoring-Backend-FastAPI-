from __future__ import annotations

from pathlib import Path
import csv
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert
from datetime import datetime, timezone

from .models import Observation, BusinessHour, StoreTimezone


DATA_DIR = Path("data")


def load_csvs_if_needed(session: Session) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    # If observations already exist, assume data was loaded
    any_obs = session.query(Observation).first()
    if any_obs is not None:
        return

    obs_path = DATA_DIR / "store_status.csv"
    # Accept alternate filenames from dataset variants
    bh_path = DATA_DIR / "business_hours.csv"
    if not bh_path.exists():
        alt_bh = DATA_DIR / "menu_hours.csv"
        if alt_bh.exists():
            bh_path = alt_bh
    tz_path = DATA_DIR / "store_timezone.csv"
    if not tz_path.exists():
        alt_tz = DATA_DIR / "timezones.csv"
        if alt_tz.exists():
            tz_path = alt_tz

    if not (obs_path.exists() and bh_path.exists() and tz_path.exists()):
        # Allow boot without data; report generation will error later
        return

    # Observations
    def parse_ts_utc(value: str) -> datetime:
        v = value.strip()
        if v.endswith("Z"):
            v = v.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(v)
        except Exception:
            # Fallback common formats
            try:
                dt = datetime.strptime(value.strip(), "%Y-%m-%d %H:%M:%S.%f %Z")
            except Exception:
                dt = datetime.strptime(value.strip(), "%Y-%m-%d %H:%M:%S %Z")
        # Normalize to naive UTC
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        # If no tzinfo, assume already UTC naive
        return dt

    with obs_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            rows.append(
                {
                    "store_id": str(row["store_id"]).strip(),
                    "timestamp_utc": parse_ts_utc(str(row["timestamp_utc"])),
                    "status": str(row["status"]).strip().lower(),
                }
            )
    if rows:
        stmt = pg_insert(Observation).values(rows)
        stmt = stmt.on_conflict_do_nothing(index_elements=[Observation.store_id, Observation.timestamp_utc])
        session.execute(stmt)

    # Business hours
    def parse_time(val: str):
        s = str(val).strip()
        for fmt in ("%H:%M:%S", "%H:%M"):
            try:
                return datetime.strptime(s, fmt).time()
            except Exception:
                continue
        raise ValueError(f"Unrecognized time format: {val}")

    with bh_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        bh_rows: list[dict] = []
        for row in reader:
            bh_rows.append(
                {
                    "store_id": str(row["store_id"]).strip(),
                    "day_of_week": int(row.get("dayOfWeek") or row.get("day_of_week")),
                    "start_time_local": parse_time(str(row["start_time_local"])),
                    "end_time_local": parse_time(str(row["end_time_local"])),
                }
            )
    if bh_rows:
        stmt = pg_insert(BusinessHour).values(bh_rows)
        stmt = stmt.on_conflict_do_nothing(
            index_elements=[
                BusinessHour.store_id,
                BusinessHour.day_of_week,
                BusinessHour.start_time_local,
                BusinessHour.end_time_local,
            ]
        )
        session.execute(stmt)

    # Timezones
    with tz_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        tz_rows: list[dict] = []
        for row in reader:
            tz_rows.append(
                {
                    "store_id": str(row["store_id"]).strip(),
                    "timezone_str": str(row.get("timezone_str") or "America/Chicago"),
                }
            )
    if tz_rows:
        stmt = pg_insert(StoreTimezone).values(tz_rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=[StoreTimezone.store_id],
            set_={"timezone_str": stmt.excluded.timezone_str},
        )
        session.execute(stmt)

    session.commit()


