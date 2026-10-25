# Spec Delta

## Purpose

Collect the published Pittsburgh, PA high and low forecasts for tomorrow and for five days ahead from weather.com, AccuWeather, and WTAE, in both Fahrenheit and Celsius.

## ADDED Requirements

### Requirement: Pittsburgh forecast sources
The collector MUST read the daily high and low published for Pittsburgh, PA from the weather.com, accuweather.com, and wtae.com/weather pages in a browser. It MUST NOT call a weather data API for those readings.

#### Scenario: All three sources are read
- **WHEN** a collection runs for Pittsburgh, PA
- **THEN** the result includes a separate forecast reading for weather.com, AccuWeather, and WTAE

### Requirement: Target dates are Eastern calendar dates
The collector MUST request the high and low for the next America/New_York calendar date and for the America/New_York calendar date five days after the observation date. It MUST NOT substitute a source's day index when that index names a different date.

#### Scenario: Run just after midnight Eastern
- **WHEN** the observation time is 00:30 America/New_York on 2026-10-26
- **THEN** the tomorrow target is 2026-10-27 and the five-day target is 2026-10-31

#### Scenario: Run before midnight Eastern
- **WHEN** the observation time is 23:30 America/New_York on 2026-10-25
- **THEN** the tomorrow target is 2026-10-26 and the five-day target is 2026-10-30

#### Scenario: Source day index does not match the calendar date
- **WHEN** a source labels its first forecast day as today, or its fifth forecast day as a date other than the observation date plus five
- **THEN** the reading uses the values published for the target calendar dates, not the values at those indexes

### Requirement: Both temperature units
Each forecast reading MUST include Fahrenheit and Celsius highs and lows. The collector MUST take the unit the source publishes as native and MUST derive the other unit from that native value. It MUST record which unit was native.

#### Scenario: Source publishes Fahrenheit
- **WHEN** a source publishes a high of 69°F and a low of 45°F for a target date
- **THEN** the reading stores 69°F and 45°F as native, stores the converted Celsius values, and records Fahrenheit as the native unit

#### Scenario: Source publishes Celsius
- **WHEN** a source publishes a high of 20°C and a low of 7°C for a target date
- **THEN** the reading stores 20°C and 7°C as native, stores the converted Fahrenheit values, and records Celsius as the native unit

### Requirement: Published precision
A stored temperature MUST keep the precision the source published. A whole number MUST stay a whole number. A decimal number MUST keep the source's decimal places. The converted unit MUST use (F − 32) × 5/9 or C × 9/5 + 32 and MUST be shown at that same precision, with the last displayed digit rounded half away from zero.

#### Scenario: Whole number stays whole
- **WHEN** a source publishes 69°F
- **THEN** the stored Fahrenheit value is 69 and the stored Celsius value is a whole number

#### Scenario: One decimal place is kept
- **WHEN** a source publishes 69.4°F
- **THEN** the stored Fahrenheit value is 69.4 and the stored Celsius value has one decimal place

#### Scenario: Converted half rounds away from zero
- **WHEN** a native value converts to a digit of 5 immediately after the last displayed place
- **THEN** that displayed digit rounds away from zero

### Requirement: Observation time
Each forecast reading MUST include the America/New_York observation time of the collection and the source name.

#### Scenario: Observation time is local
- **WHEN** a collection observes a source at 10:00 UTC during Eastern Daylight Time
- **THEN** the reading's observation time is 06:00 America/New_York on that local date

### Requirement: Missing forecast date
If a source does not publish a high and low for a target date, the collector MUST record that date as missing for that source and MUST still return any target date that source did publish.

#### Scenario: Five-day forecast is absent
- **WHEN** AccuWeather publishes tomorrow's high and low but not the five-day target date
- **THEN** the AccuWeather reading includes tomorrow's values and marks the five-day date missing
