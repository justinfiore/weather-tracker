# Spec Delta

## Purpose

Record each Pittsburgh collection morning as one sheet row, with separate Fahrenheit and Celsius forecast columns per site, and write the previous day's NWS actuals onto the previous row.

## ADDED Requirements

### Requirement: One row per collection date
The sheet MUST have one data row per America/New_York collection date. That row MUST hold the forecasts collected on that date. It MUST NOT hold the previous day's actuals.

#### Scenario: First collection for a date
- **WHEN** a collection runs on 2026-10-25 and no row exists for that date
- **THEN** the sheet gains one row whose date is 2026-10-25 and whose forecast cells come from that morning

#### Scenario: Same collection date already has a row
- **WHEN** a row for the collection date already exists
- **THEN** the writer does not add a second row for that date

### Requirement: Forecast columns
Each forecast source MUST have its own columns, in this order: Next Day High (F), Next Day High (C), Next Day Low (F), Next Day Low (C), 5-Day High (F), 5-Day High (C), 5-Day Low (F), 5-Day Low (C), and 5-Day Date. The sources MUST appear in this order: weather.com, AccuWeather, WTAE.

#### Scenario: Tomorrow forecast is stored in both units
- **WHEN** weather.com publishes a next-day high of 69°F and a next-day low of 45°F
- **THEN** the weather.com next-day columns on that collection row show 69, the converted Celsius high, 45, and the converted Celsius low

#### Scenario: Five-day date is recorded per source
- **WHEN** a collection on 2026-10-25 reads a five-day forecast
- **THEN** that source's 5-Day Date cell is 2026-10-30

### Requirement: Actuals go on the previous row
The previous day's observed high and low MUST be written to the row whose date is the previous America/New_York date. Actual columns MUST be High (F), High (C), Low (F), and Low (C). The current collection row's actual cells MUST stay blank.

#### Scenario: Next morning fills yesterday
- **WHEN** a collection runs on 2026-10-26 and the NWS actual for 2026-10-25 is 63°F high and 39°F low
- **THEN** those values, with converted Celsius, are written on the 2026-10-25 row and the 2026-10-26 actual cells stay blank

#### Scenario: Previous row is missing
- **WHEN** the NWS actual is available and the previous date has no row
- **THEN** the writer creates that date's row, writes the actuals, and leaves its forecast cells blank

### Requirement: Written temperatures are not replaced
The writer MUST fill a temperature or date cell only when that cell is blank. It MUST NOT replace a forecast or actual already written.

#### Scenario: Later run finds a filled forecast
- **WHEN** the collection row already has a weather.com next-day high
- **THEN** that cell is left unchanged

#### Scenario: Later run fills a blank actual
- **WHEN** the previous row exists and its actual cells are blank
- **THEN** the writer fills those actual cells and does not change that row's forecast cells

### Requirement: Published precision is preserved
A stored temperature MUST keep the precision the source published. A whole number MUST stay a whole number. A decimal number MUST keep the source's decimal places. The converted unit MUST keep that same precision.

#### Scenario: Whole-number forecast
- **WHEN** a source publishes 69°F
- **THEN** the Fahrenheit cell is 69 and the Celsius cell is the conversion of 69 shown to the same whole-number precision

#### Scenario: Decimal forecast
- **WHEN** a source publishes 69.4°F
- **THEN** the Fahrenheit cell is 69.4 and the Celsius cell is the conversion of 69.4 shown to one decimal place

### Requirement: Partial success is written
After retries, the writer MUST write every source that succeeded. A failed source MUST leave its temperature and date cells blank. A source that succeeded MUST NOT be skipped because another source failed.

#### Scenario: One forecast source fails
- **WHEN** WTAE fails after retries and the other sources succeed
- **THEN** the collection row is written, WTAE cells stay blank, and the other forecast cells are filled

#### Scenario: Actuals fail and forecasts succeed
- **WHEN** the NWS actual is missing and at least one forecast source succeeds
- **THEN** the collection row's forecasts are written and the previous row's actual cells stay blank

#### Scenario: Every source fails
- **WHEN** every forecast source and the NWS actuals fail after retries
- **THEN** no new row is created and no filled cell is changed

### Requirement: Sheet location is configured
The writer MUST update the spreadsheet and tab named by configuration. It MUST NOT create a second spreadsheet when the configured one is reachable.

#### Scenario: Configured tab exists
- **WHEN** the configured spreadsheet and tab can be opened
- **THEN** the collection row and any actuals update are written to that tab

#### Scenario: Sheet cannot be opened
- **WHEN** the spreadsheet or tab cannot be opened
- **THEN** the run fails with an error that names the configured destination and no cell is written
