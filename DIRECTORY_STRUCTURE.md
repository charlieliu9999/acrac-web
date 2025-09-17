# ACRAC 项目目录结构说明

## 项目根目录

```
ACRAC-web/
├── README.md                          # 项目主要说明文档
├── PROJECT_STATUS.md                  # 项目状态报告
├── DIRECTORY_STRUCTURE.md             # 本文件 - 目录结构说明
├── .gitignore                         # Git忽略文件配置
├── docker-compose.yml                 # Docker容器编排配置
├── ACR_data/                          # 原始数据目录
├── backend/                           # 后端服务目录
├── frontend/                          # 前端应用目录
├── docs/                              # 项目文档目录
├── deployment/                        # 部署配置目录
├── backup/                            # 备份文件目录
├── data/                              # 处理后的数据目录
├── standard/                          # 标准文件目录
└── logs/                              # 日志文件目录
```

## 后端目录 (backend/)

```
backend/
├── README.md                          # 后端说明文档
├── .env                               # 环境配置文件
├── acrac.env.example                  # 环境配置示例（复制为 .env 使用）
├── requirements.txt                   # Python依赖包
├── requirements-vector.txt            # 向量相关依赖
├── Dockerfile                         # Docker镜像构建文件
├── app/                               # 应用核心代码
│   ├── __init__.py
│   ├── main.py                        # FastAPI应用入口
│   ├── api/                           # API路由层
│   │   ├── __init__.py
│   │   ├── api_v1/                    # API v1版本
│   │   └── deps.py                    # 依赖注入
│   ├── core/                          # 核心配置
│   │   ├── __init__.py
│   │   ├── config.py                  # 配置管理
│   │   └── security.py                # 安全相关
│   ├── models/                        # 数据模型
│   │   ├── __init__.py
│   │   ├── acrac_models.py            # ACRAC业务模型
│   │   └── system_models.py           # 系统模型
│   ├── schemas/                       # 数据模式
│   │   ├── __init__.py
│   │   └── acrac_schemas.py           # API数据模式
│   ├── services/                      # 业务逻辑层
│   │   ├── __init__.py
│   │   ├── vector_search_service.py   # 向量搜索服务
│   │   ├── data_service.py            # 数据服务
│   │   └── recommendation_service.py  # 推荐服务
│   └── utils/                         # 工具函数
│       ├── __init__.py
│       └── helpers.py                 # 辅助函数
├── scripts/                           # 数据库构建脚本
│   ├── README.md                      # 脚本说明文档
│   ├── build_acrac_from_csv_siliconflow.py  # 主构建脚本
│   ├── test_clinical_scenarios.py     # 临床场景测试
│   ├── test_vector_search_simple.py   # 向量搜索测试
│   ├── run_vector_build.py            # 构建启动器
│   ├── README_向量数据库构建.md        # 构建详细文档
│   └── 00_create_tables.sql           # 数据库表创建脚本
├── alembic/                           # 数据库迁移
│   └── versions/                      # 迁移版本文件
├── tests/                             # 测试文件目录
├── logs/                              # 日志文件目录
└── venv/                              # Python虚拟环境
```

## 前端目录 (frontend/)

```
frontend/
├── README.md                          # 前端说明文档
├── package.json                       # Node.js依赖配置
├── package-lock.json                  # 依赖锁定文件
├── vite.config.ts                     # Vite构建配置
├── tsconfig.json                      # TypeScript配置
├── tsconfig.app.json                  # 应用TypeScript配置
├── tsconfig.node.json                 # Node TypeScript配置
├── index.html                         # HTML入口文件
├── public/                            # 静态资源
│   └── vite.svg                       # 网站图标
├── src/                               # 源代码目录
│   ├── main.ts                        # 应用入口
│   ├── App.vue                        # 根组件
│   ├── style.css                      # 全局样式
│   ├── env.d.ts                       # 环境类型声明
│   ├── vite-env.d.ts                  # Vite环境类型
│   ├── components/                    # Vue组件
│   │   ├── README.md                  # 组件说明
│   │   ├── common/                    # 通用组件
│   │   ├── medical/                   # 医疗相关组件
│   │   └── search/                    # 搜索相关组件
│   ├── views/                         # 页面视图
│   │   ├── HomeView.vue               # 首页
│   │   ├── SearchView.vue             # 搜索页面
│   │   └── AboutView.vue              # 关于页面
│   ├── stores/                        # 状态管理
│   │   ├── index.ts                   # 状态管理入口
│   │   ├── search.ts                  # 搜索状态
│   │   └── user.ts                    # 用户状态
│   ├── router/                        # 路由配置
│   │   └── index.ts                   # 路由定义
│   ├── api/                           # API客户端
│   │   └── client.ts                  # API客户端配置
│   ├── types/                         # TypeScript类型定义
│   │   ├── index.ts                   # 类型入口
│   │   └── medical.ts                 # 医疗相关类型
│   ├── utils/                         # 工具函数
│   │   └── helpers.ts                 # 辅助函数
│   └── locales/                       # 国际化
│       ├── index.ts                   # 国际化入口
│       └── zh.ts                      # 中文语言包
└── tests/                             # 测试文件目录
```

