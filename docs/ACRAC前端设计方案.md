# ACRAC系统前端设计方案

## 1. 设计原则

### 1.1 医疗专业性原则
- **专业导向**：界面设计符合医疗专业人员使用习惯
- **信息密度**：高效展示大量结构化医疗数据
- **层级清晰**：四层数据结构（Panel→Topic→Variant→Procedure）直观呈现
- **证据可追溯**：每个推荐都能查看完整的证据链和推理过程

### 1.2 用户体验原则
- **直观性**：无需培训即可快速上手
- **效率性**：减少用户操作步骤，提高查询效率
- **一致性**：统一的交互模式和视觉风格
- **容错性**：友好的错误提示和处理机制

### 1.3 技术设计原则
- **组件化**：高度可复用的Vue组件
- **响应式**：适配不同设备和屏幕尺寸
- **渐进式**：支持功能模块的逐步扩展
- **国际化**：完整的中英文支持

## 2. 视觉设计风格

### 2.1 色彩方案
```scss
// 主色调 - 医疗蓝
$primary-color: #2E86AB;        // 主蓝色
$primary-light: #5BA3C7;       // 浅蓝色  
$primary-dark: #1A5F80;        // 深蓝色

// 功能色彩
$success-color: #28A745;       // 成功绿
$warning-color: #FFC107;       // 警告橙
$error-color: #DC3545;         // 错误红
$info-color: #17A2B8;          // 信息青

// 中性色
$white: #FFFFFF;
$gray-50: #F8F9FA;
$gray-100: #E9ECEF;
$gray-200: #DEE2E6;
$gray-300: #CED4DA;
$gray-500: #6C757D;
$gray-700: #495057;
$gray-900: #212529;

// 医疗专业色
$appropriateness-high: #28A745;    // 通常适宜
$appropriateness-medium: #FFC107;  // 可能适宜
$appropriateness-low: #DC3545;     // 通常不适宜
```

### 2.2 字体系统
```scss
// 中文字体
font-family-zh: 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;

// 英文字体  
font-family-en: 'Roboto', 'Arial', sans-serif;

// 字号系统
font-size-xs: 12px;     // 辅助信息
font-size-sm: 14px;     // 正文
font-size-base: 16px;   // 基础字号
font-size-lg: 18px;     // 小标题
font-size-xl: 20px;     // 中标题
font-size-2xl: 24px;    // 大标题
font-size-3xl: 30px;    // 页面标题
```

## 3. 页面架构设计

### 3.1 整体布局
```
┌─────────────────────────────────────────────────────────────┐
│                    顶部导航栏 (Header)                        │
│  Logo | 主导航 | 搜索框 | 语言切换 | 用户菜单                 │
├─────────────────────────────────────────────────────────────┤
│         │                                                   │
│  侧边菜单 │                 主内容区                          │
│         │            (Dynamic Content)                      │
│  - 数据浏览│                                                │
│  - 智能检索│                                                │
│  - 数据管理│                                                │
│  - 推理服务│                                                │
│  - 系统设置│                                                │
│         │                                                   │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 核心组件设计

#### (1) 数据浏览组件 `DataBrowser`
```vue
<template>
  <!-- 四层级展示模式 -->
  <div class="data-browser">
    <!-- 面包屑导航 -->
    <BreadcrumbNav :path="currentPath" />
    
    <!-- 层级展示卡片 -->
    <div class="hierarchy-container">
      <!-- Panel 层级 -->
      <DataCard
        v-if="!selectedPanel"
        type="panel" 
        :items="panels"
        @select="selectPanel"
        :loading="panelsLoading"
      />
      
      <!-- Topic 层级 -->
      <DataCard
        v-if="selectedPanel && !selectedTopic"
        type="topic"
        :items="topics" 
        @select="selectTopic"
        @back="resetPanel"
        :loading="topicsLoading"
      />
      
      <!-- Variant 层级 -->
      <DataCard
        v-if="selectedTopic && !selectedVariant"
        type="variant"
        :items="variants"
        @select="selectVariant" 
        @back="resetTopic"
        :loading="variantsLoading"
      />
      
      <!-- Procedure 详情 -->
      <ProcedureDetails
        v-if="selectedVariant"
        :procedures="procedures"
        @back="resetVariant"
        :loading="proceduresLoading"
      />
    </div>
  </div>
