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

# PARAMETERS CELL ********************

months = ""

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

import os
from functools import reduce

from pyspark.sql import DataFrame
from pyspark.sql import functions as F

spark.conf.set("spark.sql.session.timeZone", "UTC")

yellow = "abfss://{{WORKSPACE_ID}}@onelake.dfs.fabric.microsoft.com/{{LH_BRONZE_ID}}/Files/taxi/yellow"
money = "decimal(10,2)"
columns = [
    ("vendor_id", "int", ["VendorID"]),
    ("pickup_datetime", "timestamp", ["tpep_pickup_datetime"]),
    ("dropoff_datetime", "timestamp", ["tpep_dropoff_datetime"]),
    ("passenger_count", "int", ["passenger_count"]),
    ("trip_distance", "double", ["trip_distance"]),
    ("ratecode_id", "int", ["RatecodeID"]),
    ("store_and_fwd_flag", "string", ["store_and_fwd_flag"]),
    ("pickup_zone_id", "int", ["PULocationID"]),
    ("dropoff_zone_id", "int", ["DOLocationID"]),
    ("payment_type", "int", ["payment_type"]),
    ("fare_amount", money, ["fare_amount"]),
    ("extra", money, ["extra"]),
    ("mta_tax", money, ["mta_tax"]),
    ("tip_amount", money, ["tip_amount"]),
    ("tolls_amount", money, ["tolls_amount"]),
    ("improvement_surcharge", money, ["improvement_surcharge"]),
    ("congestion_surcharge", money, ["congestion_surcharge"]),
    ("airport_fee", money, ["airport_fee", "Airport_fee"]),
    ("cbd_congestion_fee", money, ["cbd_congestion_fee"]),
    ("total_amount", money, ["total_amount"]),
]

spark.sql("""
CREATE TABLE IF NOT EXISTS taxi_trips (
    vendor_id INT,
    pickup_datetime TIMESTAMP,
    dropoff_datetime TIMESTAMP,
    passenger_count INT,
    trip_distance DOUBLE,
    ratecode_id INT,
    store_and_fwd_flag STRING,
    pickup_zone_id INT,
    dropoff_zone_id INT,
    payment_type INT,
    fare_amount DECIMAL(10,2),
    extra DECIMAL(10,2),
    mta_tax DECIMAL(10,2),
    tip_amount DECIMAL(10,2),
    tolls_amount DECIMAL(10,2),
    improvement_surcharge DECIMAL(10,2),
    congestion_surcharge DECIMAL(10,2),
    airport_fee DECIMAL(10,2),
    cbd_congestion_fee DECIMAL(10,2),
    total_amount DECIMAL(10,2),
    pickup_date DATE,
    pickup_hour INT,
    duration_min DOUBLE,
    source_month STRING
) USING DELTA
PARTITIONED BY (source_month)
""")

spark.sql("""
CREATE TABLE IF NOT EXISTS taxi_month_audit (
    source_month STRING,
    source_rows BIGINT,
    valid_rows BIGINT,
    silver_rows BIGINT,
    loaded_at TIMESTAMP
) USING DELTA
""")

available = sorted(
    f.name[len("yellow_tripdata_"):-len(".parquet")]
    for f in notebookutils.fs.ls(yellow)
    if f.name.startswith("yellow_tripdata_") and f.name.endswith(".parquet")
)
if months:
    selected = [m for m in months.split(";") if m in available]
else:
    loaded = {r.source_month for r in spark.sql("SELECT DISTINCT source_month FROM taxi_trips").collect()}
    selected = sorted({m for m in available if m not in loaded} | set(available[-3:]))

if not selected:
    raise ValueError(f"none of the requested months are in Bronze: {months}")
print(f"processing {len(selected)} months: {selected[0]} .. {selected[-1]}")


def standardize(month):
    raw = spark.read.parquet(f"{yellow}/yellow_tripdata_{month}.parquet")
    present = {c.lower(): c for c in raw.columns}
    picked = []
    for name, dtype, sources in columns:
        source = next((present[s.lower()] for s in sources if s.lower() in present), None)
        picked.append((F.col(source) if source else F.lit(None)).cast(dtype).alias(name))
    return raw.select(*picked, F.lit(month).alias("source_month"))


trips = reduce(DataFrame.unionByName, [standardize(m) for m in selected])
trips = (
    trips.withColumn("duration_min", F.round((F.unix_timestamp("dropoff_datetime") - F.unix_timestamp("pickup_datetime")) / 60, 2))
    .withColumn("pickup_date", F.to_date("pickup_datetime"))
    .withColumn("pickup_hour", F.hour("pickup_datetime"))
)
valid = (
    (F.date_format("pickup_datetime", "yyyy-MM") == F.col("source_month"))
    & (F.col("duration_min") > 0)
    & (F.col("duration_min") <= 1440)
    & (F.col("trip_distance") >= 0)
    & (F.col("fare_amount") >= 0)
    & (F.col("total_amount") >= 0)
    & F.col("pickup_zone_id").isNotNull()
    & F.col("dropoff_zone_id").isNotNull()
)
flagged = trips.withColumn("is_valid", F.coalesce(valid, F.lit(False)))

condition = "source_month IN ({})".format(", ".join(f"'{m}'" for m in selected))
(
    flagged.where("is_valid")
    .drop("is_valid")
    .dropDuplicates()
    .write.format("delta")
    .mode("overwrite")
    .partitionBy("source_month")
    .option("replaceWhere", condition)
    .saveAsTable("taxi_trips")
)

counts = flagged.groupBy("source_month").agg(
    F.count(F.lit(1)).alias("source_rows"),
    F.sum(F.col("is_valid").cast("long")).alias("valid_rows"),
)
written = spark.read.table("taxi_trips").where(condition).groupBy("source_month").agg(F.count(F.lit(1)).alias("silver_rows"))
audit = counts.join(written, "source_month", "left").withColumn("loaded_at", F.current_timestamp())

spark.sql(f"DELETE FROM taxi_month_audit WHERE {condition}")
audit.select("source_month", "source_rows", "valid_rows", "silver_rows", "loaded_at").write.insertInto("taxi_month_audit")

os.makedirs("/lakehouse/default/Files/reports", exist_ok=True)
spark.read.table("taxi_month_audit").orderBy("source_month").toPandas().to_csv("/lakehouse/default/Files/reports/taxi_month_audit.csv", index=False)
print(f"done: {len(selected)} months written to taxi_trips")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
