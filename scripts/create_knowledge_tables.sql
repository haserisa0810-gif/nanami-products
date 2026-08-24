CREATE SCHEMA IF NOT EXISTS nanami_products;

CREATE TABLE IF NOT EXISTS nanami_products.knowledge_documents (
    source_key          TEXT PRIMARY KEY,
    collection          TEXT NOT NULL,
    source_path         TEXT NOT NULL,
    title               TEXT NOT NULL,
    kind                TEXT NOT NULL,
    status              TEXT NOT NULL CHECK (status IN ('draft', 'active', 'superseded', 'archived')),
    owner               TEXT,
    tags                JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata            JSONB NOT NULL DEFAULT '{}'::jsonb,
    content             TEXT NOT NULL,
    content_sha256      TEXT NOT NULL,
    source_updated_at   TEXT,
    git_commit          TEXT,
    indexed_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (collection, source_path)
);

CREATE TABLE IF NOT EXISTS nanami_products.knowledge_chunks (
    source_key          TEXT NOT NULL REFERENCES nanami_products.knowledge_documents(source_key),
    chunk_no            INTEGER NOT NULL,
    heading             TEXT,
    content             TEXT NOT NULL,
    content_sha256      TEXT NOT NULL,
    indexed_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (source_key, chunk_no)
);

CREATE INDEX IF NOT EXISTS idx_knowledge_documents_collection_status
    ON nanami_products.knowledge_documents (collection, status);

CREATE INDEX IF NOT EXISTS idx_knowledge_documents_kind
    ON nanami_products.knowledge_documents (kind);

CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_source
    ON nanami_products.knowledge_chunks (source_key);

-- pgvector/embeddingは初期段階では必須にしない。
-- 日本語検索はアプリ側の部分一致とチャンク取得から始め、必要になった時点で追加する。
