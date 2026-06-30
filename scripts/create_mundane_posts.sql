CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE SCHEMA IF NOT EXISTS nanami_products;

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

CREATE UNIQUE INDEX IF NOT EXISTS idx_mundane_posts_slug_unique
  ON nanami_products.mundane_posts (slug);

CREATE INDEX IF NOT EXISTS idx_mundane_posts_public
  ON nanami_products.mundane_posts (slug, published_at)
  WHERE status = 'published';

-- アプリ実行ユーザー名が authenticator 以外の場合は、実際のロール名へ置き換えてください。
GRANT USAGE ON SCHEMA nanami_products TO authenticator;
GRANT SELECT, INSERT, UPDATE ON TABLE nanami_products.mundane_posts TO authenticator;
