# Tasks

## 1. Package skeleton

- [x] 1.1 Add Google auth, Sheets, and Playwright dependencies in Poetry and verify `poetry sync` succeeds
- [x] 1.2 Add the `weather-tracker` console script and verify `poetry run weather-tracker --help` lists `collect` and `auth`
- [x] 1.3 Add date helpers for America/New_York observation, tomorrow, plus-five, and previous dates, and verify tests cover 00:30 and 23:30 Eastern plus a DST date

## 2. Readings and conversion

- [x] 2.1 Add the shared reading type for native unit, both units, target dates, and source error, and verify a missing value stays missing rather than zero
- [x] 2.2 Add precision-preserving F/C conversion and verify 69°F stays a whole number, 69.4°F keeps one decimal in both units, and a trailing 5 rounds away from zero

## 3. Forecast and actuals adapters

- [x] 3.1 Add the Playwright weather.com adapter for the Pittsburgh forecast page and verify a saved page fixture selects the Eastern calendar dates rather than day indexes
- [x] 3.2 Add the Playwright AccuWeather adapter for the Pittsburgh daily page and verify a fixture whose fifth labeled day is the wrong date marks that date missing and keeps tomorrow
- [x] 3.3 Add the Playwright WTAE adapter for wtae.com/weather fixed to Pittsburgh, PA, and verify a saved rendered-page fixture returns highs and lows for both target dates
- [x] 3.4 Add the Playwright NWS adapter for the Pittsburgh daily climate report on weather.gov/wrh/Climate?wfo=pbz and verify the saved October 24 2026 summary parses maximum 63 and minimum 39, and an older summary date is missing

## 4. Google sheet

- [x] 4.1 Unpack `GWS_AUTH` to a mode-0600 `client_secret.json` outside the repo, ignore `.encryption_key`, and verify a fixture round-trip does not print the payload and rejects an empty secret
- [x] 4.2 Add `weather-tracker auth` for the Sheets scope only, using a loopback redirect, and verify it refuses to run when the client has no matching redirect URI and does not read cubscouts credential blobs
- [x] 4.3 Add the date-row sheet updater and verify tests for the forecast columns, writing NWS actuals onto the previous date, leaving the current row's actuals blank, filling only blank cells, a partial WTAE failure, and an all-failed run that writes nothing

## 5. Daily command

- [x] 5.1 Add `weather-tracker collect` so sources run independently with three attempts and the documented backoff, and verify a source that fails then succeeds is `ok` while a source that always fails does not cancel the others
- [x] 5.2 Wire collect to the sheet updater and verify the command exits 0 when rows are created or updated or when the values were already present, and exits 1 when every source fails or the sheet cannot be opened
- [x] 5.3 Document setup in the README: browser collection, project secrets `GWS_AUTH` and `SHEETS_REFRESH_TOKEN`, the sheet env vars, the auth command, and the 6:00 a.m. America/New_York orb schedule. Verify the documented help commands match the CLI

## 6. Operator setup

- [x] 6.1 Run `weather-tracker auth` as the Google user who owns the science-project sheet and store the refresh token as project secret `SHEETS_REFRESH_TOKEN`. Verify a later collect does not open a browser
- [x] 6.2 Run one live `weather-tracker collect` against the configured sheet and verify the collection-date row has forecast columns filled and actuals written only on the previous date's row
- [ ] 6.3 Create the Amp schedule for 6:00 a.m. America/New_York that runs `poetry run weather-tracker collect`, and verify the saved prompt names that command and the thread is not set to archive
