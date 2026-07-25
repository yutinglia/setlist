-- Paced full-catalog video backfill for newly added channels.
-- Existing channels default to done (recent-only refresh stays unchanged).
ALTER TABLE channels
    ADD COLUMN video_backfill_status VARCHAR(20) NOT NULL DEFAULT 'done',
    ADD COLUMN video_backfill_offset INTEGER NOT NULL DEFAULT 1,
    ADD COLUMN video_backfill_updated_at TIMESTAMP;

ALTER TABLE channels
    ADD CONSTRAINT chk_channels_video_backfill_status
    CHECK (video_backfill_status IN ('pending', 'running', 'done', 'failed'));

ALTER TABLE channels
    ADD CONSTRAINT chk_channels_video_backfill_offset
    CHECK (video_backfill_offset >= 1);
