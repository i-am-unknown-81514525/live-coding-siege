import logging
import sqlite3
import os
from contextlib import contextmanager
import json
from datetime import datetime, timezone
from cryptography.hazmat.primitives.hashes import Hash, SHA3_512
from pathlib import Path
import arrow
from base import Client
import live.base as base
from dataclasses import dataclass
from slack_sdk.socket_mode.client import BaseSocketModeClient

import slack.api
from slack.client import SlackClient

DB_FILE = Path() / "data" / "live_coding.db"
SCHEMA_FILE = os.path.join(Path(), "schema.sql")


@contextmanager
def get_db_connection():
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

    with get_db_connection() as conn:
        with open(SCHEMA_FILE, "r") as f:
            schema_sql = f.read()

        cursor = conn.cursor()
        cursor.executescript(schema_sql)
        conn.commit()
    print("Database initialized successfully.")


def _sha3(text: str) -> str:
    hash_obj = Hash(SHA3_512())
    hash_obj.update(text.encode("utf-8"))
    return hash_obj.finalize().hex()


def get_latest_transaction_hash(conn: sqlite3.Connection, game_id: int) -> str | None:
    """Retrieves the hash of the most recent transaction for a given game."""
    cursor = conn.cursor()
    row = cursor.execute(
        """
        SELECT transaction_hash FROM event_transaction
        WHERE game_id = ?
        ORDER BY timestamp DESC, id DESC
        LIMIT 1
        """,
        (game_id,),
    ).fetchone()
    return row["transaction_hash"] if row else None


def _add_transaction(
    conn: sqlite3.Connection,
    game_id: int,
    event_type: str,
    client_secret: str,
    server_secret: str,
    user_id: str | None = None,
    details: dict | None = None,
) -> str:
    """
    A generic internal function to add a new transaction to the event log.
    Handles cryptographic chaining. It's the caller's responsibility to commit.
    """
    details_json = json.dumps(details) if details else None
    timestamp = datetime.now(timezone.utc).isoformat()

    prev_hash = get_latest_transaction_hash(conn, game_id)

    # Create a consistent string representation for hashing
    hash_content = (
        f"{prev_hash or ''}{event_type}{game_id}{user_id or ''}"
        f"{details_json or ''}{client_secret}{server_secret}{timestamp}"
    )
    new_hash = _sha3(hash_content)

    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO event_transaction (transaction_hash, previous_transaction_hash, timestamp, event_type, game_id, user_id, details, client_secret, server_secret)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            new_hash,
            prev_hash,
            timestamp,
            event_type,
            game_id,
            user_id,
            details_json,
            client_secret,
            server_secret,
        ),
    )
    return new_hash


def start_game(
    huddle_id: str,
    channel_id: str,
    thread_ts: str,
    start_time: datetime,
    client_secret: str,
    server_secret: str,
    mode: str,
) -> int:
    """Creates a new game and its initial 'GAME_START' transaction."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        row = cursor.execute(
            "INSERT INTO game (huddle_id, channel_id, thread_ts, start_time, status, mode) VALUES (?, ?, ?, ?, 'ACTIVE', ?) RETURNING id",
            (huddle_id, channel_id, thread_ts, start_time.isoformat(), mode),
        ).fetchone()
        if not row:
            # This case should not be reached if the insert is successful and RETURNING is supported.
            raise RuntimeError("Failed to create a new game record.")
        game_id = row["id"]
        _add_transaction(
            conn,
            game_id,
            "GAME_START",
            client_secret,
            server_secret,
            details={"mode": mode},
        )
        conn.commit()
        return game_id


def edit_game(game_id: int, huddle_id: str, channel_id: str, thread_ts: str):
    """Move a game to a new huddle/channel/thread."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE game SET huddle_id = ?, channel_id = ?, thread_ts = ? WHERE id = ?",
            (huddle_id, channel_id, thread_ts, game_id),
        )
        conn.commit()


def add_message_transaction(
    game_id: int, user_id: str, message_text: str, message_id: str
) -> str:
    """
    Adds a 'MSG_SENT' transaction.
    """
    with get_db_connection() as conn:
        secrets = get_latest_secrets(game_id)
        if not secrets:
            raise ValueError(
                f"Cannot add message to game {game_id} with no existing transactions."
            )
        old_client_secret, server_secret = secrets
        new_client_secret = _sha3(f"{old_client_secret}:{message_text}:{message_id}")
        new_hash = _add_transaction(
            conn,
            game_id=game_id,
            event_type="MSG_SENT",
            client_secret=new_client_secret,
            server_secret=server_secret,
            user_id=user_id,
            details={"text": message_text},
        )
        conn.commit()
        return new_hash


