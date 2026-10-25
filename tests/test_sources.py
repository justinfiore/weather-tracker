from datetime import datetime

import pytest

from weather_tracker.readings import Targets
from weather_tracker.sources import ParseError, parse_forecast, parse_nws

TARGETS = Targets(datetime.fromisoformat("2026-10-25T06:00:00-04:00"))


@pytest.mark.parametrize("source, fixture, expected", [
    ("weather.com", "weather", ("70", "47", "71", "48")),
    ("AccuWeather", "accuweather", ("72", "47", "72", "51")),
    ("WTAE", "wtae", ("69", "40", "70", "48")),
])
def test_saved_rendered_forecasts(page, fixture_html, source, fixture, expected):
    page.set_content(fixture_html(fixture))
    result = parse_forecast(page, source, TARGETS)
    assert result.error is None
    assert result.observed_at == TARGETS.observed_at
    assert tuple(str(temp.f) for day in result.days.values() for temp in (day.high, day.low)) == expected
    assert all(temp.native_unit == "F" for day in result.days.values() for temp in (day.high, day.low))


def test_accuweather_missing_plus_five_keeps_tomorrow(page, fixture_html):
    page.set_content(fixture_html("accuweather"))
    # The fifth card is October 29, not October 30. Removing October 30
    # must not make the adapter substitute the fifth card's temperatures.
    page.locator('.daily-forecast-card').filter(has=page.locator('.sub', has_text='10/30')).evaluate('(e) => e.remove()')
    result = parse_forecast(page, "AccuWeather", TARGETS)
    assert result.days[TARGETS.tomorrow].high.f == 72
    assert not result.days[TARGETS.five_day].available
    assert "2026-10-30" in result.error


def test_nws_summary_date_and_observed_not_record_values(page, fixture_html):
    page.set_content(fixture_html("nws"))
    result = parse_nws(page, TARGETS)
    day = result.days[TARGETS.previous]
    assert result.error is None
    assert (day.high.f, day.high.c, day.low.f, day.low.c) == (63, 17, 39, 4)
    later = Targets(datetime.fromisoformat("2026-10-26T06:00:00-04:00"))
    stale = parse_nws(page, later)
    assert not stale.available
    assert "2026-10-25" in stale.error


def test_wrong_location_is_not_used(page, fixture_html):
    page.set_content(fixture_html("weather").replace("Pittsburgh, Pennsylvania", "Philadelphia, Pennsylvania"))
    with pytest.raises(ParseError, match="location"):
        parse_forecast(page, "weather.com", TARGETS)


def test_weather_month_rollover_uses_dated_labels(page, fixture_html):
    page.set_content(fixture_html("weather"))
    targets = Targets(datetime.fromisoformat("2026-10-31T06:00:00-04:00"))
    result = parse_forecast(page, "weather.com", targets)
    assert result.error is None
    assert (result.days[targets.tomorrow].high.f, result.days[targets.tomorrow].low.f) == (71, 56)
    assert (result.days[targets.five_day].high.f, result.days[targets.five_day].low.f) == (63, 45)
