# 04-开发指南 (Development Guides)

本模块包含ACRAC系统的开发指南，涵盖开发环境搭建、开发规范、项目计划等开发相关内容。

## 📋 文档列表

- [ACRAC V2 开发指南](ACRAC_V2_开发指南.md) - 开发环境搭建和开发规范
- [前端设计方案](ACRAC前端设计方案.md) - 前端架构和组件设计
- [系统开发检查清单](ACRAC系统开发检查清单.md) - 开发质量检查清单
- [系统项目计划](ACRAC系统项目计划.md) - 项目计划和里程碑
- [开发计划](开发计划.md) - 详细开发计划
- [快速启动指南](快速启动指南.md) - 快速上手指南
- [管理界面](admin_ui.md) - 管理界面设计说明
- [数据库设置指南](DATABASE_SETUP_GUIDE.md) - 数据库配置和设置

## 🛠️ 开发环境

### 技术栈
- **后端**: Python 3.11+ + FastAPI + SQLAlchemy
- **前端**: Node.js 18+ + React 18 + TypeScript
- **数据库**: PostgreSQL 15+ + pgvector
- **容器**: Docker + Docker Compose

### 开发工具
- **代码格式化**: Black (Python) + Prettier (TypeScript)
- **代码检查**: Flake8 + ESLint
- **类型检查**: MyPy + TypeScript
- **测试框架**: Pytest + Jest

## 🎯 模块目标

本模块旨在为开发者提供：
- 完整的开发环境搭建指南
- 统一的开发规范和最佳实践
- 详细的项目计划和里程碑
- 质量检查和代码审查标准

## 📚 开发流程

### 环境搭建
1. 阅读 [快速启动指南](快速启动指南.md)
2. 按照 [ACRAC V2 开发指南](ACRAC_V2_开发指南.md) 搭建环境
3. 参考 [前端设计方案](ACRAC前端设计方案.md) 了解前端架构

### 开发规范
1. 遵循 [系统开发检查清单](ACRAC系统开发检查清单.md)
2. 参考 [管理界面](admin_ui.md) 进行界面开发
3. 按照 [开发计划](开发计划.md) 进行功能开发

### 质量保证
1. 使用 [系统开发检查清单](ACRAC系统开发检查清单.md) 进行自检
2. 遵循代码规范和最佳实践
3. 进行充分的测试和验证

## 🔗 相关模块

- [01-项目概览](../01-project-overview/) - 项目背景
- [02-系统架构](../02-system-architecture/) - 技术架构
- [03-API文档](../03-api-documentation/) - API开发
