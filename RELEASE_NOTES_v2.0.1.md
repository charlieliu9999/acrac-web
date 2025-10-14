# ACRAC v2.0.1 发布说明

## 🐛 错误修复

ACRAC v2.0.1 是一个重要的错误修复版本，解决了数据库连接问题，确保系统在各种部署环境下都能稳定运行。

## 🔧 主要修复

### 数据库连接问题修复
- **问题**: 修复了 `psycopg2.OperationalError: connection to server at "localhost" (::1), port 5432 failed: Connection refused` 错误
- **原因**: 在 Docker 容器环境中，应用尝试连接 localhost:5432，但应该连接 Docker 服务名
- **解决方案**: 
  - 更新数据库配置，优先使用 Docker 服务名 `postgres` 而不是 `localhost`
  - 实现连接重试和主机回退机制
  - 添加详细的数据库配置指南

### 技术改进

#### 后端配置优化
- **config.py**: 修复数据库连接配置，使用 Docker 服务名
  ```python
  PGHOST: str = os.getenv("PGHOST", "postgres")  # 使用docker服务名
  DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:password@postgres:5432/acrac_db")
  REDIS_URL: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
  ```

#### 连接管理增强
- **DBManager**: 实现智能连接重试和主机回退
  - 当连接 localhost/127.0.0.1 失败时，自动尝试连接 `postgres` 服务名
  - 添加连接超时和重试机制
  - 优化连接池管理

#### 环境配置完善
- **Docker Compose**: 确保服务间网络通信正常
- **环境变量**: 提供完整的开发和生产环境配置示例
- **文档更新**: 添加详细的数据库设置指南

## 📚 配置指南

### Docker 环境
```bash
# 启动所有服务
docker-compose up -d

# 检查服务状态
docker-compose ps
```

### 开发环境
```bash
# 使用开发环境配置
cp backend/acrac.env.example backend/.env.dev

# 启动开发服务
./start-dev.sh
```

## 🔍 验证步骤

1. **启动服务**: 确保所有 Docker 容器正常启动
2. **检查连接**: 验证数据库连接是否成功
3. **测试功能**: 运行核心功能测试，确保推荐系统正常工作

## 📊 影响范围

- ✅ **数据库连接**: 修复了所有数据库连接问题
- ✅ **Docker 部署**: 确保容器间通信正常
- ✅ **开发环境**: 支持本地和容器化开发
- ✅ **生产环境**: 提供稳定的生产部署配置

## 🚀 升级建议

- **从 v2.0.0 升级**: 直接拉取最新代码即可
- **配置更新**: 建议使用新的环境配置模板
- **测试验证**: 升级后请验证数据库连接和核心功能

## 📞 支持

如有问题，请参考：
- 数据库配置指南: `docs/04-development-guides/DATABASE_SETUP_GUIDE.md`
- 快速启动指南: `docs/04-development-guides/快速启动指南.md`
- 项目概览: `PROJECT_OVERVIEW.md`

---

**ACRAC v2.0.1** - 更稳定、更可靠的医疗影像智能推荐系统
