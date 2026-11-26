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

history = "false"

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

import os
import time
from datetime import date, datetime, timedelta, timezone

import requests
from pyspark.sql import functions as F

spark.conf.set("spark.sql.session.timeZone", "UTC")

BOROUGHS = [
    ("Manhattan", 40.7831, -73.9712),
    ("Brooklyn", 40.6782, -73.9442),
    ("Queens", 40.7282, -73.7949),
    ("Bronx", 40.8448, -73.8648),
    ("Staten Island", 40.5795, -74.1502),
]
VARIABLES = ["temperature_2m", "relative_humidity_2m", "precipitation", "snowfall", "wind_speed_10m", "cloud_cover", "weather_code"]
ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
FORECAST = "https://api.open-meteo.com/v1/forecast"
HISTORY_START = date(2019, 1, 1)

spark.sql("""
CREATE TABLE IF NOT EXISTS weather_hourly (
    borough STRING,
    latitude DOUBLE,
    longitude DOUBLE,
    observed_utc TIMESTAMP,
    temperature_c DOUBLE,
    relative_humidity_pct DOUBLE,
    precipitation_mm DOUBLE,
    snowfall_cm DOUBLE,
    wind_speed_kmh DOUBLE,
    cloud_cover_pct DOUBLE,
    weather_code INT,
    source STRING,
    loaded_at TIMESTAMP
) USING DELTA
""")

schema = spark.read.table("weather_hourly").schema
now = datetime.now(timezone.utc)
loaded_at = now
today = now.date()
session = requests.Session()


def get(url, params):
    for attempt in range(6):
        try:
            response = session.get(url, params=params, timeout=300)
        except requests.RequestException:
            time.sleep(30 * (attempt + 1))
            continue
        if response.status_code == 200:
            return response.json()
        if response.status_code == 429:
            time.sleep(61)
            continue
        if response.status_code >= 500:
            time.sleep(30 * (attempt + 1))
            continue
        response.raise_for_status()
    raise RuntimeError(f"{url} {params} still failing after retries")


def number(value):
    return None if value is None else float(value)


def fetch(url, source, params):
    payload = get(url, {
        "latitude": ",".join(str(latitude) for _, latitude, _ in BOROUGHS),
        "longitude": ",".join(str(longitude) for _, _, longitude in BOROUGHS),
        "hourly": ",".join(VARIABLES),
        "timezone": "GMT",
        **params,
    })
    locations = payload if isinstance(payload, list) else [payload]
    rows = []
    for (borough, latitude, longitude), location in zip(BOROUGHS, locations):
        hourly = location["hourly"]
        for index, stamp in enumerate(hourly["time"]):
            observed = datetime.fromisoformat(stamp).replace(tzinfo=timezone.utc)
            values = [hourly[variable][index] for variable in VARIABLES]
            if observed > now or all(value is None for value in values):
                continue
            code = values[-1]
            rows.append((borough, latitude, longitude, observed, *[number(value) for value in values[:-1]], None if code is None else int(code), source, loaded_at))
    return rows


archive_from = HISTORY_START if history == "true" else today - timedelta(days=40)
archive_to = today - timedelta(days=6)
rows = []
for year in range(archive_from.year, archive_to.year + 1):
    start = max(archive_from, date(year, 1, 1))
    end = min(archive_to, date(year, 12, 31))
    rows += fetch(ARCHIVE, "archive", {"start_date": start.isoformat(), "end_date": end.isoformat()})
rows += fetch(FORECAST, "forecast", {"past_days": 10, "forecast_days": 1})

batch = spark.createDataFrame(rows, schema)
batch.write.insertInto("weather_hourly")

os.makedirs("/lakehouse/default/Files/reports", exist_ok=True)
batch.groupBy("source", "borough").agg(
    F.count(F.lit(1)).alias("rows"),
    F.min("observed_utc").alias("first_utc"),
    F.max("observed_utc").alias("last_utc"),
    F.sum(F.col("temperature_c").isNull().cast("int")).alias("missing_temperature"),
).orderBy("source", "borough").toPandas().to_csv("/lakehouse/default/Files/reports/weather_load.csv", index=False)
print(f"appended {len(rows)} rows; weather_hourly now holds {spark.read.table('weather_hourly').count()} rows")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
