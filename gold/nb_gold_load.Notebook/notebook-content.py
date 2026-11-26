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

full = "false"

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

import os
import sys
import traceback

reports = "/lakehouse/default/Files/reports"
errors = f"{reports}/gold_load_error.txt"
os.makedirs(reports, exist_ok=True)
if os.path.exists(errors):
    os.remove(errors)

try:
    import struct
    import time

    import pandas as pd
    import pyodbc
    import requests
    from sqlalchemy import create_engine

    sys.path.insert(0, "/lakehouse/default/Files/code")
    from gold.load import run

    server = "{{WH_GOLD_SERVER}}"

    def connect():
        token = notebookutils.credentials.getToken("https://database.windows.net/").encode("utf-16-le")
        return pyodbc.connect(
            "Driver={ODBC Driver 18 for SQL Server};Server=" + server + ",1433;Database=wh_gold;Encrypt=yes;TrustServerCertificate=no",
            attrs_before={1256: struct.pack(f"<I{len(token)}s", len(token), token)},
        )

    api = "https://api.fabric.microsoft.com/v1/workspaces/{{WORKSPACE_ID}}"
    lakehouse_id = "{{LAKEHOUSE_ID}}"
    headers = {"Authorization": "Bearer " + notebookutils.credentials.getToken("pbi")}
    lakehouse = requests.get(f"{api}/lakehouses/{lakehouse_id}", headers=headers, timeout=60)
    lakehouse.raise_for_status()
    endpoint = lakehouse.json()["properties"]["sqlEndpointProperties"]["id"]
    refresh = requests.post(f"{api}/sqlEndpoints/{endpoint}/refreshMetadata", headers=headers, json={}, timeout=60)
    refresh.raise_for_status()
    location = refresh.headers.get("Location")
    for _ in range(60):
        if not location:
            break
        status = requests.get(location, headers=headers, timeout=60).json().get("status")
        if status == "Succeeded":
            break
        if status in ("Failed", "Cancelled"):
            raise RuntimeError(f"lh_silver SQL endpoint metadata refresh {status}")
        time.sleep(5)

    engine = create_engine("mssql+pyodbc://", creator=connect)
    results = run(engine, full=full.lower() == "true")
    pd.DataFrame(results).to_csv(f"{reports}/gold_load.csv", index=False)
except Exception:
    with open(errors, "w") as handle:
        handle.write(traceback.format_exc())
    raise

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
