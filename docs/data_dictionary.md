# Data dictionary

## Bronze: lh_bronze

### ecb_usd_eur

Written by `df_ecb_fx`.

| Column | Type |
|---|---|
| rate_date | DATE |
| usd_per_eur | DOUBLE |
| obs_status | STRING |
| loaded_at | TIMESTAMP |

### openaq_backfill_log

Written by `nb_bronze_openaq_backfill`.

| Column | Type |
|---|---|
| sensor_id | BIGINT |
| source_month | STRING |
| row_count | INT |
| loaded_at | TIMESTAMP |

### openaq_hours

Written by `nb_bronze_openaq_backfill`.

| Column | Type |
|---|---|
| sensor_id | BIGINT |
| parameter | STRING |
| units | STRING |
| period_start_utc | TIMESTAMP |
| period_start_local | STRING |
| value | DOUBLE |
| observed_count | BIGINT |
| percent_coverage | DOUBLE |
| loaded_at | TIMESTAMP |

### openaq_hours_landing

Written by `df_openaq`.

| Column | Type |
|---|---|
| sensor_id | BIGINT |
| parameter | STRING |
| units | STRING |
| period_start_utc | TIMESTAMP |
| period_start_local | STRING |
| value | DOUBLE |
| observed_count | BIGINT |
| percent_coverage | DOUBLE |
| loaded_at | TIMESTAMP |

### openaq_sensors

Written by `df_openaq`.

| Column | Type |
|---|---|
| location_id | BIGINT |
| location_name | STRING |
| provider | STRING |
| timezone | STRING |
| latitude | DOUBLE |
| longitude | DOUBLE |
| sensor_id | BIGINT |
| parameter | STRING |
| units | STRING |
| loaded_at | TIMESTAMP |

### weather_hourly

Written by `nb_bronze_weather`.

| Column | Type |
|---|---|
| borough | STRING |
| latitude | DOUBLE |
| longitude | DOUBLE |
| observed_utc | TIMESTAMP |
| temperature_c | DOUBLE |
| relative_humidity_pct | DOUBLE |
| precipitation_mm | DOUBLE |
| snowfall_cm | DOUBLE |
| wind_speed_kmh | DOUBLE |
| cloud_cover_pct | DOUBLE |
| weather_code | INT |
| source | STRING |
| loaded_at | TIMESTAMP |

### worldbank_gdp

Written by `df_worldbank_gdp`.

| Column | Type |
|---|---|
| country_code | STRING |
| year | BIGINT |
| gdp_usd | DOUBLE |
| obs_status | STRING |
| loaded_at | TIMESTAMP |

## Silver: lh_silver

### air_quality_hourly

Written by `nb_silver_air_quality`.

| Column | Type |
|---|---|
| sensor_id | BIGINT |
| location_id | BIGINT |
| parameter | STRING |
| unit | STRING |
| period_start_utc | TIMESTAMP |
| period_start_local | TIMESTAMP |
| local_date | DATE |
| local_hour | INT |
| value | DOUBLE |
| observed_count | BIGINT |
| percent_coverage | DOUBLE |

### calendar

Written by `nb_silver_reference`.

| Column | Type |
|---|---|
| date | DATE |
| date_key | INT |
| year | INT |
| quarter | INT |
| month | INT |
| month_name | STRING |
| day | INT |
| weekday | INT |
| weekday_name | STRING |
| is_weekend | BOOLEAN |

### fx_daily

Written by `nb_silver_reference`.

| Column | Type |
|---|---|
| rate_date | DATE |
| usd_per_eur | DECIMAL(10,4) |
| is_published | BOOLEAN |

### gdp_yearly

Written by `nb_silver_reference`.

| Column | Type |
|---|---|
| country_code | STRING |
| year | INT |
| gdp_usd | DECIMAL(20,2) |

### monitor_zone

Written by `nb_silver_reference`.

