-- Persist scheduling state so process restarts and APP_ENV do not change cadence.
ALTER TABLE channels
    ADD COLUMN last_video_scan_at TIMESTAMP,
    ADD COLUMN next_video_scan_at TIMESTAMP,
    ADD COLUMN video_scan_failures INTEGER NOT NULL DEFAULT 0;

ALTER TABLE channels
    ADD CONSTRAINT ck_channels_video_scan_failures_nonnegative
    CHECK (video_scan_failures >= 0);

-- Explicit analysis state prevents a successful "no setlist" scrape from being
-- retried immediately on every worker tick. Fresh VODs can still be rechecked
-- later because comments/setlists often arrive after the archive is published.
ALTER TABLE videos
    ADD COLUMN analysis_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    ADD COLUMN next_analysis_at TIMESTAMP;

UPDATE videos
SET analysis_status = CASE
    WHEN type <> 'karaoke' OR type IS NULL THEN 'skipped'
    WHEN has_song_list_comment THEN 'done'
    WHEN analyze_attempts >= 3 THEN 'exhausted'
    ELSE 'pending'
END;

ALTER TABLE videos
    ADD CONSTRAINT ck_videos_analysis_status
    CHECK (
        analysis_status IN (
            'pending',
            'retry',
            'no_setlist',
            'done',
            'exhausted',
            'skipped'
        )
    );

CREATE INDEX idx_channels_discovery_due
    ON channels (video_backfill_status, next_video_scan_at, video_backfill_updated_at);

CREATE INDEX idx_videos_analysis_queue
    ON videos (analysis_status, next_analysis_at, upload_date DESC, id)
    WHERE type = 'karaoke';

