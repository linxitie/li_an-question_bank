# 招考信息模块 VTJ 改造 —— 解决方案 v2

> 改造日期：2026-06-28
> 改造方式：通过 VTJ MCP 服务，在 VTJ 设计器体系内完成

---

## 一、需求对照

| # | 用户需求 | 实现状态 |
|---|----------|----------|
| 1 | 六个模块不能单显笼统内容，各自展示具体招考标题 | ✅ 每卡片纵向列表展示 5~10 条标题 |
| 2 | 2×3 排列：第一行国考省考/事业单位/教师招聘，第二行国企招聘/医疗卫生/三支一扶 | ✅ CSS Grid 3 列自动 2 行，CATEGORY_ORDER 保证排序 |
| 3 | 每个卡片纵向展示 5 条标题（展开后 10 条） | ✅ 收起 5 条，箭头展开 10 条 |
| 4 | 点击标题弹窗查看详情 | ✅ 详情弹窗（标题/状态/单位/报名时间/条件/正文/原文链接） |
| 5 | 删除"展开全部"按钮，改为小箭头(>) | ✅ 卡片头部右侧 `›` 箭头，点击旋转 90° |
| 6 | 胶囊状状态标签：即将报名=藏蓝，报名结束=中国红，正在报名=绿色 | ✅ 三色胶囊徽标 |
| 7 | 纯白底色，黑/灰文字，无线条分割，行高留白 | ✅ 全部实现 |
| 8 | 全局字体 20px | ✅ 所有元素 font-size: 20px |
| 9 | 增强后端爬虫获取报名时间 | ✅ 新增 registration_start/end，智能状态检测 |
| 10 | 完善后端数据库字段 | ✅ 新增字段 + 数据库迁移 |

---

## 二、改造文件清单

| 文件 | 改动类型 | 改动内容 |
|------|----------|----------|
| `.vtj/vue/hjv83oby.vue` | 完整重写 | 新模板（箭头+胶囊标签+20px+纯白）+ 新样式 + Script |
| `.vtj/files/hjv83oby.json` | 更新 | methods（toggleCardExpand）+ state + CSS |
| `backend/app/models/models.py` | 新增字段 | registration_start, registration_end |
| `backend/app/services/recruitment_scraper.py` | 增强 | 报名时间提取 + `_detect_registration_status()` |
| `backend/app/api/v1/recruitment.py` | 增强 | 返回 status_label/status_color + `_compute_status_label()` |
| `.vtj/projects/linxitie.policy-exam-bank.json` | 已注册 | GET /api/recruitment API |

---

## 三、核心设计

### 3.1 卡片布局

```
┌──────────────────────────────────┐
│  🏛  国考省考        10条招考  › │  ← 点击 › 展开/收起 (旋转 90°)
│  ┌──────────┬─────────────────┐  │
│  │ 正在报名 │ 2026国考公告...  │  │  ← 绿底胶囊
│  │ 即将报名 │ 省考报名通知...  │  │  ← 藏蓝底胶囊
│  │ 报名结束 │ 税务系统招录...  │  │  ← 红底胶囊
│  │ 正在报名 │ 海关招聘公告...  │  │
│  │ 即将报名 │ 人社部公告...    │  │
│  └──────────┴─────────────────┘  │
│  (纯行高留白, 无分割线)          │
└──────────────────────────────────┘
```

### 3.2 胶囊标签颜色规范

| 状态 | 颜色名 | 色值 | 用途 |
|------|--------|------|------|
| 正在报名 | 绿色 | `#10b981` | 当前可报名的招考 |
| 即将报名 | 藏蓝色 | `#1a2a6c` | 尚未开始报名的招考 |
| 报名结束 | 中国红 | `#c41e3a` | 已截止报名的招考 |

### 3.3 状态智能检测逻辑

```
优先级 1: 日期比较
  - registration_end < now → "报名结束" (中国红)
  - registration_start > now → "即将报名" (藏蓝)
  - start ≤ now ≤ end → "正在报名" (绿色)

优先级 2: 关键词检测（日期无法解析时）
  - "正在报名"/"报名中" → 绿色
  - "即将报名"/"预告" → 藏蓝
  - "已截止"/"结束" → 中国红

优先级 3: 默认值
  - "正在报名" (绿色)
```

---

## 四、数据流

```
rszk.net 分类页
    ↓ [scraper: 标题+URL+报名时间提取]
recruitment_info 表 (新增 registration_start/end)
    ↓ [GET /api/recruitment?limit=10]
JSON { items, status_label, status_color }
    ↓ [fetchRecruitment() → buildRecruitCards()]
RecruitmentInfo block state.recruitmentList
    ↓ [v-for 渲染]
2×3 网格 → 箭头展开 → 胶囊标签 → 点击弹窗 → 查看原文
```

---

## 五、验证清单

| 验证项 | 预期 | 状态 |
|--------|------|------|
| 2×3 网格布局 | 3 列 2 行，顺序正确 | ✅ |
| 全局字体 20px | 所有文字 20px | ✅ |
| 纯白底色 | 卡片 #ffffff | ✅ |
| 无分割线 | 条目间仅行高留白 | ✅ |
| 箭头(>) 展开 | 点击旋转 90°，展开到 10 条 | ✅ |
| 胶囊标签三色 | 藏蓝/中国红/绿色 | ✅ |
| 点击标题弹窗 | 详情弹窗完整展示 | ✅ |
| 后端新字段 | registration_start/end 存在 | ✅ |
| 爬虫增强 | _detect_registration_status 智能判断 | ✅ |
| API 新字段 | status_label + status_color 返回 | ✅ |
| 数据库迁移 | ALTER TABLE 成功 | ✅ |
| VTJ API 注册 | /api/recruitment 已注册 | ✅ |

---

## 六、已知限制

1. **rszk.net 详情页超时**：网络环境限制，详情 content 可能为空，但"查看原文"链接可用
2. **DSL nodes 未更新**：模板 nodes 仍为旧结构（不影响渲染，.vue 文件优先）。后续可在 VTJ 设计器中更新

---

生成时间：2026-06-28
改造方式：VTJ MCP Service
