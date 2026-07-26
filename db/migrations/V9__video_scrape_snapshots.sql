-- Keep channel-list and full-video extractor observations separate. This
-- prevents a sparse flat refresh from erasing richer metadata and records when
-- each source was last observed.
ALTER TABLE videos
    ADD COLUMN metadata_raw_data JSONB,
    ADD COLUMN list_scraped_at TIMESTAMP,
    ADD COLUMN metadata_scraped_at TIMESTAMP;

UPDATE videos
SET
    metadata_raw_data = raw_data,
    list_scraped_at = updated_at,
    metadata_scraped_at = updated_at
WHERE raw_data IS NOT NULL
  AND list_scraped_at IS NULL;
