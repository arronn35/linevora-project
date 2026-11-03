"""Versioned schema migrations (stdlib sqlite3; PostgreSQL DDL is also generated).

The migration list is append-only: the SQL of an existing version is never
changed; a fix arrives as a new version. Applied versions are written to
the ``schema_migrations`` table; the runner is idempotent.
"""

from __future__ import annotations

import sqlite3
import time

MIGRATIONS: list[tuple[int, str]] = [
    (
        1,
        """
        CREATE TABLE IF NOT EXISTS store_snapshots (
            namespace TEXT PRIMARY KEY,
            payload TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS store_rows (
            namespace TEXT NOT NULL,
            item_key TEXT NOT NULL,
            payload TEXT NOT NULL,
            PRIMARY KEY (namespace, item_key)
        );
        """,
    ),
    (
        2,
        """
        CREATE INDEX IF NOT EXISTS idx_store_rows_namespace
            ON store_rows(namespace);
        """,
    ),
]

# The PostgreSQL counterpart of the same schema (used when moving to a managed RDBMS).
POSTGRES_DDL = """
CREATE TABLE IF NOT EXISTS store_snapshots (
    namespace TEXT PRIMARY KEY,
    payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS store_rows (
    namespace TEXT NOT NULL,
    item_key TEXT NOT NULL,
    payload TEXT NOT NULL,
    PRIMARY KEY (namespace, item_key)
);
CREATE INDEX IF NOT EXISTS idx_store_rows_namespace ON store_rows(namespace);
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at DOUBLE PRECISION NOT NULL
);
"""


def apply_migrations(conn: sqlite3.Connection) -> list[int]:
    """Applies pending migrations in order; returns the applied versions."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations "
        "(version INTEGER PRIMARY KEY, applied_at REAL NOT NULL)"
    )
    applied = {
        row[0] for row in conn.execute("SELECT version FROM schema_migrations")
    }
    done: list[int] = []
    for version, sql in MIGRATIONS:
        if version in applied:
            continue
        conn.executescript(sql)
        conn.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (version, time.time()),
        )
        done.append(version)
    conn.commit()
    return done


def parse_db_url(url: str) -> tuple[str, str]:
    """Returns ``(driver, target)``: a sqlite path or a postgres DSN."""
    if url.startswith("sqlite:///"):
        return "sqlite", url[len("sqlite:///") :]
    if url.startswith(("postgresql://", "postgres://")):
        return "postgresql", url
    raise ValueError(f"unsupported LINEVORA_DB_URL: {url!r}")