| Column | Type |
|---|---|
| location_id | BIGINT |
| location_name | STRING |
| latitude | DOUBLE |
| longitude | DOUBLE |
| zone_id | INT |

### taxi_month_audit

Written by `nb_silver_taxi`.

| Column | Type |
|---|---|
| source_month | STRING |
| source_rows | BIGINT |
| valid_rows | BIGINT |
| silver_rows | BIGINT |
| loaded_at | TIMESTAMP |

### taxi_trips

Written by `nb_silver_taxi`.

| Column | Type |
|---|---|
| vendor_id | INT |
| pickup_datetime | TIMESTAMP |
| dropoff_datetime | TIMESTAMP |
| passenger_count | INT |
| trip_distance | DOUBLE |
| ratecode_id | INT |
| store_and_fwd_flag | STRING |
| pickup_zone_id | INT |
| dropoff_zone_id | INT |
| payment_type | INT |
| fare_amount | DECIMAL(10,2) |
| extra | DECIMAL(10,2) |
| mta_tax | DECIMAL(10,2) |
| tip_amount | DECIMAL(10,2) |
| tolls_amount | DECIMAL(10,2) |
| improvement_surcharge | DECIMAL(10,2) |
| congestion_surcharge | DECIMAL(10,2) |
| airport_fee | DECIMAL(10,2) |
| cbd_congestion_fee | DECIMAL(10,2) |
| total_amount | DECIMAL(10,2) |
| pickup_date | DATE |
| pickup_hour | INT |
| duration_min | DOUBLE |
| source_month | STRING |

### weather_hourly

Written by `nb_silver_weather`.

| Column | Type |
|---|---|
| borough | STRING |
| local_date | DATE |
| local_hour | INT |
| hour_start_utc | TIMESTAMP |
| temperature_c | DOUBLE |
| relative_humidity_pct | DOUBLE |
| precipitation_mm | DOUBLE |
| snowfall_cm | DOUBLE |
| wind_speed_kmh | DOUBLE |
| cloud_cover_pct | DOUBLE |
| weather_code | INT |
| source | STRING |

### zones

Written by `nb_silver_reference`.

| Column | Type |
|---|---|
| zone_id | INT |
| borough | STRING |
| zone | STRING |
| service_zone | STRING |

## Gold: wh_gold

### DimDate

| Column | Type | Nullable | Description |
|---|---|---|---|
| date_key | INTEGER | key | Date as yyyymmdd, the key used by every fact |
| calendar_date | DATETIME | no | Calendar date |
| year | SMALLINT | no | Calendar year |
| quarter | SMALLINT | no | Calendar quarter 1-4 |
| month | SMALLINT | no | Month number 1-12 |
| month_name | VARCHAR(9) | no | Month name |
| day | SMALLINT | no | Day of month |
| weekday | SMALLINT | no | ISO weekday, Monday = 1 |
| weekday_name | VARCHAR(9) | no | Weekday name |
| is_weekend | BIT | no | Saturday or Sunday |

### DimFX

| Column | Type | Nullable | Description |
|---|---|---|---|
| date_key | INTEGER | key | Date as yyyymmdd |
| rate_date | DATETIME | no | Calendar date |
| usd_per_eur | NUMERIC(10, 4) | no | ECB reference rate in US dollars per euro, carried forward on days without a publication |
| is_published | BIT | no | True when the ECB published a rate that day |

### DimGDP

| Column | Type | Nullable | Description |
|---|---|---|---|
| year | SMALLINT | key | Calendar year |
| country_code | VARCHAR(3) | no | ISO 3166 alpha-3 country code |
| gdp_usd | NUMERIC(20, 2) | no | GDP in current US dollars (World Bank NY.GDP.MKTP.CD) |

### DimHour

