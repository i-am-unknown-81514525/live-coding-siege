CREATE TABLE IF NOT EXISTS proj_record(
    proj_id INT not null,
    measurement_time DATETIME not null DEFAULT CURRENT_TIMESTAMP,
    title TEXT not null,
    description TEXT not null,
    user_id INT not null,
    hours FLOAT not null,
    repo_url TEXT null,
    demo_url TEXT null,
    proj_status TEXT NOT NULL
);