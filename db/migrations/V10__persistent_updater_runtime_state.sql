-- Keep enough updater lifecycle state to distinguish a healthy idle worker
-- from one that died or stalled mid-cycle. The row remains the singleton
-- created by V7, alongside the process-independent YouTube cooldown.
ALTER TABLE scraper_state
    ADD COLUMN updater_cycle_started_at TIMESTAMP,
    ADD COLUMN updater_cycle_finished_at TIMESTAMP,
    ADD COLUMN updater_last_success_at TIMESTAMP,
    ADD COLUMN updater_heartbeat_at TIMESTAMP,
    ADD COLUMN updater_outcome VARCHAR(20) NOT NULL DEFAULT 'never',
    ADD COLUMN updater_owner_id VARCHAR(255),
    ADD CONSTRAINT chk_scraper_state_updater_outcome CHECK (
        updater_outcome IN (
            'never',
            'running',
            'success',
            'cooldown',
            'error',
            'cancelled'
        )
    );
