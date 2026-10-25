# Rendered-page fixtures

Captured October 25, 2026 using Playwright attached to the orb's Chrome.
These are DOM excerpts (outerHTML), not API responses or invented forecast data.
Scripts, advertising, and unrelated page sections were omitted. Original forecast
card markup, location headings, and unit indicators are retained. External
requests are blocked when tests render these excerpts.

- `weather.html`: https://weather.com/weather/tenday/l/40.44062,-79.99589
  redirects to `/us/pennsylvania/city/pittsburgh/tenday`; includes daily links
  and the checked unit radio from the More menu. Temperature order is low, high.
- `accuweather.html`: https://www.accuweather.com/en/us/pittsburgh/15219/daily-weather-forecast/1310
  redirects to the 10-day page; daily wrappers plus location and native-unit header.
- `wtae.html`: https://www.wtae.com/weather; extended forecast rows plus location.
- `nws.html`: https://www.weather.gov/wrh/Climate?wfo=pbz; Observed Weather →
  Daily Climate Report (CLI) → Pittsburgh, Pennsylvania; rendered `#textArea`.
  The summary is October 24, 2026, maximum 63°F and minimum 39°F.
