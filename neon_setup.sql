CREATE SCHEMA IF NOT EXISTS nanami_products;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS nanami_products.redemptions (
  order_code TEXT PRIMARY KEY,
  email TEXT,
  buyer_name TEXT,
  token TEXT UNIQUE NOT NULL,
  used_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS nanami_products.charts (
  token TEXT PRIMARY KEY,
  order_code TEXT,
  buyer_name TEXT,
  birth_date TEXT NOT NULL,
  birth_time TEXT,
  birth_place TEXT,
  options JSONB,
  yaml_text TEXT NOT NULL,
  prompt_text TEXT NOT NULL,
  share_yaml_text TEXT,
  horoscope_svg TEXT,
  shichusuimei_svg TEXT,
  expires_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS nanami_products.stores_orders (
  stores_order_no TEXT PRIMARY KEY,
  provider TEXT,
  product_type TEXT,
  amount INTEGER,
  payment_status TEXT DEFAULT 'paid',
  mail_subject TEXT,
  raw_message_id TEXT,
  mail_received_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS nanami_products.addon_redemptions (
  order_code TEXT NOT NULL,
  addon_type TEXT NOT NULL,
  used_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (order_code, addon_type)
);

CREATE TABLE IF NOT EXISTS nanami_products.transit_addon_links (
  token TEXT PRIMARY KEY,
  yaml_text TEXT NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS nanami_products.mundane_posts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title TEXT NOT NULL,
  slug TEXT NOT NULL UNIQUE,
  target_year INTEGER NOT NULL,
  target_month INTEGER NOT NULL,
  summary TEXT,
  yaml_content TEXT NOT NULL,
  body_markdown TEXT,
  status TEXT NOT NULL DEFAULT 'draft',
  published_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS nanami_products.api_keys (
  id BIGSERIAL PRIMARY KEY,
  key_hash TEXT UNIQUE NOT NULL,
  key_prefix TEXT,
  label TEXT,
  owner_email TEXT,
  order_code TEXT UNIQUE,
  status TEXT NOT NULL DEFAULT 'active',
  credits_remaining INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_used_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS nanami_products.api_usage_logs (
  id BIGSERIAL PRIMARY KEY,
  api_key_id BIGINT REFERENCES nanami_products.api_keys(id),
  endpoint TEXT NOT NULL,
  credits_used INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL,
  error_code TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_api_usage_logs_key_created
  ON nanami_products.api_usage_logs (api_key_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_api_usage_logs_endpoint_created
  ON nanami_products.api_usage_logs (endpoint, created_at DESC);

ALTER TABLE nanami_products.api_keys
  ADD COLUMN IF NOT EXISTS owner_email TEXT;

ALTER TABLE nanami_products.api_keys
  ADD COLUMN IF NOT EXISTS order_code TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS idx_api_keys_order_code_unique
  ON nanami_products.api_keys (order_code)
  WHERE order_code IS NOT NULL;

ALTER TABLE nanami_products.stores_orders
  ADD COLUMN IF NOT EXISTS product_type TEXT;
ALTER TABLE nanami_products.stores_orders
  ADD COLUMN IF NOT EXISTS provider TEXT;

-- 旧DDL互換: 管理者手動発行では order_code が NULL になるため許可する
ALTER TABLE nanami_products.charts ALTER COLUMN order_code DROP NOT NULL;

ALTER TABLE nanami_products.charts
  ADD COLUMN IF NOT EXISTS share_yaml_text TEXT;

ALTER TABLE nanami_products.charts
  ADD COLUMN IF NOT EXISTS horoscope_svg TEXT;

ALTER TABLE nanami_products.charts
  ADD COLUMN IF NOT EXISTS shichusuimei_svg TEXT;

ALTER TABLE nanami_products.charts
  ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;

UPDATE nanami_products.charts
SET share_yaml_text = yaml_text
WHERE share_yaml_text IS NULL;

UPDATE nanami_products.charts
SET expires_at = created_at + INTERVAL '90 days'
WHERE expires_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_charts_expires_at
  ON nanami_products.charts (expires_at);

ALTER TABLE nanami_products.mundane_posts
  ADD COLUMN IF NOT EXISTS summary TEXT;

ALTER TABLE nanami_products.mundane_posts
  ADD COLUMN IF NOT EXISTS body_markdown TEXT;

ALTER TABLE nanami_products.mundane_posts
  ADD COLUMN IF NOT EXISTS published_at TIMESTAMPTZ;

ALTER TABLE nanami_products.mundane_posts
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mundane_posts_slug_unique
  ON nanami_products.mundane_posts (slug);

CREATE INDEX IF NOT EXISTS idx_mundane_posts_public
  ON nanami_products.mundane_posts (slug, published_at)
  WHERE status = 'published';

-- Cloud Run の DATABASE_URL が authenticator の場合
GRANT USAGE ON SCHEMA nanami_products TO authenticator;
GRANT CREATE ON SCHEMA nanami_products TO authenticator;
GRANT ALL PRIVILEGES ON TABLE nanami_products.charts TO authenticator;
GRANT ALL PRIVILEGES ON TABLE nanami_products.redemptions TO authenticator;
GRANT ALL PRIVILEGES ON TABLE nanami_products.addon_redemptions TO authenticator;
GRANT ALL PRIVILEGES ON TABLE nanami_products.transit_addon_links TO authenticator;
GRANT ALL PRIVILEGES ON TABLE nanami_products.mundane_posts TO authenticator;
GRANT ALL PRIVILEGES ON TABLE nanami_products.stores_orders TO authenticator;
GRANT ALL PRIVILEGES ON TABLE nanami_products.api_keys TO authenticator;
GRANT ALL PRIVILEGES ON TABLE nanami_products.api_usage_logs TO authenticator;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA nanami_products TO authenticator;

ALTER DEFAULT PRIVILEGES IN SCHEMA nanami_products
GRANT ALL PRIVILEGES ON TABLES TO authenticator;

ALTER DEFAULT PRIVILEGES IN SCHEMA nanami_products
GRANT ALL PRIVILEGES ON SEQUENCES TO authenticator;
