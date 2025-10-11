
CREATE TABLE IF NOT EXISTS "user" (
    "slack_id" TEXT PRIMARY KEY,
    "name" TEXT NOT NULL,
);

CREATE TABLE IF NOT EXISTS "huddle" (
    "id" TEXT PRIMARY KEY,
    "channel_id" TEXT NOT NULL,
    "start_time" DATETIME NOT NULL,
    "end_time" DATETIME
);

CREATE TABLE IF NOT EXISTS "game" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
    "huddle_id" TEXT NOT NULL,
    "start_time" DATETIME NOT NULL,
    "end_time" DATETIME,
    "status" TEXT NOT NULL CHECK("status" IN ('PENDING', 'ACTIVE', 'COMPLETED', 'CANCELLED')),
    FOREIGN KEY("huddle_id") REFERENCES "huddle"("id")
);


CREATE TABLE IF NOT EXISTS "game_turn" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
    "game_id" INTEGER NOT NULL,
    "user_id" TEXT NOT NULL,
    "selection_time" DATETIME NOT NULL,
    "assigned_duration_seconds" INTEGER NOT NULL,
    "status" TEXT NOT NULL CHECK("status" IN ('PENDING', 'SKIPPED', 'COMPLETED', 'FAILED')),
    FOREIGN KEY("game_id") REFERENCES "game"("id"),
    FOREIGN KEY("user_id") REFERENCES "user"("slack_id")
);

CREATE TABLE IF NOT EXISTS "game_manager" (
    "game_id" INTEGER NOT NULL,
    "user_id" TEXT NOT NULL,
    PRIMARY KEY ("game_id", "user_id"),
    FOREIGN KEY("game_id") REFERENCES "game"("id"),
    FOREIGN KEY("user_id") REFERENCES "user"("slack_id")
);

-- Tracks users participating in a game and their opt-out status for that game.
CREATE TABLE IF NOT EXISTS "game_participant" (
    "game_id" INTEGER NOT NULL,
    "user_id" TEXT NOT NULL,
    "is_opted_out" BOOLEAN NOT NULL DEFAULT FALSE,
    "successful_rounds" INTEGER NOT NULL DEFAULT 0,
    "consecutive_skips" INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY ("game_id", "user_id"),
    FOREIGN KEY("game_id") REFERENCES "game"("id"),
    FOREIGN KEY("user_id") REFERENCES "user"("slack_id")
);
CREATE TABLE IF NOT EXISTS "event_transaction" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT,    
    "transaction_hash" TEXT NOT NULL UNIQUE, -- The hash of the current transaction's data of the game
    "previous_transaction_hash" TEXT, -- The hash of the parent transaction of the game, forming a chain. NULL for the first event in a game.
    "timestamp" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "event_type" TEXT NOT NULL, -- e.g., 'HUDDLE_START', 'GAME_START', 'USER_SELECTED', 'COIN_AWARDED', 'MSG_SENT', 'SERVER_SECRET_UPDATE', 'SERVER_SECRET_REVEAL'
    "game_id" INTEGER NOT NULL, -- A transaction chain is scoped to a single game
    "user_id" TEXT,
    "details" TEXT,
    "client_secret" TEXT NOT NULL,
    "server_secret" TEXT NOT NULL,
    FOREIGN KEY("previous_transaction_hash") REFERENCES "event_transaction"("transaction_hash"),
    FOREIGN KEY("game_id") REFERENCES "game"("id"),
    FOREIGN KEY("user_id") REFERENCES "user"("slack_id")
);