def add_user_selection_transaction(
    game_id: int,
    user_id: str,
    duration_seconds: int,
) -> str:
    """Adds a 'USER_SELECTED' transaction and creates the game_turn record."""
    with get_db_connection() as conn:
        secrets = get_latest_secrets(game_id)
        if not secrets:
            raise ValueError(
                f"Cannot select user for game {game_id} with no existing transactions."
            )
        client_secret, server_secret = secrets

        cursor = conn.cursor()
        # # The following should never happen and now the required additional parameter make it not possible to have this fallback
        # cursor.execute(
        #     "INSERT OR IGNORE INTO game_participant (game_id, user_id) VALUES (?, ?)",
        #     (game_id, user_id),
        # )
        cursor.execute(
            "INSERT INTO game_turn (game_id, user_id, selection_time, assigned_duration_seconds, status) VALUES (?, ?, ?, ?, 'PENDING')",
            (
                game_id,
                user_id,
                datetime.now(timezone.utc).isoformat(),
                duration_seconds,
            ),
        )
        new_hash = _add_transaction(
            conn,
            game_id=game_id,
            event_type="USER_SELECTED",
            client_secret=client_secret,
            server_secret=server_secret,
            user_id=user_id,
            details={"duration_seconds": duration_seconds},
        )
        conn.commit()
        return new_hash


def update_game_status(
    game_id: int,
    status: str,  # Should be 'COMPLETED' or 'CANCELLED'
) -> str:
    """Updates a game's status and logs the event as a transaction."""
    with get_db_connection() as conn:
        secrets = get_latest_secrets(game_id)
        if not secrets:
            raise ValueError(
                f"Cannot update status for game {game_id} with no existing transactions."
            )
        client_secret, server_secret = secrets

        cursor = conn.cursor()
        cursor.execute(
            "UPDATE game SET status = ?, end_time = ? WHERE id = ?",
            (status, datetime.now(timezone.utc).isoformat(), game_id),
        )
        event_type = f"GAME_{status.upper()}"  # e.g., GAME_COMPLETED
        new_hash = _add_transaction(
            conn,
            game_id=game_id,
            event_type=event_type,
            client_secret=client_secret,
            server_secret=server_secret,
            details={"new_status": status},
        )
        conn.commit()
        return new_hash


def get_slack_user(user_id: str) -> tuple[str, str | None] | None:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        row = cursor.execute(
            "SELECT name, avatar_url FROM user WHERE slack_id = ?", (user_id,)
        ).fetchone()
        if not row:
            return None
        return row["name"], row["avatar_url"]


def start_turn(game_id: int, user_id: str) -> sqlite3.Row:
    """Updates a pending turn to 'IN_PROGRESS' and sets its start time, logging the transaction."""
    with get_db_connection() as conn:
        secrets = get_latest_secrets(game_id)
        if not secrets:
            raise ValueError(
                f"Cannot start turn for game {game_id} with no existing transactions."
            )
        client_secret, server_secret = secrets

        cursor = conn.cursor()

        turn_details = cursor.execute(
            "SELECT * FROM game_turn WHERE game_id = ? AND user_id = ? AND status = 'PENDING'",
            (game_id, user_id),
        ).fetchone()

        if not turn_details:
            raise ValueError(
                f"No pending turn found for user {user_id} in game {game_id} to start."
            )

        cursor.execute(
            """
            UPDATE game_turn 
            SET status = 'IN_PROGRESS', start_time = ? 
            WHERE id = ?
            """,
            (datetime.now(timezone.utc).isoformat(), turn_details["id"]),
        )

        if cursor.rowcount == 0:
            raise ValueError(
                f"No pending turn found for user {user_id} in game {game_id} to start."
            )

        new_hash = _add_transaction(
            conn,
            game_id=game_id,
            event_type="TURN_START",
            client_secret=client_secret,
            server_secret=server_secret,
            user_id=user_id,
            details={"new_status": "IN_PROGRESS"},
        )
        conn.commit()
        return turn_details


def update_turn_status(
    game_id: int,
    user_id: str,
    new_status: str,  # 'COMPLETED', 'SKIPPED', or 'FAILED'
) -> str:
    """Updates a turn's status and participant stats, logging the transaction."""
    with get_db_connection() as conn:
        secrets = get_latest_secrets(game_id)
        if not secrets:
            raise ValueError(
                f"Cannot update turn for game {game_id} with no existing transactions."
            )
        client_secret, server_secret = secrets

        cursor = conn.cursor()

        cursor.execute(
            "UPDATE game_turn SET status = ? WHERE game_id = ? AND user_id = ? AND status IN ('PENDING', 'IN_PROGRESS')",
            (new_status, game_id, user_id),
        )

        if new_status == "COMPLETED":
            cursor.execute(
                "UPDATE game_participant SET successful_rounds = successful_rounds + 1, consecutive_skips = 0 WHERE game_id = ? AND user_id = ?",
                (game_id, user_id),
            )
        elif new_status == "SKIPPED":
            cursor.execute(
                "UPDATE game_participant SET consecutive_skips = consecutive_skips + 1 WHERE game_id = ? AND user_id = ?",
                (game_id, user_id),
            )

        event_type = f"TURN_{new_status.upper()}"
        new_hash = _add_transaction(
            conn,
            game_id=game_id,
            event_type=event_type,
            client_secret=client_secret,
            server_secret=server_secret,
            user_id=user_id,
            details={"new_status": new_status},
        )
        conn.commit()
        return new_hash


