# ACRAC 项目文档中心

欢迎来到 ACRAC 医疗影像智能推荐系统的文档中心。本文档按模块和时间线进行了重新整理，便于快速查找和使用。

## 📚 文档结构

### 01-项目概览 (Project Overview)
- [项目进度报告](01-project-overview/PROJECT_PROGRESS_REPORT.md) - 项目整体进展和完成情况
- [项目进度日志](01-project-overview/PROJECT_PROGRESS_LOG.md) - 2025年起的详细开发日志
- [项目发展时间线](01-project-overview/PROJECT_TIMELINE.md) - 项目从启动到现在的完整时间线
- [项目清理总结](01-project-overview/CLEANUP_SUMMARY.md) - 项目清理和重构总结
- [目录结构说明](01-project-overview/DIRECTORY_STRUCTURE.md) - 项目文件组织结构
- [版本控制说明](01-project-overview/VERSION_CONTROL.md) - Git工作流和版本管理
- [安全说明](01-project-overview/SECURITY.md) - 安全策略和最佳实践

### 02-系统架构 (System Architecture)
- [ACRAC V2.0 系统文档](02-system-architecture/ACRAC_V2_系统文档.md) - 系统整体架构和设计
- [RAG模块化服务](02-system-architecture/RAG_MODULAR_SERVICE.md) - RAG服务架构说明
- [RAG服务架构](02-system-architecture/rag_service_arch.md) - 详细的服务架构设计
- [规则引擎](02-system-architecture/rules_engine.md) - 规则引擎设计和实现
- [推理开关](02-system-architecture/INFERENCE_SWITCHES.md) - 推理参数控制说明
- [硬编码模型修复报告](02-system-architecture/HARDCODED_MODEL_FIX_REPORT.md) - 模型配置修复报告

### 03-API文档 (API Documentation)
- [API端点审计](03-api-documentation/API_ENDPOINTS_AUDIT.md) - API使用情况分析和优化建议
- [生产推荐API](03-api-documentation/PRODUCTION_RECOMMENDATION_API.md) - 生产环境推荐API文档
- [ACRAC V2 API使用指南](03-api-documentation/ACRAC_V2_API使用指南.md) - 完整API使用说明
- [三个推荐方案API端点总结](03-api-documentation/ACRAC_V2_三个推荐方案API端点总结.md) - 推荐方案API对比
- [三个推荐方法API使用指南](03-api-documentation/ACRAC_V2_三个推荐方法API使用指南.md) - 推荐方法API详解
- [向量检索详细使用指南](03-api-documentation/向量检索详细使用指南.md) - 向量搜索API使用

### 04-开发指南 (Development Guides)
- [ACRAC V2 开发指南](04-development-guides/ACRAC_V2_开发指南.md) - 开发环境搭建和开发规范
- [前端设计方案](04-development-guides/ACRAC前端设计方案.md) - 前端架构和组件设计
- [系统开发检查清单](04-development-guides/ACRAC系统开发检查清单.md) - 开发质量检查清单
- [系统项目计划](04-development-guides/ACRAC系统项目计划.md) - 项目计划和里程碑
- [开发计划](04-development-guides/开发计划.md) - 详细开发计划
- [快速启动指南](04-development-guides/快速启动指南.md) - 快速上手指南
- [管理界面](04-development-guides/admin_ui.md) - 管理界面设计说明
- [数据库设置指南](04-development-guides/DATABASE_SETUP_GUIDE.md) - 数据库配置和设置

### 05-部署运维 (Deployment & Operations)
- [BGE-Large-ZH-Ollama集成总结](05-deployment/BGE-Large-ZH-Ollama集成总结.md) - 模型集成方案
- [Ollama-BGE配置指南](05-deployment/Ollama-BGE配置指南.md) - 本地模型配置
- [部署指南](05-deployment/DEPLOYMENT_GUIDE.md) - 项目部署配置指南
- [发布说明](05-deployment/RELEASE_NOTES.md) - 版本发布记录

### 06-评测测试 (Evaluation & Testing)
- [A/B测试推理报告](06-evaluation-testing/AB_TEST_SHOW_REASONING_REPORT.md) - 推理功能A/B测试
- [临床案例推荐分析](06-evaluation-testing/ACRAC_V2_临床案例推荐分析.md) - 临床案例测试分析
- [推荐方法优化方案](06-evaluation-testing/ACRAC_V2_推荐方法优化方案.md) - 推荐算法优化
- [RAGAS API综合测试报告](06-evaluation-testing/RAGAS_API_COMPREHENSIVE_TEST_REPORT.md) - RAGAS API测试报告
- [RAGAS清理计划](06-evaluation-testing/RAGAS_CLEANUP_PLAN.md) - RAGAS系统清理计划
- [RAGAS数据分析](06-evaluation-testing/RAGAS_DATA_INPUT_ANALYSIS.md) - RAGAS数据分析报告
- [RAGAS评测分析报告](06-evaluation-testing/RAGAS_EVALUATION_ANALYSIS_REPORT.md) - RAGAS评测分析

### 07-历史归档 (History Archive)
- [ACRAC V2.0 实施完成报告](07-history-archive/ACRAC_V2_智能推荐系统实施完成报告.md) - V2.0版本完成报告
- [项目完成检查清单](07-history-archive/ACRAC_V2_项目完成检查清单.md) - V2.0版本检查清单
- [优化计划](07-history-archive/OPTIMIZATION_PLAN.md) - 系统优化计划（历史版本）
- [项目清理审计报告](07-history-archive/PROJECT_CLEANUP_AUDIT_REPORT.md) - 项目清理审计报告

## 🕒 项目时间线

### 2024年 - 项目启动和V1.0开发
- 项目初始化和基础架构搭建
- 核心功能模块开发
- 数据库设计和向量化

### 2025年1月 - V2.0系统完成
- 三层混合推荐架构实施
- RAG+LLM智能分析集成
- 规则过滤系统完善
- 前端界面优化

### 2025年2月 - 生产优化
- 轻量级生产推荐API
- 批量文件上传功能
- 系统清理和文档整理
- 性能优化和稳定性提升

## 🚀 快速导航

### 新用户入门
1. 阅读 [项目进度报告](01-project-overview/PROJECT_PROGRESS_REPORT.md) 了解项目概况
2. 查看 [快速启动指南](04-development-guides/快速启动指南.md) 快速上手
3. 参考 [ACRAC V2 开发指南](04-development-guides/ACRAC_V2_开发指南.md) 搭建开发环境

### 开发者参考
1. [系统架构文档](02-system-architecture/ACRAC_V2_系统文档.md) - 了解整体架构
2. [API文档](03-api-documentation/) - 查看API使用说明
3. [开发指南](04-development-guides/) - 开发规范和最佳实践

### 运维人员
1. [部署运维文档](05-deployment/) - 部署和配置指南
2. [安全说明](01-project-overview/SECURITY.md) - 安全配置
3. [版本控制](01-project-overview/VERSION_CONTROL.md) - 版本管理

## 📝 文档维护

- **最后更新**: 2025年1月
- **维护者**: ACRAC开发团队
- **更新频率**: 随项目进展定期更新

## 🔗 相关链接

- [项目主页](../README.md)
- [项目概览](../PROJECT_OVERVIEW.md)
- [清理总结](../CLEANUP_SUMMARY.md)

---

如有文档问题或建议，请提交Issue或联系开发团队。
