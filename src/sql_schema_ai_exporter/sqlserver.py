"""SQL Server catalog only: no SELECT from user tables or views."""
from __future__ import annotations
import getpass
import os
from .model import from_records, Snapshot

CATALOG_SQL = """
SELECT
  DB_NAME() AS database_name,
  s.name AS schema_name,
  CASE WHEN o.type = 'U' THEN 'T' ELSE 'V' END AS object_type,
  o.name AS object_name,
  c.column_id AS column_ordinal,
  c.name AS field_name
FROM sys.objects AS o
JOIN sys.schemas AS s ON s.schema_id = o.schema_id
LEFT JOIN sys.columns AS c ON c.object_id = o.object_id
WHERE o.type IN ('U', 'V')
  AND o.is_ms_shipped = 0
ORDER BY s.name, o.type, o.name, c.column_id;
"""


def _braced(value: str) -> str:
    """Escape a value for an ODBC connection string (not SQL interpolation)."""
    if "\x00" in value:
        raise ValueError("NUL is not permitted in connection properties")
    return "{" + value.replace("}", "}}") + "}"


def fetch_schema(*, server: str, database: str, driver: str,
                 auth: str, username: str | None, password_env: str | None,
                 trust_server_certificate: bool = False,
                 timeout: int = 15) -> Snapshot:
    try:
        import pyodbc
    except ImportError as exc:
        raise RuntimeError('pyodbc is required for SQL connections: python -m pip install -e ".[sql]"') from exc
    if not server or not database:
        raise ValueError("--server and --database are required")
    if timeout <= 0:
        raise ValueError("--timeout must be positive")
    props = [f"DRIVER={_braced(driver)}", f"SERVER={_braced(server)}", f"DATABASE={_braced(database)}",
             "Encrypt=yes", "TrustServerCertificate=" + ("yes" if trust_server_certificate else "no"),
             f"Connection Timeout={timeout}", "ApplicationIntent=ReadOnly"]
    if auth == "windows":
        props.append("Trusted_Connection=yes")
    elif auth == "sql":
        if not username:
            raise ValueError("--user is required with --auth sql")
        secret = os.environ.get(password_env) if password_env else getpass.getpass("SQL Server password: ")
        if not secret:
            raise ValueError("SQL password is empty or password environment variable is missing")
        props.extend((f"UID={_braced(username)}", f"PWD={_braced(secret)}"))
    else:
        raise ValueError("--auth must be windows or sql")
    connection_string = ";".join(props) + ";"
    # Do not log connection_string: it can contain a password.
    try:
        conn = pyodbc.connect(connection_string, timeout=timeout, autocommit=True)
        try:
            cursor = conn.cursor()
            try:
                cursor.timeout = timeout
                cursor.execute(CATALOG_SQL)
                headers = [desc[0] for desc in cursor.description]
                rows = [dict(zip(headers, row)) for row in cursor.fetchall()]
            finally:
                cursor.close()
        finally:
            conn.close()
    except pyodbc.Error:
        raise RuntimeError("SQL Server catalog query failed. Verify driver, TLS, permissions, "
                           "database, connectivity, and login. Details are omitted to avoid leaking secrets.") from None
    if not rows:
        raise RuntimeError("No visible user tables or views. Verify database selection and metadata permissions.")
    return from_records(rows, database)
