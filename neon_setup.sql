CREATE SCHEMA IF NOT EXISTS nanami_products;

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
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS nanami_products.stores_orders (
  stores_order_no TEXT PRIMARY KEY,
  product_type TEXT,
  amount INTEGER,
  payment_status TEXT DEFAULT 'paid',
  mail_subject TEXT,
  raw_message_id TEXT,
  mail_received_at TIMESTAMPTZ,
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

-- 旧DDL互換: 管理者手動発行では order_code が NULL になるため許可する
ALTER TABLE nanami_products.charts ALTER COLUMN order_code DROP NOT NULL;

-- Cloud Run の DATABASE_URL が authenticator の場合
GRANT USAGE ON SCHEMA nanami_products TO authenticator;
GRANT CREATE ON SCHEMA nanami_products TO authenticator;
GRANT ALL PRIVILEGES ON TABLE nanami_products.charts TO authenticator;
GRANT ALL PRIVILEGES ON TABLE nanami_products.redemptions TO authenticator;
GRANT ALL PRIVILEGES ON TABLE nanami_products.stores_orders TO authenticator;
GRANT ALL PRIVILEGES ON TABLE nanami_products.api_keys TO authenticator;
GRANT ALL PRIVILEGES ON TABLE nanami_products.api_usage_logs TO authenticator;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA nanami_products TO authenticator;

ALTER DEFAULT PRIVILEGES IN SCHEMA nanami_products
GRANT ALL PRIVILEGES ON TABLES TO authenticator;

ALTER DEFAULT PRIVILEGES IN SCHEMA nanami_products
GRANT ALL PRIVILEGES ON SEQUENCES TO authenticator;
