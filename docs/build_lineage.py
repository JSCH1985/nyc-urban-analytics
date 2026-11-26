import json
import pathlib
import re

from sqlalchemy.dialects import mssql

from gold.load import HISTORY_START, history, steps
from gold.models import Gold

ROOT = pathlib.Path(__file__).resolve().parent.parent
LAKEHOUSES = {"bronze": "lh_bronze", "silver": "lh_silver"}
TYPES = {"PL": "DataPipeline", "DF": "Dataflow", "NB": "Notebook"}


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def dataflows():
    flows = {}
    for mashup in sorted((ROOT / "bronze").glob("*.Dataflow/mashup.pq")):
        text = mashup.read_text(encoding="utf-8")
        queries = re.findall(r"^shared (?:#\")?([\w ]+?)\"? =", text, re.M)
        targets = sorted(name for name in queries if re.fullmatch(r"[a-z][a-z0-9_]*", name) and not name.endswith("_DataDestination"))
        sources = sorted(set(re.findall(r'Web\.Contents\(\s*"https://([^"/]+)', text)))
        flows[mashup.parent.name.split(".")[0]] = {"sources": sources, "targets": [f"lh_bronze.{name}" for name in targets]}
    return flows


def copy_pipeline():
    text = read("bronze/pl_taxi_copy/pipeline-content.json")
    folders = sorted(set(re.findall(r'"folderPath":\s*"([^"]+)"', text)))
    return {"sources": ["d37ci6vzurychx.cloudfront.net"], "targets": [f"lh_bronze.Files/{folder}" for folder in folders]}


def notebooks():
    found = {}
    for folder, lakehouse in LAKEHOUSES.items():
        for source in sorted((ROOT / folder).glob("nb_*.Notebook/notebook-content.py")):
            text = source.read_text(encoding="utf-8")
            writes = {f"{lakehouse}.{table}" for table in re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)", text)}
            reads = {f"{lakehouse}.{table}" for table in re.findall(r'spark\.read\.table\("(\w+)"\)', text)}
            reads |= {f"lh_bronze.{table}" for table in re.findall(r"(?:\{bronze\}|\{\{LH_BRONZE_ID\}\})/Tables/(\w+)", text)}
            for path in re.findall(r"(?:\{bronze\}|\{\{LH_BRONZE_ID\}\})/Files/([\w/.]+)", text):
                parts = path.strip("/").split("/")
                reads.add("lh_bronze.Files/" + "/".join(parts[:-1] if "." in parts[-1] else parts))
            found[source.parent.name.split(".")[0]] = {"hosts": sorted(set(re.findall(r'"https://([^"/{]+)', text))), "reads": sorted(reads - writes), "writes": sorted(writes)}
    return found


def gold():
    loads = {}
    for step in steps(history(HISTORY_START), HISTORY_START):
        sql = str(step.insert.compile(dialect=mssql.dialect()))
        sources = {f"lh_silver.{table}" for table in re.findall(r"lh_silver\.dbo\.(\w+)", sql)}
        sources |= {f"wh_gold.{table}" for table in Gold.metadata.tables if table != step.target and re.search(rf"(?<![\w.]){table}\b", sql)}
        loads[f"wh_gold.{step.target}"] = sorted(sources)
    return loads


def semantic_model():
    tables = {}
    for tmdl in sorted((ROOT / "semantic").glob("*.SemanticModel/definition/tables/*.tmdl")):
        entity = re.search(r"entityName: (\w+)", tmdl.read_text(encoding="utf-8"))
        tables[tmdl.stem] = f"wh_gold.{entity.group(1)}"
    return tables


def report_pages():
    pages = []
    root = ROOT / "report/rpt_nyc_urban.Report/definition/pages"
    order = json.loads((root / "pages.json").read_text(encoding="utf-8"))["pageOrder"]
    for name in order:
        page = json.loads((root / name / "page.json").read_text(encoding="utf-8"))
        entities = set()
        for visual in (root / name / "visuals").glob("*/visual.json"):
            entities |= set(re.findall(r'"Entity": "(\w+)"', visual.read_text(encoding="utf-8")))
        pages.append((page["displayName"], sorted(entities)))
    return pages