| Column | Type | Nullable | Description |
|---|---|---|---|
| hour | SMALLINT | key | Hour of day 0-23 |
| hour_label | VARCHAR(5) | no | Hour as hh:00 |
| day_part | VARCHAR(16) | no | Night, Morning peak, Midday, Evening peak or Evening |
| day_part_order | SMALLINT | no | Sort order of the day part |

### DimWeatherCondition

| Column | Type | Nullable | Description |
|---|---|---|---|
| weather_code | SMALLINT | key | WMO weather interpretation code reported by Open-Meteo |
| description | VARCHAR(40) | no | WMO description of the code |
| condition | VARCHAR(16) | no | Clear, Cloudy, Fog, Drizzle, Rain, Snow or Thunderstorm |
| condition_order | SMALLINT | no | Sort order of the condition, clear to severe |

### DimZone

| Column | Type | Nullable | Description |
|---|---|---|---|
| zone_id | INTEGER | key | TLC taxi zone (LocationID); 0 = Outside NYC |
| borough | VARCHAR(32) | yes | Borough; Outside NYC for monitors beyond the five boroughs |
| zone | VARCHAR(64) | yes | TLC zone name |
| service_zone | VARCHAR(32) | yes | TLC service zone |

### FactAirQualityDaily

| Column | Type | Nullable | Description |
|---|---|---|---|
| date_key | INTEGER | key | Local date of the hourly readings |
| location_id | BIGINT | key | OpenAQ location (monitoring site) |
| parameter | VARCHAR(8) | key | Pollutant: pm25, no2 or o3 |
| zone_id | INTEGER | yes | Taxi zone containing the monitor; 0 = Outside NYC |
| unit | VARCHAR(8) | no | ug/m3 for pm25, ppb for no2 and o3 |
| readings | INTEGER | no | Hourly readings that passed the Silver checks |
| value_sum | FLOAT | no | Sum of hourly values; divide by readings for the mean |
| value_max | FLOAT | no | Highest hourly value |

### FactAirQualityHourly

| Column | Type | Nullable | Description |
|---|---|---|---|
| date_key | INTEGER | key | Local date of the reading |
| hour | SMALLINT | key | Local hour of the reading |
| location_id | BIGINT | key | OpenAQ location (monitoring site) |
| parameter | VARCHAR(8) | key | Pollutant: pm25, no2 or o3 |
| zone_id | INTEGER | no | Taxi zone containing the monitor; 0 = Outside NYC |
| unit | VARCHAR(8) | no | ug/m3 for pm25, ppb for no2 and o3 |
| readings | INTEGER | no | Sensor readings in the hour |
| value_sum | FLOAT | no | Sum of the readings; divide by readings for the mean |

### FactTaxiDaily

| Column | Type | Nullable | Description |
|---|---|---|---|
| date_key | INTEGER | key | Pickup date, NYC local time |
| zone_id | INTEGER | key | Pickup zone |
| trips | INTEGER | no | Trips that passed the Silver validity rules |
| passengers | INTEGER | yes | Sum of passenger counts |
| distance_miles | NUMERIC(14, 2) | yes | Sum of trip distances in miles |
| duration_minutes | NUMERIC(14, 2) | yes | Sum of trip durations in minutes |
| fare_usd | NUMERIC(14, 2) | yes | Sum of metered fares in USD |
| tip_usd | NUMERIC(14, 2) | yes | Sum of recorded tips in USD |
| total_usd | NUMERIC(14, 2) | yes | Sum of total amounts charged in USD |

### FactTaxiHourly

| Column | Type | Nullable | Description |
|---|---|---|---|
| date_key | INTEGER | key | Pickup date, NYC local time |
| hour | SMALLINT | key | Pickup hour, NYC local time |
| zone_id | INTEGER | key | Pickup zone |
| trips | INTEGER | no | Trips that passed the Silver validity rules |
| distance_miles | NUMERIC(14, 2) | yes | Sum of trip distances in miles |
| duration_minutes | NUMERIC(14, 2) | yes | Sum of trip durations in minutes |
| total_usd | NUMERIC(14, 2) | yes | Sum of total amounts charged in USD |
| speed_distance_miles | NUMERIC(14, 2) | yes | Distance of plausible trips only (0 < distance <= 100 miles, duration <= 180 minutes, average speed <= 80 mph) |
| speed_duration_minutes | NUMERIC(14, 2) | yes | Duration of the same plausible trips |

