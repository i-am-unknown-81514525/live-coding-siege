from dataclasses import dataclass
import os
from pathlib import Path
import sqlite3
from contextlib import contextmanager
import logging
import time
import threading

from arrow import Arrow
import arrow
from slack_sdk.socket_mode import SocketModeClient

from live.live import push_ticket_update_ws
from schema.siege import SiegeProject, SiegeUser
from live.live_base import LiveModuleBase, GameInstance
import api, utils

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
            (proj.id, proj.week, proj.name, proj.description, proj.user.id, proj.hours, proj.repo_url, proj.demo_url, proj.status))
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
                coin_count,
                user_status
            )
            VALUES (?, CURRENT_TIMESTAMP, ?, ?, ?)
            """, (user.id, user.name, user.coins, user.status))
            conn.commit()

def push_link(game_id: int, user_id: int) -> None:
    with get_siege_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO game_link (
            game_id,
            user_id
        )
        VALUES (?, ?)
        ON CONFLICT (game_id, user_id) DO NOTHING
        """, (game_id, user_id))
        conn.commit()

def push_mapping(slack_id: str, siege_user_id: int) -> None:
    with get_siege_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO user_mapping (
            slack_id,
            siege_user_id
        )
        VALUES (?, ?)
        ON CONFLICT (slack_id) DO UPDATE SET siege_user_id=excluded.siege_user_id
        """, (slack_id, siege_user_id))
        conn.commit()

def get_user_id_from_proj() -> list[int]:
    with get_siege_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""SELECT user_id FROM proj_record GROUP BY user_id""")
        rows = cursor.fetchall()
        return [row["user_id"] for row in rows]

def get_user_proj(user_id: int, week: int | None) -> int | None:
    if week is None:
        week = utils.guess_week()
    return {proj.week: proj.id for proj in api.get_user(user_id).projects}.get(week)

