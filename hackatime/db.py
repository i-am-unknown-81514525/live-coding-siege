from contextlib import contextmanager
import logging
import os
from pathlib import Path
import sqlite3

from base import ExecutionContext


BASE_DIR = Path()
DB_FILE = Path(BASE_DIR) / "data" / "hackatime.db"
SCHEMA_FILE = os.path.join(BASE_DIR, "hackatime_schema.sql")


@contextmanager
def get_hackatime_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    if not os.path.exists(SCHEMA_FILE):
        raise FileNotFoundError(f"Siege Schema file not found at {SCHEMA_FILE}")

    with get_hackatime_db_connection() as conn:
        with open(SCHEMA_FILE, "r") as f:
            schema_sql = f.read()

        cursor = conn.cursor()
        cursor.executescript(schema_sql)
        conn.commit()
    logging.info("Hackatime Database initialized successfully.")

def append_game(user_id: str, game_id: int, hours: float):
    with get_hackatime_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO link(user_id, game_id, start_hours) VALUES (?, ?, ?) ON CONFLICT(user_id, game_id) DO NOTHING", (user_id, game_id, hours))
        conn.commit()

def start(client: ExecutionContext):
    init_db()