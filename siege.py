import os
from pathlib import Path
import sqlite3
from contextlib import contextmanager

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = Path(BASE_DIR) / "data" / "siege.db"
SCHEMA_FILE = os.path.join(BASE_DIR, "siege_schema.sql")


@contextmanager
def get_siege_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    if not os.path.exists(SCHEMA_FILE):
        raise FileNotFoundError(f"Schema file not found at {SCHEMA_FILE}")

    with get_siege_db_connection() as conn:
        with open(SCHEMA_FILE, "r") as f:
            schema_sql = f.read()

        cursor = conn.cursor()
        cursor.executescript(schema_sql)
        conn.commit()
    print("Database initialized successfully.")