def fetch_linked_users(game_id: int) -> list[int]:
    with get_siege_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT user_id FROM game_link WHERE game_id = ?
        """, (game_id,))
        rows = cursor.fetchall()
        return [row["user_id"] for row in rows]

def fetch_all_user_link(used_ids: list[int]) -> list[int]:
    with get_siege_db_connection() as conn:
        cursor = conn.cursor()
        placeholder = ",".join("?" for _ in used_ids)
        query = f"""
        SELECT DISTINCT game_id FROM game_link WHERE user_id IN ({placeholder})
        """
        cursor.execute(query, used_ids)
        rows = cursor.fetchall()
        return [row["game_id"] for row in rows]

def prox_get_all_projs() -> list[SiegeProject]:
    result = api.get_all_projs()
    try:
        push_proj(result)
    except Exception as e:
        logging.warning(f"Failed to push update to db", exc_info=True)
    return result

def prox_get_project(proj_id: api.ProjAlike) -> SiegeProject:
    project = api.get_project(proj_id)
    try:
        push_proj([project])
    except Exception as e:
        logging.warning(f"Failed to push update to db", exc_info=True)
    return project

def prox_get_user(user_id: api.UserAlike) -> SiegeUser:
    user = api.get_user(user_id)
    try:
        push_user([user])
    except Exception as e:
        logging.warning(f"Fail to push update to db", exc_info=True)
    return user


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
        try:
            game_req_update = fetch_all_user_link(list(set(proj.user.id for proj in projs)))
            for game_id in game_req_update:
                try:
                    push_ticket_update_ws(game_id)
                except Exception as e:
                    logging.info(f"Faile to push update on game", exc_info=True)
        except Exception as e:
            logging.warning(f"Faile to push update on game", exc_info=True)
        curr = time.perf_counter()
        logging.info(f"Fetched and processed {len(projs)} projects in {curr-start}s (Loop time: {PROJ_LOOP_TIME}s)")
        sleep_time = PROJ_LOOP_TIME - (curr - start)
        if sleep_time > 0:
            time.sleep(sleep_time)

USER_LOOP_TIME = 450
IDV_DELAY = 0.5
def user_loop():
    while True:
        start = time.perf_counter()
        user_id_list: list[int] = get_user_id_from_proj()
        users: list[SiegeUser] = []
        try:
            for user_id in user_id_list:
                try:
                    idv_start = time.perf_counter()
                    user = api.get_user(user_id)
                    users.append(user)
                    idv_curr = time.perf_counter()
                    if IDV_DELAY - (idv_curr - idv_start) > 0:
                        time.sleep(IDV_DELAY - (idv_curr - idv_start))
                except Exception as e:
                    logging.info(f"Faile to fetch users with user id: {user_id}", exc_info=True)
            push_user(users)
            for user in users:
                try:
                    push_mapping(user.slack_id, user.id)
                except Exception as e:
                    logging.info(f"Faile to push mapping for user id: {user.id}", exc_info=True)
        except Exception as e:
            logging.warning(f"Faile to fetch users", exc_info=True)
        curr = time.perf_counter()
        logging.info(f"Fetched and processed {len(users)} users in {curr-start}s (Loop time: {USER_LOOP_TIME}s)")
        sleep_time = USER_LOOP_TIME - (curr - start)
        if sleep_time > 0:
            time.sleep(sleep_time)

@dataclass(frozen=True)
class ProjHeartbeatRecord:
    proj_id: int
    measurement_time: Arrow
    week_num: int
    title: str
    description: str
    user_id: int
    hours: float
    repo_url: str
    demo_url: str
    proj_status: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "ProjHeartbeatRecord":
        return cls(
            proj_id=row["proj_id"],
            measurement_time=arrow.get(row["measurement_time"]),
            week_num=row["week_num"],
            title=row["title"],
            description=row["description"],
            user_id=row["user_id"],
            hours=row["hours"],
            repo_url=row["repo_url"],
            demo_url=row["demo_url"],
            proj_status=row["proj_status"]
        )
    
    def compare_to_new(self, new: "ProjHeartbeatRecord") -> dict[str, tuple[str, str]]:
        diffs: dict[str, tuple[str, str]] = {}
        if self.title != new.title:
            diffs["Project Name"] = (self.title, new.title)
        if self.description != new.description:
            diffs["Description"] = (self.description, new.description)
        if self.hours != new.hours:
            diffs["Hours"] = (str(self.hours), str(new.hours))
        if self.repo_url != new.repo_url:
            diffs["Repo URL"] = (self.repo_url, new.repo_url)
        if self.demo_url != new.demo_url:
            diffs["Demo URL"] = (self.demo_url, new.demo_url)
        if self.proj_status != new.proj_status:
            diffs["Project Status"] = (self.proj_status, new.proj_status)
        return diffs
    
    def compare_to_old(self, old: "ProjHeartbeatRecord") -> dict[str, tuple[str, str]]:
        return old.compare_to_new(self)

@dataclass(frozen=True)
class UserHeartbeatRecord:
    user_id: int
    measurement_time: Arrow
    username: str
    coin_count: int
    user_status: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "UserHeartbeatRecord":
        return cls(
            user_id=row["user_id"],
            measurement_time=arrow.get(row["measurement_time"]),
            username=row["username"],
            coin_count=row["coin_count"],
            user_status=row["user_status"]
        )
    
    def compare_to_new(self, new: "UserHeartbeatRecord") -> dict[str, tuple[str, str]]:
        diffs: dict[str, tuple[str, str]] = {}
        if self.username != new.username:
            diffs["Username"] = (self.username, new.username)
        if self.coin_count != new.coin_count:
            diffs["Coin Count"] = (str(self.coin_count), str(new.coin_count))
        if self.user_status != new.user_status:
            diffs["User Status"] = (self.user_status, new.user_status)
        return diffs
    def compare_to_old(self, old: "UserHeartbeatRecord") -> dict[str, tuple[str, str]]:
        return old.compare_to_new(self)

def retrieve_all_user_record(user_id: int) -> list[UserHeartbeatRecord]:
    with get_siege_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT
            user_id,
            measurement_time,
            username,
            coin_count,
            user_status
        FROM user_record
        WHERE user_id = ?
        ORDER BY measurement_time DESC
        """, (user_id,))
        rows = cursor.fetchall()
        records = []
        for row in rows:
            record = UserHeartbeatRecord.from_row(row)
            records.append(record)
        return records

def retrieve_all_user_proj_record(user_id: int) -> list[ProjHeartbeatRecord]:
    with get_siege_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT
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
        FROM proj_record
        WHERE user_id = ?
        ORDER BY measurement_time DESC
        """, (user_id,))
        rows = cursor.fetchall()
        records = []
        for row in rows:
            record = ProjHeartbeatRecord.from_row(row)
            records.append(record)
        return records

def retrieve_all_proj_record(proj_id: int) -> list[ProjHeartbeatRecord]:
    with get_siege_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT
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
        FROM proj_record
        WHERE proj_id = ?
        ORDER BY measurement_time DESC
        """, (proj_id,))
        rows = cursor.fetchall()
        records = []
        for row in rows:
            record = ProjHeartbeatRecord.from_row(row)
            records.append(record)
        return records

