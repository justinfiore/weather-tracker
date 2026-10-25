# Spec Delta

## Purpose

Collect the previous day's observed high and low for Pittsburgh, PA from the National Weather Service daily climate report that backs the PBZ climate page.

## ADDED Requirements

### Requirement: Previous-day Pittsburgh actuals
The collector MUST read the observed maximum and minimum temperature for Pittsburgh, PA for the America/New_York calendar date before the observation date, from the NWS daily climate report for that location.

#### Scenario: Morning collection reads yesterday
- **WHEN** a collection runs at 06:00 America/New_York on 2026-10-26
- **THEN** the actuals reading is for 2026-10-25

#### Scenario: Report names the summary date
- **WHEN** the climate report is titled as the Pittsburgh climate summary for a specific date
- **THEN** the reading uses that summary date only when it equals the previous America/New_York date

### Requirement: Official climate report, not a live observation
The actuals MUST come from the Pittsburgh daily climate summary shown by weather.gov/wrh/Climate?wfo=pbz, read in a browser. A weather data API, including api.weather.gov, MUST NOT be used. A current station observation MUST NOT be used as the previous-day high or low.

#### Scenario: Climate page is the control source
- **WHEN** the collector needs the previous day's actual high and low
- **THEN** it reads the Pittsburgh daily climate report associated with WFO PBZ

#### Scenario: Latest observation is not yesterday's climate
- **WHEN** a live station observation is available but the daily climate report is not
- **THEN** the actuals reading is missing rather than filled from the live observation

### Requirement: Both units for actuals
The actuals reading MUST include Fahrenheit and Celsius highs and lows, the native unit, and the observation time in America/New_York. Conversion MUST follow the same precision rules as forecast readings.

#### Scenario: Climate report publishes Fahrenheit
- **WHEN** the report lists yesterday's maximum as 63°F and minimum as 39°F
- **THEN** the reading stores 63°F and 39°F as native and stores the converted Celsius values

### Requirement: Report not yet issued
If the daily climate report for the previous local date is not available, the collector MUST record the actuals as missing and MUST NOT substitute an older summary date.

#### Scenario: Only an older summary is available
- **WHEN** the newest Pittsburgh climate summary is for two days before the observation date
- **THEN** the actuals reading is missing and names the date that was required
