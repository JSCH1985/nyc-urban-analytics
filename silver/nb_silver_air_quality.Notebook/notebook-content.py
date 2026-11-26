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
CREATE TABLE IF NOT EXISTS air_quality_hourly (
    sensor_id BIGINT,
    location_id BIGINT,
    parameter STRING,
    unit STRING,
    period_start_utc TIMESTAMP,
    period_start_local TIMESTAMP,
    local_date DATE,
    local_hour INT,
    value DOUBLE,
    observed_count BIGINT,
    percent_coverage DOUBLE
) USING DELTA
""")

hours = spark.read.format("delta").load(f"{bronze}/Tables/openaq_hours")
sensors = spark.read.format("delta").load(f"{bronze}/Tables/openaq_sensors").select("sensor_id", "location_id").dropDuplicates(["sensor_id"])

latest = Window.partitionBy("sensor_id", "period_start_utc").orderBy(F.col("loaded_at").desc())
units = F.lower(F.col("units"))
factor = (
    F.when((F.col("parameter") == "pm25") & units.contains("g/m"), F.lit(1.0))
    .when(F.col("parameter").isin("no2", "o3") & (units == "ppm"), F.lit(1000.0))
    .when(F.col("parameter").isin("no2", "o3") & (units == "ppb"), F.lit(1.0))
)
unit = F.when(F.col("parameter") == "pm25", F.lit("ug/m3")).otherwise(F.lit("ppb"))
local = F.to_timestamp(F.substring("period_start_local", 1, 19), "yyyy-MM-dd'T'HH:mm:ss")

unique = hours.withColumn("version", F.row_number().over(latest)).where(F.col("version") == 1).drop("version")
clean = (
    unique.withColumn("factor", factor)
    .where(F.col("factor").isNotNull() & F.col("value").isNotNull() & (F.col("value") >= 0))
    .join(sensors, "sensor_id", "left")
    .select(
        "sensor_id",
        "location_id",
        "parameter",
        unit.alias("unit"),
        "period_start_utc",
        local.alias("period_start_local"),
        F.to_date(local).alias("local_date"),
        F.hour(local).alias("local_hour"),
        (F.col("value") * F.col("factor")).alias("value"),
        "observed_count",
        "percent_coverage",
    )
)
clean.write.insertInto("air_quality_hourly", overwrite=True)

year = F.year("period_start_utc").alias("year")
bronze_rows = hours.groupBy("parameter", year).agg(F.count(F.lit(1)).alias("bronze_rows"))
unique_rows = unique.groupBy("parameter", year).agg(F.count(F.lit(1)).alias("unique_rows"))
silver_rows = spark.read.table("air_quality_hourly").groupBy("parameter", year).agg(
    F.count(F.lit(1)).alias("silver_rows"),
    F.countDistinct("sensor_id").alias("sensors"),
)
os.makedirs("/lakehouse/default/Files/reports", exist_ok=True)
bronze_rows.join(unique_rows, ["parameter", "year"]).join(silver_rows, ["parameter", "year"], "left").orderBy("parameter", "year").toPandas().to_csv(
    "/lakehouse/default/Files/reports/air_quality_audit.csv", index=False
)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
