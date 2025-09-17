-- 更新批次ID字段长度
-- 创建时间: 2025-01-13

-- 更新临床场景数据表的upload_batch_id字段长度
ALTER TABLE clinical_scenario_data 
ALTER COLUMN upload_batch_id TYPE VARCHAR(100);

-- 更新数据上传批次表的batch_id字段长度
ALTER TABLE data_upload_batches 
ALTER COLUMN batch_id TYPE VARCHAR(100);

-- 添加注释
COMMENT ON COLUMN clinical_scenario_data.upload_batch_id IS '上传批次ID (扩展到100字符)';
COMMENT ON COLUMN data_upload_batches.batch_id IS '批次ID (扩展到100字符)';