def set_turn_timeout_notified(game_id: int, user_id: str):
    """
    Sets the timeout_notified flag to TRUE for the most recent turn for a user in a game.
    This prevents duplicate timeout notifications on restart.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE game_turn SET timeout_notified = TRUE WHERE id = (SELECT id FROM game_turn WHERE game_id = ? AND user_id = ? ORDER BY selection_time DESC, id DESC LIMIT 1)",
            (game_id, user_id),
        )
        conn.commit()


def get_latest_secrets(game_id: int) -> tuple[str, str] | None:
    """Retrieves the latest client and server secrets for a given game."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        row = cursor.execute(
            """
            SELECT client_secret, server_secret FROM event_transaction
            WHERE game_id = ?
            ORDER BY timestamp DESC, id DESC
            LIMIT 1
            """,
            (game_id,),
        ).fetchone()
        if not row:
            return None
        return (row["client_secret"], row["server_secret"])


def update_server_secret(
    game_id: int,
    new_server_secret: str,
) -> str:
    """Updates the server secret and logs a 'SERVER_SECRET_UPDATE' transaction."""
    with get_db_connection() as conn:
        secrets = get_latest_secrets(game_id)
        if not secrets:
            raise ValueError(
                f"Cannot update server secret for game {game_id} with no existing transactions."
            )
        client_secret, _old_server_secret = secrets

        new_hash = _add_transaction(
            conn,
            game_id=game_id,
            event_type="SERVER_SECRET_UPDATE",
            client_secret=client_secret,
            server_secret=new_server_secret,
            details={"new_server_secret": new_server_secret},
        )
        conn.commit()
        return new_hash


def upsert_user(user_id: str, name: str, avatar_url: str | None = None, client: Client[BaseSocketModeClient] | None = None):
    """Adds a new user or updates their name. It avoids overwriting a real name with 'UNKNOWN'."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO user (slack_id, name, avatar_url) VALUES (?, ?, ?)
            ON CONFLICT(slack_id) DO UPDATE SET 
                name = excluded.name,
                avatar_url = excluded.avatar_url
            WHERE excluded.name != 'UNKNOWN' OR user.name = 'UNKNOWN'
            """,
            (user_id, name, avatar_url),
        )
        conn.commit()
        cursor.execute("SELECT avatar_url FROM user WHERE slack_id = ?", (user_id,))
        res = cursor.fetchone()
        if res is not None:
            avatar_url = res[0]
            if avatar_url is None and client:
                avatar_url = slack.api.get_profile_picture(user_id, client) # pyright: ignore[reportArgumentType]
                cursor.execute(
                    "UPDATE user SET avatar_url = ? WHERE slack_id = ?",
                    (avatar_url, user_id),
                )
                conn.commit()
            logging.info(f"User {user_id} avatar URL: {res[0]} -> {avatar_url}")
        else:
            logging.info(f"User {user_id} not found???.")
    


# def auto_add(game_id: int, user_id: str, week: int | None = None):
#     week_num = week or guess_week()
#     projs = get_user(user_id).projects
#     proj = [proj for proj in projs if proj.week == week_num]
#     if proj:
#         full_proj = get_project(proj[0].id)
#         add_game_participant(
#             game_id, user_id, h_now=full_proj.hours, proj_id=proj[0].id
#         )
#     else:
#         add_game_participant(game_id, user_id, h_now=0, proj_id=None)


# def auto_add_no_siege(game_id, user_id):
#     add_game_participant(game_id, user_id, 0, None)

# def reset_game_participant(game_id: int, user_id: str, week: int | None = None):
#     week_num = week or guess_week()
#     projs = get_user(user_id).projects
#     proj = [proj for proj in projs if proj.week == week_num]
#     if proj:
#         with get_db_connection() as conn:
#             cursor = conn.cursor()
#             cursor.execute(
#                 """SELECT proj_id WHERE game_id = ? AND user_id = ?""",
#                 (game_id, user_id)
#             )
#             result = cursor.fetchone()
#             if result and result[0] == proj[0].id:
#                 update_time(game_id, user_id)
#                 return
#             cursor = conn.cursor()
#             cursor.execute("""
#                         INSERT INTO game_participant (game_id, user_id, h_start, h_curr, proj_id, h_lastcheck) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
#                         ON CONFLICT (game_id, user_id) DO UPDATE SET
#                             h_curr = excluded.h_curr
#                             h_start = excluded.h_start
#                             proj_id = excluded.proj_id
#                             h_lastcheck = CURRENT_TIMESTAMP
#                             h_penalty = 0
#                         """
#             )
#             conn.commit()
#             update_time(game_id, user_id)


