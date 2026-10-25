from datetime import datetime
from decimal import Decimal

import pytest

from weather_tracker.readings import EASTERN, Targets, Temperature, round_to_source


@pytest.mark.parametrize("instant, expected", [
    ("2026-10-26T00:30:00-04:00", ("2026-10-26", "2026-10-27", "2026-10-31", "2026-10-25")),
    ("2026-10-26T03:30:00+00:00", ("2026-10-25", "2026-10-26", "2026-10-30", "2026-10-24")),
    ("2026-11-01T06:30:00+00:00", ("2026-11-01", "2026-11-02", "2026-11-06", "2026-10-31")),
    ("2026-12-31T23:30:00-05:00", ("2026-12-31", "2027-01-01", "2027-01-05", "2026-12-30")),
])
def test_eastern_calendar(instant, expected):
    targets = Targets(datetime.fromisoformat(instant))
    assert targets.observed_at.tzinfo == EASTERN
    assert tuple(str(getattr(targets, key)) for key in ("today", "tomorrow", "five_day", "previous")) == expected


@pytest.mark.parametrize("value, unit, f, c", [
    ("69", "F", "69", "21"), ("69.4", "F", "69.4", "20.8"),
    ("69.40", "F", "69.40", "20.78"), ("20", "C", "68", "20"),
    ("7", "C", "45", "7"), ("0.25", "C", "32.45", "0.25"),
    ("-17.75", "C", "0.05", "-17.75"),
    ("0.025", "C", "32.045", "0.025"),
])
def test_precision(value, unit, f, c):
    result = Temperature.from_native(value, unit)
    assert result.native_unit == unit
    assert str(result.f) == f
    assert str(result.c) == c


def test_missing_is_not_zero():
    assert Temperature.from_native(None, "F") is None
    assert Temperature.from_native("0", "F").f == Decimal(0)


@pytest.mark.parametrize("value, native, expected", [
    ("2.5", "69", "3"), ("-2.5", "69", "-3"),
    ("1.25", "69.4", "1.3"), ("-1.25", "69.4", "-1.3"),
])
def test_rounding_ties_away_from_zero(value, native, expected):
    assert str(round_to_source(Decimal(value), Decimal(native))) == expected
