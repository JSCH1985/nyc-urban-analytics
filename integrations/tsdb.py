import datetime as dt
import os
import re
from decimal import Decimal
from typing import Optional

from sqlalchemy import DDL, BigInteger, Date, DateTime, Float, Identity, Integer, Numeric, SmallInteger, String, create_engine, event, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

DATABASE = "nyc_weather"
OWNER = "nyc"
READER = "grafana_reader"


class Tsdb(DeclarativeBase):
    pass


class WeatherHourly(Tsdb):
    __tablename__ = "weather_hourly"

    time: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), primary_key=True, info={"description": "Start of the NYC local hour, stored in UTC; the hypertable time column"})
    borough: Mapped[str] = mapped_column(String(32), primary_key=True, info={"description": "Borough whose representative point the weather describes"})
    date_key: Mapped[int] = mapped_column(Integer, info={"description": "Local date as yyyymmdd, as in wh_gold"})
    local_hour: Mapped[int] = mapped_column(SmallInteger, info={"description": "Local hour 0-23"})
    weather_code: Mapped[int] = mapped_column(SmallInteger, info={"description": "Most severe WMO weather code in the hour"})
    weather_description: Mapped[str] = mapped_column(String(40), info={"description": "WMO description of the code"})
    weather_condition: Mapped[str] = mapped_column(String(16), info={"description": "Clear, Cloudy, Fog, Drizzle, Rain, Snow or Thunderstorm"})
    weather_condition_order: Mapped[int] = mapped_column(SmallInteger, info={"description": "Sort order of the condition, clear to severe"})
    temperature_c: Mapped[float] = mapped_column(Float, info={"description": "Air temperature at 2 m, degrees Celsius"})
    relative_humidity_pct: Mapped[float] = mapped_column(Float, info={"description": "Relative humidity at 2 m, percent"})
    precipitation_mm: Mapped[float] = mapped_column(Float, info={"description": "Precipitation in the hour, mm"})
    snowfall_cm: Mapped[float] = mapped_column(Float, info={"description": "Snowfall in the hour, cm"})
    wind_speed_kmh: Mapped[float] = mapped_column(Float, info={"description": "Wind speed at 10 m, km/h"})
    cloud_cover_pct: Mapped[float] = mapped_column(Float, info={"description": "Total cloud cover, percent"})
    trips: Mapped[Optional[int]] = mapped_column(Integer, info={"description": "Taxi trips picked up in the borough in the hour; empty after the last published TLC date"})
    total_usd: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), info={"description": "Sum of total amounts of those trips in USD"})
    speed_distance_miles: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), info={"description": "Distance of the plausible trips among them"})
    speed_duration_minutes: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), info={"description": "Duration of the same plausible trips"})
    pm25_readings: Mapped[Optional[int]] = mapped_column(Integer, info={"description": "PM2.5 readings from monitors in the borough in the hour"})
    pm25_sum: Mapped[Optional[float]] = mapped_column(Float, info={"description": "Sum of those readings, ug/m3"})
    synced_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), info={"description": "When the sync job last wrote the row, UTC"})


class SyncRun(Tsdb):
    __tablename__ = "sync_run"

    run_id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True, info={"description": "Sync run number"})
    started_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), info={"description": "Start time, UTC"})
    finished_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime(timezone=True), info={"description": "End time, UTC"})
    window_from: Mapped[Optional[dt.date]] = mapped_column(Date, info={"description": "First local date copied; empty for a full copy"})
    rows_read: Mapped[Optional[int]] = mapped_column(BigInteger, info={"description": "Rows read from wh_gold.FactWeatherHourly"})
    rows_written: Mapped[Optional[int]] = mapped_column(BigInteger, info={"description": "Rows inserted or updated in weather_hourly"})
    source_count: Mapped[Optional[int]] = mapped_column(BigInteger, info={"description": "Rows in wh_gold for the window after the copy"})
    target_count: Mapped[Optional[int]] = mapped_column(BigInteger, info={"description": "Rows in weather_hourly for the window after the copy"})
    status: Mapped[str] = mapped_column(String(16), info={"description": "running, succeeded, mismatch or failed"})
    message: Mapped[Optional[str]] = mapped_column(String(400), info={"description": "Error text when the run failed"})


event.listen(Tsdb.metadata, "before_create", DDL("CREATE EXTENSION IF NOT EXISTS timescaledb"))
event.listen(WeatherHourly.__table__, "after_create", DDL("SELECT create_hypertable('weather_hourly', by_range('time', INTERVAL '90 days'))"))


def engine():
    return create_engine(URL.create("postgresql+psycopg", username=OWNER, password=os.environ["TSDB_PASSWORD"], host="localhost", port=int(os.environ.get("TSDB_PORT", "5432")), database=DATABASE))


def setup():
    password = os.environ["TSDB_READER_PASSWORD"]
    if not re.fullmatch(r"[A-Za-z0-9]{16,}", password):
        raise ValueError("TSDB_READER_PASSWORD must be at least 16 letters and digits")
    target = engine()
    Tsdb.metadata.create_all(target)
    with target.begin() as connection:
        exists = connection.scalar(text("SELECT count(*) FROM pg_roles WHERE rolname = :name"), {"name": READER})
        verb = "ALTER" if exists else "CREATE"
        connection.exec_driver_sql(f"{verb} ROLE {READER} LOGIN PASSWORD '{password}'")
        connection.exec_driver_sql(f"GRANT CONNECT ON DATABASE {DATABASE} TO {READER}")
        connection.exec_driver_sql(f"GRANT USAGE ON SCHEMA public TO {READER}")
        connection.exec_driver_sql(f"GRANT SELECT ON ALL TABLES IN SCHEMA public TO {READER}")
        connection.exec_driver_sql(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO {READER}")


if __name__ == "__main__":
    setup()
