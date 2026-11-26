import pathlib
import re

from sqlalchemy.dialects import mssql, postgresql

from gold.models import Gold
from integrations.tsdb import Tsdb

ROOT = pathlib.Path(__file__).resolve().parent.parent
M_TYPES = {"type text": "STRING", "type number": "DOUBLE", "Int64.Type": "BIGINT", "type date": "DATE", "type datetime": "TIMESTAMP"}


def lakehouse_tables():
    tables = {}
    for folder, lakehouse in (("bronze", "lh_bronze"), ("silver", "lh_silver")):
        for source in sorted((ROOT / folder).glob("nb_*.Notebook/notebook-content.py")):
            text = source.read_text(encoding="utf-8")
            item = source.parent.name.split(".")[0]
            for name, body in re.findall(r"CREATE TABLE IF NOT EXISTS (\w+) \((.*?)\)\s*USING DELTA", text, re.S):
                columns = [part.strip().split(None, 1) for part in re.split(r",(?![^()]*\))", body) if part.strip()]
                tables.setdefault((lakehouse, name), (item, columns))
        for mashup in sorted((ROOT / folder).glob("*.Dataflow/mashup.pq")):
            text = mashup.read_text(encoding="utf-8")
            item = mashup.parent.name.split(".")[0]
            for name, body in re.findall(r"^shared (\w+) =(.*?)(?=^shared |\Z)", text, re.M | re.S):
                if not re.fullmatch(r"[a-z][a-z0-9_]*", name) or name.endswith("_DataDestination"):
                    continue
                typed = re.search(r"Table\.TransformColumnTypes\(\s*\w+,\s*\{(.*?)\}\s*(?:,\s*\"[\w-]+\"\s*)?\)", body, re.S)
                if not typed:
                    continue
                columns = [[column, M_TYPES[m_type]] for column, m_type in re.findall(r'\{"(\w+)",\s*(type \w+|Int64\.Type)\}', typed.group(1))]
                columns += [[column, M_TYPES[m_type]] for column, m_type in re.findall(r'Table\.AddColumn\(\w+, "(\w+)", .*?, (type \w+|Int64\.Type)\)', body)]
                tables[(lakehouse, name)] = (item, columns)
    return tables


def orm_tables(metadata, dialect):
    for table in metadata.sorted_tables:
        key = {column.name for column in table.primary_key.columns}
        yield table.name, [
            (column.name, str(column.type.compile(dialect=dialect)), "key" if column.name in key else ("yes" if column.nullable else "no"), column.info.get("description", ""))
            for column in table.columns
        ]


def model():
    definition = next((ROOT / "semantic").glob("*.SemanticModel/definition"))
    tables = []
    for tmdl in sorted((definition / "tables").glob("*.tmdl")):
        text = tmdl.read_text(encoding="utf-8")
        columns = []
        for name, body in re.findall(r"^\tcolumn '?([^'\n]+?)'?\n(.*?)(?=^\t\w|\Z)", text, re.M | re.S):
            data_type = re.search(r"dataType: (\w+)", body).group(1)
            source = re.search(r"sourceColumn: (\w+)", body).group(1)
            columns.append((name, source, data_type, "hidden" if "isHidden" in body else "visible"))
        measures = re.findall(r"^\tmeasure '?([^'=]+?)'? = (.+)\n\t\tformatString: (.+)$", text, re.M)
        tables.append((tmdl.stem, columns, measures))
    relationships = re.findall(r"fromColumn: (\S+)\n\ttoColumn: (\S+)", (definition / "relationships.tmdl").read_text(encoding="utf-8"))
    roles = []
    for tmdl in sorted((definition / "roles").glob("*.tmdl")):
        text = tmdl.read_text(encoding="utf-8")
        roles.append((re.search(r"^role '?([^'\n]+?)'?$", text, re.M).group(1), re.search(r"tablePermission (\w+) = (.+)$", text, re.M).groups()))
    return tables, relationships, roles


def build():
    lines = ["# Data dictionary", ""]
    lakehouse = lakehouse_tables()
    for layer, title in (("lh_bronze", "Bronze: lh_bronze"), ("lh_silver", "Silver: lh_silver")):
        lines += [f"## {title}", ""]
        for (owner, name), (item, columns) in sorted(lakehouse.items()):
            if owner != layer:
                continue
            lines += [f"### {name}", "", f"Written by `{item}`.", "", "| Column | Type |", "|---|---|"]
            lines += [f"| {column} | {data_type} |" for column, data_type in columns]
            lines.append("")
    gold = list(orm_tables(Gold.metadata, mssql.dialect()))
    timescale = list(orm_tables(Tsdb.metadata, postgresql.dialect()))
    for title, tables in (("Gold: wh_gold", gold), ("Time-series database: TimescaleDB nyc_weather", timescale)):
        lines += [f"## {title}", ""]
        for name, columns in tables:
            lines += [f"### {name}", "", "| Column | Type | Nullable | Description |", "|---|---|---|---|"]
            lines += [f"| {column} | {data_type} | {nullable} | {description} |" for column, data_type, nullable, description in columns]
            lines.append("")
    tables, relationships, roles = model()
    lines += ["## Semantic model: sm_nyc_urban (Direct Lake)", ""]
    for name, columns, measures in tables:
        lines += [f"### {name}", "", "| Field | Source column | Type | Visibility |", "|---|---|---|---|"]
        lines += [f"| {field} | {source} | {data_type} | {visibility} |" for field, source, data_type, visibility in columns]
        if measures:
            lines += ["", "| Measure | DAX | Format |", "|---|---|---|"]
            lines += [f"| {measure} | `{expression.replace('|', '&#124;')}` | `{fmt}` |" for measure, expression, fmt in measures]
        lines.append("")
    lines += ["### Relationships", "", "| From (many) | To (one) |", "|---|---|"]
    lines += [f"| {source} | {target} |" for source, target in relationships]
    lines += ["", "### Row-level security roles", "", "| Role | Table | Filter |", "|---|---|---|"]
    lines += [f"| {role} | {table} | `{expression}` |" for role, (table, expression) in roles]
    lines.append("")
    (ROOT / "docs" / "data_dictionary.md").write_text("\n".join(lines), encoding="utf-8")
    print("docs/data_dictionary.md")


if __name__ == "__main__":
    build()
