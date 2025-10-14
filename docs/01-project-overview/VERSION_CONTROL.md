# ACRAC 项目版本控制说明

## Git 仓库状态

- **主分支**: `main` - 稳定版本
- **开发分支**: `develop` - 开发版本
- **当前分支**: `develop`

## 版本历史

### v1.0.0 (2025-01-11) - 初始版本
- **提交哈希**: `34cfc0f`
- **功能特性**:
  - 完成 FastAPI 后端架构搭建
  - 实现 Vue.js 前端管理界面
  - 集成 RAGAS 评测系统
  - 添加 PostgreSQL + pgvector 向量数据库支持
  - 实现 Docker 容器化部署配置
  - 包含完整的 API 文档和部署指南

## 主要功能模块

### 后端服务 (FastAPI)
- 数据导入与向量化构建
- 智能推荐与 RAGAS 评测
- 模型配置管理
- 规则引擎配置
- 向量检索与状态监控

### 前端界面 (Vue.js)
- 数据导入页面
- 模型配置页面
- RAG 助手页面
- 工具箱页面
- 规则管理页面
- 数据浏览页面

### 数据库
- PostgreSQL 主数据库
- pgvector 向量数据库扩展
- 完整的表结构设计

## 开发工作流

1. **功能开发**: 在 `develop` 分支进行
2. **测试验证**: 在 `develop` 分支完成测试
3. **版本发布**: 合并到 `main` 分支并打标签
4. **热修复**: 在 `main` 分支创建 hotfix 分支

## 文件结构

```
ACRAC-web/
├── backend/           # FastAPI 后端服务
├── frontend/          # Vue.js 前端应用
├── docs/             # 项目文档
├── deployment/       # 部署配置
├── data/            # 数据文件
├── config/          # 配置文件
└── standard/        # 标准数据
```

## 环境要求

- Python 3.8+
- Node.js 16+
- PostgreSQL 13+
- Docker & Docker Compose

## 快速开始

1. 克隆仓库: `git clone <repository-url>`
2. 切换到开发分支: `git checkout develop`
3. 启动服务: `./start-dev.sh`
4. 访问应用: http://localhost:5173

## 贡献指南

1. 从 `develop` 分支创建功能分支
2. 完成开发后提交到功能分支
3. 创建 Pull Request 到 `develop` 分支
4. 代码审查通过后合并

## 注意事项

- 提交信息使用中文，格式: `feat: 功能描述` 或 `fix: 修复描述`
- 重要功能需要添加测试用例
- 数据库变更需要提供迁移脚本
- 新 API 需要更新文档
