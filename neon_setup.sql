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

-- 旧DDL互換: 管理者手動発行では order_code が NULL になるため許可する
ALTER TABLE nanami_products.charts ALTER COLUMN order_code DROP NOT NULL;

-- Cloud Run の DATABASE_URL が authenticator の場合
GRANT USAGE ON SCHEMA nanami_products TO authenticator;
GRANT ALL PRIVILEGES ON TABLE nanami_products.charts TO authenticator;
GRANT ALL PRIVILEGES ON TABLE nanami_products.redemptions TO authenticator;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA nanami_products TO authenticator;

ALTER DEFAULT PRIVILEGES IN SCHEMA nanami_products
GRANT ALL PRIVILEGES ON TABLES TO authenticator;

ALTER DEFAULT PRIVILEGES IN SCHEMA nanami_products
GRANT ALL PRIVILEGES ON SEQUENCES TO authenticator;
