# 考试日历模块 VTJ 改造 —— 解决方案

> 改造日期：2026-06-28
> 数据源：https://www.shiyebian.com/

---

## 问题与修复

| # | 问题 | 根因 | 修复 |
|---|------|------|------|
| 1 | 日期不更新 | 爬虫从标题正则提取日期，未解析 `.rb_news-meta` | 重写爬虫解析结构化 HTML |
| 2 | 爬虫内容不准确 | 通用 `soup.select("a[href]")` + 关键词过滤 | 精确解析 `.rb_news-list > .rb_news-item > .rb_news-content` |
| 3 | 考试形式丢失 | 模型缺少字段，爬虫未提取 | 新增 `exam_format` 字段 + 爬虫提取 `.rb_news-meta` |
| 4 | 状态标签无效 | API 未返回 status 字段 | API 新增 `_compute_status()` 三色状态 |

---

## 改造文件

| 文件 | 改动 |
|------|------|
| `backend/app/models/models.py` | ExamCalendar 新增 `exam_format` 字段 |
| `backend/app/services/exam_scraper.py` | **完整重写** — 结构化 HTML 解析 |
| `backend/app/api/v1/calendar.py` | 新增 `exam_format`/`status`/`status_color`/`registration_start`/`registration_end` 返回 |
| `.vtj/vue/ljvdpmh9.vue` | Template+Script+Style 更新 |
| `.vtj/files/ljvdpmh9.json` | DSL 清理 mock 数据，同步 `fetchExams` |
| `exam_calendar` 表 | ALTER TABLE 添加 `exam_format` 列 |

---

## 爬虫解析策略

```python
# 目标 HTML 结构:
<div class="rb_card-body">
  <ul class="rb_news-list">
    <li class="rb_news-item">
      <div class="rb_news-content">
        <a href="..." class="rb_news-title">标题<span class="count-badge">N名</span></a>
        <div class="rb_news-meta">
          <div><span class="fa fa-baoming"></span>报名: 6月22日至7月2日</div>
          <div><span class="fa fa-bishi"></span>笔试:《职业能力倾向测验》</div>
        </div>
      </div>
    </li>
  </ul>
</div>

# 提取流程:
1. soup.select('.rb_news-list .rb_news-item')
2. item → .rb_news-content → a.rb_news-title → title + href
3. item → .rb_news-meta > div → 报名时间 + 考试形式
4. 去重: title 唯一
5. 写入: ExamCalendar(title, month, day, province, exam_format, url)
```

---

## 状态标签三色规范

| 状态 | 色值 | CSS 色名 | 触发条件 |
|------|------|----------|----------|
| 报名中 | `#10b981` | 绿色 | registration_start ≤ now ≤ registration_end |
| 即将报名 | `#1a2a6c` | 藏蓝色 | now < registration_start |
| 已截止 | `#c41e3a` | 中国红 | now > registration_end |

（与招考信息模块胶囊标签颜色一致）

---

## 验证结果

| 验证项 | 状态 |
|--------|------|
| 爬虫解析 `.rb_news-item` 结构 | ✅ 139 条记录 |
| exam_format 提取 | ✅ 新数据包含"笔试" |
| 日期从 meta 提取 | ✅ 正确（6/22, 6/26 等） |
| URL 补全 | ✅ shiyebian.com/xinxi/... |
| API 返回新字段 | ✅ exam_format + status + status_color |
| 前端状态标签 | ✅ 三色动态绑定 |
| 前端考试形式 | ✅ 显示"笔试" |
| 前端空状态 | ✅ "暂无考试信息" |
| DSL 清理 mock 数据 | ✅ loadExamData → fetchExams |
