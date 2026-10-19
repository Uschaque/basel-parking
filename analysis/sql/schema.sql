CREATE TABLE observations (
    published_utc TEXT NOT NULL,
    garage_id TEXT NOT NULL,
    name TEXT,
    address TEXT,
    free INTEGER NOT NULL CHECK (free >= 0),
    total INTEGER NOT NULL CHECK (total > 0),
    published_local TEXT NOT NULL,
    weekday INTEGER NOT NULL CHECK (weekday BETWEEN 0 AND 6),
    hour INTEGER NOT NULL CHECK (hour BETWEEN 0 AND 23),
    local_date TEXT NOT NULL,
    free_ratio REAL NOT NULL CHECK (free_ratio BETWEEN 0 AND 1),
    PRIMARY KEY (garage_id, published_utc)
);

CREATE INDEX idx_observations_slot
    ON observations (garage_id, weekday, hour);
