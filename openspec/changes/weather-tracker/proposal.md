# Proposal

## Why

A science project needs the same Pittsburgh, PA forecast and previous-day actuals recorded at about the same time every day for three weeks, in both Fahrenheit and Celsius. Doing that by hand on three forecast sites plus the National Weather Service climate page is easy to miss and hard to repeat. This change automates that procedure and records each collection morning as a row in a Google Sheet.

## What Changes

- Add a collector that, for Pittsburgh, PA, records the high and low forecast for tomorrow and for the date five days ahead from weather.com, AccuWeather, and WTAE, plus the previous day's observed high and low from the NWS Pittsburgh climate report.
- Count tomorrow and five days ahead as calendar dates in America/New_York, not as whatever "day 1" or "day 5" a site labels.
- Store each site's native temperature and a converted value for the other unit. Keep the source's published precision: whole numbers stay whole, and decimal numbers stay decimal. Do not treat a second site request as a second observation.
- Keep one sheet row per America/New_York collection date. That row holds the forecasts collected that morning. The next morning writes the previous day's NWS actuals onto the previous row.
- Retry a failed source, then write the sources that succeeded and record the error for the ones that did not. Do not drop the whole day because one site failed.
- Run the collector from a command that a scheduled Amp orb thread can invoke every day at 6:00 a.m. Eastern.
- Read weather.com, AccuWeather, WTAE, and the NWS climate page in a browser. Do not use their paid or official data APIs. Google Sheets remains the only API.

## Capabilities

### New Capabilities

- `forecast-collection`: Read the published Pittsburgh high and low for the next local date and the local date five days ahead from the weather.com, AccuWeather, and WTAE pages, with native and converted units.
- `nws-actuals`: Read the previous local day's observed high and low for Pittsburgh, PA from the NWS daily climate report behind weather.gov/wrh/Climate?wfo=pbz.
- `sheet-log`: Keep one row per collection date, with separate Fahrenheit and Celsius forecast columns for each site and NWS actual columns filled on the previous day's row.
- `daily-run`: Run the full collection once, on demand or from a 6:00 a.m. America/New_York schedule, without replacing forecasts or actuals already written.

### Modified Capabilities

- None. The repository has no existing specs.

## Impact

- New application code under `src/weather_tracker/`, a CLI entry point, and tests. The package today only exposes a version.
- New runtime dependencies for Google Sheets and Playwright. Playwright reads every weather source.
- External systems: the weather.com, AccuWeather, WTAE, and NWS climate pages, plus one Google Sheet. No forecast API keys. Google OAuth uses the existing cubscouts OAuth app, already stored as the weather-tracker project secret `GWS_AUTH`. The refresh token is for a different Google user than cubscouts and is not that project's token.
- Operations: a scheduled Amp orb thread runs the CLI. The project does not add a GitHub Actions cron.
- The three-week study length is an operating window, not a hard stop in the collector. The job keeps updating the sheet until the schedule is turned off.