</template>
```

#### (2) 通用数据卡片 `DataCard`
```vue
<template>
  <div class="data-card">
    <div class="card-header">
      <h2>{{ title }}</h2>
      <div class="card-actions">
        <SearchInput @search="handleSearch" />
        <SortSelector @sort="handleSort" />
      </div>
    </div>
    
    <div class="card-content">
      <!-- 网格展示模式 -->
      <div class="items-grid">
        <div 
          v-for="item in paginatedItems" 
          :key="item.id"
          class="item-card"
          @click="selectItem(item)"
        >
          <div class="item-title">
            {{ currentLang === 'zh' ? item.name_zh : item.name_en }}
          </div>
          <div class="item-subtitle" v-if="item.description">
            {{ item.description }}
          </div>
          <div class="item-meta">
            <Badge :type="getItemType(item)" :text="getItemBadge(item)" />
          </div>
        </div>
      </div>
      
      <!-- 分页 -->
      <Pagination
        :current="currentPage"
        :total="totalItems"
        :pageSize="pageSize"
        @change="handlePageChange"
      />
    </div>
  </div>
</template>
```

#### (3) 检查项目详情 `ProcedureDetails`
```vue
<template>
  <div class="procedure-details">
    <div class="details-header">
      <h2>检查项目详情</h2>
      <div class="header-actions">
        <LanguageToggle v-model="displayLang" />
        <ExportButton @export="exportProcedures" />
      </div>
    </div>
    
    <div class="procedures-list">
      <div 
        v-for="procedure in procedures" 
        :key="procedure.id"
        class="procedure-item"
        :class="getAppropriateness(procedure.rating)"
      >
        <!-- 项目信息 -->
        <div class="procedure-info">
          <h3>{{ displayLang === 'zh' ? procedure.name_zh : procedure.name_en }}</h3>
          <div class="procedure-meta">
            <AppropriatenessTag :category="procedure.appropriateness_category_zh" />
            <RatingDisplay :rating="procedure.rating" :median="procedure.median" />
            <RadiationLevel :adult="procedure.adult_rrl" :pediatric="procedure.peds_rrl" />
          </div>
        </div>
        
        <!-- 推荐理由 -->
        <div class="recommendation-content" v-if="procedure.recommendation_zh">
          <h4>推荐理由</h4>
          <ExpandableText 
            :content="displayLang === 'zh' ? procedure.recommendation_zh : procedure.recommendation_en"
            :maxLines="3"
          />
        </div>
        
        <!-- 证据强度 -->
        <div class="evidence-level">
          <EvidenceTag :soe="procedure.soe" />
        </div>
      </div>
    </div>
  </div>
