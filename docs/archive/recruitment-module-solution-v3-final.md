# 招考信息模块 VTJ 改造 —— 最终实施方案 v3

> 改造日期：2026-06-28
> 改造方式：通过 VTJ MCP 服务在 VTJ 设计器体系内完成
> **关键发现**：前两轮修改了孤立块 `hjv83oby`（零引用），v3 正确目标为 HomePage `jjvdntly.vue`

---

## 一、问题根因

```
实际渲染链路：
  src/router/index.ts → /home → jjvdntly.vue (HomePage, raw:true)
    └── <section class="recruit-section"> ← 用户实际看到的招考信息
         (内联实现，第19-86行)

  被误改的 hjv83oby.vue → 孤立块，无任何页面引用 → 前端零变化
```

---

## 二、改造文件清单

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `.vtj/vue/jjvdntly.vue` | Template 重写 | 箭头(›)+胶囊标签+删除card-footer |
| `.vtj/vue/jjvdntly.vue` | Style 重写 | 20px/纯白/无线条/胶囊三色/箭头动画 |
| `backend/app/models/models.py` | 新增字段 | registration_start / registration_end |
| `backend/app/services/recruitment_scraper.py` | 增强 | `_detect_registration_status()` 智能状态检测 |
| `backend/app/api/v1/recruitment.py` | 增强 | 返回 status_label / status_color |
| `recruitment_info` 表 | DDL | ALTER TABLE 添加 2 列 |

---

## 三、前端改动详情 (jjvdntly.vue)

### Template 变化

| 元素 | Before | After |
|------|--------|-------|
| 卡片头部右侧 | (空) | **箭头 `›`** (点击展开/收起，旋转90°) |
| 标题条目左侧 | 红色圆点 `recruit-title-dot` | **胶囊标签 `status-badge`** (正在报名/即将报名/报名结束) |
| 卡片底部 | "展开全部(N条)" 按钮 | **(已删除)** |
| 卡片头部分割线 | border-bottom | **已删除** |
| 条目内 tag | 小型文字标签 | **合并到胶囊标签** |
| 弹窗状态 | 旧 tag 标签 | **新增 capsule + 报名时间** |
| 空状态 | (无) | "暂无招考信息" |

### Style 变化

| 属性 | Before | After |
|------|--------|-------|
| 全局字体 | 10px~19px 混杂 | **统一 20px** |
| 卡片底色 | #ffffff | #ffffff ✅ |
| 条目分割 | gap:2px + 分割线 | **padding:9px 0 纯行高** |
| 胶囊标签颜色 | - | 正在报名=绿#10b981 / 即将报名=藏蓝#1a2a6c / 报名结束=红#c41e3a |
| 箭头大小 | - | 30px |
| 箭头展开动画 | - | rotate(90deg) + 变红 |

---

## 四、后端改动详情

### 模型 (models.py)
```python
registration_start = Column(String(50), comment="报名开始时间")  # 新增
registration_end = Column(String(50), comment="报名截止时间")    # 新增
```

### 爬虫 (recruitment_scraper.py)
- 新增 `_detect_registration_status(start, end, text)` 函数
- 优先级：日期比较 > 关键词检测 > 默认"正在报名"
- 日期解析支持 `2026-03-15` / `2026年3月15日` / `3月15日` 格式

### API (recruitment.py)
- 新增 `_compute_status_label(rec)` — 根据报名时间计算状态
- 新增 `_compute_status_color(label)` — 状态→颜色映射
- 返回新增字段：`status_label`, `status_color`, `registration_start`, `registration_end`

---

## 五、状态标签三色规范

| 状态 | CSS颜色 | 色值 | 触发条件 |
|------|---------|------|----------|
| 正在报名 | 绿色 | #10b981 | 当前时间在报名区间内 / 关键词"报名中" |
| 即将报名 | 藏蓝色 | #1a2a6c | 报名尚未开始 / 关键词"即将" |
| 报名结束 | 中国红 | #c41e3a | 报名已截止 / 关键词"截止" |

---

## 六、数据流

```
rszk.net (分类列表页)
    ↓ scraper: 标题 + URL + 报名时间提取
recruitment_info 表 (67条, 6分类)
    ↓ GET /api/recruitment?limit=10
JSON { items, status_label, status_color, registration_start/end }
    ↓ fetchRecruitment() → buildRecruitCards()
state.recruitCategories (v-for 渲染)
    ↓
2×3 网格 → 箭头(›)展开 → 胶囊标签 → 点击弹窗 → 查看原文
```

---

## 七、验证清单

| # | 验证项 | 状态 |
|---|--------|------|
| 1 | 2×3 网格布局 | ✅ |
| 2 | 箭头(›)每卡片头部右侧 | ✅ |
| 3 | 箭头点击旋转90°/展开10条 | ✅ |
| 4 | 胶囊标签三色显示 | ✅ |
| 5 | recruit-section 全部 20px | ✅ |
| 6 | 纯白底色无分割线 | ✅ |
| 7 | 详情弹窗(状态+报名时间+单位+条件+原文) | ✅ |
| 8 | 空状态"暂无招考信息" | ✅ |
| 9 | 后端 registration_start/end 字段 | ✅ |
| 10 | API 返回 status_label/status_color | ✅ |
