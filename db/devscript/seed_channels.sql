-- Seed karaoke-friendly VTuber channels for manual Phase 2 testing.
-- Not a Flyway migration: run manually after migrations (see README).
--
-- Usage (works whether the dev DB is reached through Compose or Dev Container):
--   docker compose -f docker-compose.dev.yml exec -T db \
--     psql -U vks_db_user -d vks_db < db/devscript/seed_channels.sql

INSERT INTO channels (id, name, url, thumbnail_url, raw_data)
VALUES
    (
        'UCNskpCCH661BeRJkN8n8d-A',
        'UTANO ch. 白玖ウタノ',
        'https://www.youtube.com/channel/UCNskpCCH661BeRJkN8n8d-A/videos',
        NULL,
        NULL
    ),
    (
        'UCBC7vYFNQoGPupe5NxPG4Bw',
        'QuonTama Ch. 久遠たま',
        'https://www.youtube.com/channel/UCBC7vYFNQoGPupe5NxPG4Bw/videos',
        NULL,
        NULL
    ),
    (
        'UCB1s_IdO-r0nUkY2mXeti-A',
        '獅子神レオナ/レオナちゃんねる',
        'https://www.youtube.com/channel/UCB1s_IdO-r0nUkY2mXeti-A/videos',
        NULL,
        NULL
    )
ON CONFLICT (id) DO UPDATE
SET
    name = EXCLUDED.name,
    url = EXCLUDED.url,
    updated_at = CURRENT_TIMESTAMP;
