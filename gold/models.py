import datetime as dt
from decimal import Decimal
from typing import Optional

from sqlalchemy import DDL, BigInteger, Boolean, Column, Date, Float, Integer, MetaData, Numeric, PrimaryKeyConstraint, SmallInteger, String, Table, event
from sqlalchemy.dialects.mssql import DATETIME2
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Gold(DeclarativeBase):
    pass


class DimDate(Gold):
    __tablename__ = "DimDate"

    date_key: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False, info={"description": "Date as yyyymmdd, the key used by every fact"})
    calendar_date: Mapped[dt.date] = mapped_column(Date, info={"description": "Calendar date"})
    year: Mapped[int] = mapped_column(SmallInteger, info={"description": "Calendar year"})
    quarter: Mapped[int] = mapped_column(SmallInteger, info={"description": "Calendar quarter 1-4"})
    month: Mapped[int] = mapped_column(SmallInteger, info={"description": "Month number 1-12"})
    month_name: Mapped[str] = mapped_column(String(9), info={"description": "Month name"})
    day: Mapped[int] = mapped_column(SmallInteger, info={"description": "Day of month"})
    weekday: Mapped[int] = mapped_column(SmallInteger, info={"description": "ISO weekday, Monday = 1"})
    weekday_name: Mapped[str] = mapped_column(String(9), info={"description": "Weekday name"})
    is_weekend: Mapped[bool] = mapped_column(Boolean, info={"description": "Saturday or Sunday"})


class DimZone(Gold):
    __tablename__ = "DimZone"

    zone_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False, info={"description": "TLC taxi zone (LocationID); 0 = Outside NYC"})
    borough: Mapped[Optional[str]] = mapped_column(String(32), info={"description": "Borough; Outside NYC for monitors beyond the five boroughs"})
    zone: Mapped[Optional[str]] = mapped_column(String(64), info={"description": "TLC zone name"})
    service_zone: Mapped[Optional[str]] = mapped_column(String(32), info={"description": "TLC service zone"})


class DimFX(Gold):
    __tablename__ = "DimFX"

    date_key: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False, info={"description": "Date as yyyymmdd"})
    rate_date: Mapped[dt.date] = mapped_column(Date, info={"description": "Calendar date"})
    usd_per_eur: Mapped[Decimal] = mapped_column(Numeric(10, 4), info={"description": "ECB reference rate in US dollars per euro, carried forward on days without a publication"})
    is_published: Mapped[bool] = mapped_column(Boolean, info={"description": "True when the ECB published a rate that day"})


class DimGDP(Gold):
    __tablename__ = "DimGDP"

    year: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=False, info={"description": "Calendar year"})
    country_code: Mapped[str] = mapped_column(String(3), info={"description": "ISO 3166 alpha-3 country code"})
    gdp_usd: Mapped[Decimal] = mapped_column(Numeric(20, 2), info={"description": "GDP in current US dollars (World Bank NY.GDP.MKTP.CD)"})


class FactTaxiDaily(Gold):
    __tablename__ = "FactTaxiDaily"

    date_key: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False, info={"description": "Pickup date, NYC local time"})
    zone_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False, info={"description": "Pickup zone"})
    trips: Mapped[int] = mapped_column(Integer, info={"description": "Trips that passed the Silver validity rules"})
    passengers: Mapped[Optional[int]] = mapped_column(Integer, info={"description": "Sum of passenger counts"})
    distance_miles: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), info={"description": "Sum of trip distances in miles"})
    duration_minutes: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), info={"description": "Sum of trip durations in minutes"})
    fare_usd: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), info={"description": "Sum of metered fares in USD"})
    tip_usd: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), info={"description": "Sum of recorded tips in USD"})
    total_usd: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), info={"description": "Sum of total amounts charged in USD"})


class FactAirQualityDaily(Gold):
    __tablename__ = "FactAirQualityDaily"

    date_key: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False, info={"description": "Local date of the hourly readings"})
    location_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, info={"description": "OpenAQ location (monitoring site)"})
    parameter: Mapped[str] = mapped_column(String(8), primary_key=True, info={"description": "Pollutant: pm25, no2 or o3"})
    zone_id: Mapped[Optional[int]] = mapped_column(Integer, info={"description": "Taxi zone containing the monitor; 0 = Outside NYC"})
    unit: Mapped[str] = mapped_column(String(8), info={"description": "ug/m3 for pm25, ppb for no2 and o3"})
    readings: Mapped[int] = mapped_column(Integer, info={"description": "Hourly readings that passed the Silver checks"})
    value_sum: Mapped[float] = mapped_column(Float, info={"description": "Sum of hourly values; divide by readings for the mean"})
    value_max: Mapped[float] = mapped_column(Float, info={"description": "Highest hourly value"})