# def add_game_participant(
#     game_id: int, user_id: str, h_now: float | None, proj_id: int | None
# ):
#     """Adds a user to a game's participant list. Update proper field when e.g. the user don't start with having a project."""
#     # TODO: the h_penalty thing, I hope I remember and also don't have to make 2 function for it
#     with get_db_connection() as conn:
#         cursor = conn.cursor()
#         cursor.execute(
#             """
#             INSERT INTO game_participant (game_id, user_id, h_start, h_curr, proj_id, h_lastcheck) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
#             ON CONFLICT(game_id, user_id) DO UPDATE SET
#                 h_curr = CASE WHEN excluded.h_curr IS NOT NULL AND (excluded.h_curr > game_participant.h_curr OR game_participant.proj_id != excluded.proj_id) THEN excluded.h_curr ELSE game_participant.h_curr END,
#                 h_start = CASE WHEN excluded.h_start IS NOT NULL AND (game_participant.h_start IS NULL OR game_participant.proj_id != excluded.proj_id) THEN excluded.h_start ELSE game_participant.h_start END,
#                 proj_id = CASE WHEN excluded.proj_id IS NOT NULL THEN excluded.proj_id ELSE game_participant.proj_id END,
#                 h_lastcheck = CASE WHEN excluded.h_curr IS NOT NULL AND (excluded.h_curr > game_participant.h_curr OR game_participant.proj_id != excluded.proj_id) THEN CURRENT_TIMESTAMP ELSE game_participant.h_lastcheck END
#             """,
#             (game_id, user_id, h_now, h_now, proj_id),
#         )
#         conn.commit()
#     if proj_id is not None:
#         update_time(game_id, user_id)


# @dataclass
# class HourStatus:
#     h_start: Final[float]
#     h_curr: Final[float]
#     h_penalty: Final[float]


# def get_time(game_id: int, user_id: str) -> HourStatus | None:
#     with get_db_connection() as conn:
#         cursor = conn.cursor()
#         cursor.execute(
#             """SELECT  h_curr, h_start, h_penalty FROM game_participant WHERE game_id = ? AND user_id = ? LIMIT 1""",
#             (game_id, user_id),
#         )
#         result = cursor.fetchone()
#         if not result:
#             return None
#         last_h_now, h_start, h_penalty = result
#         return HourStatus(h_start, last_h_now, h_penalty)


# def update_time(game_id: int, user_id: str) -> HourStatus | None:
#     with get_db_connection() as conn:
#         cursor = conn.cursor()
#         cursor.execute(
#             """SELECT proj_id, h_lastcheck, h_curr, h_start, h_penalty FROM game_participant WHERE game_id = ? AND user_id = ? LIMIT 1""",
#             (game_id, user_id),
#         )
#         result = cursor.fetchone()
#         if not result:
#             return None
#         proj_id, last_check_time, last_h_now, h_start, h_penalty = result
#         h_now = get_project(proj_id).hours
#         last_check_time = arrow.get(last_check_time)
#         curr = arrow.now()
#         dt = curr - last_check_time
#         h_diff = h_now - last_h_now
#         c_diff = dt.total_seconds() / 3600
#         ALLOWED_LEEWAY = 0.15
#         penalty_addition = 0
#         if c_diff + ALLOWED_LEEWAY < h_diff:
#             penalty_addition = h_diff - c_diff
#         cursor.execute(
#             """UPDATE game_participant SET h_curr = ?, h_lastcheck = CURRENT_TIMESTAMP, h_penalty = h_penalty + ? WHERE game_id = ? AND user_id = ?""",
#             (h_now, penalty_addition, game_id, user_id),
#         )
#         conn.commit()
#         return HourStatus(h_start, h_now, h_penalty + penalty_addition)

