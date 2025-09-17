-- 添加clinical_scenario_id字段到scenario_results表
ALTER TABLE scenario_results 
ADD COLUMN IF NOT EXISTS clinical_scenario_id INTEGER REFERENCES clinical_scenario_data(id) ON DELETE SET NULL;

-- 添加索引
CREATE INDEX IF NOT EXISTS idx_scenario_results_clinical_scenario_id 
ON scenario_results(clinical_scenario_id);

-- 添加注释
COMMENT ON COLUMN scenario_results.clinical_scenario_id IS '关联的临床场景数据ID';