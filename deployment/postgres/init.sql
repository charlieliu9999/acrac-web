-- 初始化PostgreSQL数据库
-- 创建pgvector扩展
CREATE EXTENSION IF NOT EXISTS vector;

-- 创建用户和权限（如果需要）
-- CREATE USER acrac_user WITH PASSWORD 'acrac_password';
-- GRANT ALL PRIVILEGES ON DATABASE acrac_db TO acrac_user;

-- 设置时区
SET timezone = 'Asia/Shanghai';
