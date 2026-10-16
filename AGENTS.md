# Engineering rules for sql-schema-ai-exporter

This project renders **names-only** SQL Server table/view metadata into compact images and lossless files.

- Never query user tables or views; the SQL Server driver must read only system catalog metadata.
- Never store credentials, ODBC connection strings, or real customer/database snapshots in the repository.
- All fields and object names must remain exact in JSON/CSV/Markdown; PNG layout must not silently truncate.
- Every output image must be traceable via the manifest, and every source field must be logically accounted for.
- Run `python -m pytest -q` after changing extraction, normalization, or rendering logic.
- Do not assume a private repository is approved storage for proprietary metadata.
