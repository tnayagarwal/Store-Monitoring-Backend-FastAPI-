from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, time
from pathlib import Path
from typing import Dict, List, Tuple
import csv
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session
from sqlalchemy import func

from .models import Observation, BusinessHour, StoreTimezone, Report
from .time_utils import Interval, local_times_to_utc_intervals, daterange_days, intersect_intervals


DEFAULT_TZ = ZoneInfo("America/Chicago")


@dataclass
class StoreConfig:
    timezone: ZoneInfo
    business_hours_by_dow: Dict[int, List[Tuple[time, time]]]


def _get_reference_now(session: Session) -> datetime:
    # Per instructions: set "now" as max timestamp among observations
    max_dt: datetime | None = session.query(func.max(Observation.timestamp_utc)).scalar()
    if max_dt is None:
        # Fallback to UTC now; report will be empty
        return datetime.utcnow()
    return max_dt


def _load_store_configs(session: Session) -> Dict[str, StoreConfig]:
    # timezones
    tz_map: Dict[str, ZoneInfo] = {}
    for tz in session.query(StoreTimezone).all():
        try:
            tz_map[tz.store_id] = ZoneInfo(tz.timezone_str)
        except Exception:
            tz_map[tz.store_id] = DEFAULT_TZ

    # business hours
    bh_map: Dict[str, Dict[int, List[Tuple[time, time]]]] = defaultdict(lambda: defaultdict(list))
    for bh in session.query(BusinessHour).all():
        bh_map[bh.store_id][bh.day_of_week].append((bh.start_time_local, bh.end_time_local))

    # For stores missing BH, assume 24x7; we will detect missing when computing per-day intervals
    configs: Dict[str, StoreConfig] = {}
    store_ids = {sid for (sid,) in session.query(Observation.store_id).distinct()}
    # Include stores present in BH or TZ tables even if no observations (edge-case)
    store_ids.update([tzid.store_id for tzid in session.query(StoreTimezone).all()])
    store_ids.update([bhid.store_id for bhid in session.query(BusinessHour.store_id).distinct()])
    for store_id in store_ids:
        tzinfo = tz_map.get(store_id, DEFAULT_TZ)
        configs[store_id] = StoreConfig(timezone=tzinfo, business_hours_by_dow=bh_map.get(store_id, {}))
    return configs


def _business_intervals_utc(start_utc: datetime, end_utc: datetime, config: StoreConfig) -> List[Interval]:
    intervals: List[Interval] = []
    tz = config.timezone

    for day_midnight_local in daterange_days(start_utc, end_utc, tz):
        day_dow = day_midnight_local.weekday()  # 0=Monday ... 6=Sunday
        spans = config.business_hours_by_dow.get(day_dow)
        if not spans or len(spans) == 0:
            # If business hours missing for a store: assume 24x7
            spans = [(time(0, 0, 0), time(23, 59, 59))]

        day_intervals = local_times_to_utc_intervals(day_midnight_local, spans, tz)
        # Clamp each to [start_utc, end_utc]
        for iv in day_intervals:
            clamped = iv.clamp(start_utc, end_utc)
            if clamped is not None:
                intervals.append(clamped)
    return intervals


def _interpolate_status(observations: List[Tuple[datetime, str]], window: Interval) -> Tuple[float, float]:
    # Given observations sorted by time covering potentially sparse points,
    # extrapolate piecewise-constant status across the window.
    # Return uptime_seconds, downtime_seconds within window.
    if not observations:
        return 0.0, 0.0

    uptime = 0.0
    downtime = 0.0

    # Start with the status at the first observation; assume it holds from window.start
    idx = 0
    current_time = window.start
    current_status = observations[0][1]

    # Advance to first obs within or after window.start; if earlier obs exist, take last before window.start
    for t, s in observations:
        if t <= window.start:
            current_status = s
            current_time = window.start
            idx += 1
        else:
            break

    # Iterate over remaining observations until window.end
    all_points = [(t, s) for t, s in observations if (t > window.start and t < window.end)]
    for t, s in all_points:
        delta = (t - current_time).total_seconds()
        if current_status == "active":
            uptime += delta
        else:
            downtime += delta
        current_time = t
        current_status = s

    # Tail from last point to window.end
    delta_tail = (window.end - current_time).total_seconds()
    if delta_tail > 0:
        if current_status == "active":
            uptime += delta_tail
        else:
            downtime += delta_tail

    return uptime, downtime


