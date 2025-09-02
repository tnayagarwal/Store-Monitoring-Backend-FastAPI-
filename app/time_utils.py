from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, time
from typing import Iterable, List, Tuple
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class Interval:
    start: datetime
    end: datetime

    def clamp(self, window_start: datetime, window_end: datetime) -> "Interval | None":
        s = max(self.start, window_start)
        e = min(self.end, window_end)
        if s >= e:
            return None
        return Interval(s, e)

    def duration_seconds(self) -> float:
        return (self.end - self.start).total_seconds()


def daterange_days(start: datetime, end: datetime, tz: ZoneInfo) -> Iterable[datetime]:
    # Yield midnight-local (tz-aware) datetimes for each day touching [start, end)
    start_aware_utc = start.replace(tzinfo=ZoneInfo("UTC"))
    end_aware_utc = end.replace(tzinfo=ZoneInfo("UTC"))
    cur_local = start_aware_utc.astimezone(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    end_local = end_aware_utc.astimezone(tz)
    while cur_local <= end_local:
        yield cur_local
        cur_local = cur_local + timedelta(days=1)


def local_times_to_utc_intervals(
    day_local_midnight: datetime,
    local_spans: List[Tuple[time, time]],
    tz: ZoneInfo,
) -> List[Interval]:
    intervals: List[Interval] = []
    for start_local, end_local in local_spans:
        start_dt_local = day_local_midnight.replace(
            hour=start_local.hour, minute=start_local.minute, second=start_local.second, microsecond=0
        )
        end_dt_local = day_local_midnight.replace(
            hour=end_local.hour, minute=end_local.minute, second=end_local.second, microsecond=0
        )
        if end_dt_local <= start_dt_local:
            # Wrap past midnight
            first = start_dt_local
            first_end = day_local_midnight.replace(hour=23, minute=59, second=59, microsecond=999000)
            first_utc = first.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
            first_end_utc = first_end.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
            intervals.append(Interval(start=first_utc, end=first_end_utc))
            next_midnight = day_local_midnight + timedelta(days=1)
            second_start = next_midnight.replace(hour=0, minute=0, second=0, microsecond=0)
            second_end = end_dt_local + timedelta(days=1)
            second_start_utc = second_start.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
            second_end_utc = second_end.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
            intervals.append(Interval(start=second_start_utc, end=second_end_utc))
        else:
            start_utc = start_dt_local.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
            end_utc = end_dt_local.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
            intervals.append(Interval(start=start_utc, end=end_utc))
    return intervals


def intersect_intervals(a: Interval, b: Interval) -> Interval | None:
    s = max(a.start, b.start)
    e = min(a.end, b.end)
    if s >= e:
        return None
    return Interval(s, e)


def subtract_datetimes(a: datetime, b: datetime) -> float:
    return (a - b).total_seconds()




