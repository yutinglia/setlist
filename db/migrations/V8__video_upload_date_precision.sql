-- Channel-tab list dates come from YouTube relative time text and are
-- approximate. Track that fact so the API does not present them as exact and
-- so later full metadata can upgrade, but never downgrade, the stored date.
ALTER TABLE videos
    ADD COLUMN upload_date_precision VARCHAR(20);

UPDATE videos
SET upload_date_precision = CASE
    WHEN upload_date IS NULL THEN NULL
    WHEN raw_data ? 'upload_date' THEN 'exact'
    WHEN raw_data ? 'timestamp' OR raw_data ? 'release_timestamp'
        THEN 'approximate'
    ELSE 'exact'
END;

ALTER TABLE videos
    ADD CONSTRAINT ck_videos_upload_date_precision
    CHECK (
        (upload_date IS NULL AND upload_date_precision IS NULL)
        OR (
            upload_date IS NOT NULL
            AND upload_date_precision IN ('exact', 'approximate')
        )
    );
