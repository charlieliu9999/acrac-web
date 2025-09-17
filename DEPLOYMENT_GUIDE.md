# ACRAC项目部署指南

## 端口配置

根据标准端口配置，本项目使用以下端口：

- **前端服务**: 5173端口
- **后端API**: 8001端口
- **PostgreSQL数据库**: 5432端口 (Docker容器)
- **Redis缓存**: 6379端口 (Docker容器)

## 快速启动

### 1. 一键启动（推荐）

```bash
# 启动所有服务（前端、后端、Nginx、Postgres、Redis）
./start.sh

# 查看服务状态
docker-compose ps

# 停止所有服务
./stop.sh

# 重启所有服务
./restart.sh
```

启动完成后：
- 前端入口（经 Nginx）：http://localhost:5173
- 后端 API（直连容器端口）：http://localhost:8001

验证（可选）：
```bash
# 前端入口应返回 200/HTML
curl -I http://127.0.0.1:5173 | head -n 5

# 健康检查（经前端域名转发到后端）
curl -sS http://127.0.0.1:5173/api/v1/acrac/health | jq .

# 数据浏览接口示例
curl -sS http://127.0.0.1:5173/api/v1/acrac/data/panels | head -c 200
curl -sS "http://127.0.0.1:5173/api/v1/acrac/data/topics/by-panel?panel_id=P0001" | head -c 200
curl -sS "http://127.0.0.1:5173/api/v1/acrac/data/scenarios/by-topic?topic_id=T0001" | head -c 200
```

注意：
- 前端开发服务器（Vite）已容器化运行，由 Nginx 在 5173 端口对外提供服务。
- 前端与后端走同域转发（/api → backend），无需设置 `VITE_API_BASE` 环境变量。
- 如遇 502（Bad Gateway），先执行 `docker-compose logs nginx` 查看上游是否连到 `frontend:5173`，然后 `docker-compose restart nginx`。
- 如遇“加载科室失败: Not Found”，通常是请求路径被拼成 `/api/api/v1/...`，请确认 axios `baseURL` 为空或未重复添加 `/api` 前缀（本项目已在 compose 中移除该环境变量）。

### 2. 手动启动（可选）

#### 启动数据库服务
```bash
docker-compose up -d postgres redis
```

#### 启动后端服务
```bash
cd backend
source venv/bin/activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

#### 启动前端服务（本机直跑）
```bash
cd frontend
npm install
npm run dev -- --host --port 5173
```
## 服务访问地址

- **前端应用**: http://localhost:5173
- **后端API**: http://localhost:8001
- **API文档**: http://localhost:8001/docs
- **API交互文档**: http://localhost:8001/redoc

## 自动化脚本功能

### start.sh
- 检查系统依赖
- 终止现有进程
- 更新代码到最新版本
- 启动数据库服务
- 设置后端和前端环境
- 启动所有服务
- 显示服务状态

### stop.sh
- 停止前端服务
- 停止后端服务
- 停止数据库容器
- 清理进程文件
- 可选清理日志文件 (`./stop.sh --clean-logs`)

### restart.sh
- 快速重启所有服务
- 自动添加脚本执行权限

## 日志文件

- **后端日志**: `logs/backend.log`
- **前端日志**: `logs/frontend.log`
- **进程ID文件**: `logs/backend.pid`, `logs/frontend.pid`

## 环境要求

### 系统依赖
- Docker & Docker Compose
- Node.js (推荐v18+)
- Python 3.8+
- Git (用于代码更新)

### Python依赖
- 后端依赖在 `backend/requirements.txt` 中定义
- 自动创建和管理虚拟环境

### Node.js依赖
- 前端依赖在 `frontend/package.json` 中定义
- 自动安装npm依赖

## 开发模式

启动脚本默认以开发模式运行：
- 后端启用热重载 (`--reload`)
- 前端启用Vite开发服务器
- 数据库使用Docker容器

## 生产部署

对于生产环境，建议：
1. 使用 `docker-compose.yml` 进行容器化部署
2. 配置Nginx反向代理
3. 使用环境变量管理配置
4. 启用HTTPS

## 故障排除

### 端口冲突
如果遇到端口冲突，检查：
```bash
# 检查端口占用
lsof -i :5173  # 前端端口
lsof -i :8001  # 后端端口
lsof -i :5432  # 数据库端口
```

### 服务启动失败
1. 检查日志文件
2. 确认依赖已安装
3. 检查Docker服务状态
4. 验证端口可用性

### 数据库连接问题
```bash
# 检查数据库容器状态
docker-compose ps

# 查看数据库日志
docker-compose logs postgres
```

## 配置文件说明

- `frontend/vite.config.ts`: 前端开发服务器配置
- `backend/app/main.py`: 后端服务器配置
- `docker-compose.yml`: 容器编排配置
- `frontend/.env`: 前端环境变量
- `backend/.env`: 后端环境变量

## 更新和维护

启动脚本会自动：
1. 从Git仓库拉取最新代码
2. 重置到最新提交
3. 重新安装依赖（如有变化）
4. 重启服务

手动更新：
```bash
git pull origin main
./restart.sh
```