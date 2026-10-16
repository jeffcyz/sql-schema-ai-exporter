"""Strict metadata model; preserve exact names and column ordinals."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
import csv
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Column:
    ordinal: int
    name: str


@dataclass(frozen=True)
class DbObject:
    schema: str
    kind: str  # T = user table; V = view
    name: str
    columns: tuple[Column, ...]

    @property
    def key(self) -> str:
        return f"{self.kind}:{self.schema}.{self.name}"


@dataclass(frozen=True)
class Snapshot:
    database: str
    objects: tuple[DbObject, ...]
    timestamp_utc: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def kind_of(value: Any) -> str:
    x = str(value or "").strip().upper()
    if x in {"T", "U", "TABLE", "BASE TABLE"}:
        return "T"
    if x in {"V", "VIEW"}:
        return "V"
    raise ValueError(f"Invalid object type {value!r}, expected T/V or TABLE/VIEW")


def normalize(database: str, objects: list[DbObject], timestamp_utc: str | None = None) -> Snapshot:
    if not isinstance(database, str) or not database:
        raise ValueError("Database name must be non-empty")
    keys: set[tuple[str, str, str]] = set()
    clean: list[DbObject] = []
    for obj in objects:
        if not obj.schema or not obj.name or not isinstance(obj.schema, str) or not isinstance(obj.name, str):
            raise ValueError("Object schema/name must be non-empty strings")
        kind = kind_of(obj.kind)
        key = (obj.schema.casefold(), kind, obj.name.casefold())
        if key in keys:
            raise ValueError(f"Duplicate object {kind} {obj.schema}.{obj.name}")
        keys.add(key)
        ordinals: set[int] = set()
        names: set[str] = set()
        cols: list[Column] = []
        for col in obj.columns:
            if type(col.ordinal) is not int or col.ordinal <= 0 or not isinstance(col.name, str) or not col.name:
                raise ValueError(f"Invalid column in {obj.schema}.{obj.name}: {col!r}")
            if col.ordinal in ordinals or col.name.casefold() in names:
                raise ValueError(f"Duplicate ordinal or column name in {obj.schema}.{obj.name}: {col.name}")
            ordinals.add(col.ordinal)
            names.add(col.name.casefold())
            cols.append(col)
        clean.append(DbObject(obj.schema, kind, obj.name, tuple(sorted(cols, key=lambda c: c.ordinal))))
    clean.sort(key=lambda o: (o.schema.casefold(), o.kind, o.name.casefold()))
    return Snapshot(database=database, objects=tuple(clean), timestamp_utc=timestamp_utc or utc_now())


def as_dict(snapshot: Snapshot) -> dict[str, Any]:
    return {
        "format_version": "1.0", "database": snapshot.database,
        "exported_at_utc": snapshot.timestamp_utc,
        "objects": [{"schema": o.schema, "type": o.kind, "name": o.name,
                     "columns": [{"ordinal": c.ordinal, "name": c.name} for c in o.columns]}
                    for o in snapshot.objects],
    }


def from_records(rows: list[dict[str, Any]], database: str | None = None) -> Snapshot:
    """Accept CSV/JSON flat records. For zero-column objects field_name may be blank."""
    buckets: dict[tuple[str, str, str], list[Column]] = {}
    db: str | None = database
    for line, row in enumerate(rows, 1):
        rawdb = row.get("database_name", row.get("database"))
        if rawdb not in (None, ""):
            if db is None:
                db = str(rawdb)
            elif db != str(rawdb):
                raise ValueError(f"Row {line}: multiple database names ({db!r}, {rawdb!r})")
        schema = row.get("schema_name", row.get("schema"))
        name = row.get("object_name", row.get("name"))
        kind = kind_of(row.get("object_type", row.get("type")))
        if not schema or not name:
            raise ValueError(f"Row {line}: missing schema/object name")
        key = (str(schema), kind, str(name))
        bucket = buckets.setdefault(key, [])
        column_name = row.get("field_name", row.get("column_name"))
        if column_name is None or column_name == "":
            # An empty row is only valid for an object with no columns.
            if row.get("column_ordinal", row.get("ordinal")) not in (None, ""):
                raise ValueError(f"Row {line}: missing field name for non-empty ordinal")
            continue
        rawordinal = row.get("column_ordinal", row.get("ordinal"))
        if rawordinal is None or str(rawordinal).strip() == "":
            raise ValueError(f"Row {line}: missing column ordinal")
        bucket.append(Column(int(rawordinal), str(column_name)))
    if db is None:
        raise ValueError("No database name available; use --database for offline files")
    return normalize(db, [DbObject(s, k, n, tuple(cols)) for (s, k, n), cols in buckets.items()])


def load_file(path: Path, database: str | None = None) -> Snapshot:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open("r", newline="", encoding="utf-8-sig") as f:
            return from_records(list(csv.DictReader(f)), database)
    if suffix == ".json":
        obj = json.loads(path.read_text(encoding="utf-8-sig"))
        if isinstance(obj, list):
            return from_records(obj, database)
        if not isinstance(obj, dict):
            raise ValueError("JSON must contain a snapshot object or a list of flat records")
        if "objects" not in obj:
            raise ValueError("JSON snapshot must contain an objects array")
        db = obj.get("database", database)
        return normalize(str(db) if db is not None else "", [
            DbObject(str(o["schema"]), kind_of(o.get("type", o.get("kind"))), str(o["name"]),
                     tuple(Column(int(c["ordinal"]), str(c["name"])) for c in o.get("columns", [])))
            for o in obj["objects"]
        ], obj.get("exported_at_utc"))
    raise ValueError("Supported input formats: .csv, .json")