### FactWeatherHourly

| Column | Type | Nullable | Description |
|---|---|---|---|
| date_key | INTEGER | key | Local date, NYC time |
| hour | SMALLINT | key | Local hour, NYC time |
| borough | VARCHAR(32) | key | Borough whose representative point the weather describes |
| hour_start_utc | DATETIME2(6) | no | Start of the local hour in UTC |
| weather_code | SMALLINT | no | Most severe WMO weather code in the hour; see DimWeatherCondition |
| temperature_c | FLOAT | no | Air temperature at 2 m, degrees Celsius |
| relative_humidity_pct | FLOAT | no | Relative humidity at 2 m, percent |
| precipitation_mm | FLOAT | no | Rain, showers and snow water equivalent in the hour, mm |
| snowfall_cm | FLOAT | no | Snowfall in the hour, cm |
| wind_speed_kmh | FLOAT | no | Wind speed at 10 m, km/h |
| cloud_cover_pct | FLOAT | no | Total cloud cover, percent |
| trips | INTEGER | yes | Taxi trips picked up in the borough in the hour; empty after the last date TLC has published |
| total_usd | NUMERIC(14, 2) | yes | Sum of total amounts of those trips in USD |
| speed_distance_miles | NUMERIC(14, 2) | yes | Distance of the plausible trips among them |
| speed_duration_minutes | NUMERIC(14, 2) | yes | Duration of the same plausible trips |
| pm25_readings | INTEGER | yes | PM2.5 sensor readings from monitors in the borough in the hour; empty after the last loaded reading |
| pm25_sum | FLOAT | yes | Sum of those PM2.5 readings, ug/m3; divide by pm25_readings for the mean |

### LoadRun

| Column | Type | Nullable | Description |
|---|---|---|---|
| run_id | BIGINT | key | Load run number, shared by all tables of one run |
| target | VARCHAR(32) | key | Gold table loaded |
| period_from | DATETIME | yes | First reloaded date; empty for a full refresh |
| period_to | DATETIME | yes | Last reloaded date; empty for a full refresh |
| started_at | DATETIME2(6) | no | Start time, UTC |
| finished_at | DATETIME2(6) | yes | End time, UTC |
| status | VARCHAR(16) | no | succeeded, mismatch or failed |
| rows_deleted | BIGINT | yes | Rows removed before the reload |
| rows_inserted | BIGINT | yes | Rows written |
| source_count | BIGINT | yes | Rows counted in Silver for the period |
| target_count | BIGINT | yes | Matching count or summed trips/readings in Gold |
| message | VARCHAR(400) | yes | Error text when the load failed |

## Time-series database: TimescaleDB nyc_weather

### sync_run

| Column | Type | Nullable | Description |
|---|---|---|---|
| run_id | BIGINT | key | Sync run number |
| started_at | TIMESTAMP WITH TIME ZONE | no | Start time, UTC |
| finished_at | TIMESTAMP WITH TIME ZONE | yes | End time, UTC |
| window_from | DATE | yes | First local date copied; empty for a full copy |
| rows_read | BIGINT | yes | Rows read from wh_gold.FactWeatherHourly |
| rows_written | BIGINT | yes | Rows inserted or updated in weather_hourly |
| source_count | BIGINT | yes | Rows in wh_gold for the window after the copy |
| target_count | BIGINT | yes | Rows in weather_hourly for the window after the copy |
| status | VARCHAR(16) | no | running, succeeded, mismatch or failed |
| message | VARCHAR(400) | yes | Error text when the run failed |