def retrieve_all_heartbeat_curr_proj_curr_week(user_id: int, week_num: int, from_time: Arrow) -> list[ProjHeartbeatRecord]:
    with get_siege_db_connection() as conn:
        cursor = conn.cursor()
        curr_proj = get_user_proj(user_id, week_num)
        if curr_proj is None:
            return []
        cursor.execute("""
        SELECT
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
        FROM proj_record
        WHERE user_id = ? AND week_num = ? AND proj_id = ? AND measurement_time >= ?
        ORDER BY measurement_time DESC
        """, (user_id, week_num, curr_proj, from_time.datetime))
        rows = cursor.fetchall()
        records = []
        for row in rows:
            record = ProjHeartbeatRecord.from_row(row)
            records.append(record)
        return records

def analysis_heartbeat_hours(heartbeats: list[ProjHeartbeatRecord]) -> float:
    LEEWAY_HOURS_PER_HEARTBEAT = 0.15
    hours = 0
    if not heartbeats:
        return 0
    heartbeats_sorted = list(sorted(heartbeats, key=lambda hb: hb.measurement_time))
    earlist_heartbeat = heartbeats_sorted[0]
    initial_h = earlist_heartbeat.hours
    final_h = heartbeats_sorted[-1].hours
    curr_h = initial_h
    curr_t = earlist_heartbeat.measurement_time
    penalty_h = 0
    for hb in heartbeats_sorted[1:]:
        delta_t = (hb.measurement_time - curr_t).total_seconds() / 3600.0
        increase_h = hb.hours - curr_h
        expected_increase_h = delta_t + LEEWAY_HOURS_PER_HEARTBEAT
        if increase_h >= expected_increase_h:
            penalty_h += increase_h - delta_t
        curr_h = hb.hours
        curr_t = hb.measurement_time
    return max(0, final_h - initial_h - penalty_h)

def get_user_id_from_slack(slack_id: str) -> int | None:
    with get_siege_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT siege_user_id FROM user_mapping WHERE slack_id = ?
        """, (slack_id,))
        row = cursor.fetchone()
        if row:
            return row["siege_user_id"]
        try:
            user_id = api.get_user(slack_id).id
            push_mapping(slack_id, user_id)
            return user_id
        except Exception:
            logging.info(f"Faile to fetch user id from slack id: {slack_id}", exc_info=True)
            return None

def get_user_ticket(game_id: int, user_id: str, week_num: int, from_time: Arrow) -> int:
    siege_user_id = get_user_id_from_slack(user_id)
    if siege_user_id is None:
        return 0
    heartbeats = retrieve_all_heartbeat_curr_proj_curr_week(siege_user_id, week_num, from_time)
    return int(analysis_heartbeat_hours(heartbeats)*10) + 10

class Siege(LiveModuleBase):
    def __init__(self, instance: GameInstance):
        for participant in instance.participants:
            user_id = get_user_id_from_slack(participant)
            if user_id is not None:
                push_link(instance.game_id, user_id)
        super().__init__(instance)

    def get_ticket(self, user: str) -> int:
        week_num = utils.guess_week()
        return get_user_ticket(self._instance.game_id, user, week_num, self._instance.start_time)

    def get_tickets(self, users: list[str]) -> dict[str, int]:
        week_num = utils.guess_week()
        return {user: get_user_ticket(self._instance.game_id, user, week_num, self._instance.start_time) for user in users}

    def refresh_tickets(self, users: list[str]) -> dict[str, int]:
        projs: list[SiegeProject] = []
        try:
            projs = api.get_all_projs()
            push_proj(projs)
        except Exception as e:
            logging.warning(f"Faile to fetch project", exc_info=True)
        try:
            game_req_update = fetch_all_user_link(list(set(proj.user.id for proj in projs)))
            for game_id in game_req_update:
                try:
                    push_ticket_update_ws(game_id)
                except Exception as e:
                    logging.info(f"Faile to push update on game", exc_info=True)
        except Exception as e:
            logging.warning(f"Faile to push update on game", exc_info=True)
        return self.get_tickets(users)

def start(client: SocketModeClient):
    init_db()
    thread_proj = threading.Thread(target=proj_loop)
    thread_proj.start()
    thread_user = threading.Thread(target=user_loop)
    thread_user.start()

def get_module(instance: GameInstance) -> Siege:
    return Siege(instance)