# def update_time_multi(game_id: int, user_ids: list[str]) -> dict[str, HourStatus]:
#     with get_db_connection() as conn:
#         cursor = conn.cursor()
#         cursor.execute(
#             f"""SELECT user_id, proj_id, h_lastcheck, h_curr, h_start, h_penalty FROM game_participant WHERE game_id = ? AND user_id IN ({
#                 ",".join(["?" for v in range(len(user_ids))])
#                 })""",
#             (game_id, *user_ids)
#         )
#         data: dict[str, tuple[str, arrow.Arrow, float, float, float]] = {}
#         threads: list[tuple[str, concurrent.futures.Future[SiegeProject]]] = []
#         ret: dict[str, HourStatus] = {}
#         with concurrent.futures.ThreadPoolExecutor() as execotor:
#             for row in cursor.fetchall():
#                 user_id, proj_id, last_check_time, last_h_now, h_start, h_penalty = row
#                 data[user_id] = (proj_id, arrow.get(last_check_time), last_h_now, h_start, h_penalty)
#                 thread = execotor.submit(get_project, proj_id)
#                 threads.append((user_id, thread))
#             # logging.info(data)
#             for user_id, thread in threads:
#                 try:
#                     proj_id, last_check_time, last_h_now, h_start, h_penalty = data[user_id]
#                     h_now = thread.result(10).hours
#                     last_check_time = arrow.get(last_check_time)
#                     curr = arrow.now()
#                     dt = curr - last_check_time
#                     h_diff = h_now - last_h_now
#                     c_diff = dt.total_seconds() / 3600
#                     ALLOWED_LEEWAY = 0.15
#                     penalty_addition = 0
#                     if c_diff + ALLOWED_LEEWAY < h_diff:
#                         penalty_addition = h_diff - c_diff
#                     cursor.execute(
#                         """UPDATE game_participant SET h_curr = ?, h_lastcheck = CURRENT_TIMESTAMP, h_penalty = h_penalty + ? WHERE game_id = ? AND user_id = ?""",
#                         (h_now, penalty_addition, game_id, user_id),
#                     )
#                     conn.commit()
#                     ret[user_id] = HourStatus(h_start, h_now, h_penalty + penalty_addition)
#                 except:
#                     logging.warning(f"Failed to fetch project time for {user_id}", exc_info=True)
#         return ret


# def get_ticket(base: int, addition: int, h_per_addition: float, hour: float) -> int:
#     return base + max(0, addition * int(round(hour / h_per_addition)))


def update_participant_opt_out(game_id: int, user_id: str, is_opted_out: bool):
    """Updates a participant's opt-out status for a specific game."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE game_participant SET is_opted_out = ? WHERE game_id = ? AND user_id = ?",
            (is_opted_out, game_id, user_id),
        )
        conn.commit()


def add_game_manager(game_id: int, user_id: str):
    """Assigns a user as a manager for a game."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO game_manager (game_id, user_id) VALUES (?, ?)",
            (game_id, user_id),
        )
        conn.commit()


def remove_game_manager(game_id: int, user_id: str):
    """Removes a user as a manager for a game."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM game_manager WHERE game_id = ? AND user_id = ?",
            (game_id, user_id),
        )
        conn.commit()


def list_game_manager(game_id: int):
    """Lists all managers for a game."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        rows = cursor.execute(
            "SELECT user_id FROM game_manager WHERE game_id = ?", (game_id,)
        ).fetchall()
        return [row["user_id"] for row in rows]


def get_game_mgr_active_game(user_id: str) -> int | None:
    """Get the active game the game manager is manging, if exists"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        row = cursor.execute(
            "SELECT game_id FROM game_manager gm "
            "LEFT JOIN game ON gm.game_id = game.id "
            "WHERE gm.user_id = ? AND (game.status IS NULL OR game.status = 'ACTIVE' OR game.status = 'PENDING')",
            (user_id,),
        ).fetchone()
        return row["game_id"] if row else None


def game_exists_in_thread(channel_id: str, thread_ts: str) -> bool:
    """Checks if there are any game in the thread regardless of status"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        row = cursor.execute(
            "SELECT 1 FROM game WHERE channel_id = ? AND thread_ts = ? LIMIT 1",
            (channel_id, thread_ts),
        ).fetchone()
        return row is not None


def add_huddle_participant(huddle_id: str, user_id: str):
    """Adds a user to the list of current participants in a huddle."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO huddle_participant (huddle_id, user_id) VALUES (?, ?)",
            (huddle_id, user_id),
        )
        conn.commit()


def remove_huddle_participant(huddle_id: str, user_id: str):
    """Removes a user from the list of current participants in a huddle."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM huddle_participant WHERE huddle_id = ? AND user_id = ?",
            (huddle_id, user_id),
        )
        conn.commit()


