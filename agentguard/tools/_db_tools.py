from __future__ import annotations

import sqlite3
import threading

_CONNECTION_LOCK = threading.Lock()


def _make_connection() -> sqlite3.Connection:
    """Create a new in-memory SQLite connection that can be shared across threads."""
    return sqlite3.connect(":memory:", check_same_thread=False)


def _seed_database(connection: sqlite3.Connection) -> None:
    """Seed in-memory sample tables used by the demo and tests."""
    connection.execute("CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT)")
    connection.execute("CREATE TABLE public_notes (id INTEGER PRIMARY KEY, note TEXT)")
    connection.execute("CREATE TABLE employees_salary (id INTEGER PRIMARY KEY, salary REAL)")
    connection.execute("INSERT INTO products (name) VALUES ('Widget')")
    connection.execute("INSERT INTO public_notes (note) VALUES ('Approved note')")
    connection.execute("INSERT INTO employees_salary (salary) VALUES (50000.00)")
    connection.commit()


_CONNECTION = _make_connection()
_seed_database(_CONNECTION)


def query_db(sql: str):
    """Execute a SQL query against the in-memory simulation database."""
    with _CONNECTION_LOCK:
        cursor = _CONNECTION.execute(sql)
        rows = cursor.fetchall()
        return rows


def reset_db() -> None:
    """Reset the in-memory database to its default sample data."""
    global _CONNECTION
    with _CONNECTION_LOCK:
        try:
            _CONNECTION.close()
        except Exception:
            pass
        _CONNECTION = _make_connection()
        _seed_database(_CONNECTION)
