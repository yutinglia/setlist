-- Preserve administrator channel-add intent while YouTube access is cooling
-- down. Resolution remains paced and serialized by the background updater.
CREATE TABLE channel_ingest_queue (
    id BIGSERIAL PRIMARY KEY,
    channel_url VARCHAR(500) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    channel_id VARCHAR(255),
    error_message VARCHAR(500),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    CONSTRAINT chk_channel_ingest_queue_status
        CHECK (status IN ('pending', 'completed', 'failed')),
    CONSTRAINT chk_channel_ingest_queue_attempts_nonnegative
        CHECK (attempts >= 0),
    CONSTRAINT fk_channel_ingest_queue_channel
        FOREIGN KEY (channel_id) REFERENCES channels(id) ON DELETE SET NULL
);

CREATE INDEX idx_channel_ingest_queue_pending_fifo
    ON channel_ingest_queue (created_at, id)
    WHERE status = 'pending';

CREATE UNIQUE INDEX uq_channel_ingest_queue_pending_url
    ON channel_ingest_queue (channel_url)
    WHERE status = 'pending';