def get_user_huddles(user_id: str) -> list[str]:
    """Gets a list of huddle IDs that a user is currently a participant in."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        rows = cursor.execute(
            "SELECT huddle_id FROM huddle_participant WHERE user_id = ?", (user_id,)
        ).fetchall()
        return [row["huddle_id"] for row in rows]


def upsert_huddle(huddle_id: str, channel_id: str, start_time: datetime):
    """
    Inserts a new huddle record or updates an existing one if its channel_id is 'UNKNOWN'.
    This handles the race condition where a user join event creates a placeholder huddle
    before the huddle creation event provides the full details.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO huddle (id, channel_id, start_time) VALUES (?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                channel_id = ?
            WHERE huddle.channel_id = 'UNKNOWN'
            """,
            (huddle_id, channel_id, start_time.isoformat(), channel_id),
        )
        conn.commit()


# === State Querying Functions ===


def has_game_manager(user_id: str) -> bool:
    """Check if a user is a manager for any active game."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        row = cursor.execute(
            """SELECT 1 FROM game_manager gm LEFT JOIN game ON gm.game_id = game.id
            WHERE gm.user_id = ? AND (game.status IS NULL OR game.status = 'ACTIVE' OR game.status = 'PENDING')""",
            (user_id,),
        ).fetchone()
        return row is not None


def is_game_manager(game_id: int, user_id: str) -> bool:
    """Checks if a user is a manager for the given game."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        row = cursor.execute(
            "SELECT 1 FROM game_manager WHERE game_id = ? AND user_id = ?",
            (game_id, user_id),
        ).fetchone()
        return row is not None


def get_active_game_in_huddle(huddle_id: str) -> int | None:
    """Finds the ID of the currently active game in a given huddle."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        row = cursor.execute(
            "SELECT id FROM game WHERE huddle_id = ? AND status = 'ACTIVE' LIMIT 1",
            (huddle_id,),
        ).fetchone()
        return row["id"] if row else None


def get_active_game_by_thread(channel_id: str, thread_ts: str) -> int | None:
    """Finds the ID of the currently active game in a given thread."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        row = cursor.execute(
            "SELECT id FROM game WHERE channel_id = ? AND thread_ts = ? AND status = 'ACTIVE' LIMIT 1",
            (channel_id, thread_ts),
        ).fetchone()
        return row["id"] if row else None


def get_active_game_by_only_thread(thread_ts: str) -> int | None:
    """Finds the ID of the currently active game in a given thread."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        row = cursor.execute(
            "SELECT id FROM game WHERE thread_ts = ? AND status = 'ACTIVE' LIMIT 1",
            (thread_ts),
        ).fetchone()
        return row["id"] if row else None


def get_channel_id_by_thread(thread_ts: str) -> str | None:
    """Finds the channel ID for a given thread."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        row = cursor.execute(
            "SELECT channel_id FROM game WHERE thread_ts = ? LIMIT 1", (thread_ts)
        ).fetchone()
        return row["channel_id"] if row else None


def get_any_game_by_thread(channel_id: str, thread_ts: str) -> int | None:
    """Finds the ID of the game in a given thread."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        row = cursor.execute(
            "SELECT id FROM game WHERE channel_id = ? AND thread_ts = ? LIMIT 1",
            (channel_id, thread_ts),
        ).fetchone()
        return row["id"] if row else None


def get_huddle_id_by_game_id(game_id: int) -> str | None:
    """Finds the huddle ID for a given game ID."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        row = cursor.execute(
            "SELECT huddle_id FROM game WHERE id = ? LIMIT 1", (game_id,)
        ).fetchone()
        return row["huddle_id"] if row else None


def get_huddle_id_by_channel(channel_id: str) -> str | None:
    """Finds the ID of the most recent huddle in a given channel."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        row = cursor.execute(
            "SELECT id FROM huddle WHERE channel_id = ? ORDER BY start_time DESC LIMIT 1",
            (channel_id,),
        ).fetchone()
        return row["id"] if row else None


def huddle_exists(huddle_id: str) -> bool:
    """Checks if a huddle with the given ID exists in the database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        row = cursor.execute(
            "SELECT 1 FROM huddle WHERE id = ?", (huddle_id,)
        ).fetchone()
        return row is not None


def get_eligible_participants(game_id: int) -> list[str]:
    """
    Gets a list of user IDs who are eligible to be selected for a turn.
    This includes users in the huddle, excluding those who have opted out, skipped twice,
    or were part of the recent turn sequence since the last completed/rejected turn.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        all_turns = cursor.execute(
            "SELECT user_id, status FROM game_turn WHERE game_id = ? ORDER BY selection_time DESC, id DESC",
            (game_id,),
        ).fetchall()

        users_to_exclude = set()
        for turn in all_turns:
            users_to_exclude.add(turn["user_id"])
            if turn["status"] in ("COMPLETED", "FAILED"):
                break

        rows = cursor.execute(
            """
            SELECT hp.user_id FROM huddle_participant AS hp
            JOIN game AS g ON hp.huddle_id = g.huddle_id
            LEFT JOIN game_participant AS gp ON hp.user_id = gp.user_id AND g.id = gp.game_id
            WHERE g.id = ? 
              AND (gp.is_opted_out IS NULL OR gp.is_opted_out = FALSE)
              AND (gp.consecutive_skips IS NULL OR gp.consecutive_skips < 2)
            """,
            (game_id,),
        ).fetchall()

        eligible_users = {row["user_id"] for row in rows}
        eligible_users.difference_update(users_to_exclude)

        return list(eligible_users)


