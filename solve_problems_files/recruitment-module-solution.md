# 招考信息模块 VTJ 改造 —— 解决方案

## 问题概述

招考信息模块（RecruitmentInfo 块 `hjv83oby`）存在以下问题：
1. 六个模块各自笼统展示部分内容，无法显示具体招考标题
2. 不能点击标题查看招考详情
3. 布局不是 2×3 网格
4. 没有"展开全部"按钮
5. VTJ 未将后端数据正确输入到前端

## 根因分析

| 问题 | 根因 | 严重程度 |
|------|------|----------|
| 六模块只显示笼统信息 | Vue 模板仅有分类卡片（图标+名称+数量），无标题列表 | 🔴 核心 |
| 无法点击查看详情 | 无详情弹窗组件，`handleRecruitmentClick` 仅弹出 toast | 🔴 核心 |
| 布局非 2×3 | CSS 使用 `grid-template-columns: repeat(6, 1fr)`（6 列单行） | 🟡 中等 |
| 无"展开全部" | 未实现 expand/collapse 逻辑 | 🟡 中等 |
| 数据未流向前端 | fetchRecruitment 仅提取 count，不保存 items 数组 | 🔴 核心 |
| VTJ API 未注册 | /api/recruitment 未在 VTJ 项目中注册 | 🟡 中等 |

## 解决方案

### 1. 前端 Vue 文件重写（.vtj/vue/hjv83oby.vue）

**模板改造**：
- 布局：`grid-template-columns: repeat(3, 1fr)` → 3 列自动形成 2 行
- 响应式：≤900px → 2 列，≤600px → 1 列
- 每卡片结构：card-header（图标+分类+数量）→ title-list（5 条标题）→ card-expand-btn（展开全部）
- 新增详情弹窗：modal-overlay + modal（标题/标签/条件/详情/原文链接）
- 加载态 + 空状态处理

**Script 改造**：
- 新增方法：fetchRecruitment, buildRecruitCards, buildEmptyCards, toggleExpand, openDetail, closeDetail
- 状态管理：recruitmentList（含 allItems 数组）, showModal, selectedRecruit, recruitLoading
- CATEGORY_ORDER 确保排序：国考省考→事业单位→教师招聘→国企招聘→医疗卫生→三支一扶

### 2. VTJ DSL 同步（.vtj/files/hjv83oby.json）
- methods 更新：移除 handleRecruitmentClick，新增 9 个 methods
- state 更新：新增 recruitLoading, recruitLoaded, showModal, selectedRecruit
- lifeCycles 新增：mounted

### 3. VTJ API 注册（.vtj/projects/linxitie.policy-exam-bank.json）
- 新增 API：GET /api/recruitment，名称为 getRecruitment

### 4. 后端爬虫优化（backend/app/services/recruitment_scraper.py）
- 详情页超时从 20s → 10s
- 添加 encoding 自动检测
- 降低请求延迟 1.0~2.0s → 0.5~1.5s

## 改造文件清单

```
.vtj/vue/hjv83oby.vue                          # 完整重写（template+script+style）
.vtj/files/hjv83oby.json                        # 更新 methods/state/lifeCycles
.vtj/projects/linxitie.policy-exam-bank.json     # 新增 recruitment API
backend/app/services/recruitment_scraper.py      # 优化超时和编码
```

## 数据流

```
rszk.net (分类列表页)
    ↓ [scraper: 标题+URL 提取]
recruitment_info 表 (MySQL, 当前 67 条)
    ↓ [GET /api/recruitment?limit=10]
JSON { items: { "国考省考": [...], ... } }
    ↓ [fetchRecruitment() → buildRecruitCards()]
RecruitmentInfo block state.recruitmentList
    ↓ [v-for 渲染]
2×3 网格 → 每卡片 5 条标题 → 点击弹窗 → 查看原文
```

## 当前状态

| 检查项 | 状态 |
|--------|------|
| 2×3 网格布局 | ✅ 已实现 |
| 每卡片纵向 5 条标题 | ✅ 已实现 |
| 点击标题查看详情 | ✅ 已实现（弹窗） |
| "展开全部"按钮 | ✅ 已实现（>5 条时显示） |
| 后端 API 数据 | ✅ 67 条记录，6 分类 |
| VTJ API 注册 | ✅ 已注册 |
| 详情内容爬取 | ⚠️ rszk.net 超时，内容为空（原文链接可用） |

## 待改进项

1. **爬虫详情抓取**：rszk.net 可能需使用代理或不同策略
2. **DSL nodes 同步**：需通过 VTJ 设计器更新 nodes 以消除一致性警告
3. **详情内容缓存**：考虑增加本地缓存减少重复爬取

---

生成时间：2026-06-28
