import datetime as dt
from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy import Numeric, and_, case, cast, delete, extract, func, insert, inspect, literal_column, select, union_all
from sqlalchemy.orm import Session

from gold.models import (
    DimDate,
    DimFX,
    DimGDP,
    DimHour,
    DimWeatherCondition,
    DimZone,
    FactAirQualityDaily,
    FactAirQualityHourly,
    FactTaxiDaily,
    FactTaxiHourly,
    FactWeatherHourly,
    Gold,
    LoadRun,
    air_quality_hourly,
    calendar,
    fx_daily,
    gdp_yearly,
    monitor_zone,
    taxi_trips,
    weather_hourly,
    zones,
)

HISTORY_START = dt.date(2019, 1, 1)
OUTSIDE_NYC = 0
MAX_TRIP_MILES = 100
MAX_SPEED_MPH = 80
MAX_TRIP_MINUTES = 180
DAY_PARTS = [("Night", 0), ("Morning peak", 6), ("Midday", 10), ("Evening peak", 16), ("Evening", 20)]
CONDITIONS = ["Clear", "Cloudy", "Fog", "Drizzle", "Rain", "Snow", "Thunderstorm"]
WEATHER_CODES = [
    (0, "Clear sky", "Clear"),
    (1, "Mainly clear", "Clear"),
    (2, "Partly cloudy", "Cloudy"),
    (3, "Overcast", "Cloudy"),
    (45, "Fog", "Fog"),
    (48, "Depositing rime fog", "Fog"),
    (51, "Light drizzle", "Drizzle"),
    (53, "Moderate drizzle", "Drizzle"),
    (55, "Dense drizzle", "Drizzle"),
    (56, "Light freezing drizzle", "Drizzle"),
    (57, "Dense freezing drizzle", "Drizzle"),
    (61, "Slight rain", "Rain"),
    (63, "Moderate rain", "Rain"),
    (65, "Heavy rain", "Rain"),
    (66, "Light freezing rain", "Rain"),
    (67, "Heavy freezing rain", "Rain"),
    (71, "Slight snowfall", "Snow"),
    (73, "Moderate snowfall", "Snow"),
    (75, "Heavy snowfall", "Snow"),
    (77, "Snow grains", "Snow"),
    (80, "Slight rain showers", "Rain"),
    (81, "Moderate rain showers", "Rain"),
    (82, "Violent rain showers", "Rain"),
    (85, "Slight snow showers", "Snow"),
    (86, "Heavy snow showers", "Snow"),
    (95, "Thunderstorm", "Thunderstorm"),
    (96, "Thunderstorm with slight hail", "Thunderstorm"),
    (99, "Thunderstorm with heavy hail", "Thunderstorm"),
]


@dataclass
class Step:
    target: str
    period_from: Optional[dt.date]
    period_to: Optional[dt.date]
    delete: Any
    insert: Any
    source_count: Any
    target_count: Any
    rows: Optional[list] = None


def date_key(column):
    return extract("year", column) * 10000 + extract("month", column) * 100 + extract("day", column)


def key(day):
    return day.year * 10000 + day.month * 100 + day.day


