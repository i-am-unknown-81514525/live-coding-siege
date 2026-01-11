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
import polars as pl

from base import ExecutionContext
from live.live import push_ticket_update_ws
from homelab.schema.project import Project, User
import homelab.api as api

BASE_DIR = Path()
DB_FILE = Path(BASE_DIR) / "data" / "homelab.db"
SCHEMA_FILE = os.path.join(BASE_DIR, "homelab_schema.sql")


@contextmanager
def get_homelab_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    if not os.path.exists(SCHEMA_FILE):
        raise FileNotFoundError(f"Homelab Schema file not found at {SCHEMA_FILE}")

    with get_homelab_db_connection() as conn:
        with open(SCHEMA_FILE, "r") as f:
            schema_sql = f.read()

        cursor = conn.cursor()
        cursor.executescript(schema_sql)
        conn.commit()
    logging.info("Homelab Database initialized successfully.")


def push_proj(projs: list[Project]):
    with get_homelab_db_connection() as conn:
        cursor = conn.cursor()
        for proj in projs:
            cursor.execute(
                """
            INSERT INTO proj_record (
                proj_id,
                measurement_time,
                title,
                description,
                user_id,
                hours,
                repo_url,
                demo_url,
                proj_status
            ) VALUES (?,CURRENT_TIMESTAMP,?,?,?,?,?,?,?)""",
                (
                    proj.proj_id,
                    proj.title,
                    proj.description,
                    proj.user.id,
                    proj.time_s/3600,
                    proj.github_link,
                    proj.demo_link,
                    proj.status,
                ),
            )
            conn.commit()




def prox_get_all_projs() -> list[Project]:
    result = api.get_all_projs()
    try:
        push_proj(result)
    except Exception as e:
        logging.warning(f"Failed to push update to db", exc_info=True)
    return result

def get_user(user_id: api.UserAlike) -> User | None:
    user_id = api._as_user(user_id)
    projects = prox_get_all_projs()
    def filter_fn(proj: Project):
        return proj.user.id == user_id or proj.user.slack_id == user_id
    filtered = list(filter(filter_fn, projects))
    total_s = sum(map(lambda x: x.time_s, filtered))
    if not projects:
        return None
    hl_id = projects[0].user.id
    slack_id = projects[0].user.slack_id
    return User(id=hl_id, slack_id=slack_id, total_time_s=total_s, projects=filtered)

def get_project(proj_id: api.ProjAlike) -> Project:
    proj_id = api._as_project(proj_id)
    projects = prox_get_all_projs()
    def filter_fn(proj: Project):
        return proj.proj_id == proj_id
    filtered = list(filter(filter_fn, projects))
    if not filtered:
        raise ValueError(f"Project {proj_id} not found")
    return filtered[0]


PROJ_LOOP_TIME = 300


def proj_loop():
    while True:
        start = time.perf_counter()
        projs: list[Project] = []
        try:
            projs = api.get_all_projs()
            push_proj(projs)
        except Exception as e:
            logging.warning(f"Faile to fetch project", exc_info=True)
        curr = time.perf_counter()
        logging.info(
            f"Fetched and processed {len(projs)} homelab projects in {curr - start}s (Loop time: {PROJ_LOOP_TIME}s)"
        )
        sleep_time = PROJ_LOOP_TIME - (curr - start)
        if sleep_time > 0:
            time.sleep(sleep_time)




@dataclass(frozen=True)
class ProjHeartbeatRecord:
    proj_id: int
    measurement_time: Arrow
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
            title=row["title"],
            description=row["description"],
            user_id=row["user_id"],
            hours=row["hours"],
            repo_url=row["repo_url"],
            demo_url=row["demo_url"],
            proj_status=row["proj_status"],
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





def retrieve_all_user_proj_record(user_id: int) -> list[ProjHeartbeatRecord]:
    with get_homelab_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
        SELECT
            proj_id,
            measurement_time,
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
        """,
            (user_id,),
        )
        rows = cursor.fetchall()
        records = []
        for row in rows:
            record = ProjHeartbeatRecord.from_row(row)
            records.append(record)
        return records


def retrieve_every_proj_record(since: Arrow | None = None) -> list[ProjHeartbeatRecord]:
    if since is None:
        since = arrow.get(0)
    with get_homelab_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
        SELECT
            proj_id,
            measurement_time,
            title,
            description,
            user_id,
            hours,
            repo_url,
            demo_url,
            proj_status
        FROM proj_record
        WHERE measurement_time >= ?
        ORDER BY measurement_time DESC
        """,
            (since.datetime,),
        )
        rows = cursor.fetchall()
        records = []
        for row in rows:
            record = ProjHeartbeatRecord.from_row(row)
            records.append(record)
        return records


def analyse_hour_by_time_in_heartbeat(
    heartbeats: list[ProjHeartbeatRecord],
) -> dict[Arrow, float]:
    if not heartbeats:
        return {}

    df = pl.DataFrame(
        {
            "time": [hb.measurement_time.datetime for hb in heartbeats],
            "user_id": [hb.user_id for hb in heartbeats],
            "proj_id": [hb.proj_id for hb in heartbeats],
            "hours": [hb.hours for hb in heartbeats],
        }
    )

    df = df.sort("time")

    def user_df_handler(df: pl.DataFrame) -> pl.DataFrame:
        return (
            df.sort("time")
            .group_by_dynamic("time", every="5m")
            .agg([pl.col("hours").max()])
        )

    user_dfs = df.group_by("user_id").map_groups(user_df_handler)
    total_hours_df = (
        user_dfs.group_by("time")
        .agg(pl.sum("hours").fill_null(strategy="forward", limit=3))
        .sort("time")
    )

    return {
        arrow.get(row["time"]): row["hours"][0]
        for row in total_hours_df.iter_rows(named=True)
    }



def analyse_per_person_proj_hours(
    heartbeats: list[ProjHeartbeatRecord],
) -> dict[int, float]:
    result: dict[int, float] = {}
    if not heartbeats:
        return result

    df = pl.DataFrame(
        {
            "time": [hb.measurement_time.datetime for hb in heartbeats],
            "user_id": [hb.user_id for hb in heartbeats],
            "proj_id": [hb.proj_id for hb in heartbeats],
            "hours": [hb.hours for hb in heartbeats],
        }
    )

    df = df.sort("time")

    latest_df = df.group_by(["user_id", "proj_id"]).agg(
        [
            pl.col("hours").last(),
        ]
    )

    total_hours_df = latest_df.group_by("user_id").agg(pl.sum("hours"))

    for row in total_hours_df.iter_rows(named=True):
        result[row["user_id"]] = row["hours"]

    return result



def retrieve_all_proj_record(proj_id: int) -> list[ProjHeartbeatRecord]:
    with get_homelab_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
        SELECT
            proj_id,
            measurement_time,
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
        """,
            (proj_id,),
        )
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
    return max(0.0, final_h - initial_h - penalty_h)



def start(client: ExecutionContext):
    init_db()
    thread_proj = threading.Thread(target=proj_loop)
    thread_proj.start()