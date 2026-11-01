"""SQLite kalıcılık katmanı.

Tüm ``InMemory*Store`` sınıfları ``to_snapshot``/``load_snapshot`` taşır.
Bu modül, herhangi bir store'u SQLite'a bağlayan bir vekil (proxy) sağlar:
her değiştiren çağrıdan sonra snapshot SQLite'a yazılır, açılışta geri
yüklenir. Böylece store arayüzleri değişmeden veri süreçler arası kalıcı
olur. Tablo şeması tekil bir anahtar-değer tablosudur; her store bir
``namespace`` satırına snapshot JSON'unu yazar.

Yapılandırma: ``LINEVORA_DB_PATH`` verilirse ``create_app`` varsayılan
store'ları bu vekille sarar; verilmezse bellek içi davranış korunur.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from .db.migrations import apply_migrations

_READ_METHODS = frozenset(
    {
        "list", "get", "get_inquiry", "list_versions", "list_for_version",
        "list_for_requirement", "list_for_product", "list_for_quote",
        "list_for_inquiry", "effective", "effective_for_product",
        "to_snapshot",
    }
)


class SqliteSnapshotStore:
    """Bir store'u SQLite snapshot kalıcılığıyla saran vekil."""

    def __init__(self, inner: Any, db_path: str, namespace: str) -> None:
        object.__setattr__(self, "_inner", inner)
        object.__setattr__(self, "_db_path", db_path)
        object.__setattr__(self, "_namespace", namespace)
        object.__setattr__(self, "_lock", threading.Lock())
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            apply_migrations(conn)
            rows = conn.execute(
                "SELECT item_key, payload FROM store_rows "
                "WHERE namespace = ? ORDER BY item_key",
                (namespace,),
            ).fetchall()
            row = conn.execute(
                "SELECT payload FROM store_snapshots WHERE namespace = ?",
                (namespace,),
            ).fetchone()
        if hasattr(inner, "load_snapshot"):
            if rows:
                inner.load_snapshot(
                    {"items": [json.loads(payload) for _key, payload in rows]}
                )
            elif row is not None:
                # Bozuk kayıt sessizce yutulmaz: sessiz veri kaybını önle.
                payload = json.loads(row[0])
                if isinstance(payload, dict) and payload.get("schema_version") == 1:
                    payload = payload.get("data")
                inner.load_snapshot(payload)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=5.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _persist(self) -> None:
        inner = object.__getattribute__(self, "_inner")
        if not hasattr(inner, "to_snapshot"):
            return
        namespace = object.__getattribute__(self, "_namespace")
        snapshot = inner.to_snapshot()
        items = snapshot.get("items") if isinstance(snapshot, dict) else None
        if isinstance(items, list) and all(
            isinstance(item, dict) and "id" in item for item in items
        ):
            # Satır bazlı artımlı yazım: yalnızca değişen kayıtlar yazılır.
            current = {
                str(item["id"]): json.dumps(item, ensure_ascii=False, default=str)
                for item in items
            }
            with self._connect() as conn:
                existing = dict(
                    conn.execute(
                        "SELECT item_key, payload FROM store_rows WHERE namespace = ?",
                        (namespace,),
                    ).fetchall()
                )
                for key, payload in current.items():
                    if existing.get(key) != payload:
                        conn.execute(
                            "INSERT INTO store_rows(namespace, item_key, payload) "
                            "VALUES(?, ?, ?) ON CONFLICT(namespace, item_key) "
                            "DO UPDATE SET payload = excluded.payload",
                            (namespace, key, payload),
                        )
                for key in existing:
                    if key not in current:
                        conn.execute(
                            "DELETE FROM store_rows WHERE namespace = ? AND item_key = ?",
                            (namespace, key),
                        )
                conn.execute(
                    "DELETE FROM store_snapshots WHERE namespace = ?", (namespace,)
                )
            return
        payload = json.dumps(
            {"schema_version": 1, "data": snapshot},
            ensure_ascii=False,
            default=str,
        )
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO store_snapshots(namespace, payload) VALUES(?, ?) "
                "ON CONFLICT(namespace) DO UPDATE SET payload = excluded.payload",
                (namespace, payload),
            )

    def __getattr__(self, name: str) -> Any:
        inner = object.__getattribute__(self, "_inner")
        attr = getattr(inner, name)
        if not callable(attr) or name in ("to_snapshot", "load_snapshot"):
            return attr

        def wrapped(*args: Any, **kwargs: Any) -> Any:
            lock = object.__getattribute__(self, "_lock")
            with lock:
                result = attr(*args, **kwargs)
                if name not in _READ_METHODS:
                    self._persist()
                return result

        return wrapped

    def __setattr__(self, name: str, value: Any) -> None:
        setattr(object.__getattribute__(self, "_inner"), name, value)


def wrap_store(inner: Any, db_path: str | None, namespace: str) -> Any:
    """``db_path`` verilmişse store'u kalıcı vekille sar, yoksa aynen döndür."""
    if not db_path:
        return inner
    return SqliteSnapshotStore(inner, db_path, namespace)
