import os
import struct
from pathlib import Path

import pyodbc
from azure.identity import AuthenticationRecord, InteractiveBrowserCredential, TokenCachePersistenceOptions
from sqlalchemy import create_engine

SCOPE = "https://database.windows.net/.default"
RECORD = Path(os.environ["LOCALAPPDATA"]) / "nyc-urban-analytics" / "fabric_sign_in.json"


def credential(interactive=True):
    record = AuthenticationRecord.deserialize(RECORD.read_text(encoding="utf-8")) if RECORD.exists() else None
    if record is None and not interactive:
        raise RuntimeError("No saved Fabric sign-in")
    signed_in = InteractiveBrowserCredential(
        cache_persistence_options=TokenCachePersistenceOptions(name="nyc-urban-analytics"),
        authentication_record=record,
        disable_automatic_authentication=not interactive,
    )
    if record is None:
        RECORD.parent.mkdir(parents=True, exist_ok=True)
        RECORD.write_text(signed_in.authenticate(scopes=[SCOPE]).serialize(), encoding="utf-8")
    return signed_in


def warehouse_engine(server, database="wh_gold", interactive=True):
    signed_in = credential(interactive)

    def connect():
        token = signed_in.get_token(SCOPE).token.encode("utf-16-le")
        return pyodbc.connect(
            "Driver={ODBC Driver 18 for SQL Server};Server=" + server + ",1433;Database=" + database + ";Encrypt=yes;TrustServerCertificate=no",
            attrs_before={1256: struct.pack(f"<I{len(token)}s", len(token), token)},
        )

    return create_engine("mssql+pyodbc://", creator=connect)
