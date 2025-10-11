import sqlite3
import os
from contextlib import contextmanager
import json
from datetime import datetime
from cryptography.hazmat.primitives.hashes import Hash, SHA3_512

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "live_coding.db")
SCHEMA_FILE = os.path.join(BASE_DIR, "schema.sql")

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
        with open(SCHEMA_FILE, 'r') as f:
            schema_sql = f.read()
        
        cursor = conn.cursor()
        cursor.executescript(schema_sql)
        conn.commit()
    print("Database initialized successfully.")

def _sha3(text: str) -> str:
    hash_obj = Hash(SHA3_512())
    hash_obj.update(text.encode('utf-8'))
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
        (game_id,)
    ).fetchone()
    return row['transaction_hash'] if row else None

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
    timestamp = datetime.utcnow().isoformat()

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
        (new_hash, prev_hash, timestamp, event_type, game_id, user_id, details_json, client_secret, server_secret)
    )
    return new_hash

def start_game(huddle_id: str, start_time: datetime, client_secret: str, server_secret: str) -> int:
    """Creates a new game and its initial 'GAME_START' transaction."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        row = cursor.execute(
            "INSERT INTO game (huddle_id, start_time, status) VALUES (?, ?, 'ACTIVE') RETURNING id",
            (huddle_id, start_time.isoformat())
        ).fetchone()
        if not row:
            # This case should not be reached if the insert is successful and RETURNING is supported.
            raise RuntimeError("Failed to create a new game record.")
        game_id = row['id']
        _add_transaction(conn, game_id, "GAME_START", client_secret, server_secret)
        conn.commit()
        return game_id

def add_message_transaction(
    game_id: int,
    user_id: str,
    message_text: str,
) -> str:
    """
    Adds a 'MSG_SENT' transaction.
    """
    with get_db_connection() as conn:
        secrets = get_latest_secrets(game_id)
        if not secrets:
            raise ValueError(f"Cannot add message to game {game_id} with no existing transactions.")
        old_client_secret, server_secret = secrets
        new_client_secret = _sha3(f"{old_client_secret}{message_text}")
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
            raise ValueError(f"Cannot select user for game {game_id} with no existing transactions.")
        client_secret, server_secret = secrets

        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO game_turn (game_id, user_id, selection_time, assigned_duration_seconds, status) VALUES (?, ?, ?, ?, 'PENDING')",
            (game_id, user_id, datetime.utcnow().isoformat(), duration_seconds)
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
    status: str, # Should be 'COMPLETED' or 'CANCELLED'
) -> str:
    """Updates a game's status and logs the event as a transaction."""
    with get_db_connection() as conn:
        secrets = get_latest_secrets(game_id)
        if not secrets:
            raise ValueError(f"Cannot update status for game {game_id} with no existing transactions.")
        client_secret, server_secret = secrets

        cursor = conn.cursor()
        cursor.execute(
            "UPDATE game SET status = ?, end_time = ? WHERE id = ?",
            (status, datetime.utcnow().isoformat(), game_id)
        )
        event_type = f"GAME_{status.upper()}" # e.g., GAME_COMPLETED
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

def update_turn_status(
    game_id: int,
    user_id: str,
    new_status: str, # 'COMPLETED', 'SKIPPED', or 'FAILED'
) -> str:
    """Updates a turn's status and participant stats, logging the transaction."""
    with get_db_connection() as conn:
        secrets = get_latest_secrets(game_id)
        if not secrets:
            raise ValueError(f"Cannot update turn for game {game_id} with no existing transactions.")
        client_secret, server_secret = secrets

        cursor = conn.cursor()
        # Update the turn status itself
        cursor.execute(
            "UPDATE game_turn SET status = ? WHERE game_id = ? AND user_id = ? AND status = 'PENDING'",
            (new_status, game_id, user_id)
        )

        # Update participant stats based on the outcome
        if new_status == 'COMPLETED':
            cursor.execute("UPDATE game_participant SET successful_rounds = successful_rounds + 1, consecutive_skips = 0 WHERE game_id = ? AND user_id = ?", (game_id, user_id))
        elif new_status == 'SKIPPED':
            cursor.execute("UPDATE game_participant SET consecutive_skips = consecutive_skips + 1 WHERE game_id = ? AND user_id = ?", (game_id, user_id))

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
            (game_id,)
        ).fetchone()
        if not row:
            return None
        return (row['client_secret'], row['server_secret'])

def update_server_secret(
    game_id: int,
    new_server_secret: str,
) -> str:
    """Updates the server secret and logs a 'SERVER_SECRET_UPDATE' transaction."""
    with get_db_connection() as conn:
        secrets = get_latest_secrets(game_id)
        if not secrets:
            raise ValueError(f"Cannot update server secret for game {game_id} with no existing transactions.")
        client_secret, _old_server_secret = secrets

        new_hash = _add_transaction(
            conn,
            game_id=game_id,
            event_type="SERVER_SECRET_UPDATE",
            # The client secret is passed through unchanged, as per the rules.
            client_secret=client_secret,
            # The new server secret is recorded.
            server_secret=new_server_secret,
            details={"new_server_secret": new_server_secret}, # Log the new secret for audit purposes
        )
        conn.commit()
        return new_hash


