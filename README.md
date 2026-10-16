# sql-schema-ai-exporter

**Read-only SQL Server metadata → lossless structured files + dense, multi-column PNG pages for visual AI.**

Works with **tables, views and field names only** (plus database/schema names, object type and field ordinals). Does not query customer/business rows, data types, stored procedure definitions, or secrets.

[中文使用说明](docs/README_zh.md)

## Install (Windows PowerShell)

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[sql,test]"
```

No Chromium or browser download required. Uses Pillow and your local TrueType fonts.

## Online export (Windows integrated authentication)

```powershell
.\.venv\Scripts\python.exe -m sql_schema_ai_exporter `
  --server "YOUR-SQL-SERVER" --database "YOUR_DATABASE" `
  --auth windows --out "D:\SQLSchemaExports\YOUR_DATABASE" --mode balanced
```

Default driver: **ODBC Driver 18 for SQL Server**, which must be installed separately. TLS certificate validation is on by default. Only use `--trust-server-certificate` if authorized by your organization.

SQL authentication (password prompted, not saved):

```powershell
.\.venv\Scripts\python.exe -m sql_schema_ai_exporter `
  --server "YOUR-SQL-SERVER" --database "YOUR_DATABASE" `
  --auth sql --user "YOUR_USERNAME" --out ".\output"
```

## Offline render from CSV/JSON

```powershell
.\.venv\Scripts\python.exe -m sql_schema_ai_exporter `
  --input .\examples\schema_sample.csv --out .\output --mode balanced
```

Input CSV headers: `database_name,schema_name,object_type,object_name,column_ordinal,field_name`.
Snapshot JSON is also accepted (see generated `data/schema_snapshot.json`).

### Density presets

| Mode | Dimensions | Columns | Font |
|---|---:|---:|---:|
| balanced (default) | 2400×3200 | 3 | 20px |
| dense | 2800×3600 | 4 | 18px |
| readable | 2000×2800 | 2 | 22px |

Override: `--width 2600 --height 3400 --columns 3 --font-size 19 --theme dark --font-path "C:\Windows\Fonts\msyh.ttc"`.

## Output

```text
output/
  data/
    schema_snapshot.json      # authoritative exact names, ordinals, objects
    objects.jsonl
    columns.jsonl
    schema_columns.csv
  docs/
    schema_catalog.md         # all names in a readable text table
  images/
    schema_001.png
    schema_002.png
    image_manifest.csv        # image ↔ object and field ordinal mapping
    render_report.json
  export_report.json          # logical coverage and SHA256
```

Each object has a clear `T`/`V` label; field names are packed inline with `·` delimiters. Long identifiers wrap instead of being truncated; long objects continue across columns/pages with repeated headers. No ellipsis is used. The renderer checks coverage of all objects and field ordinals. **Layout integrity ≠ guaranteed visual AI/OCR transcription**; use JSON/CSV for exact identifiers and PNGs for visual overview.

SQL Server metadata visibility follows account permissions. Missing objects in the returned catalog are not necessarily absent from the database. Company authorization is required before moving any schema information to personal GitHub, ChatGPT, or any external service; **a private GitHub repository alone is not authorization**.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

No license is automatically granted for proprietary use; choose a license with your collaborators/organization before public distribution.