### weather_hourly

| Column | Type | Nullable | Description |
|---|---|---|---|
| time | TIMESTAMP WITH TIME ZONE | key | Start of the NYC local hour, stored in UTC; the hypertable time column |
| borough | VARCHAR(32) | key | Borough whose representative point the weather describes |
| date_key | INTEGER | no | Local date as yyyymmdd, as in wh_gold |
| local_hour | SMALLINT | no | Local hour 0-23 |
| weather_code | SMALLINT | no | Most severe WMO weather code in the hour |
| weather_description | VARCHAR(40) | no | WMO description of the code |
| weather_condition | VARCHAR(16) | no | Clear, Cloudy, Fog, Drizzle, Rain, Snow or Thunderstorm |
| weather_condition_order | SMALLINT | no | Sort order of the condition, clear to severe |
| temperature_c | FLOAT | no | Air temperature at 2 m, degrees Celsius |
| relative_humidity_pct | FLOAT | no | Relative humidity at 2 m, percent |
| precipitation_mm | FLOAT | no | Precipitation in the hour, mm |
| snowfall_cm | FLOAT | no | Snowfall in the hour, cm |
| wind_speed_kmh | FLOAT | no | Wind speed at 10 m, km/h |
| cloud_cover_pct | FLOAT | no | Total cloud cover, percent |
| trips | INTEGER | yes | Taxi trips picked up in the borough in the hour; empty after the last published TLC date |
| total_usd | NUMERIC(14, 2) | yes | Sum of total amounts of those trips in USD |
| speed_distance_miles | NUMERIC(14, 2) | yes | Distance of the plausible trips among them |
| speed_duration_minutes | NUMERIC(14, 2) | yes | Duration of the same plausible trips |
| pm25_readings | INTEGER | yes | PM2.5 readings from monitors in the borough in the hour |
| pm25_sum | FLOAT | yes | Sum of those readings, ug/m3 |
| synced_at | TIMESTAMP WITH TIME ZONE | no | When the sync job last wrote the row, UTC |

## Semantic model: sm_nyc_urban (Direct Lake)

### DimDate

| Field | Source column | Type | Visibility |
|---|---|---|---|
| date_key | date_key | int64 | hidden |
| Date | calendar_date | dateTime | visible |
| Year | year | int64 | visible |
| Quarter | quarter | int64 | visible |
| Month | month | int64 | visible |
| Month Name | month_name | string | visible |
| Day | day | int64 | visible |
| Weekday | weekday | int64 | visible |
| Weekday Name | weekday_name | string | visible |
| Is Weekend | is_weekend | boolean | visible |

### DimFX

| Field | Source column | Type | Visibility |
|---|---|---|---|
| date_key | date_key | int64 | hidden |
| rate_date | rate_date | dateTime | hidden |
| USD per EUR | usd_per_eur | decimal | visible |
| Is Published | is_published | boolean | visible |

| Measure | DAX | Format |
|---|---|---|
| Avg USD per EUR | `AVERAGE(DimFX[USD per EUR])` | `0.0000` |

### DimGDP

| Field | Source column | Type | Visibility |
|---|---|---|---|
| year | year | int64 | hidden |
| country_code | country_code | string | hidden |
| gdp_usd | gdp_usd | double | hidden |

| Measure | DAX | Format |
|---|---|---|
| GDP USD | `CALCULATE(SUM(DimGDP[gdp_usd]), TREATAS(VALUES(DimDate[Year]), DimGDP[year]))` | `#,0` |

### DimHour

| Field | Source column | Type | Visibility |
|---|---|---|---|
| hour | hour | int64 | hidden |
| Hour of Day | hour_label | string | visible |
| day_part_order | day_part_order | int64 | hidden |
| Day Part | day_part | string | visible |

### DimZone

