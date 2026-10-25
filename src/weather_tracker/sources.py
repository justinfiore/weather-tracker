"""Read rendered Pittsburgh weather pages; never request weather data APIs."""

from datetime import datetime, timedelta
import re

from playwright.sync_api import Page

from weather_tracker.readings import Daily, Reading, Targets, Temperature

URLS = {
    "weather.com": "https://weather.com/weather/tenday/l/40.44062,-79.99589",
    "AccuWeather": "https://www.accuweather.com/en/us/pittsburgh/15219/10-day-weather-forecast/1310",
    "WTAE": "https://www.wtae.com/weather",
    "NWS": "https://www.weather.gov/wrh/Climate?wfo=pbz",
}
ROWS = {
    "weather.com": 'a[href*="/hourbyhour/day-"]',
    "AccuWeather": ".daily-forecast-card",
    "WTAE": 'li[role="row"][aria-label*="High"]',
    "NWS": "#textArea",
}
NUMBER = r"[−+-]?\d+(?:\.\d+)?"


class ParseError(ValueError):
    """Rendered source content is missing or cannot be interpreted safely."""


def _temperature(text, unit):
    match = re.search(NUMBER, text.replace("−", "-"))
    return Temperature.from_native(match[0], unit) if match else None


def _reading(source, targets, found):
    dates = (targets.previous,) if source == "NWS" else (targets.tomorrow, targets.five_day)
    days = {day: found.get(day, Daily()) for day in dates}
    missing = [str(day) for day, values in days.items() if not values.available]
    return Reading(source, targets.observed_at, days, "Missing " + ", ".join(missing) if missing else None)


def parse_forecast(page: Page, source: str, targets: Targets) -> Reading:
    """Match visible date labels, not card position or provider day indexes."""
    location_selector = {"weather.com": "h2", "AccuWeather": ".header-loc", "WTAE": "span:has(>small)"}[source]
    locations = page.locator(location_selector).all_inner_texts()
    location = "Pittsburgh, Pennsylvania" if source == "weather.com" else "Pittsburgh, PA"
    if not any(location in text for text in locations):
        raise ParseError("Pittsburgh location not confirmed")
    found = {}
    dates = [targets.today + timedelta(days=i) for i in range(15)]
    if source == "weather.com":
        selected = page.locator('[role="radio"][aria-checked="true"]')
        title = selected.get_attribute("title") or ""
        unit_match = re.search(r"°([FC])", title)
        if not unit_match:
            raise ParseError("Temperature unit not confirmed")
        unit = unit_match[1]
    elif source == "AccuWeather":
        unit = page.locator(".header-temp .unit").inner_text().strip()
        if unit not in ("F", "C"):
            raise ParseError("Temperature unit not confirmed")
    for row in page.locator(ROWS[source]).all():
        if source == "weather.com":
            label = row.locator("span").first.inner_text().strip()
            # This page prints weekday/day-of-month, but not month. Resolve that
            # label within the displayed 15-day horizon, including month rollover.
            day = next((day for day in dates if day.strftime("%a %d") == label), None)
            values = row.locator('[data-testid="TemperatureValue"]').all_inner_texts()
            if day is None or len(values) != 2:
                continue
            low, high = values
        elif source == "AccuWeather":
            label = row.locator(".date .sub").inner_text().strip()
            day = next((day for day in dates if day.strftime("%-m/%-d") == label), None)
            high = row.locator(".high").inner_text()
            low = row.locator(".low").inner_text()
        else:
            text = row.inner_text()
            label = re.search(r"\b([A-Z]+\s+\d{1,2})\b", text, re.I)
            high_match = re.search(r"High\s*(" + NUMBER + r")°([FC])", text)
            low_match = re.search(r"Low\s*(" + NUMBER + r")°([FC])", text)
            if not label or not high_match or not low_match or high_match[2] != low_match[2]:
                continue
            day = next((day for day in dates if day.strftime("%B %-d").upper() == label[1].upper()), None)
            high, low, unit = high_match[1], low_match[1], high_match[2]
        if day in (targets.tomorrow, targets.five_day):
            found[day] = Daily(_temperature(high, unit), _temperature(low, unit))
    return _reading(source, targets, found)


def parse_nws(page: Page, targets: Targets) -> Reading:
    text = page.locator("#textArea").inner_text().replace("\xa0", " ")
    summary = re.search(r"THE PITTSBURGH PA CLIMATE SUMMARY FOR ([A-Z]+ \d{1,2} \d{4})", text)
    if not summary:
        raise ParseError("Pittsburgh climate summary not found")
    summary_date = datetime.strptime(summary[1], "%B %d %Y").date()
    found = {}
    if summary_date == targets.previous:
        temperature = re.search(r"TEMPERATURE \(([FC])\)(.*?)PRECIPITATION", text, re.S)
        if not temperature:
            raise ParseError("Climate temperatures not found")
        high = re.search(r"^\s*MAXIMUM\s+(" + NUMBER + r")\b", temperature[2], re.M)
        low = re.search(r"^\s*MINIMUM\s+(" + NUMBER + r")\b", temperature[2], re.M)
        found[summary_date] = Daily(
            _temperature(high[1], temperature[1]) if high else None,
            _temperature(low[1], temperature[1]) if low else None,
        )
    return _reading("NWS", targets, found)


def collect_source(page: Page, source: str, targets: Targets) -> Reading:
    response = page.goto(URLS[source], wait_until="domcontentloaded", timeout=60000)
    if response is not None and response.status == 403:
        raise ParseError("Source denied browser access (HTTP 403)")
    if source == "NWS":
        page.locator('[data-tab="observed"]').click()
        page.get_by_label("Daily Climate Report (CLI)", exact=True).check()
        page.locator("#availableLocs").select_option(label="Pittsburgh, Pennsylvania")
        page.wait_for_function("/CLIMATE\\s+SUMMARY/.test(document.querySelector('#textArea')?.innerText || '')")
    elif source == "WTAE":
        page.locator(".weather-lead span:has(>small)").wait_for()
        if "Pittsburgh, PA" not in page.locator(".weather-lead span:has(>small)").inner_text():
            page.get_by_role("button", name="Change location", exact=True).click()
            page.get_by_role("textbox").fill("15219")
            page.get_by_role("button", name="Search ZIP code", exact=True).click()
            page.get_by_role("button", name="Close ZIP modal").wait_for(state="hidden")
    page.locator(ROWS[source]).first.wait_for(timeout=60000)
    if source == "weather.com":
        page.get_by_role("button", name="Overflow Menu Horizontal More").click()
        page.locator('[role="radio"][aria-checked="true"]').wait_for()
    result = parse_nws(page, targets) if source == "NWS" else parse_forecast(page, source, targets)
    return result