def get_huddle_participants(game_id: int) -> list[str]:
    """
    Gets a list of user IDs who are in the huddle, even if currently not eligiable.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()

        rows = cursor.execute(
            """
            SELECT hp.user_id FROM huddle_participant AS hp
            JOIN game g ON hp.huddle_id = g.huddle_id
            LEFT JOIN game_participant gp ON hp.user_id = gp.user_id AND g.id = gp.game_id
            WHERE g.id = ?
            """,
            (game_id,),
        ).fetchall()

        eligible_users = {row["user_id"] for row in rows}

        return list(eligible_users)


def get_pending_turn_user(game_id: int) -> str | None:
    """Gets the user ID for the current pending turn in a game."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        row = cursor.execute(
            "SELECT user_id FROM game_turn WHERE game_id = ? AND status = 'PENDING' ORDER BY selection_time DESC, id DESC LIMIT 1",
            (game_id,),
        ).fetchone()
        if not row:
            return None
        return row["user_id"]


def get_in_progress_turn_user(game_id: int) -> str | None:
    """Gets the user ID for the current in-progress turn in a game."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        row = cursor.execute(
            "SELECT user_id FROM game_turn WHERE game_id = ? AND status = 'IN_PROGRESS' ORDER BY start_time DESC, id DESC LIMIT 1",
            (game_id,),
        ).fetchone()
        if not row:
            return None
        return row["user_id"]


def get_turn_by_status(game_id: int, statuses: list[str]) -> sqlite3.Row | None:
    """Gets the details for the current turn if it matches one of the given statuses."""
    if not statuses:
        return None

    with get_db_connection() as conn:
        cursor = conn.cursor()
        placeholders = ",".join("?" for _ in statuses)
        query = f"""
            SELECT user_id, status, start_time, assigned_duration_seconds, timeout_notified
            FROM game_turn
            WHERE game_id = ? AND status IN ({placeholders})
            ORDER BY selection_time DESC, id DESC 
            LIMIT 1
        """
        row = cursor.execute(query, (game_id, *statuses)).fetchone()
        return row


def get_active_turn_details(game_id: int) -> sqlite3.Row | None:
    """Gets the full details for the current active turn (PENDING or IN_PROGRESS)."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        row = cursor.execute(
            """
            SELECT user_id, status, start_time, assigned_duration_seconds 
            FROM game_turn 
            WHERE game_id = ? AND status IN ('PENDING', 'IN_PROGRESS') 
            ORDER BY selection_time DESC, id DESC 
            LIMIT 1
            """,
            (game_id,),
        ).fetchone()
        return row


def get_all_turns_by_status(statuses: list[str]) -> list[sqlite3.Row]:
    """Gets all turns that are currently in one of the given states."""
    if not statuses:
        return []
    with get_db_connection() as conn:
        cursor = conn.cursor()
        placeholders = ",".join("?" for _ in statuses)
        rows = cursor.execute(
            f"""
            SELECT
                t.game_id,
                t.user_id,
                t.selection_time,
                t.start_time,
                t.assigned_duration_seconds,
                t.timeout_notified,
                g.channel_id,
                g.thread_ts
            FROM game_turn AS t
            JOIN game AS g ON t.game_id = g.id
            WHERE t.status IN ({placeholders})
            """,
            statuses,
        ).fetchall()
        return rows


def get_game_summary_stats(game_id: int) -> list[sqlite3.Row]:
    """
    Gets summary statistics for all participants in a completed game.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        rows = cursor.execute(
            """
            SELECT
                p.user_id,
                p.successful_rounds,
                p.consecutive_skips,
                u.name
            FROM game_participant AS p
            JOIN user AS u ON p.user_id = u.slack_id
            WHERE p.game_id = ?
            ORDER BY p.successful_rounds DESC, p.consecutive_skips ASC
            """,
            (game_id,),
        ).fetchall()
        return rows


def get_all_turns_for_game(game_id: int) -> list[sqlite3.Row]:
    """Gets all turns for a specific game, ordered by selection time."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        rows = cursor.execute(
            """
            SELECT
                t.user_id,
                t.status,
                t.selection_time,
                t.start_time,
                t.assigned_duration_seconds,
                u.name
            FROM game_turn AS t
            JOIN user AS u ON t.user_id = u.slack_id
            WHERE t.game_id = ?
            ORDER BY t.selection_time ASC, t.id ASC
            """,
            (game_id,),
        ).fetchall()
        return rows


