from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from app.config import Settings


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_parent_dir(path: str) -> None:
    Path(path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)


def get_connection(settings: Settings) -> sqlite3.Connection:
    ensure_parent_dir(settings.database_path)
    connection = sqlite3.connect(settings.database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL;")
    connection.execute("PRAGMA foreign_keys=ON;")
    return connection


@contextmanager
def connection(settings: Settings) -> Iterator[sqlite3.Connection]:
    conn = get_connection(settings)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(settings: Settings) -> None:
    with connection(settings) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS peers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                public_key TEXT NOT NULL,
                private_key TEXT NOT NULL,
                preshared_key TEXT NOT NULL,
                client_ip TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_handshake TEXT,
                rx_bytes INTEGER NOT NULL DEFAULT 0,
                tx_bytes INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS app_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )


def get_state(conn: sqlite3.Connection, key: str, default: str | None = None) -> str | None:
    row = conn.execute("SELECT value FROM app_state WHERE key = ?", (key,)).fetchone()
    if row is None:
        return default
    return row["value"]


def set_state(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO app_state(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


def list_peers(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM peers ORDER BY id DESC").fetchall()


def get_peer(conn: sqlite3.Connection, peer_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM peers WHERE id = ?", (peer_id,)).fetchone()


def get_peer_by_name(conn: sqlite3.Connection, name: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM peers WHERE lower(name) = lower(?)", (name,)).fetchone()


def insert_peer(
    conn: sqlite3.Connection,
    name: str,
    public_key: str,
    private_key: str,
    preshared_key: str,
    client_ip: str,
) -> int:
    now = utcnow_iso()
    cursor = conn.execute(
        """
        INSERT INTO peers(name, public_key, private_key, preshared_key, client_ip, enabled, created_at, updated_at)
        VALUES(?, ?, ?, ?, ?, 1, ?, ?)
        """,
        (name, public_key, private_key, preshared_key, client_ip, now, now),
    )
    return int(cursor.lastrowid)


def update_peer(conn: sqlite3.Connection, peer_id: int, **fields: object) -> None:
    if not fields:
        return
    fields["updated_at"] = utcnow_iso()
    assignments = ", ".join(f"{key} = ?" for key in fields)
    conn.execute(
        f"UPDATE peers SET {assignments} WHERE id = ?",
        (*fields.values(), peer_id),
    )


def delete_peer(conn: sqlite3.Connection, peer_id: int) -> None:
    conn.execute("DELETE FROM peers WHERE id = ?", (peer_id,))


def count_peers(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) AS total FROM peers").fetchone()
    return int(row["total"] if row else 0)


def count_enabled_peers(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) AS total FROM peers WHERE enabled = 1").fetchone()
    return int(row["total"] if row else 0)
