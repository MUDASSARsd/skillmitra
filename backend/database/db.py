"""
Database Connection Manager for SQLite database.
"""
import sqlite3
import os
from pathlib import Path
from backend.database.models import init_db_schema

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "nqr_database.db"


def get_db_connection(db_path=None):
    """Returns a SQLite connection configured with row factory and foreign keys."""
    path = Path(db_path) if db_path else DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path=None):
    """Initializes the SQLite database schema."""
    conn = get_db_connection(db_path)
    init_db_schema(conn)
    return conn