def get_game_participants_by_status(game_id: int) -> dict[str, list[str]]:
    """
    Gets all participants for a game, categorized by their opt-out status.
    Returns a dictionary with 'opted_in' and 'opted_out' lists of user IDs.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        rows = cursor.execute(
            "SELECT user_id, is_opted_out FROM game_participant WHERE game_id = ?",
            (game_id,),
        ).fetchall()

        participants = {"opted_in": [], "opted_out": []}
        for row in rows:
            if row["is_opted_out"]:
                participants["opted_out"].append(row["user_id"])
            else:
                participants["opted_in"].append(row["user_id"])
        return participants


def get_user_names(user_ids: list[str]) -> dict[str, str]:
    """Gets a mapping of user IDs to names for a given list of IDs."""
    if not user_ids:
        return {}
    with get_db_connection() as conn:
        cursor = conn.cursor()
        placeholders = ",".join("?" for _ in user_ids)
        query = f"SELECT slack_id, name FROM user WHERE slack_id IN ({placeholders})"
        rows = cursor.execute(query, user_ids).fetchall()
        return {row["slack_id"]: row["name"] for row in rows}


def has_user(user_id: str) -> bool:
    """Checks if a user exists in the database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        row = cursor.execute(
            "SELECT 1 FROM user WHERE slack_id = ?", (user_id,)
        ).fetchone()
        return row is not None


def get_game_instance[T](game_id: int, client: Client[T]) -> base.GameInstance[T]:
    """
    Query the database and return a populated GameInstance for the given game_id.
    Raises ValueError if the game does not exist.
    """
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT channel_id, thread_ts, mode, start_time FROM game WHERE id = ? LIMIT 1",
            (game_id,),
        )
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Game {game_id} not found")
        channel_id = row["channel_id"]
        thread_ts = row["thread_ts"]
        mode = row["mode"]
        start_time = arrow.get(row["start_time"])

        cur.execute(
            "SELECT id, user_id, status, start_time, assigned_duration_seconds "
            "FROM game_turn WHERE game_id = ? ORDER BY selection_time ASC, id ASC",
            (game_id,),
        )
        turn_rows = cur.fetchall()

    client_secret, server_secret = get_latest_secrets(game_id) or ("", "")
    managers = list_game_manager(game_id) or []
    participants = get_huddle_participants(game_id) or []

    turns: list[base.Turns] = []
    for r in turn_rows:
        start_val = r["start_time"]
        user_id = r["user_id"]
        seq_id = r["id"]
        status = r["status"]
        duration = r["assigned_duration_seconds"]

        start_ts: float | None = None
        if start_val:
            try:
                start_ts = (
                    datetime.fromisoformat(start_val)
                    .replace(tzinfo=timezone.utc)
                    .timestamp()
                )
            except Exception:
                start_ts = None

        turns.append(
            base.Turns(
                used_id=user_id,
                seq_id=seq_id,
                status=status,
                time_start=start_ts,
                duration=duration,
            )
        )

    return base.GameInstance(
        game_id=game_id,
        client_secret=client_secret,
        server_secret=server_secret,
        channel_id=channel_id,
        thread_ts=thread_ts,
        turns=turns,
        managers=managers,
        participants=participants,
        mode=mode,
        start_time=start_time,
        client=client,
    )


def add_game_participant(game_id: int, user_id: str, ticket_count: int):
    """Adds a user to a game's participant list. Update proper field when e.g. the user don't start with having a project."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO game_participant (game_id, user_id, ticket_count) VALUES (?, ?, ?)
            ON CONFLICT(game_id, user_id) DO UPDATE SET
                ticket_count = excluded.ticket_count
            """,
            (game_id, user_id, ticket_count),
        )
        conn.commit()


def get_participant_ticket_count(game_id: int, user_id: str) -> int | None:
    """Return ticket_count for a given participant in a game, or None if not present."""
    with get_db_connection() as conn:
        cur = conn.cursor()
        row = cur.execute(
            "SELECT ticket_count FROM game_participant WHERE game_id = ? AND user_id = ? LIMIT 1",
            (game_id, user_id),
        ).fetchone()
        return row["ticket_count"] if row else None


def get_all_participant_ticket_counts(game_id: int) -> dict[str, int]:
    """Return mapping user_id -> ticket_count for all participants in a game."""
    with get_db_connection() as conn:
        cur = conn.cursor()
        rows = cur.execute(
            "SELECT user_id, ticket_count FROM game_participant WHERE game_id = ?",
            (game_id,),
        ).fetchall()
        return {r["user_id"]: (r["ticket_count"] or 0) for r in rows}


if __name__ == "__main__":
    init_db()
