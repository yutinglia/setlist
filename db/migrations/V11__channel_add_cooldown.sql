-- Pace administrator-triggered channel resolution across processes and restarts.
-- This is distinct from the longer YouTube block cooldown: it only guards
-- channel-add requests and bulk-add items.
ALTER TABLE scraper_state
    ADD COLUMN channel_add_cooldown_until TIMESTAMP;
