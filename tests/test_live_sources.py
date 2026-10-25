"""Opt-in, read-only browser smoke test. Never writes Google Sheets."""

from datetime import datetime
import os

import pytest

from weather_tracker.cli import collect_all
from weather_tracker.readings import EASTERN, Targets


@pytest.mark.live
@pytest.mark.skipif(os.environ.get("WEATHER_TRACKER_LIVE") != "1", reason="Opt-in live page visits")
def test_live_pages(browser):
    with browser.new_context(locale="en-US", timezone_id="America/New_York") as context:
        results = collect_all(context, Targets(datetime.now(EASTERN)))
    assert all(result.available and not result.error for result in results), [(r.source, r.error) for r in results]
