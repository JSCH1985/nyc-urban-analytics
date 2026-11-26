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

# CELL ********************

from pyspark.sql import functions as F

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

columns = ["sensor_id", "parameter", "units", "period_start_utc", "period_start_local", "value", "observed_count", "percent_coverage", "loaded_at"]
batch = spark.read.table("openaq_hours_landing").select(*columns)
landing_mark = batch.agg(F.max("loaded_at")).first()[0]

if landing_mark is None:
    print("landing is empty, nothing appended")
elif spark.read.table("openaq_hours").where(F.col("loaded_at") == landing_mark).limit(1).count():
    print(f"batch loaded at {landing_mark} is already in history, nothing appended")
else:
    batch.write.insertInto("openaq_hours")
    print(f"appended {batch.count()} rows loaded at {landing_mark}")

print(f"openaq_hours now holds {spark.read.table('openaq_hours').count()} rows")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
