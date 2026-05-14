"""SQLite connection setup for MedScribe."""

import sqlite3
from pathlib import Path
from typing import Iterator

from backend.database.models import SCHEMA_STATEMENTS

DATABASE_PATH = Path("data/medscribe.db")


def get_connection() -> sqlite3.Connection:
    """Create a SQLite connection with row dictionaries and FK support."""
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Create database tables if they do not already exist."""
    with get_connection() as conn:
        for statement in SCHEMA_STATEMENTS:
            conn.execute(statement)
        conn.commit()


def connection_scope() -> Iterator[sqlite3.Connection]:
    """Yield a connection and commit or rollback around the caller."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

