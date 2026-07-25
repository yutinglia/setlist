-- Flat channel extracts omit upload_date. Preserve their playlist position so
-- recent archives are still analyzed and displayed before older backfill rows.
ALTER TABLE videos
    ADD COLUMN playlist_position INTEGER;

ALTER TABLE videos
    ADD CONSTRAINT ck_videos_playlist_position_positive
    CHECK (playlist_position IS NULL OR playlist_position >= 1);

DROP INDEX idx_videos_analysis_queue;
CREATE INDEX idx_videos_analysis_queue
    ON videos (
        analysis_status,
        next_analysis_at,
        upload_date DESC,
        playlist_position,
        id
    )
    WHERE type = 'karaoke';

