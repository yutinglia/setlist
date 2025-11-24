-- Create channels table
CREATE TABLE channels (
    id VARCHAR(255) PRIMARY KEY,
    name VARCHAR(500) NOT NULL,
    url VARCHAR(500) NOT NULL,
    thumbnail_url VARCHAR(500),
    raw_data JSONB,
    -- Edit tracking fields
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
-- Create videos table
CREATE TABLE videos (
    id VARCHAR(255) PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    url VARCHAR(500) NOT NULL,
    upload_date VARCHAR(50),
    type VARCHAR(50),
    channel_id VARCHAR(255) NOT NULL,
    raw_data JSONB,
    -- Comment fields
    comments_raw_data JSONB,
    -- Analysis fields
    analyze_attempts INTEGER DEFAULT 0,
    last_analyzed_at TIMESTAMP,
    has_song_list_comment BOOLEAN DEFAULT FALSE,
    song_list_comment_raw_data JSONB,
    -- LLM comment cleaning fields
    cleaning_attempts INTEGER DEFAULT 0,
    last_cleaned_at TIMESTAMP,
    cleaned_song_list_comment JSONB,
    -- Edit tracking fields
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_videos_channel FOREIGN KEY (channel_id) REFERENCES channels(id) ON DELETE CASCADE
);
-- Create songs table
CREATE TABLE songs (
    id SERIAL PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    timestamp VARCHAR(50),
    video_id VARCHAR(255) NOT NULL,
    analyzed_by_llm BOOLEAN DEFAULT FALSE,
    -- Edit tracking fields
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_songs_video FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
);