def _compute_store_metrics(session: Session, store_id: str, now_utc: datetime, config: StoreConfig) -> Dict[str, float]:
    # Windows
    one_hour_start = now_utc - timedelta(hours=1)
    one_day_start = now_utc - timedelta(days=1)
    one_week_start = now_utc - timedelta(days=7)

    windows = {
        "last_hour": Interval(one_hour_start, now_utc),
        "last_day": Interval(one_day_start, now_utc),
        "last_week": Interval(one_week_start, now_utc),
    }

    # Fetch observations overlapping the last week window (superset)
    obs_rows = (
        session.query(Observation)
        .filter(Observation.store_id == store_id)
        .filter(Observation.timestamp_utc >= one_week_start - timedelta(hours=2))
        .filter(Observation.timestamp_utc <= now_utc + timedelta(hours=2))
        .order_by(Observation.timestamp_utc.asc())
        .all()
    )
    observations = [(r.timestamp_utc, r.status) for r in obs_rows]

    metrics: Dict[str, float] = {}
    for key, win in windows.items():
        business_intervals = _business_intervals_utc(win.start, win.end, config)
        uptime_total = 0.0
        downtime_total = 0.0
        for iv in business_intervals:
            # Interpolate using all observations but constrained to iv
            # Intersect observation series to this interval by passing window
            up, down = _interpolate_status(observations, iv)
            uptime_total += up
            downtime_total += down

        if key == "last_hour":
            # output in minutes
            metrics["uptime_last_hour_min"] = uptime_total / 60.0
            metrics["downtime_last_hour_min"] = downtime_total / 60.0
        else:
            # output in hours
            suffix = "day" if key == "last_day" else "week"
            metrics[f"uptime_last_{suffix}_hr"] = uptime_total / 3600.0
            metrics[f"downtime_last_{suffix}_hr"] = downtime_total / 3600.0

    return metrics


def generate_report(session: Session, report_id: str) -> None:
    now_utc = _get_reference_now(session)
    configs = _load_store_configs(session)

    rows: List[Dict[str, object]] = []
    for store_id, config in configs.items():
        metrics = _compute_store_metrics(session, store_id, now_utc, config)
        rows.append(
            {
                "store_id": store_id,
                "uptime_last_hour(in minutes)": round(metrics.get("uptime_last_hour_min", 0.0), 2),
                "uptime_last_day(in hours)": round(metrics.get("uptime_last_day_hr", 0.0), 2),
                "update_last_week(in hours)": round(metrics.get("uptime_last_week_hr", 0.0), 2),
                "downtime_last_hour(in minutes)": round(metrics.get("downtime_last_hour_min", 0.0), 2),
                "downtime_last_day(in hours)": round(metrics.get("downtime_last_day_hr", 0.0), 2),
                "downtime_last_week(in hours)": round(metrics.get("downtime_last_week_hr", 0.0), 2),
            }
        )

    out_dir = Path("reports")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"report_{report_id}.csv"
    # Write CSV
    if rows:
        fieldnames = list(rows[0].keys())
    else:
        fieldnames = [
            "store_id",
            "uptime_last_hour(in minutes)",
            "uptime_last_day(in hours)",
            "update_last_week(in hours)",
            "downtime_last_hour(in minutes)",
            "downtime_last_day(in hours)",
            "downtime_last_week(in hours)",
        ]
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    rep: Report | None = session.get(Report, report_id)
    if rep is not None:
        rep.status = "Complete"
        rep.completed_at = datetime.utcnow()
        rep.file_path = str(out_path)
        rep.error_message = None
        session.commit()


