-- Backfill nullable legacy defaults before enforcing application invariants.
UPDATE videos SET analyze_attempts = 0 WHERE analyze_attempts IS NULL;
UPDATE videos SET cleaning_attempts = 0 WHERE cleaning_attempts IS NULL;
UPDATE videos SET has_song_list_comment = FALSE WHERE has_song_list_comment IS NULL;
UPDATE songs SET analyzed_by_llm = FALSE WHERE analyzed_by_llm IS NULL;

-- Flat yt-dlp rows often have a Unix timestamp but no upload_date column.
UPDATE videos
SET upload_date = to_char(
    to_timestamp((raw_data ->> 'timestamp')::double precision) AT TIME ZONE 'UTC',
    'YYYYMMDD'
)
WHERE upload_date IS NULL
  AND jsonb_typeof(raw_data -> 'timestamp') = 'number'
  AND (raw_data ->> 'timestamp')::double precision > 0;

UPDATE videos
SET upload_date = to_char(
    to_timestamp((raw_data ->> 'release_timestamp')::double precision)
        AT TIME ZONE 'UTC',
    'YYYYMMDD'
)
WHERE upload_date IS NULL
  AND jsonb_typeof(raw_data -> 'release_timestamp') = 'number'
  AND (raw_data ->> 'release_timestamp')::double precision > 0;

ALTER TABLE videos
    ALTER COLUMN analyze_attempts SET DEFAULT 0,
    ALTER COLUMN analyze_attempts SET NOT NULL,
    ALTER COLUMN cleaning_attempts SET DEFAULT 0,
    ALTER COLUMN cleaning_attempts SET NOT NULL,
    ALTER COLUMN has_song_list_comment SET DEFAULT FALSE,
    ALTER COLUMN has_song_list_comment SET NOT NULL;

ALTER TABLE songs
    ALTER COLUMN analyzed_by_llm SET DEFAULT FALSE,
    ALTER COLUMN analyzed_by_llm SET NOT NULL;

ALTER TABLE videos
    ADD CONSTRAINT ck_videos_analyze_attempts_nonnegative
        CHECK (analyze_attempts >= 0),
    ADD CONSTRAINT ck_videos_cleaning_attempts_nonnegative
        CHECK (cleaning_attempts >= 0);

CREATE INDEX idx_videos_channel_upload_date
    ON videos (channel_id, upload_date DESC NULLS LAST, id);
CREATE INDEX idx_videos_channel_analysis
    ON videos (channel_id, type, has_song_list_comment, analyze_attempts);
CREATE INDEX idx_songs_video_id_id
    ON songs (video_id, id);
