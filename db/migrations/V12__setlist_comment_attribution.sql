-- Promote the selected setlist comment's attribution out of the raw yt-dlp
-- snapshot. The JSONB payload remains the source observation; these nullable
-- columns make public attribution and contributor aggregation explicit.
ALTER TABLE videos
    ADD COLUMN setlist_comment_author VARCHAR(255),
    ADD COLUMN setlist_comment_author_id VARCHAR(255),
    ADD COLUMN setlist_comment_id VARCHAR(255);

UPDATE videos
SET
    setlist_comment_author = NULLIF(
        LEFT(BTRIM(song_list_comment_raw_data->>'author'), 255),
        ''
    ),
    setlist_comment_author_id = NULLIF(
        LEFT(BTRIM(song_list_comment_raw_data->>'author_id'), 255),
        ''
    ),
    setlist_comment_id = NULLIF(
        LEFT(BTRIM(song_list_comment_raw_data->>'id'), 255),
        ''
    )
WHERE jsonb_typeof(song_list_comment_raw_data) = 'object';

CREATE INDEX idx_videos_setlist_comment_author
    ON videos (setlist_comment_author_id)
    WHERE setlist_comment_author_id IS NOT NULL
      AND has_song_list_comment;