def orchestration():
    content = json.loads(read("orchestration/pl_daily/pipeline-content.json"))
    activities = []
    for activity in content["properties"]["activities"]:
        token = re.search(r"\{\{((PL|DF|NB)_[A-Z_]+)_ID\}\}", json.dumps(activity["typeProperties"]))
        item = f"{token.group(1).lower()}.{TYPES[token.group(2)]}" if token else ""
        activities.append((activity["name"], item, [dependency["activity"] for dependency in activity["dependsOn"]]))
    return activities


def node(name):
    return re.sub(r"\W", "_", name)


def names(values):
    return ", ".join(f"`{value}`" for value in values)


def build():
    flows = dataflows()
    copy = copy_pipeline()
    books = notebooks()
    loads = gold()
    model = semantic_model()
    pages = report_pages()
    activities = orchestration()

    items = {item: (flow["sources"], [], flow["targets"]) for item, flow in {**flows, "pl_taxi_copy": copy}.items()}
    items |= {item: (book["hosts"], book["reads"], book["writes"]) for item, book in books.items()}
    edges = set()
    for item, (hosts, reads, writes) in items.items():
        edges |= {(host, item) for host in hosts}
        edges |= {(source.split(".")[0], item) for source in reads}
        edges |= {(item, target.split(".")[0]) for target in writes}
    edges |= {("lh_silver", "nb_gold_load"), ("nb_gold_load", "wh_gold"), ("wh_gold", "sm_nyc_urban"), ("sm_nyc_urban", "rpt_nyc_urban")}
    edges |= {("wh_gold", "weather_sync"), ("weather_sync", "TimescaleDB"), ("TimescaleDB", "Grafana")}

    lines = ["# Lineage", "", "## Items", "", "```mermaid", "flowchart LR"]
    for source, target in sorted(edges):
        lines.append(f"    {node(source)}[{source}] --> {node(target)}[{target}]")
    lines += ["```", "", "## Bronze and Silver", "", "| Item | Reads | Writes |", "|---|---|---|"]
    for item, (hosts, reads, writes) in sorted(items.items(), key=lambda entry: (any(name.startswith("lh_silver.") for name in entry[1][2]), entry[0].startswith("nb_"), entry[0])):
        lines.append(f"| {item} | {names(hosts + reads)} | {names(writes)} |")
    lines += ["", "## Gold wh_gold (nb_gold_load, SQLAlchemy ORM)", "", "| Table | Inputs |", "|---|---|"]
    lines += [f"| `{target}` | {names(sources or ['fixed values'])} |" for target, sources in sorted(loads.items())]
    lines += ["", "## TimescaleDB (integrations/weather_sync.py, daily Windows task)", "", "| Table | Inputs |", "|---|---|"]
    lines.append("| `TimescaleDB.weather_hourly` | `wh_gold.FactWeatherHourly`, `wh_gold.DimWeatherCondition` |")
    lines += ["", "## Semantic model sm_nyc_urban (Direct Lake)", "", "| Model table | Warehouse table |", "|---|---|"]
    lines += [f"| {table} | `{entity}` |" for table, entity in model.items()]
    lines += ["", "## Report rpt_nyc_urban", "", "| Page | Model tables used |", "|---|---|"]
    lines += [f"| {page} | {', '.join(entities)} |" for page, entities in pages]
    lines += ["", "## Daily orchestration pl_daily (03:00 Asia/Tashkent)", "", "```mermaid", "flowchart LR"]
    for name, item, after in activities:
        label = f"{name}<br/>{item}" if item else name
        lines.append(f'    {node(name)}["{label}"]')
        lines += [f"    {node(dependency)} --> {node(name)}" for dependency in after]
    lines += ["```", ""]
    (ROOT / "docs" / "lineage.md").write_text("\n".join(lines), encoding="utf-8")
    print("docs/lineage.md")


if __name__ == "__main__":
    build()
