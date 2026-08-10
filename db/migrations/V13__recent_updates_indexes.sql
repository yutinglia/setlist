-- Support the fixed-size public recent-updates feed without sorting the full
-- channel and song catalogs on every cache miss.
CREATE INDEX idx_channels_recent_updates
    ON channels (updated_at DESC NULLS LAST, id);

CREATE INDEX idx_songs_recent_updates
    ON songs (updated_at DESC NULLS LAST, id DESC);
