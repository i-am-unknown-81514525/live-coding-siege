CREATE TABLE IF NOT EXISTS proj_record(
    proj_id INT not null,
    measuremen_time DATETIME not null DEFAULT CURRENT_TIMESTAMP,
    week_num INT not null,
    title TEXT not null,
    description TEXT not null,
    user_id INT not null,
    hours FLOAT not null,
    repo_url TEXT null,
    demo_url TEXT null,
    proj_status TEXT NOT NULL,
    PRIMARY KEY (proj_id, measuremen_time)
);

CREATE TABLE IF NOT EXISTS user_record(
    user_id INT not null,
    measurement_time DATETIME not null DEFAULT CURRENT_TIMESTAMP,
    coin_count INT not null,
    user_status TEXT not null,
);