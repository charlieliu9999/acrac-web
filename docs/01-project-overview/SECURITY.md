# 安全配置指南

## 环境变量配置

### 后端环境变量
复制 `backend/acrac.env.example` 到 `backend/.env` 并配置：

```bash
# 数据库配置
PGHOST=localhost
PGPORT=5432
PGDATABASE=acrac_db
PGUSER=postgres
PGPASSWORD=your_secure_password

# API密钥配置
SILICONFLOW_API_KEY=your_siliconflow_api_key_here
SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1

# 其他配置
DEBUG=False
LOG_LEVEL=INFO
```

### 前端环境变量
复制 `frontend/.env.example` 到 `frontend/.env` 并配置：

```bash
VITE_API_BASE=http://localhost:8001
```

## 数据安全

### 敏感文件保护
以下文件类型不应提交到Git：
- 环境变量文件 (`.env*`)
- 医疗数据文件 (`*.csv`, `*.xlsx`)
- 上传文件 (`uploads/`)
- API密钥文件
- 数据库文件 (`*.db`)

### 已配置的.gitignore规则
- `.env*` - 所有环境变量文件
- `ACR_data/` - 医疗数据目录
- `uploads/` - 上传文件目录
- `*.csv`, `*.xlsx` - 数据文件
- `**/config/*.json` - 配置文件（除示例文件外）

## 部署安全建议

1. **生产环境**：
   - 使用强密码
   - 定期轮换API密钥
   - 启用HTTPS
   - 配置防火墙规则

2. **开发环境**：
   - 使用测试数据
   - 不要提交真实API密钥
   - 定期检查敏感文件

3. **代码审查**：
   - 检查所有提交是否包含敏感信息
   - 使用预提交钩子检查敏感文件
   - 定期审计Git历史

## 应急响应

如果发现敏感信息已提交：
1. 立即从Git历史中移除文件
2. 轮换所有暴露的API密钥
3. 检查是否有未授权访问
4. 更新安全配置

## 联系方式

如有安全问题，请联系项目维护者。
