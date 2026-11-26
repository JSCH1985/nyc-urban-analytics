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
# META         },
# META         {
# META           "id": "{{LH_BRONZE_ID}}"
# META         }
# META       ]
# META     }
# META   }
# META }

# CELL ********************

import math
import os
import struct
import zipfile


def read_dbf(data):
    count, header_length, record_length = struct.unpack("<IHH", data[4:12])
    fields, offset = [], 32
    while data[offset] != 0x0D:
        name = data[offset:offset + 11].split(b"\x00")[0].decode("ascii")
        fields.append((name, data[offset + 16]))
        offset += 32
    records = []
    for index in range(count):
        start = header_length + index * record_length + 1
        position, record = start, {}
        for name, width in fields:
            record[name] = data[position:position + width].decode("latin-1").strip()
            position += width
        records.append(record)
    return records


def read_shp(data):
    shapes, offset = [], 100
    while offset < len(data):
        length = struct.unpack(">i", data[offset + 4:offset + 8])[0] * 2
        content = data[offset + 8:offset + 8 + length]
        shape_type = struct.unpack("<i", content[:4])[0]
        if shape_type in (5, 15, 25):
            bbox = struct.unpack("<4d", content[4:36])
            parts_count, points_count = struct.unpack("<2i", content[36:44])
            parts = list(struct.unpack(f"<{parts_count}i", content[44:44 + 4 * parts_count]))
            start = 44 + 4 * parts_count
            points = [struct.unpack("<2d", content[start + 16 * i:start + 16 * i + 16]) for i in range(points_count)]
            rings = [points[a:b] for a, b in zip(parts, parts[1:] + [points_count])]
            shapes.append((bbox, rings))
        else:
            shapes.append((None, []))
        offset += 8 + length
    return shapes


def to_state_plane(latitude, longitude):
    a, f = 6378137.0, 1 / 298.257222101
    e = math.sqrt(2 * f - f * f)
    lat1, lat2, lat0, lon0 = map(math.radians, (41 + 2 / 60, 40 + 40 / 60, 40 + 10 / 60, -74.0))
    m = lambda phi: math.cos(phi) / math.sqrt(1 - (e * math.sin(phi)) ** 2)
    t = lambda phi: math.tan(math.pi / 4 - phi / 2) / ((1 - e * math.sin(phi)) / (1 + e * math.sin(phi))) ** (e / 2)
    n = (math.log(m(lat1)) - math.log(m(lat2))) / (math.log(t(lat1)) - math.log(t(lat2)))
    big_f = m(lat1) / (n * t(lat1) ** n)
    rho = lambda phi: a * big_f * t(phi) ** n
    theta = n * (math.radians(longitude) - lon0)
    x = rho(math.radians(latitude)) * math.sin(theta) + 300000.0
    y = rho(lat0) - rho(math.radians(latitude)) * math.cos(theta)
    feet = 1200 / 3937
    return x / feet, y / feet


def contains(rings, x, y):
    inside = False
    for ring in rings:
        for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
            if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
                inside = not inside
    return inside


def zone_lookup(zip_path):
    with zipfile.ZipFile(zip_path) as archive:
        names = {n.lower().rsplit("/", 1)[-1]: n for n in archive.namelist()}
        shapes = read_shp(archive.read(names["taxi_zones.shp"]))
        records = read_dbf(archive.read(names["taxi_zones.dbf"]))
    zones = [(int(float(r["LocationID"])), bbox, rings) for r, (bbox, rings) in zip(records, shapes) if bbox]

    def lookup(latitude, longitude):
        x, y = to_state_plane(latitude, longitude)
        for zone_id, (xmin, ymin, xmax, ymax), rings in zones:
            if xmin <= x <= xmax and ymin <= y <= ymax and contains(rings, x, y):
                return zone_id
        return None

    return lookup

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

from pyspark.sql import Window
from pyspark.sql import functions as F

spark.conf.set("spark.sql.session.timeZone", "UTC")

bronze = "abfss://{{WORKSPACE_ID}}@onelake.dfs.fabric.microsoft.com/{{LH_BRONZE_ID}}"

