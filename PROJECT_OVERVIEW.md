# ACRAC 医疗影像智能推荐系统

## 项目简介

ACRAC (American College of Radiology Appropriateness Criteria) 是一个基于向量数据库的医疗影像智能推荐系统，能够根据患者症状、病史和临床特征，智能推荐最适合的影像检查项目。

## 快速开始

### 方式一：Docker 容器化部署（推荐）
```bash
# 启动所有服务
./start.sh

# 停止所有服务
./stop.sh

# 重启服务
./restart.sh
```

### 方式二：开发环境
```bash
# 启动开发环境（数据库容器 + 本地前后端）
./start-dev.sh

# 停止开发环境
./stop.sh
```

## 服务访问地址

- **前端应用**: http://localhost:5173 (开发) / http://localhost:8080 (生产)
- **后端API**: http://localhost:8001
- **API文档**: http://localhost:8001/docs
- **数据库**: localhost:5432 (postgres/password)
- **Redis**: localhost:6379

## 项目结构

```
ACRAC-web/
├── backend/                    # 后端服务 (FastAPI)
├── frontend/                   # 前端应用 (React + Vite)
├── docs/                       # 项目文档
├── ACR_data/                   # 原始数据
├── deployment/                 # 部署配置
├── config/                     # 配置文件
├── logs/                       # 运行日志
├── start.sh                    # 生产环境启动脚本
├── start-dev.sh               # 开发环境启动脚本
├── stop.sh                    # 停止脚本
└── restart.sh                 # 重启脚本
```

## 重要文档

- [项目进度报告](docs/PROJECT_PROGRESS_REPORT.md)
- [目录结构说明](docs/DIRECTORY_STRUCTURE.md)
- [版本控制说明](docs/VERSION_CONTROL.md)
- [安全说明](docs/SECURITY.md)
- [生产推荐API文档](docs/PRODUCTION_RECOMMENDATION_API.md)

## 技术栈

- **后端**: FastAPI + SQLAlchemy + PostgreSQL + pgvector
- **前端**: React 18 + TypeScript + Vite + Ant Design
- **向量模型**: SiliconFlow BGE-M3 (1024维)
- **容器化**: Docker + Docker Compose

## 环境配置

1. 复制环境配置文件：
   ```bash
   cp backend/acrac.env.example backend/.env
   ```

2. 编辑配置文件，设置必要的API密钥：
   ```bash
   vim backend/.env
   ```

## 开发指南

### 后端开发
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

### 前端开发
```bash
cd frontend
npm install
npm run dev
```

## 故障排除

### 常见问题
1. **端口占用**: 检查 8001、5173、5432 端口是否被占用
2. **数据库连接失败**: 确认 PostgreSQL 服务状态
3. **API调用失败**: 检查后端服务是否正常运行

### 查看日志
```bash
# 查看后端日志
tail -f logs/backend.log

# 查看前端日志
tail -f logs/frontend.log

# 查看容器日志
docker-compose logs -f
```

## 贡献指南

1. Fork 项目
2. 创建功能分支
3. 提交更改（使用中文 Conventional Commits）
4. 创建 Pull Request

## 许可证

本项目采用 MIT 许可证。

---

**注意**: 本系统仅供医疗研究和教育用途，不应用于实际临床诊断决策。
