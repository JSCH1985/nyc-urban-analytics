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

import os

from pyspark.sql import Window
from pyspark.sql import functions as F

spark.conf.set("spark.sql.session.timeZone", "UTC")

bronze = "abfss://{{WORKSPACE_ID}}@onelake.dfs.fabric.microsoft.com/{{LH_BRONZE_ID}}"

spark.sql("""
CREATE TABLE IF NOT EXISTS weather_hourly (
    borough STRING,
    local_date DATE,
    local_hour INT,
    hour_start_utc TIMESTAMP,
    temperature_c DOUBLE,
    relative_humidity_pct DOUBLE,
    precipitation_mm DOUBLE,
    snowfall_cm DOUBLE,
    wind_speed_kmh DOUBLE,
    cloud_cover_pct DOUBLE,
    weather_code INT,
    source STRING
) USING DELTA
""")

raw = spark.read.format("delta").load(f"{bronze}/Tables/weather_hourly")

preferred = Window.partitionBy("borough", "observed_utc").orderBy(F.when(F.col("source") == "archive", 0).otherwise(1), F.col("loaded_at").desc())
unique = raw.withColumn("version", F.row_number().over(preferred)).where(F.col("version") == 1).drop("version")
valid = unique.where(
    F.col("temperature_c").between(-50, 60)
    & F.col("relative_humidity_pct").between(0, 100)
    & (F.col("precipitation_mm") >= 0)
    & (F.col("snowfall_cm") >= 0)
    & (F.col("wind_speed_kmh") >= 0)
    & F.col("cloud_cover_pct").between(0, 100)
    & F.col("weather_code").isNotNull()
)
local = F.from_utc_timestamp("observed_utc", "America/New_York")
clean = (
    valid.withColumn("local", local)
    .groupBy("borough", F.to_date("local").alias("local_date"), F.hour("local").alias("local_hour"))
    .agg(
        F.min("observed_utc").alias("hour_start_utc"),
        F.avg("temperature_c").alias("temperature_c"),
        F.avg("relative_humidity_pct").alias("relative_humidity_pct"),
        F.sum("precipitation_mm").alias("precipitation_mm"),
        F.sum("snowfall_cm").alias("snowfall_cm"),
        F.avg("wind_speed_kmh").alias("wind_speed_kmh"),
        F.avg("cloud_cover_pct").alias("cloud_cover_pct"),
        F.max("weather_code").alias("weather_code"),
        F.min("source").alias("source"),
    )
    .where(F.col("local_date") >= F.lit("2019-01-01").cast("date"))
)
clean.write.insertInto("weather_hourly", overwrite=True)

year = F.year("observed_utc").alias("year")
bronze_rows = raw.groupBy("borough", year).agg(F.count(F.lit(1)).alias("bronze_rows"))
unique_rows = unique.groupBy("borough", year).agg(F.count(F.lit(1)).alias("unique_hours"))
valid_rows = valid.groupBy("borough", year).agg(
    F.count(F.lit(1)).alias("valid_hours"),
    F.sum((F.col("source") == "forecast").cast("int")).alias("forecast_hours"),
)
silver_rows = spark.read.table("weather_hourly").groupBy("borough", F.year("local_date").alias("year")).agg(F.count(F.lit(1)).alias("silver_rows"))
os.makedirs("/lakehouse/default/Files/reports", exist_ok=True)
bronze_rows.join(unique_rows, ["borough", "year"]).join(valid_rows, ["borough", "year"], "left").join(silver_rows, ["borough", "year"], "left").orderBy("borough", "year").toPandas().to_csv(
    "/lakehouse/default/Files/reports/weather_audit.csv", index=False
)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
