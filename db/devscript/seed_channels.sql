-- Seed 1–2 known karaoke-friendly VTuber channels for manual Phase 2 testing.
-- Not a Flyway migration: run manually after migrations (see README).
--
-- Usage (Compose/Dev Container DB published on localhost:5432):
--   psql "postgresql://vks_db_user:vks_db_pwd@localhost:5432/vks_db" \
--     -f db/devscript/seed_channels.sql
--
-- Or from inside the db container:
--   docker compose -f .devcontainer/docker-compose.yml exec -T db \
--     psql -U vks_db_user -d vks_db < db/devscript/seed_channels.sql

INSERT INTO channels (id, name, url, thumbnail_url, raw_data)
VALUES
    (
        'UC5CwaMl1eIgY8h02uZw7u8A',
        'Suisei Channel',
        'https://www.youtube.com/channel/UC5CwaMl1eIgY8h02uZw7u8A/videos',
        NULL,
        NULL
    ),
    (
        'UCCzUftOSwRqkmn4C2LQLZLg',
        'Marine Ch. 宝鐘マリン',
        'https://www.youtube.com/channel/UCCzUftOSwRqkmn4C2LQLZLg/videos',
        NULL,
        NULL
    )
ON CONFLICT (id) DO UPDATE
SET
    name = EXCLUDED.name,
    url = EXCLUDED.url,
    updated_at = CURRENT_TIMESTAMP;
