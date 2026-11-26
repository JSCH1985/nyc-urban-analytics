import argparse
import json
import os
import re
import sys
import uuid
from pathlib import Path


def fail(message):
    sys.exit(f"build_dataflow: {message}")


def composite(reference_id, datasource_id):
    try:
        parsed = json.loads(reference_id)
    except (TypeError, ValueError):
        return datasource_id
    return json.dumps({"ClusterId": parsed["ClusterId"], "DatasourceId": datasource_id}, separators=(",", ":"))


def destination_parts(mashup, query):
    annotation = re.search(rf"^(\[DataDestinations\b.*?)\r?\n\s*shared {re.escape(query)} =", mashup, re.S | re.M)
    destination = re.search(rf"shared {re.escape(query)}_DataDestination = (let\b.*?\bin\s+\w+);", mashup, re.S)
    if not annotation or not destination:
        fail(f"the reference has no saved data destination for '{query}'")
    return annotation.group(1), destination.group(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", required=True)
    parser.add_argument("--reference-query", required=True)
    parser.add_argument("--template", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--connection-id", required=True)
    parser.add_argument("--web-path", required=True)
    parser.add_argument("--targets", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    key = os.environ.get("OPENAQ_API_KEY")
    if not key:
        fail("OPENAQ_API_KEY is not set")

    reference = Path(args.reference)
    metadata = json.loads((reference / "queryMetadata.json").read_text(encoding="utf-8-sig"))
    mashup = (reference / "mashup.pq").read_text(encoding="utf-8-sig")
    template = (Path(args.template) / "mashup.pq").read_text(encoding="utf-8-sig")
    targets = args.targets.split(",")

    connections = metadata.get("connections") or []
    web = next((c for c in connections if c.get("kind") == "Web"), None)
    lakehouse = next((c for c in connections if c.get("kind") == "Lakehouse"), None)
    if not web or not lakehouse:
        fail("the reference must have both a Web and a Lakehouse connection bound")

    annotation, destination = destination_parts(mashup, args.reference_query)
    old = args.reference_query

    header, separator, body = template.partition("section Section1;")
    if not separator:
        fail("the template has no 'section Section1;' line")
    for target in targets:
        if f"shared {target} =" not in body:
            fail(f"the template has no query named '{target}'")
        marker = annotation.replace(old, target)
        marker = re.sub(r"IsNewTarget\s*=\s*(true|false)", "IsNewTarget = true", marker)
        body = body.replace(f"shared {target} =", f"{marker}\nshared {target} =", 1)
        body += f"\nshared {target}_DataDestination = {destination.replace(chr(34) + old + chr(34), chr(34) + target + chr(34))};\n"
    out_mashup = header + separator + body
    out_mashup = out_mashup.replace("{{OPENAQ_API_KEY}}", key)

    entries = metadata.get("queriesMetadata") or {}
    source_entry = {k: v for k, v in entries.get(old, {}).items() if k not in ("queryId", "queryName")}
    destination_entry = {k: v for k, v in entries.get(f"{old}_DataDestination", {}).items() if k not in ("queryId", "queryName")}
    queries = re.findall(r"^shared (\w+) =", out_mashup, re.M)
    queries_metadata = {}
    for query in queries:
        if query in targets:
            extra = source_entry
        elif query.endswith("_DataDestination"):
            extra = destination_entry or {"isHidden": True, "loadEnabled": False}
        else:
            extra = {"loadEnabled": False}
        queries_metadata[query] = {"queryId": str(uuid.uuid4()), "queryName": query, **extra}

    out_metadata = {k: v for k, v in metadata.items() if k not in ("queriesMetadata", "connections", "name")}
    out_metadata["name"] = args.name
    out_metadata["queriesMetadata"] = queries_metadata
    out_metadata["connections"] = [
        {**web, "path": args.web_path, "connectionId": composite(web["connectionId"], args.connection_id)},
        lakehouse,
    ]

    platform = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "Dataflow", "displayName": args.name},
        "config": {"version": "2.0", "logicalId": "00000000-0000-0000-0000-000000000000"},
    }

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "mashup.pq").write_text(out_mashup, encoding="utf-8")
    (out / "queryMetadata.json").write_text(json.dumps(out_metadata, indent=2), encoding="utf-8")
    (out / ".platform").write_text(json.dumps(platform, indent=2), encoding="utf-8")
    print(f"built {out} with queries {', '.join(queries)}")


if __name__ == "__main__":
    main()