spark.sql("CREATE TABLE IF NOT EXISTS zones (zone_id INT, borough STRING, zone STRING, service_zone STRING) USING DELTA")
spark.sql("CREATE TABLE IF NOT EXISTS monitor_zone (location_id BIGINT, location_name STRING, latitude DOUBLE, longitude DOUBLE, zone_id INT) USING DELTA")
spark.sql("CREATE TABLE IF NOT EXISTS fx_daily (rate_date DATE, usd_per_eur DECIMAL(10,4), is_published BOOLEAN) USING DELTA")
spark.sql("CREATE TABLE IF NOT EXISTS gdp_yearly (country_code STRING, year INT, gdp_usd DECIMAL(20,2)) USING DELTA")
spark.sql("""
CREATE TABLE IF NOT EXISTS calendar (
    date DATE,
    date_key INT,
    year INT,
    quarter INT,
    month INT,
    month_name STRING,
    day INT,
    weekday INT,
    weekday_name STRING,
    is_weekend BOOLEAN
) USING DELTA
""")

zones = (
    spark.read.option("header", True).csv(f"{bronze}/Files/taxi/zones/taxi_zone_lookup.csv")
    .select(
        F.col("LocationID").cast("int").alias("zone_id"),
        F.col("Borough").alias("borough"),
        F.col("Zone").alias("zone"),
        F.col("service_zone"),
    )
)
zones.write.insertInto("zones", overwrite=True)

notebookutils.fs.cp(f"{bronze}/Files/taxi/zones/taxi_zones.zip", "file:/tmp/taxi_zones.zip")
lookup = zone_lookup("/tmp/taxi_zones.zip")
locations = (
    spark.read.format("delta").load(f"{bronze}/Tables/openaq_sensors")
    .select("location_id", "location_name", "latitude", "longitude")
    .dropDuplicates(["location_id"])
    .collect()
)
mapped = [(r.location_id, r.location_name, r.latitude, r.longitude, lookup(r.latitude, r.longitude)) for r in locations]
spark.createDataFrame(mapped, "location_id BIGINT, location_name STRING, latitude DOUBLE, longitude DOUBLE, zone_id INT").write.insertInto("monitor_zone", overwrite=True)

rates = spark.read.format("delta").load(f"{bronze}/Tables/ecb_usd_eur").select("rate_date", "usd_per_eur")
days = spark.sql("SELECT explode(sequence(DATE'2018-12-01', current_date(), INTERVAL 1 DAY)) AS rate_date")
carried = Window.orderBy("rate_date").rowsBetween(Window.unboundedPreceding, 0)
fx = (
    days.join(rates, "rate_date", "left")
    .withColumn("is_published", F.col("usd_per_eur").isNotNull())
    .withColumn("usd_per_eur", F.last("usd_per_eur", ignorenulls=True).over(carried).cast("decimal(10,4)"))
    .where(F.col("rate_date") >= "2019-01-01")
    .select("rate_date", "usd_per_eur", "is_published")
)
fx.write.insertInto("fx_daily", overwrite=True)

gdp = spark.read.format("delta").load(f"{bronze}/Tables/worldbank_gdp").select(
    F.col("country_code"),
    F.col("year").cast("int").alias("year"),
    F.col("gdp_usd").cast("decimal(20,2)").alias("gdp_usd"),
)
gdp.write.insertInto("gdp_yearly", overwrite=True)

weekday = ((F.dayofweek("date") + 5) % 7) + 1
calendar = (
    spark.sql("SELECT explode(sequence(DATE'2019-01-01', DATE'2027-12-31', INTERVAL 1 DAY)) AS date")
    .select(
        "date",
        F.date_format("date", "yyyyMMdd").cast("int").alias("date_key"),
        F.year("date").alias("year"),
        F.quarter("date").alias("quarter"),
        F.month("date").alias("month"),
        F.date_format("date", "MMMM").alias("month_name"),
        F.dayofmonth("date").alias("day"),
        weekday.alias("weekday"),
        F.date_format("date", "EEEE").alias("weekday_name"),
        (weekday >= 6).alias("is_weekend"),
    )
)
calendar.write.insertInto("calendar", overwrite=True)

summary = spark.createDataFrame(
    [
        ("zones", spark.read.table("zones").count()),
        ("monitor_zone", spark.read.table("monitor_zone").count()),
        ("monitor_zone_unmapped", spark.read.table("monitor_zone").where("zone_id IS NULL").count()),
        ("fx_daily", spark.read.table("fx_daily").count()),
        ("fx_daily_null_rate", spark.read.table("fx_daily").where("usd_per_eur IS NULL").count()),
        ("gdp_yearly", spark.read.table("gdp_yearly").count()),
        ("calendar", spark.read.table("calendar").count()),
    ],
    "check STRING, value BIGINT",
)
os.makedirs("/lakehouse/default/Files/reports", exist_ok=True)
summary.toPandas().to_csv("/lakehouse/default/Files/reports/reference_summary.csv", index=False)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
