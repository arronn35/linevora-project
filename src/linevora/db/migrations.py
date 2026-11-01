"""Sürümli şema migration'ları (stdlib sqlite3; PostgreSQL DDL'i de üretilir).

Migration listesi yalnızca eklemelidir: mevcut bir sürümün SQL'i asla
değiştirilmez, düzeltme yeni sürümle gelir. Uygulanan sürümler
``schema_migrations`` tablosuna yazılır; runner idempotenttir.
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

# Aynı şemanın PostgreSQL karşılığı (yönetilen RDBMS geçişinde kullanılır).
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
    """Bekleyen migration'ları sırayla uygular, uygulanan sürümleri döndürür."""
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
    """``(sürücü, yol)`` döndürür: sqlite yolu veya postgres DSN'i."""
    if url.startswith("sqlite:///"):
        return "sqlite", url[len("sqlite:///") :]
    if url.startswith(("postgresql://", "postgres://")):
        return "postgresql", url
    raise ValueError(f"desteklenmeyen LINEVORA_DB_URL: {url!r}")
