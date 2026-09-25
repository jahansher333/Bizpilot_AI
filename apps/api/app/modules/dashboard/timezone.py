"""Timezone and period resolution utilities for deterministic dashboard queries (DASH-001)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from enum import StrEnum
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


DEFAULT_TIMEZONE = "Asia/Karachi"


class DashboardPeriod(StrEnum):
    TODAY = "today"
    YESTERDAY = "yesterday"
    THIS_WEEK = "this_week"
    THIS_MONTH = "this_month"
    CUSTOM = "custom"


@dataclass(frozen=True)
class PeriodRange:
    """Resolved UTC query boundaries with local representation metadata."""

    period: str
    start_utc: datetime
    end_utc: datetime
    timezone_name: str
    local_start_date: date
    local_end_date: date


def get_zone_info(tz_name: str | None) -> ZoneInfo:
    """Safely obtain a ZoneInfo instance with fallback to DEFAULT_TIMEZONE."""
    if not tz_name or not tz_name.strip():
        return ZoneInfo(DEFAULT_TIMEZONE)
    try:
        return ZoneInfo(tz_name.strip())
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        return ZoneInfo(DEFAULT_TIMEZONE)


def resolve_period_range(
    period: str | DashboardPeriod,
    tz_name: str = DEFAULT_TIMEZONE,
    custom_start_date: date | None = None,
    custom_end_date: date | None = None,
    reference_utc: datetime | None = None,
) -> PeriodRange:
    """Resolve a logical dashboard period into exact UTC start and end bounds.

    Bounds are computed with respect to the organization's local date calendar:
    - start: 00:00:00.000000 on local_start_date
    - end: 23:59:59.999999 on local_end_date

    Then converted to UTC for database comparison.
    """
    tz = get_zone_info(tz_name)
    effective_tz_name = tz.key

    now_utc = reference_utc or datetime.now(timezone.utc)
    local_now = now_utc.astimezone(tz)
    local_today = local_now.date()

    period_str = str(period).lower().strip()

    if period_str == DashboardPeriod.TODAY:
        start_date = local_today
        end_date = local_today
    elif period_str == DashboardPeriod.YESTERDAY:
        yesterday = local_today - timedelta(days=1)
        start_date = yesterday
        end_date = yesterday
    elif period_str == DashboardPeriod.THIS_WEEK:
        # Monday is day 0 in Python weekday()
        start_date = local_today - timedelta(days=local_today.weekday())
        end_date = local_today
    elif period_str == DashboardPeriod.THIS_MONTH:
        start_date = local_today.replace(day=1)
        end_date = local_today
    elif period_str == DashboardPeriod.CUSTOM:
        if not custom_start_date or not custom_end_date:
            raise ValueError("custom_start_date and custom_end_date are required for custom period")
        if custom_start_date > custom_end_date:
            raise ValueError("custom_start_date cannot be after custom_end_date")
        start_date = custom_start_date
        end_date = custom_end_date
    else:
        # Fallback to TODAY for unsupported strings
        period_str = DashboardPeriod.TODAY.value
        start_date = local_today
        end_date = local_today

    local_start_dt = datetime.combine(start_date, time.min, tzinfo=tz)
    local_end_dt = datetime.combine(end_date, time.max, tzinfo=tz)

    start_utc = local_start_dt.astimezone(timezone.utc)
    end_utc = local_end_dt.astimezone(timezone.utc)

    return PeriodRange(
        period=period_str,
        start_utc=start_utc,
        end_utc=end_utc,
        timezone_name=effective_tz_name,
        local_start_date=start_date,
        local_end_date=end_date,
    )