def upsert_user(user_id: str, name: str):
    """Adds a new user or updates their name if they already exist."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO user (slack_id, name) VALUES (?, ?)
            ON CONFLICT(slack_id) DO UPDATE SET name = excluded.name
            """,
            (user_id, name)
        )
        conn.commit()

def add_game_participant(game_id: int, user_id: str):
    """Adds a user to a game's participant list. Does nothing if they already exist."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO game_participant (game_id, user_id) VALUES (?, ?)",
            (game_id, user_id)
        )
        conn.commit()

def update_participant_opt_out(game_id: int, user_id: str, is_opted_out: bool):
    """Updates a participant's opt-out status for a specific game."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE game_participant SET is_opted_out = ? WHERE game_id = ? AND user_id = ?",
            (is_opted_out, game_id, user_id)
        )
        conn.commit()

def add_game_manager(game_id: int, user_id: str):
    """Assigns a user as a manager for a game."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO game_manager (game_id, user_id) VALUES (?, ?)",
            (game_id, user_id)
        )
        conn.commit()

def add_huddle_participant(huddle_id: str, user_id: str):
    """Adds a user to the list of current participants in a huddle."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO huddle_participant (huddle_id, user_id) VALUES (?, ?)",
            (huddle_id, user_id)
        )
        conn.commit()

def remove_huddle_participant(huddle_id: str, user_id: str):
    """Removes a user from the list of current participants in a huddle."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM huddle_participant WHERE huddle_id = ? AND user_id = ?",
            (huddle_id, user_id)
        )
        conn.commit()


# === State Querying Functions ===

def get_active_game_in_huddle(huddle_id: str) -> int | None:
    """Finds the ID of the currently active game in a given huddle."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        row = cursor.execute(
            "SELECT id FROM game WHERE huddle_id = ? AND status = 'ACTIVE' LIMIT 1",
            (huddle_id,)
        ).fetchone()
        return row['id'] if row else None

def get_huddle_id_by_channel(channel_id: str) -> str | None:
    """Finds the ID of the most recent huddle in a given channel."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        row = cursor.execute(
            "SELECT id FROM huddle WHERE channel_id = ? ORDER BY start_time DESC LIMIT 1",
            (channel_id,)
        ).fetchone()
        return row['id'] if row else None

def is_game_manager(game_id: int, user_id: str) -> bool:
    """Checks if a user is a manager for the given game."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        row = cursor.execute(
            "SELECT 1 FROM game_manager WHERE game_id = ? AND user_id = ?",
            (game_id, user_id)
        ).fetchone()
        return row is not None

def get_game_latest_transaction_hash(game_id: int) -> str | None:
    """Retrieves the hash of the most recent transaction for a given game."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        row = cursor.execute(
            """
            SELECT transaction_hash FROM event_transaction
            WHERE game_id = ? ORDER BY timestamp DESC, id DESC LIMIT 1
            """,
            (game_id,)
        ).fetchone()
        return row['transaction_hash'] if row else None


def get_eligible_participants(game_id: int) -> list[str]:
    """
    Gets a list of user IDs who are eligible to be selected for a turn.
    This includes users currently in the huddle, excluding those who have opted out of the game,
    skipped twice, or were the last participant.
    """
    with get_db_connection() as conn:
        # Get the last user to have a turn in this game
        cursor = conn.cursor()

        last_participant_row = cursor.execute(
            "SELECT user_id FROM game_turn WHERE game_id = ? ORDER BY selection_time DESC, id DESC LIMIT 1",
            (game_id,)
        ).fetchone()
        last_participant_id = last_participant_row['user_id'] if last_participant_row else None

        # Get all users in the huddle who are eligible for this specific game
        rows = cursor.execute(
            """
            SELECT hp.user_id FROM huddle_participant AS hp
            JOIN game g ON hp.huddle_id = g.huddle_id
            LEFT JOIN game_participant gp ON hp.user_id = gp.user_id AND g.id = gp.game_id
            WHERE g.id = ?
              AND (gp.is_opted_out IS NULL OR gp.is_opted_out = FALSE)
              AND (gp.consecutive_skips IS NULL OR gp.consecutive_skips < 2)
            """,
            (game_id,)
        ).fetchall()
        
        eligible_users = {row['user_id'] for row in rows}
        # Exclude the last person who had a turn
        if last_participant_id:
            eligible_users.discard(last_participant_id)
        
        return list(eligible_users)

if __name__ == "__main__":
    init_db()