def months_back(day, count):
    month = day.year * 12 + day.month - 1 - count
    return dt.date(month // 12, month % 12 + 1, 1)


def utc_now():
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


def full_refresh(target, model, columns, source, source_table, extra_rows=0):
    return Step(
        target,
        None,
        None,
        delete(model),
        insert(model).from_select(columns, source),
        select(func.count() + extra_rows if extra_rows else func.count()).select_from(source_table),
        select(func.count()).select_from(model),
    )


def hours():
    rows = []
    for hour in range(24):
        order = max(index for index, (_, start) in enumerate(DAY_PARTS) if hour >= start)
        rows.append({"hour": hour, "hour_label": f"{hour:02d}:00", "day_part": DAY_PARTS[order][0], "day_part_order": order})
    return rows


def weather_conditions():
    return [
        {"weather_code": code, "description": description, "condition": condition, "condition_order": CONDITIONS.index(condition)}
        for code, description, condition in WEATHER_CODES
    ]


def periods(today, full=False, rebuilt=()):
    rebuilt = set(rebuilt)
    taxi = months_back(today, 3)
    air = today - dt.timedelta(days=7)
    recent = {
        "FactTaxiDaily": (taxi, {"FactTaxiDaily"}),
        "FactAirQualityDaily": (air, {"FactAirQualityDaily"}),
        "FactTaxiHourly": (taxi, {"FactTaxiHourly"}),
        "FactAirQualityHourly": (air, {"FactAirQualityHourly"}),
        "FactWeatherHourly": (taxi, {"FactWeatherHourly", "FactTaxiHourly", "FactAirQualityHourly"}),
    }
    return {target: HISTORY_START if full or inputs & rebuilt else start for target, (start, inputs) in recent.items()}


def history(today):
    return periods(today, full=True)


def steps(periods, today):
    taxi_daily_from = periods["FactTaxiDaily"]
    air_daily_from = periods["FactAirQualityDaily"]
    taxi_hourly_from = periods["FactTaxiHourly"]
    air_hourly_from = periods["FactAirQualityHourly"]
    weather_from = periods["FactWeatherHourly"]
    taxi_daily_period = taxi_trips.c.pickup_date.between(taxi_daily_from, today)
    taxi_hourly_period = taxi_trips.c.pickup_date.between(taxi_hourly_from, today)
    air_daily_period = air_quality_hourly.c.local_date.between(air_daily_from, today) & air_quality_hourly.c.location_id.is_not(None)
    air_hourly_period = air_quality_hourly.c.local_date.between(air_hourly_from, today) & air_quality_hourly.c.location_id.is_not(None)
    weather_period = weather_hourly.c.local_date.between(weather_from, today)
    taxi_keys = FactTaxiDaily.date_key.between(key(taxi_daily_from), key(today))
    air_keys = FactAirQualityDaily.date_key.between(key(air_daily_from), key(today))
    taxi_hour_keys = FactTaxiHourly.date_key.between(key(taxi_hourly_from), key(today))
    air_hour_keys = FactAirQualityHourly.date_key.between(key(air_hourly_from), key(today))
    weather_keys = FactWeatherHourly.date_key.between(key(weather_from), key(today))
    taxi_borough = (
        select(
            FactTaxiHourly.date_key,
            FactTaxiHourly.hour,
            DimZone.borough,
            func.sum(FactTaxiHourly.trips).label("trips"),
            func.sum(FactTaxiHourly.total_usd).label("total_usd"),
            func.sum(FactTaxiHourly.speed_distance_miles).label("speed_distance_miles"),
            func.sum(FactTaxiHourly.speed_duration_minutes).label("speed_duration_minutes"),
        )
        .join(DimZone, DimZone.zone_id == FactTaxiHourly.zone_id)
        .where(FactTaxiHourly.date_key.between(key(weather_from), key(today)))
        .group_by(FactTaxiHourly.date_key, FactTaxiHourly.hour, DimZone.borough)
        .subquery("taxi_borough")
    )
    pm25_borough = (
        select(
            FactAirQualityHourly.date_key,
            FactAirQualityHourly.hour,
            DimZone.borough,
            func.sum(FactAirQualityHourly.readings).label("readings"),
            func.sum(FactAirQualityHourly.value_sum).label("value_sum"),
        )
        .join(DimZone, DimZone.zone_id == FactAirQualityHourly.zone_id)
        .where(FactAirQualityHourly.parameter == "pm25", FactAirQualityHourly.date_key.between(key(weather_from), key(today)))
        .group_by(FactAirQualityHourly.date_key, FactAirQualityHourly.hour, DimZone.borough)
        .subquery("pm25_borough")
    )
    weather_date_key = date_key(weather_hourly.c.local_date)
    weather_source = weather_hourly.outerjoin(
        taxi_borough,
        and_(taxi_borough.c.date_key == weather_date_key, taxi_borough.c.hour == weather_hourly.c.local_hour, taxi_borough.c.borough == weather_hourly.c.borough),
    ).outerjoin(
        pm25_borough,
        and_(pm25_borough.c.date_key == weather_date_key, pm25_borough.c.hour == weather_hourly.c.local_hour, pm25_borough.c.borough == weather_hourly.c.borough),
    )
    taxi_covered = weather_date_key <= select(func.max(FactTaxiHourly.date_key)).scalar_subquery()
    pm25_covered = weather_date_key <= select(func.max(FactAirQualityHourly.date_key)).where(FactAirQualityHourly.parameter == "pm25").scalar_subquery()
    weather_rows = weather_conditions()
    air_source = air_quality_hourly.outerjoin(monitor_zone, monitor_zone.c.location_id == air_quality_hourly.c.location_id)
    air_zone = func.coalesce(monitor_zone.c.zone_id, OUTSIDE_NYC)
    plausible = (
        (taxi_trips.c.trip_distance > 0)
        & (taxi_trips.c.trip_distance <= MAX_TRIP_MILES)
        & (taxi_trips.c.trip_distance * 60 <= MAX_SPEED_MPH * taxi_trips.c.duration_min)
        & (taxi_trips.c.duration_min <= MAX_TRIP_MINUTES)
    )
    hour_rows = hours()
    return [
        full_refresh(
            "DimDate",
            DimDate,
            ["date_key", "calendar_date", "year", "quarter", "month", "month_name", "day", "weekday", "weekday_name", "is_weekend"],
            select(
                calendar.c.date_key,
                calendar.c.date,
                calendar.c.year,
                calendar.c.quarter,
                calendar.c.month,
                calendar.c.month_name,
                calendar.c.day,
                calendar.c.weekday,
                calendar.c.weekday_name,
                calendar.c.is_weekend,
            ),
            calendar,
        ),
        full_refresh(
            "DimZone",
            DimZone,
            ["zone_id", "borough", "zone", "service_zone"],
            union_all(
                select(zones.c.zone_id, zones.c.borough, zones.c.zone, zones.c.service_zone),
                select(literal_column(str(OUTSIDE_NYC)), literal_column("'Outside NYC'"), literal_column("'Outside NYC'"), literal_column("'N/A'")),
            ),
            zones,
            extra_rows=1,
        ),
        full_refresh(
            "DimFX",
            DimFX,
            ["date_key", "rate_date", "usd_per_eur", "is_published"],
            select(date_key(fx_daily.c.rate_date), fx_daily.c.rate_date, fx_daily.c.usd_per_eur, fx_daily.c.is_published),
            fx_daily,
        ),
        full_refresh(
            "DimGDP",
            DimGDP,
            ["year", "country_code", "gdp_usd"],
            select(gdp_yearly.c.year, gdp_yearly.c.country_code, gdp_yearly.c.gdp_usd),
            gdp_yearly,
        ),
        Step(
            "DimHour",
            None,
            None,
            delete(DimHour),
            insert(DimHour),
            select(literal_column(str(len(hour_rows)))),
            select(func.count()).select_from(DimHour),
            hour_rows,
        ),
        Step(
            "FactTaxiDaily",
            taxi_daily_from,
            today,
            delete(FactTaxiDaily).where(taxi_keys),
            insert(FactTaxiDaily).from_select(
                ["date_key", "zone_id", "trips", "passengers", "distance_miles", "duration_minutes", "fare_usd", "tip_usd", "total_usd"],
                select(
                    date_key(taxi_trips.c.pickup_date),
                    taxi_trips.c.pickup_zone_id,
                    func.count(),
                    func.sum(taxi_trips.c.passenger_count),
                    cast(func.sum(taxi_trips.c.trip_distance), Numeric(14, 2)),
                    cast(func.sum(taxi_trips.c.duration_min), Numeric(14, 2)),
                    func.sum(taxi_trips.c.fare_amount),
                    func.sum(taxi_trips.c.tip_amount),
                    func.sum(taxi_trips.c.total_amount),
                )
                .where(taxi_daily_period)
                .group_by(taxi_trips.c.pickup_date, taxi_trips.c.pickup_zone_id),
            ),
            select(func.count()).select_from(taxi_trips).where(taxi_daily_period),
            select(func.coalesce(func.sum(FactTaxiDaily.trips), 0)).where(taxi_keys),
        ),
        Step(
            "FactAirQualityDaily",
            air_daily_from,
            today,
            delete(FactAirQualityDaily).where(air_keys),
            insert(FactAirQualityDaily).from_select(
                ["date_key", "location_id", "parameter", "zone_id", "unit", "readings", "value_sum", "value_max"],
                select(
                    date_key(air_quality_hourly.c.local_date),
                    air_quality_hourly.c.location_id,
                    air_quality_hourly.c.parameter,
                    air_zone,
                    air_quality_hourly.c.unit,
                    func.count(),
                    func.sum(air_quality_hourly.c.value),
                    func.max(air_quality_hourly.c.value),
                )
                .select_from(air_source)
                .where(air_daily_period)
                .group_by(
                    air_quality_hourly.c.local_date,
                    air_quality_hourly.c.location_id,
                    air_quality_hourly.c.parameter,
                    monitor_zone.c.zone_id,
                    air_quality_hourly.c.unit,
                ),
            ),
            select(func.count()).select_from(air_quality_hourly).where(air_daily_period),
            select(func.coalesce(func.sum(FactAirQualityDaily.readings), 0)).where(air_keys),
        ),
        Step(
            "FactTaxiHourly",
            taxi_hourly_from,
            today,
            delete(FactTaxiHourly).where(taxi_hour_keys),
            insert(FactTaxiHourly).from_select(
                ["date_key", "hour", "zone_id", "trips", "distance_miles", "duration_minutes", "total_usd", "speed_distance_miles", "speed_duration_minutes"],
                select(
                    date_key(taxi_trips.c.pickup_date),
                    taxi_trips.c.pickup_hour,
                    taxi_trips.c.pickup_zone_id,
                    func.count(),
                    cast(func.sum(taxi_trips.c.trip_distance), Numeric(14, 2)),
                    cast(func.sum(taxi_trips.c.duration_min), Numeric(14, 2)),
                    func.sum(taxi_trips.c.total_amount),
                    cast(func.sum(case((plausible, taxi_trips.c.trip_distance))), Numeric(14, 2)),
                    cast(func.sum(case((plausible, taxi_trips.c.duration_min))), Numeric(14, 2)),
                )
                .where(taxi_hourly_period)
                .group_by(taxi_trips.c.pickup_date, taxi_trips.c.pickup_hour, taxi_trips.c.pickup_zone_id),
            ),
            select(func.count()).select_from(taxi_trips).where(taxi_hourly_period),
            select(func.coalesce(func.sum(FactTaxiHourly.trips), 0)).where(taxi_hour_keys),
        ),
        Step(
            "FactAirQualityHourly",
            air_hourly_from,
            today,
            delete(FactAirQualityHourly).where(air_hour_keys),
            insert(FactAirQualityHourly).from_select(
                ["date_key", "hour", "location_id", "parameter", "zone_id", "unit", "readings", "value_sum"],
                select(
                    date_key(air_quality_hourly.c.local_date),
                    air_quality_hourly.c.local_hour,
                    air_quality_hourly.c.location_id,
                    air_quality_hourly.c.parameter,
                    air_zone,
                    air_quality_hourly.c.unit,
                    func.count(),
                    func.sum(air_quality_hourly.c.value),
                )
                .select_from(air_source)
                .where(air_hourly_period)
                .group_by(
                    air_quality_hourly.c.local_date,
                    air_quality_hourly.c.local_hour,
                    air_quality_hourly.c.location_id,
                    air_quality_hourly.c.parameter,
                    monitor_zone.c.zone_id,
                    air_quality_hourly.c.unit,
                ),
            ),
            select(func.count()).select_from(air_quality_hourly).where(air_hourly_period),
            select(func.coalesce(func.sum(FactAirQualityHourly.readings), 0)).where(air_hour_keys),
        ),
        Step(
            "DimWeatherCondition",
            None,
            None,
            delete(DimWeatherCondition),
            insert(DimWeatherCondition),
            select(literal_column(str(len(weather_rows)))),
            select(func.count()).select_from(DimWeatherCondition),
            weather_rows,
        ),
        Step(
            "FactWeatherHourly",
            weather_from,
            today,
            delete(FactWeatherHourly).where(weather_keys),
            insert(FactWeatherHourly).from_select(
                [
                    "date_key",
                    "hour",
                    "borough",
                    "hour_start_utc",
                    "weather_code",
                    "temperature_c",
                    "relative_humidity_pct",
                    "precipitation_mm",
                    "snowfall_cm",
                    "wind_speed_kmh",
                    "cloud_cover_pct",
                    "trips",
                    "total_usd",
                    "speed_distance_miles",
                    "speed_duration_minutes",
                    "pm25_readings",
                    "pm25_sum",
                ],
                select(
                    weather_date_key,
                    weather_hourly.c.local_hour,
                    weather_hourly.c.borough,
                    weather_hourly.c.hour_start_utc,
                    weather_hourly.c.weather_code,
                    weather_hourly.c.temperature_c,
                    weather_hourly.c.relative_humidity_pct,
                    weather_hourly.c.precipitation_mm,
                    weather_hourly.c.snowfall_cm,
                    weather_hourly.c.wind_speed_kmh,
                    weather_hourly.c.cloud_cover_pct,
                    case((taxi_covered, func.coalesce(taxi_borough.c.trips, 0))),
                    case((taxi_covered, func.coalesce(taxi_borough.c.total_usd, 0))),
                    case((taxi_covered, func.coalesce(taxi_borough.c.speed_distance_miles, 0))),
                    case((taxi_covered, func.coalesce(taxi_borough.c.speed_duration_minutes, 0))),
                    case((pm25_covered, func.coalesce(pm25_borough.c.readings, 0))),
                    case((pm25_covered, func.coalesce(pm25_borough.c.value_sum, 0))),
                )
                .select_from(weather_source)
                .where(weather_period),
            ),
            select(func.count()).select_from(weather_hourly).where(weather_period),
            select(func.count()).select_from(FactWeatherHourly).where(weather_keys),
        ),
    ]


def execute(engine, run_id, step):
    record = LoadRun(run_id=run_id, target=step.target, period_from=step.period_from, period_to=step.period_to, started_at=utc_now(), status="running")
    try:
        with Session(engine, expire_on_commit=False) as session, session.begin():
            record.rows_deleted = session.execute(step.delete, execution_options={"synchronize_session": False}).rowcount
            if step.rows is None:
                record.rows_inserted = session.execute(step.insert).rowcount
            else:
                session.execute(step.insert, step.rows)
                record.rows_inserted = len(step.rows)
            record.source_count = session.scalar(step.source_count)
            record.target_count = session.scalar(step.target_count)
            record.status = "succeeded" if record.source_count == record.target_count else "mismatch"
            record.finished_at = utc_now()
            session.add(record)
    except Exception as error:
        record.status = "failed"
        record.finished_at = utc_now()
        record.message = str(error)[:400]
        with Session(engine, expire_on_commit=False) as session, session.begin():
            session.add(record)
        raise
    return {column.key: getattr(record, column.key) for column in LoadRun.__table__.columns}


def sync_schema(engine):
    inspector = inspect(engine)
    rebuilt = []
    for table in Gold.metadata.sorted_tables:
        if not inspector.has_table(table.name):
            rebuilt.append(table.name)
        elif table.name != LoadRun.__tablename__ and {(column["name"], bool(column["nullable"])) for column in inspector.get_columns(table.name)} != {(column.name, bool(column.nullable)) for column in table.columns}:
            table.drop(engine)
            rebuilt.append(table.name)
    Gold.metadata.create_all(engine)
    return rebuilt


def run(engine, full=False, today=None):
    today = today or dt.date.today()
    rebuilt = sync_schema(engine)
    with Session(engine) as session:
        run_id = session.scalar(select(func.coalesce(func.max(LoadRun.run_id), 0))) + 1
    return [execute(engine, run_id, step) for step in steps(periods(today, full, rebuilt), today)]
