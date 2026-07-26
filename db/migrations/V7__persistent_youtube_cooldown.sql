-- A process restart must not erase a YouTube block cooldown and immediately
-- retry the same IP. This table intentionally has exactly one row.
CREATE TABLE scraper_state (
    id SMALLINT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    youtube_cooldown_until TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO scraper_state (id) VALUES (1);

