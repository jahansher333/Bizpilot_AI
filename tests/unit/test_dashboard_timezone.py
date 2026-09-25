"""Unit tests for dashboard timezone and period resolution (DASH-001)."""

from datetime import date, datetime, timezone
import pytest
from zoneinfo import ZoneInfo

from app.modules.dashboard.timezone import (
    DEFAULT_TIMEZONE,
    DashboardPeriod,
    get_zone_info,
    resolve_period_range,
)


def test_get_zone_info_fallback():
    assert get_zone_info(None).key == DEFAULT_TIMEZONE
    assert get_zone_info("").key == DEFAULT_TIMEZONE
    assert get_zone_info("Invalid/Zone_Name").key == DEFAULT_TIMEZONE
    assert get_zone_info("UTC").key == "UTC"
    assert get_zone_info("Asia/Karachi").key == "Asia/Karachi"


def test_resolve_period_range_today():
    # 2026-09-26 12:00:00 UTC is 17:00:00 in Asia/Karachi (+05:00)
    ref_utc = datetime(2026, 9, 26, 12, 0, 0, tzinfo=timezone.utc)
    result = resolve_period_range(DashboardPeriod.TODAY, "Asia/Karachi", reference_utc=ref_utc)

    assert result.period == "today"
    assert result.timezone_name == "Asia/Karachi"
    assert result.local_start_date == date(2026, 9, 26)
    assert result.local_end_date == date(2026, 9, 26)

    # 2026-09-26 00:00:00 PKT is 2026-09-25 19:00:00 UTC
    expected_start = datetime(2026, 9, 25, 19, 0, 0, tzinfo=timezone.utc)
    # 2026-09-26 23:59:59.999999 PKT is 2026-09-26 18:59:59.999999 UTC
    expected_end = datetime(2026, 9, 26, 18, 59, 59, 999999, tzinfo=timezone.utc)

    assert result.start_utc == expected_start
    assert result.end_utc == expected_end


def test_resolve_period_range_yesterday():
    ref_utc = datetime(2026, 9, 26, 12, 0, 0, tzinfo=timezone.utc)
    result = resolve_period_range(DashboardPeriod.YESTERDAY, "Asia/Karachi", reference_utc=ref_utc)

    assert result.period == "yesterday"
    assert result.local_start_date == date(2026, 9, 25)
    assert result.local_end_date == date(2026, 9, 25)

    expected_start = datetime(2026, 9, 24, 19, 0, 0, tzinfo=timezone.utc)
    expected_end = datetime(2026, 9, 25, 18, 59, 59, 999999, tzinfo=timezone.utc)

    assert result.start_utc == expected_start
    assert result.end_utc == expected_end


def test_resolve_period_range_this_week():
    # 2026-09-26 is a Saturday (weekday 5). Monday was 2026-09-21.
    ref_utc = datetime(2026, 9, 26, 12, 0, 0, tzinfo=timezone.utc)
    result = resolve_period_range(DashboardPeriod.THIS_WEEK, "Asia/Karachi", reference_utc=ref_utc)

    assert result.period == "this_week"
    assert result.local_start_date == date(2026, 9, 21)
    assert result.local_end_date == date(2026, 9, 26)

    expected_start = datetime(2026, 9, 20, 19, 0, 0, tzinfo=timezone.utc)
    assert result.start_utc == expected_start


def test_resolve_period_range_this_month():
    ref_utc = datetime(2026, 9, 26, 12, 0, 0, tzinfo=timezone.utc)
    result = resolve_period_range(DashboardPeriod.THIS_MONTH, "Asia/Karachi", reference_utc=ref_utc)

    assert result.period == "this_month"
    assert result.local_start_date == date(2026, 9, 1)
    assert result.local_end_date == date(2026, 9, 26)

    # 2026-09-01 00:00:00 PKT is 2026-08-31 19:00:00 UTC
    expected_start = datetime(2026, 8, 31, 19, 0, 0, tzinfo=timezone.utc)
    assert result.start_utc == expected_start


def test_resolve_period_range_custom():
    start_d = date(2026, 9, 10)
    end_d = date(2026, 9, 15)
    result = resolve_period_range(
        DashboardPeriod.CUSTOM,
        "Asia/Karachi",
        custom_start_date=start_d,
        custom_end_date=end_d,
    )

    assert result.period == "custom"
    assert result.local_start_date == start_d
    assert result.local_end_date == end_d

    expected_start = datetime(2026, 9, 9, 19, 0, 0, tzinfo=timezone.utc)
    expected_end = datetime(2026, 9, 15, 18, 59, 59, 999999, tzinfo=timezone.utc)
    assert result.start_utc == expected_start
    assert result.end_utc == expected_end


def test_resolve_period_range_custom_validation():
    with pytest.raises(ValueError, match="required for custom period"):
        resolve_period_range(DashboardPeriod.CUSTOM, "Asia/Karachi")

    with pytest.raises(ValueError, match="cannot be after custom_end_date"):
        resolve_period_range(
            DashboardPeriod.CUSTOM,
            "Asia/Karachi",
            custom_start_date=date(2026, 9, 20),
            custom_end_date=date(2026, 9, 10),
        )