</template>
```

## 4. 页面设计方案

### 4.1 主要页面列表

| 页面 | 路由 | 功能描述 | 主要组件 |
|------|------|----------|----------|
| 首页 | `/` | 系统概览、快速导航 | `Dashboard`, `QuickStats`, `RecentActivity` |
| 数据浏览 | `/browse` | 四层级数据浏览 | `DataBrowser`, `HierarchyNav`, `DataCard` |
| 智能检索 | `/search` | 多维度搜索和筛选 | `SearchInterface`, `FilterPanel`, `ResultsList` |
| 数据管理 | `/manage` | 数据CRUD操作 | `DataTable`, `EditForm`, `BulkActions` |
| 推理服务 | `/inference` | AI推理和推荐 | `QueryInput`, `InferenceEngine`, `ResultsDisplay` |
| 字典维护 | `/dictionary` | 数据字典管理 | `DictManager`, `DictEditor`, `VersionControl` |
| 用户管理 | `/users` | 用户和权限管理 | `UserTable`, `RoleManager`, `AuditLog` |
| 系统设置 | `/settings` | 系统配置 | `SettingsPanel`, `ConfigForm`, `SystemInfo` |

### 4.2 核心页面设计

#### (1) 首页设计
```vue
<!-- Dashboard Layout -->
<template>
  <div class="dashboard">
    <!-- 统计卡片区 -->
    <div class="stats-section">
      <StatsCard icon="database" :value="totalData.panels" label="专科领域" color="blue" />
      <StatsCard icon="topics" :value="totalData.topics" label="临床主题" color="green" />
      <StatsCard icon="variants" :value="totalData.variants" label="临床情境" color="orange" />
      <StatsCard icon="procedures" :value="totalData.procedures" label="检查项目" color="purple" />
    </div>
    
    <!-- 快速导航 -->
    <div class="quick-nav">
      <QuickNavCard 
        icon="search" 
        title="智能检索" 
        description="基于关键词快速查找相关检查项目"
        @click="$router.push('/search')"
      />
      <QuickNavCard 
        icon="browse" 
        title="数据浏览" 
        description="按专科和主题浏览完整数据结构"
        @click="$router.push('/browse')"
      />
      <QuickNavCard 
        icon="ai" 
        title="AI推理" 
        description="基于临床场景智能推荐检查方案"
        @click="$router.push('/inference')"
      />
    </div>
    
    <!-- 最近活动 -->
    <div class="recent-activity">
      <ActivityTimeline :activities="recentActivities" />
    </div>
  </div>
</template>
```

#### (2) 数据浏览页面设计
```vue
<!-- 层级浏览设计 -->
<template>
  <div class="browse-page">
    <!-- 导航栏 -->
    <div class="browse-header">
      <BreadcrumbNav :path="navigationPath" />
      <div class="header-controls">
        <SearchBox v-model="searchKeyword" />
        <LanguageSwitch v-model="currentLanguage" />
        <ViewModeToggle v-model="viewMode" :options="['grid', 'list', 'tree']" />
      </div>
    </div>
    
    <!-- 主内容 -->
    <div class="browse-content">
      <!-- 左侧层级树（可选显示） -->
      <div class="hierarchy-tree" v-if="showTree">
        <DataTreeNav 
          :data="hierarchyTree"
          :selected="currentSelection"
          @navigate="handleTreeNavigation"
        />
      </div>
      
      <!-- 右侧详情展示 -->
      <div class="content-area">
        <!-- 当前层级展示 -->
        <transition name="fade" mode="out-in">
          <component 
            :is="currentComponent"
            :data="currentData"
            :loading="loading"
            @navigate="handleNavigation"
            @select="handleSelection"
          />
        </transition>
      </div>
    </div>
  </div>
</template>
```

#### (3) 智能检索页面设计
```vue
<!-- 检索界面设计 -->
<template>
  <div class="search-page">
    <!-- 搜索区域 -->
    <div class="search-section">
      <div class="search-input-area">
        <AdvancedSearchBox
          v-model="searchQuery"
          :placeholder="$t('search.placeholder')"
          @search="performSearch"
          @voice-input="handleVoiceInput"
        />
        
        <!-- 搜索建议 -->
        <SearchSuggestions 
          v-if="showSuggestions"
          :suggestions="searchSuggestions"
          @select="selectSuggestion"
        />
      </div>
      
      <!-- 筛选面板 -->
      <div class="filter-panel">
        <FilterGroup 
          title="专科筛选" 
          :options="panelOptions" 
          v-model="selectedPanels"
        />
        <FilterGroup 
          title="适宜性" 
          :options="appropriatenessOptions" 
          v-model="selectedAppropriateness"
        />
        <RangeFilter
          title="评分范围"
          :min="0" :max="10"
          v-model="ratingRange"
        />
      </div>
    </div>
    
    <!-- 结果展示 -->
    <div class="results-section">
      <div class="results-header">
        <ResultsInfo 
          :total="searchResults.total"
          :time="searchResults.time"
        />
        <SortOptions
          v-model="sortBy"
          :options="sortOptions"
        />
      </div>
      
      <!-- 搜索结果 -->
      <div class="results-list">
        <SearchResultCard
          v-for="result in searchResults.items"
          :key="result.id"
          :result="result"
          :highlight="searchKeyword"
          @view-detail="viewDetail"
        />
      </div>
      
      <!-- 分页 -->
      <Pagination
        :current="currentPage"
        :total="searchResults.total"
        :pageSize="pageSize"
        @change="handlePageChange"
      />
    </div>
  </div>