## 数据目录 (ACR_data/)

```
ACR_data/
├── ACR_final.csv                      # 主要数据文件
├── ACR_final.xlsx                     # Excel格式数据
├── procedure_standard.xlsx            # 检查项目标准
├── ACR_Rec.xlsx                       # 推荐数据
├── ACR_Rec_Filled.xlsx                # 填充后的推荐数据
├── ACR_NotRec.xlsx                    # 非推荐数据
├── merged_data.csv                    # 合并数据
└── 原始检查项目_with_merged_procedures.xlsx  # 原始检查项目
```

## 文档目录 (docs/)

```
docs/
├── ACRAC_V2_API使用指南.md             # API使用指南
├── ACRAC_V2_三个推荐方案API端点总结.md   # API端点总结
├── ACRAC_V2_三个推荐方法API使用指南.md   # 推荐方法指南
├── ACRAC_V2_临床案例推荐分析.md         # 临床案例分析
├── ACRAC_V2_开发指南.md                # 开发指南
├── ACRAC_V2_推荐方法优化方案.md         # 优化方案
├── ACRAC_V2_智能推荐系统实施完成报告.md  # 实施报告
├── ACRAC_V2_系统文档.md                # 系统文档
├── ACRAC_V2_项目完成检查清单.md         # 项目检查清单
├── ACRAC前端设计方案.md                # 前端设计方案
├── ACRAC系统开发检查清单.md            # 开发检查清单
├── ACRAC系统项目计划.md                # 项目计划
├── BGE-Large-ZH-Ollama集成总结.md      # 模型集成总结
├── Ollama-BGE配置指南.md               # 配置指南
├── 向量检索详细使用指南.md              # 向量检索指南
├── 开发计划.md                        # 开发计划
└── 快速启动指南.md                     # 快速启动指南
```

## 部署目录 (deployment/)

```
deployment/
├── docker/                            # Docker相关配置
├── nginx/                             # Nginx配置
├── postgres/                          # PostgreSQL配置
│   └── init.sql                       # 数据库初始化脚本
└── scripts/                           # 部署脚本
```

## 备份目录 (backup/)

```
backup/
├── legacy_code/                       # 过时代码备份
│   ├── backend/                       # 后端过时代码
│   │   ├── old_tests/                 # 过时测试文件
│   │   ├── old_analysis/              # 过时分析文件
│   │   └── scripts/                   # 过时脚本文件
│   └── [过时文档文件]                  # 过时文档
├── old_backend_code/                  # 旧后端代码
├── old_docs/                          # 旧文档
└── old_scripts/                       # 旧脚本
```

## 标准目录 (standard/)

```
standard/
├── 基础版本-V3.8.2标准检查项目-all.xlsx  # 基础标准
├── 核医学标准-pet.xlsx                 # 核医学标准
├── 核医学标准:pet:spect:多sheet.xlsx    # 核医学多sheet标准
└── 超声标准v1.1 1.xlsx                 # 超声标准
```

## 数据目录 (data/)

```
data/
├── ACR_Rec_test_32B_0829_lora.json   # 测试数据
├── ACR_Rec_test_32B_0829.json        # 测试数据
├── test_sample.csv                    # 测试样本
├── processed/                         # 处理后数据
└── raw/                              # 原始数据
```

## 文件说明

### 核心文件
- **README.md**: 项目主要说明文档
- **PROJECT_STATUS.md**: 项目当前状态报告
- **docker-compose.yml**: Docker容器编排配置

### 配置文件
- **backend/.env**: 后端环境配置
- **backend/requirements.txt**: Python依赖包
- **frontend/package.json**: Node.js依赖包

### 主要脚本
- **backend/scripts/build_acrac_from_csv_siliconflow.py**: 数据库构建主脚本
- **backend/scripts/test_clinical_scenarios.py**: 临床场景测试脚本
- **backend/scripts/test_vector_search_simple.py**: 向量搜索测试脚本

### 数据文件
- **ACR_data/ACR_final.csv**: 主要数据源文件
- **backend/app.db**: SQLite数据库文件（开发用）

## 目录使用指南

### 开发人员
1. **后端开发**: 主要工作在 `backend/` 目录
2. **前端开发**: 主要工作在 `frontend/` 目录
3. **数据工程**: 主要工作在 `ACR_data/` 和 `backend/scripts/` 目录

### 运维人员
1. **部署配置**: 查看 `deployment/` 目录
2. **Docker配置**: 查看 `docker-compose.yml`
3. **环境配置**: 查看 `backend/acrac.env.example`

### 测试人员
1. **功能测试**: 运行 `backend/scripts/` 中的测试脚本
2. **API测试**: 使用 `docs/` 中的API文档
3. **集成测试**: 参考 `PROJECT_STATUS.md`

---

**最后更新**: 2024年9月8日  
**维护者**: ACRAC开发团队
