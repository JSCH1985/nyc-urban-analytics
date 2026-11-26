# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "{{LAKEHOUSE_ID}}",
# META       "default_lakehouse_name": "{{LAKEHOUSE_NAME}}",
# META       "default_lakehouse_workspace_id": "{{WORKSPACE_ID}}",
# META       "known_lakehouses": [
# META         {
# META           "id": "{{LAKEHOUSE_ID}}"
# META         }
# META       ]
# META     }
# META   }
# META }

# PARAMETERS CELL ********************

years = ""
api_key = ""

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

import os
import time
from datetime import datetime, timezone

import requests
from pyspark.sql import functions as F

if not api_key:
    raise ValueError("api_key parameter is required")

spark.sql("""
CREATE TABLE IF NOT EXISTS openaq_hours (
    sensor_id BIGINT,
    parameter STRING,
    units STRING,
    period_start_utc TIMESTAMP,
    period_start_local STRING,
    value DOUBLE,
    observed_count BIGINT,
    percent_coverage DOUBLE,
    loaded_at TIMESTAMP
) USING DELTA
""")
spark.sql("""
CREATE TABLE IF NOT EXISTS openaq_backfill_log (
    sensor_id BIGINT,
    source_month STRING,
    row_count INT,
    loaded_at TIMESTAMP
) USING DELTA
""")

session = requests.Session()
session.headers.update({"X-API-Key": api_key, "Accept": "application/json"})
last_call = 0.0


def get(path, params):
    global last_call
    for attempt in range(8):
        pause = 1.85 - (time.monotonic() - last_call)
        if pause > 0:
            time.sleep(pause)
        last_call = time.monotonic()
        try:
            response = session.get(f"https://api.openaq.org/{path}", params=params, timeout=120)
        except requests.RequestException:
            time.sleep(30 * (attempt + 1))
            continue
        if response.status_code == 200:
            return response.json()
        if response.status_code == 404:
            return None
        if response.status_code == 429:
            time.sleep(61)
            continue
        if response.status_code == 408 or response.status_code >= 500:
            time.sleep(30 * (attempt + 1))
            continue
        response.raise_for_status()
    raise RuntimeError(f"{path} {params} still failing after retries")


def utc(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)


def active_months(sensor_id):
    result = ((get(f"v3/sensors/{sensor_id}", {}) or {}).get("results") or [{}])[0]
    first = (result.get("datetimeFirst") or {}).get("utc")
    last = (result.get("datetimeLast") or {}).get("utc")
    return (first[:7] if first else "0000-00"), (last[:7] if last else "9999-99")


def bounds(month):
    year, number = int(month[:4]), int(month[5:])
    start = datetime(year, number, 1, tzinfo=timezone.utc)
    end = datetime(year + number // 12, number % 12 + 1, 1, tzinfo=timezone.utc)
    return start, min(end, now)


def fetch_hours(sensor, month):
    start, end = bounds(month)
    params = {"datetime_from": start.strftime("%Y-%m-%dT%H:%M:%SZ"), "datetime_to": end.strftime("%Y-%m-%dT%H:%M:%SZ"), "limit": 1000}
    rows, page = [], 1
    while True:
        results = (get(f"v3/sensors/{sensor.sensor_id}/hours", {**params, "page": page}) or {}).get("results") or []
        for hour in results:
            period = hour["period"]["datetimeFrom"]
            coverage = hour.get("coverage") or {}
            rows.append((
                sensor.sensor_id,
                sensor.parameter,
                sensor.units,
                utc(period["utc"]),
                period.get("local"),
                hour.get("value"),
                coverage.get("observedCount"),
                coverage.get("percentCoverage"),
                loaded_at,
            ))
        if len(results) < 1000:
            return rows
        page += 1


now = datetime.now(timezone.utc)
loaded_at = now
current = now.strftime("%Y-%m")
selected = [int(year) for year in years.split(";") if year.strip()] or list(range(2019, now.year + 1))
months = [f"{year}-{number:02d}" for year in selected for number in range(1, 13) if f"{year}-{number:02d}" <= current]

hour_schema = spark.read.table("openaq_hours").schema
log_schema = spark.read.table("openaq_backfill_log").schema
done = {(row.sensor_id, row.source_month) for row in spark.read.table("openaq_backfill_log").collect()}
sensors = spark.read.table("openaq_sensors").select("sensor_id", "parameter", "units").dropDuplicates(["sensor_id"]).orderBy("sensor_id").collect()

for sensor in sensors:
    pending = [month for month in months if (sensor.sensor_id, month) not in done]
    if not pending:
        continue
    first, last = active_months(sensor.sensor_id)
    rows, log = [], []
    for month in pending:
        fetched = fetch_hours(sensor, month) if first <= month <= last else []
        rows.extend(fetched)
        if month < current:
            log.append((sensor.sensor_id, month, len(fetched), loaded_at))
    if rows:
        spark.createDataFrame(rows, hour_schema).write.insertInto("openaq_hours")
    if log:
        spark.createDataFrame(log, log_schema).write.insertInto("openaq_backfill_log")
    print(f"sensor {sensor.sensor_id} {sensor.parameter}: {len(pending)} months, {len(rows)} rows")

summary = (
    spark.read.table("openaq_backfill_log")
    .groupBy(F.substring("source_month", 1, 4).alias("year"))
    .agg(
        F.countDistinct("sensor_id").alias("sensors"),
        F.count(F.lit(1)).alias("sensor_months"),
        F.sum(F.when(F.col("row_count") == 0, 1).otherwise(0)).alias("empty_months"),
        F.sum("row_count").alias("rows"),
    )
    .orderBy("year")
)
os.makedirs("/lakehouse/default/Files/reports", exist_ok=True)
summary.toPandas().to_csv("/lakehouse/default/Files/reports/openaq_backfill.csv", index=False)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
