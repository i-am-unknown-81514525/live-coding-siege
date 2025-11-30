CREATE TABLE IF NOT EXISTS "link" (
    "user_id" TEXT NOT NULL,
    "game_id" INT NOT NULL,
    "start_hours" REAL NOT NULL,
    PRIMARY KEY(user_id, game_id)
);