import os
from pathlib import Path
import sqlite3
from contextlib import contextmanager

from slack_sdk.socket_mode import SocketModeClient

from schema.siege import SiegeProject, SiegeUser

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
        raise FileNotFoundError(f"Siege Schema file not found at {SCHEMA_FILE}")

    with get_siege_db_connection() as conn:
        with open(SCHEMA_FILE, "r") as f:
            schema_sql = f.read()

        cursor = conn.cursor()
        cursor.executescript(schema_sql)
        conn.commit()
    print("Siege Database initialized successfully.")

def push_proj(projs: list[SiegeProject]):
    with get_siege_db_connection() as conn:
        cursor = conn.cursor()
        for proj in projs:
            cursor.execute("""
            INSERT INTO proj_record (
                proj_id,
                measurement_time,
                week_num,
                title,
                description,
                user_id,
                hours,
                repo_url,
                demo_url,
                proj_status
            ) VALUES (?,CURRENT_TIMESTAMP,?,?,?,?,?,?,?,?)""",
            (proj.id, proj.week, proj.name, proj.description, proj.user.id, proj.hours))
            conn.commit()
        
def push_user(users: list[SiegeUser]):
    with get_siege_db_connection() as conn:
        cursor = conn.cursor()
        for user in users:
            cursor.execute("""
            INSERT INTO user_record (
                user_id,
                measurement_time,
                username,
                coin_aount,
                user_status
            )
            VALUES (?, CURRENT_TIMESTAMP, ?, ?, ?)
            """, (user.id, user.name, user.coins, user.status))

def start(client: SocketModeClient):
    init_db()