| Field | Source column | Type | Visibility |
|---|---|---|---|
| zone_id | zone_id | int64 | hidden |
| Borough | borough | string | visible |
| Zone | zone | string | visible |
| Service Zone | service_zone | string | visible |

### FactAirQualityDaily

| Field | Source column | Type | Visibility |
|---|---|---|---|
| date_key | date_key | int64 | hidden |
| location_id | location_id | int64 | hidden |
| Pollutant | parameter | string | visible |
| zone_id | zone_id | int64 | hidden |
| Unit | unit | string | visible |
| reading_count | readings | int64 | hidden |
| value_sum | value_sum | double | hidden |
| value_max | value_max | double | hidden |

| Measure | DAX | Format |
|---|---|---|
| Readings | `SUM(FactAirQualityDaily[reading_count])` | `#,0` |
| Monitors | `DISTINCTCOUNT(FactAirQualityDaily[location_id])` | `#,0` |
| Avg PM2.5 ug/m3 | `DIVIDE(CALCULATE(SUM(FactAirQualityDaily[value_sum]), FactAirQualityDaily[Pollutant] = "pm25"), CALCULATE(SUM(FactAirQualityDaily[reading_count]), FactAirQualityDaily[Pollutant] = "pm25"))` | `0.0` |
| Max PM2.5 ug/m3 | `CALCULATE(MAX(FactAirQualityDaily[value_max]), FactAirQualityDaily[Pollutant] = "pm25")` | `0.0` |
| Avg NO2 ppb | `DIVIDE(CALCULATE(SUM(FactAirQualityDaily[value_sum]), FactAirQualityDaily[Pollutant] = "no2"), CALCULATE(SUM(FactAirQualityDaily[reading_count]), FactAirQualityDaily[Pollutant] = "no2"))` | `0.0` |
| Avg O3 ppb | `DIVIDE(CALCULATE(SUM(FactAirQualityDaily[value_sum]), FactAirQualityDaily[Pollutant] = "o3"), CALCULATE(SUM(FactAirQualityDaily[reading_count]), FactAirQualityDaily[Pollutant] = "o3"))` | `0.0` |

### FactAirQualityHourly

| Field | Source column | Type | Visibility |
|---|---|---|---|
| date_key | date_key | int64 | hidden |
| hour | hour | int64 | hidden |
| location_id | location_id | int64 | hidden |
| parameter | parameter | string | hidden |
| zone_id | zone_id | int64 | hidden |
| unit | unit | string | hidden |
| reading_count | readings | int64 | hidden |
| value_sum | value_sum | double | hidden |

| Measure | DAX | Format |
|---|---|---|
| Hourly PM2.5 ug/m3 | `DIVIDE(CALCULATE(SUM(FactAirQualityHourly[value_sum]), FactAirQualityHourly[parameter] = "pm25"), CALCULATE(SUM(FactAirQualityHourly[reading_count]), FactAirQualityHourly[parameter] = "pm25"))` | `0.0` |
| Hourly NO2 ppb | `DIVIDE(CALCULATE(SUM(FactAirQualityHourly[value_sum]), FactAirQualityHourly[parameter] = "no2"), CALCULATE(SUM(FactAirQualityHourly[reading_count]), FactAirQualityHourly[parameter] = "no2"))` | `0.0` |
| Hourly O3 ppb | `DIVIDE(CALCULATE(SUM(FactAirQualityHourly[value_sum]), FactAirQualityHourly[parameter] = "o3"), CALCULATE(SUM(FactAirQualityHourly[reading_count]), FactAirQualityHourly[parameter] = "o3"))` | `0.0` |

### FactTaxiDaily