class DimHour(Gold):
    __tablename__ = "DimHour"

    hour: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=False, info={"description": "Hour of day 0-23"})
    hour_label: Mapped[str] = mapped_column(String(5), info={"description": "Hour as hh:00"})
    day_part: Mapped[str] = mapped_column(String(16), info={"description": "Night, Morning peak, Midday, Evening peak or Evening"})
    day_part_order: Mapped[int] = mapped_column(SmallInteger, info={"description": "Sort order of the day part"})


class FactTaxiHourly(Gold):
    __tablename__ = "FactTaxiHourly"

    date_key: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False, info={"description": "Pickup date, NYC local time"})
    hour: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=False, info={"description": "Pickup hour, NYC local time"})
    zone_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False, info={"description": "Pickup zone"})
    trips: Mapped[int] = mapped_column(Integer, info={"description": "Trips that passed the Silver validity rules"})
    distance_miles: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), info={"description": "Sum of trip distances in miles"})
    duration_minutes: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), info={"description": "Sum of trip durations in minutes"})
    total_usd: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), info={"description": "Sum of total amounts charged in USD"})
    speed_distance_miles: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), info={"description": "Distance of plausible trips only (0 < distance <= 100 miles, duration <= 180 minutes, average speed <= 80 mph)"})
    speed_duration_minutes: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), info={"description": "Duration of the same plausible trips"})


class FactAirQualityHourly(Gold):
    __tablename__ = "FactAirQualityHourly"

    date_key: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False, info={"description": "Local date of the reading"})
    hour: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=False, info={"description": "Local hour of the reading"})
    location_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, info={"description": "OpenAQ location (monitoring site)"})
    parameter: Mapped[str] = mapped_column(String(8), primary_key=True, info={"description": "Pollutant: pm25, no2 or o3"})
    zone_id: Mapped[int] = mapped_column(Integer, info={"description": "Taxi zone containing the monitor; 0 = Outside NYC"})
    unit: Mapped[str] = mapped_column(String(8), info={"description": "ug/m3 for pm25, ppb for no2 and o3"})
    readings: Mapped[int] = mapped_column(Integer, info={"description": "Sensor readings in the hour"})
    value_sum: Mapped[float] = mapped_column(Float, info={"description": "Sum of the readings; divide by readings for the mean"})


class LoadRun(Gold):
    __tablename__ = "LoadRun"

    run_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, info={"description": "Load run number, shared by all tables of one run"})
    target: Mapped[str] = mapped_column(String(32), primary_key=True, info={"description": "Gold table loaded"})
    period_from: Mapped[Optional[dt.date]] = mapped_column(Date, info={"description": "First reloaded date; empty for a full refresh"})
    period_to: Mapped[Optional[dt.date]] = mapped_column(Date, info={"description": "Last reloaded date; empty for a full refresh"})
    started_at: Mapped[dt.datetime] = mapped_column(DATETIME2(6), info={"description": "Start time, UTC"})
    finished_at: Mapped[Optional[dt.datetime]] = mapped_column(DATETIME2(6), info={"description": "End time, UTC"})
    status: Mapped[str] = mapped_column(String(16), info={"description": "succeeded, mismatch or failed"})
    rows_deleted: Mapped[Optional[int]] = mapped_column(BigInteger, info={"description": "Rows removed before the reload"})
    rows_inserted: Mapped[Optional[int]] = mapped_column(BigInteger, info={"description": "Rows written"})
    source_count: Mapped[Optional[int]] = mapped_column(BigInteger, info={"description": "Rows counted in Silver for the period"})
    target_count: Mapped[Optional[int]] = mapped_column(BigInteger, info={"description": "Matching count or summed trips/readings in Gold"})
    message: Mapped[Optional[str]] = mapped_column(String(400), info={"description": "Error text when the load failed"})


class DimWeatherCondition(Gold):
    __tablename__ = "DimWeatherCondition"

    weather_code: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=False, info={"description": "WMO weather interpretation code reported by Open-Meteo"})
    description: Mapped[str] = mapped_column(String(40), info={"description": "WMO description of the code"})
    condition: Mapped[str] = mapped_column(String(16), info={"description": "Clear, Cloudy, Fog, Drizzle, Rain, Snow or Thunderstorm"})
    condition_order: Mapped[int] = mapped_column(SmallInteger, info={"description": "Sort order of the condition, clear to severe"})


