-- 创建支持向量的ACRAC数据库表结构

-- 用户表
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    is_superuser BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 规则表
CREATE TABLE rules (
    id SERIAL PRIMARY KEY,
    rule_name VARCHAR(255) NOT NULL,
    rule_description TEXT,
    rule_content TEXT NOT NULL,
    status VARCHAR(50) DEFAULT 'active',
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 数据导入任务表
CREATE TABLE data_import_tasks (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    progress INTEGER DEFAULT 0,
    total_records INTEGER DEFAULT 0,
    processed_records INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 推理日志表
CREATE TABLE inference_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    query_text TEXT NOT NULL,
    response_text TEXT,
    model_name VARCHAR(100),
    processing_time FLOAT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Panel表 (支持向量)
CREATE TABLE panels (
    id SERIAL PRIMARY KEY,
    name_en VARCHAR(255) NOT NULL,
    name_zh VARCHAR(255) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    embedding vector(1024),  -- 向量列
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Topic表 (支持向量)
CREATE TABLE topics (
    id SERIAL PRIMARY KEY,
    panel_id INTEGER NOT NULL REFERENCES panels(id) ON DELETE CASCADE,
    name_en VARCHAR(255) NOT NULL,
    name_zh VARCHAR(255) NOT NULL,
    description TEXT,
    keywords_zh TEXT,
    keywords_en TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    embedding vector(1024),  -- 向量列
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Variant表 (支持向量)
CREATE TABLE variants (
    id SERIAL PRIMARY KEY,
    topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    description_en TEXT,
    description_zh TEXT,
    variant_type VARCHAR(100),
    clinical_context TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    embedding vector(1024),  -- 向量列
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Procedure表 (支持向量)
CREATE TABLE procedures (
    id SERIAL PRIMARY KEY,
    variant_id INTEGER NOT NULL REFERENCES variants(id) ON DELETE CASCADE,
    name_en VARCHAR(255) NOT NULL,
    name_zh VARCHAR(255) NOT NULL,
    recommendation_en TEXT,
    recommendation_zh TEXT,
    appropriateness_category VARCHAR(100),
    appropriateness_category_zh VARCHAR(100),
    rating FLOAT,
    median FLOAT,
    soe VARCHAR(50),
    adult_rrl VARCHAR(50),
    peds_rrl VARCHAR(50),
    steps_zh TEXT,
    steps_en TEXT,
    is_generated BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    embedding vector(1024),  -- 向量列
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 创建索引
CREATE INDEX idx_panels_name_en ON panels(name_en);
CREATE INDEX idx_panels_name_zh ON panels(name_zh);
CREATE INDEX idx_panels_embedding_vector ON panels USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

CREATE INDEX idx_topics_panel_id ON topics(panel_id);
CREATE INDEX idx_topics_name_en ON topics(name_en);
CREATE INDEX idx_topics_name_zh ON topics(name_zh);
CREATE INDEX idx_topics_embedding_vector ON topics USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

CREATE INDEX idx_variants_topic_id ON variants(topic_id);
CREATE INDEX idx_variants_embedding_vector ON variants USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

CREATE INDEX idx_procedures_variant_id ON procedures(variant_id);
CREATE INDEX idx_procedures_name_en ON procedures(name_en);
CREATE INDEX idx_procedures_name_zh ON procedures(name_zh);
CREATE INDEX idx_procedures_rating ON procedures(rating);
CREATE INDEX idx_procedures_embedding_vector ON procedures USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- 创建序列
CREATE SEQUENCE panels_id_seq;
CREATE SEQUENCE topics_id_seq;
CREATE SEQUENCE variants_id_seq;
CREATE SEQUENCE procedures_id_seq;
CREATE SEQUENCE users_id_seq;
CREATE SEQUENCE rules_id_seq;
CREATE SEQUENCE data_import_tasks_id_seq;
CREATE SEQUENCE inference_logs_id_seq;

-- 设置序列所有者
ALTER SEQUENCE panels_id_seq OWNED BY panels.id;
ALTER SEQUENCE topics_id_seq OWNED BY topics.id;
ALTER SEQUENCE variants_id_seq OWNED BY variants.id;
ALTER SEQUENCE procedures_id_seq OWNED BY procedures.id;
ALTER SEQUENCE users_id_seq OWNED BY users.id;
ALTER SEQUENCE rules_id_seq OWNED BY rules.id;
ALTER SEQUENCE data_import_tasks_id_seq OWNED BY data_import_tasks.id;
ALTER SEQUENCE inference_logs_id_seq OWNED BY inference_logs.id;
