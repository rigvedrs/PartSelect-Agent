CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS parts (
    id SERIAL PRIMARY KEY,
    ps_number TEXT UNIQUE NOT NULL,
    manufacturer_part_number TEXT,
    name TEXT NOT NULL,
    price NUMERIC,
    stock_status TEXT,
    brand TEXT,
    manufactured_for TEXT,
    description TEXT,
    category TEXT,
    product_url TEXT,
    image_url TEXT,
    video_url TEXT,
    symptoms TEXT[],
    replaces TEXT[],
    installation_steps TEXT[]
);
CREATE INDEX IF NOT EXISTS idx_parts_category ON parts(category);

CREATE TABLE IF NOT EXISTS compatibility (
    id SERIAL PRIMARY KEY,
    ps_number TEXT NOT NULL REFERENCES parts(ps_number) ON DELETE CASCADE,
    model_number TEXT NOT NULL,
    brand TEXT,
    appliance TEXT,
    UNIQUE (ps_number, model_number)
);
CREATE INDEX IF NOT EXISTS idx_compat_model ON compatibility(model_number);
CREATE INDEX IF NOT EXISTS idx_compat_ps ON compatibility(ps_number);

CREATE TABLE IF NOT EXISTS repair_guides (
    id SERIAL PRIMARY KEY,
    appliance TEXT,
    symptom TEXT,
    part_name TEXT,
    content TEXT
);

CREATE TABLE IF NOT EXISTS articles (
    id SERIAL PRIMARY KEY,
    url TEXT,
    title TEXT,
    content TEXT,
    category TEXT
);

CREATE TABLE IF NOT EXISTS embeddings (
    id SERIAL PRIMARY KEY,
    source_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    content TEXT NOT NULL,
    embedding vector(384),
    UNIQUE (source_type, source_id)
);
CREATE INDEX IF NOT EXISTS idx_embeddings_hnsw
    ON embeddings USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    appliance_model TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS pending_intent TEXT;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS pending_part_query TEXT;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS last_parts_json JSONB;

CREATE TABLE IF NOT EXISTS session_messages (
    id SERIAL PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_session_messages_session
    ON session_messages(session_id, id);

CREATE TABLE IF NOT EXISTS carts (
    session_id TEXT PRIMARY KEY REFERENCES sessions(session_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS cart_items (
    id SERIAL PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES carts(session_id) ON DELETE CASCADE,
    ps_number TEXT NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    UNIQUE (session_id, ps_number)
);