| Field | Source column | Type | Visibility |
|---|---|---|---|
| date_key | date_key | int64 | hidden |
| zone_id | zone_id | int64 | hidden |
| trip_count | trips | int64 | hidden |
| passenger_count | passengers | int64 | hidden |
| distance_miles | distance_miles | decimal | hidden |
| duration_minutes | duration_minutes | decimal | hidden |
| fare_usd | fare_usd | decimal | hidden |
| tip_usd | tip_usd | decimal | hidden |
| total_usd | total_usd | decimal | hidden |

| Measure | DAX | Format |
|---|---|---|
| Trips | `SUM(FactTaxiDaily[trip_count])` | `#,0` |
| Passengers | `SUM(FactTaxiDaily[passenger_count])` | `#,0` |
| Revenue USD | `SUM(FactTaxiDaily[total_usd])` | `#,0.00` |
| Revenue EUR | `SUMX(VALUES(DimDate[date_key]), DIVIDE(CALCULATE(SUM(FactTaxiDaily[total_usd])), CALCULATE(MAX(DimFX[USD per EUR]))))` | `#,0.00` |
| Fare USD | `SUM(FactTaxiDaily[fare_usd])` | `#,0` |
| Tips USD | `SUM(FactTaxiDaily[tip_usd])` | `#,0` |
| Distance Miles | `SUM(FactTaxiDaily[distance_miles])` | `#,0` |
| Avg Trip Miles | `DIVIDE([Distance Miles], [Trips])` | `0.00` |
| Avg Trip Minutes | `DIVIDE(SUM(FactTaxiDaily[duration_minutes]), [Trips])` | `0.0` |
| Avg Fare USD | `DIVIDE([Fare USD], [Trips])` | `0.00` |
| Tip Rate | `DIVIDE([Tips USD], [Fare USD])` | `0.0%` |
| Taxi Revenue Share of GDP | `DIVIDE(CONVERT([Revenue USD], DOUBLE), [GDP USD])` | `0.0000%` |

### FactTaxiHourly

| Field | Source column | Type | Visibility |
|---|---|---|---|
| date_key | date_key | int64 | hidden |
| hour | hour | int64 | hidden |
| zone_id | zone_id | int64 | hidden |
| trip_count | trips | int64 | hidden |
| distance_miles | distance_miles | decimal | hidden |
| duration_minutes | duration_minutes | decimal | hidden |
| total_usd | total_usd | decimal | hidden |
| speed_distance_miles | speed_distance_miles | decimal | hidden |
| speed_duration_minutes | speed_duration_minutes | decimal | hidden |

| Measure | DAX | Format |
|---|---|---|
| Hourly Trips | `SUM(FactTaxiHourly[trip_count])` | `#,0` |
| Avg Speed mph | `DIVIDE(SUM(FactTaxiHourly[speed_distance_miles]), SUM(FactTaxiHourly[speed_duration_minutes]) / 60)` | `0.0` |

### Relationships

| From (many) | To (one) |
|---|---|
| FactTaxiDaily.date_key | DimDate.date_key |
| FactTaxiDaily.zone_id | DimZone.zone_id |
| FactAirQualityDaily.date_key | DimDate.date_key |
| FactAirQualityDaily.zone_id | DimZone.zone_id |
| DimFX.date_key | DimDate.date_key |
| FactTaxiHourly.date_key | DimDate.date_key |
| FactTaxiHourly.zone_id | DimZone.zone_id |
| FactTaxiHourly.hour | DimHour.hour |
| FactAirQualityHourly.date_key | DimDate.date_key |
| FactAirQualityHourly.zone_id | DimZone.zone_id |
| FactAirQualityHourly.hour | DimHour.hour |

### Row-level security roles

| Role | Table | Filter |
|---|---|---|
| Bronx | DimZone | `[Borough] = "Bronx"` |
| Brooklyn | DimZone | `[Borough] = "Brooklyn"` |
| Manhattan | DimZone | `[Borough] = "Manhattan"` |
| Queens | DimZone | `[Borough] = "Queens"` |
| Staten Island | DimZone | `[Borough] = "Staten Island"` |
