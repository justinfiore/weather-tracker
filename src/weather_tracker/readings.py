"""Eastern calendar targets and source-precision temperatures."""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal
from zoneinfo import ZoneInfo

EASTERN = ZoneInfo("America/New_York")
Unit = Literal["F", "C"]
FORECAST_SOURCES = ("weather.com", "AccuWeather", "WTAE")


def round_to_source(value: Decimal, source: Decimal) -> Decimal:
    """Retain the source's decimal places, rounding ties away from zero."""
    quantum = Decimal(1).scaleb(source.as_tuple().exponent)
    return value.quantize(quantum, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Targets:
    observed_at: datetime
    today: date = field(init=False)
    tomorrow: date = field(init=False)
    five_day: date = field(init=False)
    previous: date = field(init=False)

    def __post_init__(self):
        if self.observed_at.tzinfo is None:
            raise ValueError("Observation time must include a timezone")
        local = self.observed_at.astimezone(EASTERN)
        object.__setattr__(self, "observed_at", local)
        for name, offset in (("today", 0), ("tomorrow", 1), ("five_day", 5), ("previous", -1)):
            object.__setattr__(self, name, local.date() + timedelta(days=offset))


@dataclass(frozen=True)
class Temperature:
    native_unit: Unit
    f: Decimal
    c: Decimal

    @classmethod
    def from_native(cls, value: str | None, unit: Unit):
        if value is None:
            return None
        native = Decimal(value)
        if not native.is_finite():
            raise ValueError("Temperature must be finite")
        if unit == "F":
            converted = round_to_source((native - 32) * 5 / 9, native)
            return cls(unit, native, converted)
        if unit == "C":
            converted = round_to_source(native * 9 / 5 + 32, native)
            return cls(unit, converted, native)
        raise ValueError("Unknown temperature unit")


@dataclass(frozen=True)
class Daily:
    high: Temperature | None = None
    low: Temperature | None = None

    @property
    def available(self):
        return self.high is not None and self.low is not None


@dataclass
class Reading:
    source: str
    observed_at: datetime
    days: dict[date, Daily]
    error: str | None = None

    @property
    def available(self):
        return any(day.available for day in self.days.values())
