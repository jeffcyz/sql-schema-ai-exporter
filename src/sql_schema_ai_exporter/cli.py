"""Command line: SQL Server catalog query or offline CSV/JSON -> lossless files + compact PNG."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
from .model import load_file
from .sqlserver import fetch_schema
from .exports import export_text, write_json
from .render import Config, PRESETS, render


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="schema-ai-export",
        description="Export SQL Server user table/view and field NAMES ONLY into full text + AI-dense PNGs."
    )
    conn = p.add_argument_group("Metadata input (choose SQL Server or offline)")
    src = conn.add_mutually_exclusive_group(required=True)
    src.add_argument("--input", type=Path, metavar="CSV_OR_JSON", help="Offline flat CSV or snapshot JSON")
    src.add_argument("--server", help="SQL Server hostname or host\\instance")
    conn.add_argument("--database", help="SQL Server database name (also for CSV without database_name)")
    conn.add_argument("--driver", default="ODBC Driver 18 for SQL Server")
    conn.add_argument("--auth", choices=["windows", "sql"], default="windows")
    conn.add_argument("--user", help="Username for --auth sql")
    conn.add_argument("--password-env", help="Name of environment variable containing SQL password")
    conn.add_argument("--trust-server-certificate", action="store_true",
                      help="Opt in to bypass TLS certificate verification (not recommended)")
    conn.add_argument("--timeout", type=int, default=15)
    p.add_argument("--out", type=Path, default=Path("output"), help="Output directory; never use a public repo")
    p.add_argument("--mode", choices=sorted(PRESETS), default="balanced")
    p.add_argument("--width", type=int, help="Override PNG width (pixels)")
    p.add_argument("--height", type=int, help="Override PNG height (pixels)")
    p.add_argument("--columns", type=int, help="Override object columns count")
    p.add_argument("--font-size", type=int, help="Override font size (pixels)")
    p.add_argument("--theme", choices=["light", "dark"], default="light")
    p.add_argument("--font-path", type=str, help="TrueType font file (Windows: C:\\Windows\\Fonts\\msyh.ttc)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.server:
            if not args.database:
                raise ValueError("--database is required when using --server")
            snap = fetch_schema(server=args.server, database=args.database, driver=args.driver,
                                auth=args.auth, username=args.user, password_env=args.password_env,
                                trust_server_certificate=args.trust_server_certificate,
                                timeout=args.timeout)
        else:
            snap = load_file(args.input, args.database)
        if not snap.objects:
            raise ValueError("No user tables/views in input or none visible to this account")
        preset = dict(PRESETS[args.mode])
        for arg in ("width", "height", "columns", "font_size"):
            v = getattr(args, arg)
            if v is not None:
                preset[arg] = v
        cfg = Config(**preset, theme=args.theme, font_path=args.font_path)
        sha = export_text(snap, args.out)
        report = render(snap, args.out / "images", cfg)
        report["snapshot_sha256"] = sha
        write_json(args.out / "export_report.json", report)
        print(f"Database: {snap.database}")
        print(f"Objects: {report['objects']} (Tables: {report['tables']}, Views: {report['views']})")
        print(f"Fields: {report['source_fields']} (all covered in layout)")
        print(f"Images: {report['images']}; Status: {report['status']}")
        print(f"Output: {args.out.resolve()}")
        return 0
    except (ValueError, RuntimeError, OSError) as exc:
        # Avoid including connection strings, credentials, and ODBC stack traces.
        print(f"ERROR: {type(exc).__name__}: {str(exc)[:500]}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