</template>
```

## 3. 组件库设计

### 3.1 基础组件

#### 数据展示组件
- `DataCard` - 通用数据卡片
- `DataTable` - 数据表格（支持排序、筛选）
- `StatCard` - 统计信息卡片
- `InfoPanel` - 信息面板
- `DetailsDrawer` - 详情抽屉

#### 导航组件
- `BreadcrumbNav` - 面包屑导航
- `SideMenu` - 侧边菜单
- `TabNav` - 标签页导航
- `HierarchyTree` - 层级树形导航

#### 搜索组件
- `SearchBox` - 搜索框
- `AdvancedSearch` - 高级搜索
- `FilterPanel` - 筛选面板
- `SearchResults` - 搜索结果

#### 表单组件
- `FormBuilder` - 动态表单构建
- `FieldEditor` - 字段编辑器
- `FileUploader` - 文件上传
- `ValidationTooltip` - 验证提示

### 3.2 业务组件

#### 医疗数据专用组件
- `AppropriatenessTag` - 适宜性标签
- `RatingDisplay` - 评分显示
- `RadiationLevel` - 辐射剂量指示
- `EvidenceTag` - 证据强度标签
- `RecommendationCard` - 推荐理由卡片

#### 国际化组件
- `LanguageSwitch` - 语言切换器
- `LocalizedText` - 本地化文本显示
- `BilingualEditor` - 双语编辑器

## 4. 技术架构

### 4.1 技术栈
```json
{
  "framework": "Vue 3.3+",
  "language": "TypeScript",
  "ui_library": "Element Plus",
  "state_management": "Pinia", 
  "routing": "Vue Router 4",
  "http_client": "Axios",
  "i18n": "Vue I18n 9",
  "charts": "ECharts",
  "icons": "Element Plus Icons",
  "css": "SCSS + CSS Modules"
}
```

### 4.2 目录结构
```
frontend/
├── src/
│   ├── assets/           # 静态资源
│   │   ├── images/
│   │   ├── icons/
│   │   └── styles/
│   ├── components/       # 通用组件
│   │   ├── base/         # 基础组件
│   │   ├── business/     # 业务组件
│   │   └── layout/       # 布局组件
│   ├── views/           # 页面组件
│   │   ├── Dashboard.vue
│   │   ├── Browse/
│   │   ├── Search/
│   │   ├── Manage/
│   │   └── Settings/
│   ├── router/          # 路由配置
│   ├── stores/          # 状态管理
│   │   ├── user.ts
│   │   ├── data.ts
│   │   └── settings.ts
│   ├── utils/           # 工具函数
│   ├── locales/         # 国际化文件
│   │   ├── zh.ts
│   │   └── en.ts
│   ├── types/           # TypeScript类型定义
│   └── api/             # API接口封装
```

## 5. 数据展示设计

### 5.1 适宜性可视化
```scss
.appropriateness {
  &.usually-appropriate {
    background: linear-gradient(135deg, #d4edda, #c3e6cb);
    border-left: 4px solid #28a745;
  }
  
  &.may-be-appropriate {
    background: linear-gradient(135deg, #fff3cd, #ffeaa7);
    border-left: 4px solid #ffc107;
  }
  
  &.usually-not-appropriate {
    background: linear-gradient(135deg, #f8d7da, #f5c2c7);
    border-left: 4px solid #dc3545;
  }
}
```

### 5.2 评分可视化
```vue
<!-- 评分圆形进度条 -->
<template>
  <div class="rating-display">
    <div class="rating-circle" :style="circleStyle">
      <span class="rating-value">{{ rating }}</span>
    </div>
    <div class="rating-label">
      {{ $t('rating.label') }}
    </div>
  </div>
</template>
```

### 5.3 辐射剂量可视化
```vue
<!-- 辐射剂量指示器 -->
<template>
  <div class="radiation-indicator">
    <div class="radiation-level">
      <div 
        v-for="level in radiationLevels" 
        :key="level"
        class="level-bar"
        :class="{ active: level <= currentLevel }"
      />
    </div>
    <span class="radiation-text">{{ radiationText }}</span>
  </div>
</template>
```

## 6. 响应式设计

### 6.1 断点设计
```scss
// 响应式断点
$breakpoints: (
  xs: 0,
  sm: 576px,   // 手机
  md: 768px,   // 平板
  lg: 992px,   // 小屏桌面
  xl: 1200px,  // 大屏桌面
  xxl: 1400px  // 超大屏
);
```

### 6.2 适配策略
- **桌面端(≥992px)**：完整功能，双栏布局
- **平板端(768-991px)**：简化布局，单栏为主
- **手机端(<768px)**：核心功能，抽屉式导航

## 7. 国际化方案

### 7.1 语言配置
```typescript
// locales/zh.ts
export default {
  nav: {
    dashboard: '首页',
    browse: '数据浏览',
    search: '智能检索',
    manage: '数据管理',
    inference: '推理服务'
  },
  data: {
    panel: '专科',
    topic: '临床主题',
    variant: '临床情境', 
    procedure: '检查项目'
  },
  appropriateness: {
    'Usually appropriate': '通常适宜',
    'May be appropriate': '可能适宜',
    'Usually not appropriate': '通常不适宜'
  }
}

// locales/en.ts  
export default {
  nav: {
    dashboard: 'Dashboard',
    browse: 'Browse Data',
    search: 'Smart Search',
    manage: 'Data Management',
    inference: 'Inference Service'
  }
  // ... 英文配置
}
```

### 7.2 动态语言切换
```vue
<!-- 语言切换组件 -->
<template>
  <div class="language-switcher">
    <el-switch
      v-model="isEnglish"
      :active-text="$t('lang.en')"
      :inactive-text="$t('lang.zh')"
      @change="handleLanguageChange"
    />
  </div>
</template>

<script setup lang="ts">
const { locale } = useI18n()
const isEnglish = ref(locale.value === 'en')

const handleLanguageChange = (value: boolean) => {
  locale.value = value ? 'en' : 'zh'
  // 保存到localStorage
  localStorage.setItem('preferred-language', locale.value)
  // 更新API请求头
  updateApiLanguage(locale.value)
}
</script>
```

## 8. 交互设计细节

### 8.1 层级导航体验
- **渐进式导航**：Panel→Topic→Variant→Procedure逐层深入
- **面包屑回退**：点击任意层级快速返回
- **侧边树形导航**：提供全局视图和快速定位
- **搜索定位**：搜索结果直接定位到具体层级

### 8.2 数据加载策略
- **懒加载**：按需加载下级数据
- **预加载**：预取用户可能访问的数据
- **缓存策略**：合理缓存已加载的数据
- **Loading状态**：优雅的加载动画

### 8.3 错误处理设计
- **网络错误**：友好的重试机制
- **数据为空**：引导用户的空状态页
- **权限不足**：清晰的权限说明
- **操作失败**：具体的错误信息和建议

## 9. 性能优化策略

### 9.1 代码分割
```typescript
// 路由懒加载
const routes = [
  {
    path: '/browse',
    component: () => import('@/views/Browse/index.vue')
  },
  {
    path: '/search', 
    component: () => import('@/views/Search/index.vue')
  }
]
```

### 9.2 虚拟滚动
```vue
<!-- 大数据量列表使用虚拟滚动 -->
<template>
  <VirtualList
    :items="procedures"
    :item-height="80"
    :container-height="600"
  >
    <template #item="{ item }">
      <ProcedureCard :procedure="item" />
    </template>
  </VirtualList>
</template>
```

## 10. 开发计划

### 10.1 第一阶段：基础框架（1周）
- [ ] Vue3项目搭建
- [ ] 路由和布局配置
- [ ] 基础组件库建立
- [ ] API接口封装
- [ ] 国际化配置

### 10.2 第二阶段：核心页面（1.5周）
- [ ] 首页Dashboard
- [ ] 数据浏览页面
- [ ] 四层级导航组件
- [ ] 数据展示组件
- [ ] 搜索功能

### 10.3 第三阶段：高级功能（1.5周）
- [ ] 数据管理界面
- [ ] 用户权限系统
- [ ] 数据字典管理
- [ ] 导入导出功能
- [ ] 系统设置页面

## 11. 设计稿预览

### 11.1 首页设计
```
┌─────────────────────────────────────────────────────────────┐
│ ACRAC 影像学检查适宜性数据库           🌐 中文 | English  👤    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  📊 系统概览                                                │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐              │
│  │   13    │ │   285   │ │  1391   │ │ 15974   │              │
│  │  专科    │ │ 临床主题 │ │ 临床情境 │ │ 检查项目 │              │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘              │
│                                                             │
│  🚀 快速导航                                                │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐              │
│  │  🔍 智能检索  │ │  📚 数据浏览  │ │  🧠 AI推理   │              │
│  │  快速查找    │ │  层级浏览    │ │  智能推荐    │              │
│  └─────────────┘ └─────────────┘ └─────────────┘              │
└─────────────────────────────────────────────────────────────┘
```

### 11.2 数据浏览页设计
```
┌─────────────────────────────────────────────────────────────┐
│ 首页 > 数据浏览                    🔍 搜索框     🌐 中文     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  选择专科领域：                                             │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐              │
│  │ 🫀 心血管内科  │ │ 🧠 神经内科   │ │ 🫁 呼吸内科   │              │
│  │ 285个主题   │ │ 156个主题   │ │ 198个主题   │              │
│  └─────────────┘ └─────────────┘ └─────────────┘              │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐              │
│  │ 🩻 放射科    │ │ 👩‍⚕️ 妇产科    │ │ 👶 儿科      │              │
│  │ 423个主题   │ │ 167个主题   │ │ 234个主题   │              │
│  └─────────────┘ └─────────────┘ └─────────────┘              │
│                                                             │
│  第1页 / 共3页                          [<] [1] [2] [3] [>]  │
└─────────────────────────────────────────────────────────────┘
```

## 12. 用户测试方案

### 12.1 可用性测试
- **任务场景**：临床医生查找特定检查项目
- **测试指标**：任务完成率、操作时长、错误率
- **用户群体**：放射科医生、临床医生、医学生

### 12.2 性能测试
- **加载时间**：首屏加载 < 3秒
- **交互响应**：点击响应 < 200ms
- **搜索性能**：搜索结果返回 < 1秒

## 13. 无障碍设计

### 13.1 可访问性要求
- **键盘导航**：所有功能支持键盘操作
- **屏幕阅读器**：ARIA标签完整
- **颜色对比度**：符合WCAG 2.1 AA标准
- **字体大小**：支持用户自定义缩放

### 13.2 多语言支持
- **RTL支持**：预留从右到左语言支持
- **字体适配**：不同语言使用最佳字体
- **格式适配**：日期、数字格式本地化

---

## ❓ 确认要点

请您确认以下关键设计决策：

1. **🎨 视觉风格**：是否同意采用医疗蓝主色调的专业风格？
2. **📱 响应式策略**：是否桌面优先，平板适配，手机精简？
3. **🌐 国际化方案**：是否采用完整的中英文双语支持？
4. **📊 数据展示**：是否使用卡片式网格布局展示层级数据？
5. **🔍 搜索体验**：是否需要高级搜索和智能建议功能？
6. **📈 可视化需求**：评分、适宜性、辐射剂量的图形化展示方案是否合适？

请告诉我您的意见，我会根据您的反馈调整设计方案，然后开始前端开发！
