import os
from pathlib import Path
import sqlite3
from contextlib import contextmanager
import logging
import time
import threading

from slack_sdk.socket_mode import SocketModeClient

from schema.siege import SiegeProject, SiegeUser
from live_base import LiveModuleBase, GameInstance
import api

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

def push_link(game_id: int, user_id: int) -> None:
    with get_siege_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO link_record (
            game_id,
            user_id
        )
        VALUES (?, ?)
        ON CONFLICT (game_id, user_id) DO NOTHING
        """, (game_id, user_id))
        conn.commit()


class Siege(LiveModuleBase):
    def __init__(self, instance: GameInstance):
        super().__init__(instance)

    def get_ticket(self, user: str) -> int:
        return 1

    def get_tickets(self, users: list[str]) -> dict[str, int]:
        return {user: 1 for user in users}

    def refresh_tickets(self, users: list[str]) -> dict[str, int]:
        return self.get_tickets(users)

PROJ_LOOP_TIME = 300
def proj_loop():
    while True:
        start = time.perf_counter()
        projs: list[SiegeProject] = []
        try:
            projs = api.get_all_projs()
            push_proj(projs)
        except Exception as e:
            logging.warning(f"Faile to fetch project", exc_info=True)
        curr = time.perf_counter()
        logging.info(f"Fetched and processed {len(projs)} projects in {curr-start}s (Loop time: {PROJ_LOOP_TIME}s)")
        sleep_time = PROJ_LOOP_TIME - (curr - start)
        if sleep_time > 0:
            time.sleep(sleep_time)


def start(client: SocketModeClient):
    init_db()
    thread_proj = threading.Thread(target=proj_loop)
    thread_proj.start()

def get_module(instance: GameInstance) -> Siege:
    return Siege(instance)