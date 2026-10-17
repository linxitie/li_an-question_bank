# 考试日历模块 v2 改造 —— 解决方案

> 改造日期：2026-06-28
> 数据源：https://www.shiyebian.com/
> 前端文件：`.vtj/vue/ljvdpmh9.vue`（HomePage 实际引用）

---

## 改造成果

| # | 改造项 | 改造前 | 改造后 |
|---|--------|--------|--------|
| 1 | 数据 | 139条旧数据，无考试形式 | 清库重爬，6条最新数据，全部含考试形式 |
| 2 | 过期清理 | 无 | `cleanup_expired_exams()` — 已截止>1天自动硬删除 |
| 3 | 排序 | 仅按日期升序 | 报名中(0) → 即将报名(1) → 已截止(2)，同状态按日期 |
| 4 | 定时爬取 | 每日00:10 | 每日**00:00**准时爬取+清理 |
| 5 | 卡片底色 | 纯白 #ffffff | **浅蓝 #e8f4fd**（清爽专业） |
| 6 | 列表条目 | 灰底 #f8f9fc | **纯白 #ffffff** 卡片+大圆角14px，浮在浅蓝背景上 |
| 7 | 装饰图标 | 无 | 右上角半透明日历图标 (opacity: 0.15) |
| 8 | 信息层级 | 标题+地名 | 深色加粗标题 + 浅灰元信息(地区/考试形式/报名时间) |
| 9 | 状态标签 | 无颜色绑定 | 三色胶囊（报名中=绿, 即将报名=藏蓝, 已截止=红） |

---

## 修改文件

| 文件 | 操作 |
|------|------|
| `backend/app/services/exam_scraper.py` | 新增 `cleanup_expired_exams()`, `clear_all_exams()`, 更新 `scrape_all_exams()` |
| `backend/app/api/v1/calendar.py` | API排序：报名中优先，新增 `_compute_status()` 时间判定 |
| `backend/app/services/scheduler.py` | 考试日历爬取时间改为 00:00 |
| `.vtj/vue/ljvdpmh9.vue` | **完整UI重写**：浅蓝底色+纯白条目+大圆角+装饰图标 |
| `.vtj/files/ljvdpmh9.json` | DSL清理+同步 fetchExams |
| `exam_calendar` 表 | 清库 → 重爬 → 6条最新数据 |

---

## 时间判定逻辑

```python
def _compute_status(e):
    now = datetime.now()
    if e.registration_end and e.registration_end < now:  return "已截止"
    if e.registration_start and e.registration_start > now: return "即将报名"
    if start ≤ now ≤ end:                                   return "报名中"
    if e.exam_date and e.exam_date < now:                  return "已截止"
    return "报名中"
```

---

## 状态标签颜色

| 状态 | 色值 | 说明 |
|------|------|------|
| 报名中 | `#10b981` 绿色 | 当前正在报名 |
| 即将报名 | `#1a2a6c` 藏蓝色 | 尚未开始 |
| 已截止 | `#c41e3a` 中国红 | 报名已结束 |

---

## 自动清理规则

- 考试日期（exam_date）距今超过1天 → 后端硬删除
- 调度器每日 00:00 先执行清理，再爬取最新
- 前端API排序保证"报名中"始终在最前面
