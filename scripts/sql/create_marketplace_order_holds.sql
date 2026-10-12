-- Additive operator review and notice deduplication. Test on an isolated DB first.
-- Production DDL requires separate approval; not executed by this task.
CREATE TABLE IF NOT EXISTS nanami_products.marketplace_order_holds (
    provider TEXT NOT NULL,
    order_code TEXT NOT NULL,
    reason TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'held' CHECK (status IN ('held', 'resolved')),
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    notification_status TEXT NOT NULL DEFAULT 'pending' CHECK (notification_status IN ('pending', 'sent')),
    notification_attempts INTEGER NOT NULL DEFAULT 0,
    last_notification_at TIMESTAMPTZ,
    PRIMARY KEY (provider, order_code)
)
;
ALTER TABLE nanami_products.marketplace_order_holds
    ADD COLUMN IF NOT EXISTS candidate JSONB,
    ADD COLUMN IF NOT EXISTS review_version BIGINT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS review_history JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS approved_version BIGINT,
    ADD COLUMN IF NOT EXISTS approved_at TIMESTAMPTZ
;
CREATE TABLE IF NOT EXISTS nanami_products.marketplace_processed_notices (
    provider TEXT NOT NULL,
    order_code TEXT NOT NULL,
    notice_fingerprint TEXT NOT NULL,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (provider, order_code, notice_fingerprint)
);
