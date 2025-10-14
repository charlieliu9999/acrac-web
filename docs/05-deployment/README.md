# 05-部署运维 (Deployment & Operations)

本模块包含ACRAC系统的部署和运维相关文档，涵盖模型集成、配置指南、版本发布等运维内容。

## 📋 文档列表

- [BGE-Large-ZH-Ollama集成总结](BGE-Large-ZH-Ollama集成总结.md) - 模型集成方案
- [Ollama-BGE配置指南](Ollama-BGE配置指南.md) - 本地模型配置
- [部署指南](DEPLOYMENT_GUIDE.md) - 项目部署配置指南
- [发布说明](RELEASE_NOTES.md) - 版本发布记录

## 🚀 部署架构

### 容器化部署
```
┌─────────────────────────────────────┐
│            Nginx (反向代理)          │
├─────────────────────────────────────┤
│         FastAPI (后端服务)          │
├─────────────────────────────────────┤
│         PostgreSQL + pgvector       │
├─────────────────────────────────────┤
│            Redis (缓存)             │
└─────────────────────────────────────┘
```

### 服务组件
- **Web服务**: Nginx + FastAPI
- **数据库**: PostgreSQL + pgvector
- **缓存**: Redis
- **AI模型**: SiliconFlow BGE-M3 / Ollama

## 🎯 模块目标

本模块旨在为运维人员提供：
- 完整的部署和配置指南
- 模型集成和配置方案
- 版本发布和升级流程
- 运维监控和故障排除

## 📚 部署指南

### 生产环境部署
1. 参考 [BGE-Large-ZH-Ollama集成总结](BGE-Large-ZH-Ollama集成总结.md) 配置AI模型
2. 按照 [Ollama-BGE配置指南](Ollama-BGE配置指南.md) 配置本地模型
3. 查看 [发布说明](RELEASE_NOTES.md) 了解版本更新

### 开发环境部署
1. 使用Docker Compose快速部署
2. 配置本地开发环境
3. 进行功能测试和验证

## 🔗 相关模块

- [02-系统架构](../02-system-architecture/) - 技术架构
- [04-开发指南](../04-development-guides/) - 开发环境
- [06-评测测试](../06-evaluation-testing/) - 测试验证