class FactWeatherHourly(Gold):
    __tablename__ = "FactWeatherHourly"

    date_key: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False, info={"description": "Local date, NYC time"})
    hour: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=False, info={"description": "Local hour, NYC time"})
    borough: Mapped[str] = mapped_column(String(32), primary_key=True, info={"description": "Borough whose representative point the weather describes"})
    hour_start_utc: Mapped[dt.datetime] = mapped_column(DATETIME2(6), info={"description": "Start of the local hour in UTC"})
    weather_code: Mapped[int] = mapped_column(SmallInteger, info={"description": "Most severe WMO weather code in the hour; see DimWeatherCondition"})
    temperature_c: Mapped[float] = mapped_column(Float, info={"description": "Air temperature at 2 m, degrees Celsius"})
    relative_humidity_pct: Mapped[float] = mapped_column(Float, info={"description": "Relative humidity at 2 m, percent"})
    precipitation_mm: Mapped[float] = mapped_column(Float, info={"description": "Rain, showers and snow water equivalent in the hour, mm"})
    snowfall_cm: Mapped[float] = mapped_column(Float, info={"description": "Snowfall in the hour, cm"})
    wind_speed_kmh: Mapped[float] = mapped_column(Float, info={"description": "Wind speed at 10 m, km/h"})
    cloud_cover_pct: Mapped[float] = mapped_column(Float, info={"description": "Total cloud cover, percent"})
    trips: Mapped[Optional[int]] = mapped_column(Integer, info={"description": "Taxi trips picked up in the borough in the hour; empty after the last date TLC has published"})
    total_usd: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), info={"description": "Sum of total amounts of those trips in USD"})
    speed_distance_miles: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), info={"description": "Distance of the plausible trips among them"})
    speed_duration_minutes: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), info={"description": "Duration of the same plausible trips"})
    pm25_readings: Mapped[Optional[int]] = mapped_column(Integer, info={"description": "PM2.5 sensor readings from monitors in the borough in the hour; empty after the last loaded reading"})
    pm25_sum: Mapped[Optional[float]] = mapped_column(Float, info={"description": "Sum of those PM2.5 readings, ug/m3; divide by pm25_readings for the mean"})


silver = MetaData(schema="lh_silver.dbo")

taxi_trips = Table(
    "taxi_trips",
    silver,
    Column("pickup_date", Date),
    Column("pickup_zone_id", Integer),
    Column("pickup_hour", Integer),
    Column("passenger_count", Integer),
    Column("trip_distance", Float),
    Column("duration_min", Float),
    Column("fare_amount", Numeric(10, 2)),
    Column("tip_amount", Numeric(10, 2)),
    Column("total_amount", Numeric(10, 2)),
)

air_quality_hourly = Table(
    "air_quality_hourly",
    silver,
    Column("location_id", BigInteger),
    Column("parameter", String),
    Column("unit", String),
    Column("local_date", Date),
    Column("local_hour", Integer),
    Column("value", Float),
)

monitor_zone = Table("monitor_zone", silver, Column("location_id", BigInteger), Column("zone_id", Integer))

zones = Table("zones", silver, Column("zone_id", Integer), Column("borough", String), Column("zone", String), Column("service_zone", String))

calendar = Table(
    "calendar",
    silver,
    Column("date", Date),
    Column("date_key", Integer),
    Column("year", Integer),
    Column("quarter", Integer),
    Column("month", Integer),
    Column("month_name", String),
    Column("day", Integer),
    Column("weekday", Integer),
    Column("weekday_name", String),
    Column("is_weekend", Boolean),
)

fx_daily = Table("fx_daily", silver, Column("rate_date", Date), Column("usd_per_eur", Numeric(10, 4)), Column("is_published", Boolean))

weather_hourly = Table(
    "weather_hourly",
    silver,
    Column("borough", String),
    Column("local_date", Date),
    Column("local_hour", Integer),
    Column("hour_start_utc", DATETIME2(6)),
    Column("temperature_c", Float),
    Column("relative_humidity_pct", Float),
    Column("precipitation_mm", Float),
    Column("snowfall_cm", Float),
    Column("wind_speed_kmh", Float),
    Column("cloud_cover_pct", Float),
    Column("weather_code", Integer),
)

gdp_yearly = Table("gdp_yearly", silver, Column("country_code", String), Column("year", Integer), Column("gdp_usd", Numeric(20, 2)))


@compiles(PrimaryKeyConstraint, "mssql")
def inline_primary_key(constraint, compiler, **kw):
    return None


def primary_key_ddl(table):
    columns = ", ".join(column.name for column in table.primary_key.columns)
    return f"ALTER TABLE {table.name} ADD CONSTRAINT pk_{table.name} PRIMARY KEY NONCLUSTERED ({columns}) NOT ENFORCED"


for gold_table in Gold.metadata.tables.values():
    event.listen(gold_table, "after_create", DDL(primary_key_ddl(gold_table)))
