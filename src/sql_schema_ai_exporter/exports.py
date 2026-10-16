"""Lossless text and structured exports, with source integrity hash."""
from __future__ import annotations
import csv
import hashlib
import json
from pathlib import Path
from .model import Snapshot, as_dict


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sql_ident(name: str) -> str:
    return "[" + name.replace("]", "]]") + "]"


def md_cell(name: str) -> str:
    return name.replace("\\", "\\\\").replace("|", "\\|").replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")


def export_text(snapshot: Snapshot, out: Path) -> str:
    data = out / "data"
    docs = out / "docs"
    data.mkdir(parents=True, exist_ok=True)
    docs.mkdir(parents=True, exist_ok=True)
    snap_path = data / "schema_snapshot.json"
    write_json(snap_path, as_dict(snapshot))
    sha = hashlib.sha256(snap_path.read_bytes()).hexdigest()
    with (data / "objects.jsonl").open("w", encoding="utf-8", newline="\n") as f:
        for o in snapshot.objects:
            f.write(json.dumps({"database": snapshot.database, "type": o.kind, "schema": o.schema,
                                "object_name": o.name, "column_count": len(o.columns)}, ensure_ascii=False) + "\n")
    with (data / "columns.jsonl").open("w", encoding="utf-8", newline="\n") as f:
        for o in snapshot.objects:
            for c in o.columns:
                f.write(json.dumps({"database": snapshot.database, "type": o.kind, "schema": o.schema,
                                    "object_name": o.name, "column_ordinal": c.ordinal, "field_name": c.name}, ensure_ascii=False) + "\n")
    with (data / "schema_columns.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["database_name", "schema_name", "object_type", "object_name", "column_ordinal", "field_name"])
        for o in snapshot.objects:
            if not o.columns:
                writer.writerow([snapshot.database, o.schema, o.kind, o.name, "", ""])
            for c in o.columns:
                writer.writerow([snapshot.database, o.schema, o.kind, o.name, c.ordinal, c.name])
    lines = [f"# SQL Server Schema: {md_cell(snapshot.database)}", "",
             f"Exported at (UTC): {snapshot.timestamp_utc}", "",
             f"Tables: {sum(o.kind == 'T' for o in snapshot.objects)}; Views: {sum(o.kind == 'V' for o in snapshot.objects)}; "
             f"Fields: {sum(len(o.columns) for o in snapshot.objects)}", "",
             "Field names are complete; their order follows SQL Server column_id.", ""]
    for o in snapshot.objects:
        lines.extend([f"## {o.kind} {md_cell(sql_ident(o.schema))}.{md_cell(sql_ident(o.name))} ({len(o.columns)} fields)", "",
                      "| Ordinal | Field name |", "|---:|---|"])
        lines.extend(f"| {c.ordinal} | {md_cell(sql_ident(c.name))} |" for c in o.columns)
        if not o.columns:
            lines.append("| — | No visible columns |")
        lines.append("")
    (docs / "schema_catalog.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return sha
