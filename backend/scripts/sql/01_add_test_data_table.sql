-- 添加TestData表用于RAGAS评测

CREATE TABLE test_data (
    id SERIAL PRIMARY KEY,
    question_id VARCHAR(255),
    clinical_query TEXT NOT NULL,
    ground_truth TEXT NOT NULL,
    source_file VARCHAR(255),
    upload_batch VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 创建索引
CREATE INDEX idx_test_data_question_id ON test_data(question_id);
CREATE INDEX idx_test_data_upload_batch ON test_data(upload_batch);
CREATE INDEX idx_test_data_is_active ON test_data(is_active);
CREATE INDEX idx_test_data_created_at ON test_data(created_at);

-- 添加评估任务表
CREATE TABLE evaluation_tasks (
    id SERIAL PRIMARY KEY,
    task_name VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(50) DEFAULT 'pending',
    total_cases INTEGER DEFAULT 0,
    processed_cases INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 添加评估结果表
CREATE TABLE evaluation_results (
    id SERIAL PRIMARY KEY,
    task_id INTEGER REFERENCES evaluation_tasks(id) ON DELETE CASCADE,
    test_data_id INTEGER REFERENCES test_data(id) ON DELETE CASCADE,
    rag_response TEXT,
    ragas_scores JSONB,
    overall_score FLOAT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 创建索引
CREATE INDEX idx_evaluation_tasks_status ON evaluation_tasks(status);
CREATE INDEX idx_evaluation_results_task_id ON evaluation_results(task_id);
CREATE INDEX idx_evaluation_results_test_data_id ON evaluation_results(test_data_id);
CREATE INDEX idx_evaluation_results_overall_score ON evaluation_results(overall_score);