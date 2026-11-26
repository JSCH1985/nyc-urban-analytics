import argparse
import datetime as dt
import logging
import sys

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from gold.load import key
from gold.models import DimWeatherCondition, FactWeatherHourly
from integrations import fabric, tsdb
from integrations.tsdb import SyncRun, WeatherHourly

OVERLAP_DAYS = 100
BATCH_ROWS = 5000
COPIED = [column.name for column in WeatherHourly.__table__.columns if column.name not in ("time", "borough", "synced_at")]


def utc_now():
    return dt.datetime.now(dt.timezone.utc)


def window_start(target, full):
    if full:
        return None
    with Session(target) as session:
        latest = session.scalar(select(func.max(WeatherHourly.time)))
    return None if latest is None else latest.date() - dt.timedelta(days=OVERLAP_DAYS)


def source_query(start):
    statement = select(
        FactWeatherHourly.hour_start_utc,
        FactWeatherHourly.borough,
        FactWeatherHourly.date_key,
        FactWeatherHourly.hour,
        FactWeatherHourly.weather_code,
        DimWeatherCondition.description,
        DimWeatherCondition.condition,
        DimWeatherCondition.condition_order,
        FactWeatherHourly.temperature_c,
        FactWeatherHourly.relative_humidity_pct,
        FactWeatherHourly.precipitation_mm,
        FactWeatherHourly.snowfall_cm,
        FactWeatherHourly.wind_speed_kmh,
        FactWeatherHourly.cloud_cover_pct,
        FactWeatherHourly.trips,
        FactWeatherHourly.total_usd,
        FactWeatherHourly.speed_distance_miles,
        FactWeatherHourly.speed_duration_minutes,
        FactWeatherHourly.pm25_readings,
        FactWeatherHourly.pm25_sum,
    ).join(DimWeatherCondition, DimWeatherCondition.weather_code == FactWeatherHourly.weather_code)
    return statement if start is None else statement.where(FactWeatherHourly.date_key >= key(start))


def as_target(row, synced_at):
    values = list(row)
    return {
        "time": values[0].replace(tzinfo=dt.timezone.utc),
        "borough": values[1],
        **dict(zip(COPIED, values[2:])),
        "synced_at": synced_at,
    }


def upsert(session, rows):
    statement = insert(WeatherHourly)
    session.execute(
        statement.on_conflict_do_update(
            index_elements=[WeatherHourly.time, WeatherHourly.borough],
            set_={name: statement.excluded[name] for name in COPIED + ["synced_at"]},
        ),
        rows,
    )


def count_source(source, start):
    statement = select(func.count()).select_from(FactWeatherHourly)
    if start is not None:
        statement = statement.where(FactWeatherHourly.date_key >= key(start))
    with source.connect() as connection:
        return connection.scalar(statement)


def count_target(session, start):
    statement = select(func.count()).select_from(WeatherHourly)
    if start is not None:
        statement = statement.where(WeatherHourly.date_key >= key(start))
    return session.scalar(statement)


def sync(server, full=False, interactive=True):
    target = tsdb.engine()
    start = window_start(target, full)
    with Session(target, expire_on_commit=False) as session, session.begin():
        record = SyncRun(started_at=utc_now(), window_from=start, status="running")
        session.add(record)
    try:
        source = fabric.warehouse_engine(server, interactive=interactive)
        synced_at = utc_now()
        read = 0
        with source.connect() as connection, Session(target) as session:
            result = connection.execute(source_query(start))
            while rows := result.fetchmany(BATCH_ROWS):
                with session.begin():
                    upsert(session, [as_target(row, synced_at) for row in rows])
                read += len(rows)
        with Session(target, expire_on_commit=False) as session, session.begin():
            record = session.merge(record)
            record.rows_read = read
            record.rows_written = read
            record.source_count = count_source(source, start)
            record.target_count = count_target(session, start)
            record.status = "succeeded" if record.source_count == record.target_count else "mismatch"
            record.finished_at = utc_now()
    except Exception as error:
        with Session(target, expire_on_commit=False) as session, session.begin():
            record = session.merge(record)
            record.status = "failed"
            record.message = str(error)[:400]
            record.finished_at = utc_now()
        raise
    return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", required=True)
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--unattended", action="store_true")
    parser.add_argument("--log")
    args = parser.parse_args()
    if args.log:
        logging.basicConfig(filename=args.log, level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    else:
        logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(asctime)s %(message)s")
    logging.getLogger("azure").setLevel(logging.WARNING)
    try:
        record = sync(args.server, full=args.full, interactive=not args.unattended)
    except Exception:
        logging.exception("weather sync failed")
        sys.exit(1)
    logging.info(
        "run %s %s: window from %s, %s rows copied, wh_gold %s rows, TimescaleDB %s rows",
        record.run_id, record.status, record.window_from or "the beginning", record.rows_read, record.source_count, record.target_count,
    )
    sys.exit(0 if record.status == "succeeded" else 1)


if __name__ == "__main__":
    main()
