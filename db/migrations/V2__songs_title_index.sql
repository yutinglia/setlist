-- Speed up song title search (ILIKE '%q%') via trigram GIN index.
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX idx_songs_title_trgm ON songs USING gin (title gin_trgm_ops);
