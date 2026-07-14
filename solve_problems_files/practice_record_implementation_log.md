# 练习记录模块重构实施日志

## 日期：2026-06-28

## 实施概要

### 1. PracticeRecord 模型修复 ✅
**文件**: `backend/app/models/models.py`

- 新增 `subject_id` 列 (Integer, FK → question_subject)
- 新增 `type_id` 列 (Integer, FK → question_type)
- 新增 `practice_date` 列 (Date, 用于按日统计)
- `source_type` 从 Enum 改为 String(50), 支持更多来源类型
- 新增 `Date` 导入
- 新增 `subject` 和 `question_type` relationship

### 2. Practice API 重写 ✅
**文件**: `backend/app/api/v1/practice.py`

修复端点:
- `POST /api/practice/record` — 字段名修正 (answer_detail→answer, source→source_type)
- `GET /api/practice/records` — 查询字段修正

新增端点:
- `POST /api/practice/batch-record` — 批量提交练习记录 (交卷时一次性提交)
- `GET /api/practice/type-summary` — 按科目+子科目统计完成/未完成状态
- `GET /api/practice/stats-card` — 今日/本周/累计统计卡片 + 7天趋势数据

### 3. 自动迁移 ✅
**文件**: `backend/app/main.py`

新增 practice_record 表的自动列迁移:
- `subject_id` (INTEGER)
- `type_id` (INTEGER)
- `practice_date` (DATE)

### 4. exercise.vue 提交记录修复 ✅
**文件**: `src/views/exercise.vue`

- 新增 `submitPracticeRecords()` 方法
- 在 `handleSubmit()` 中调用，批量提交练习记录到 `/api/practice/batch-record`
- source 标记为 "快速练习"

### 5. 题库页面练习记录面板重设计 ✅
**文件**: `.vtj/vue/mjvdqdu1.vue` + `.vtj/files/mjvdqdu1.json`

新增/修改 UI 元素:
- **统计卡片**: 今日(题) / 本周(题)(点击展开图表) / 累计(题)
- **用时&正确率**: 显示今日做题用时和总体正确率 (绿色≥70%, 红色<70%)
- **题目类型进度**: 胶囊徽章列表
  - 红色边框+红色文字 = "未完成"
  - 绿色边框+绿色文字 = "已完成"
  - 点击胶囊跳转到对应答题页
  - 可滚动 (max-height: 200px)
- **本周趋势图表**: 点击"本周(题)"展开
  - 柱状图模式: 7天做题量条形图
  - 折线图模式: 7天趋势 SVG 折线图
  - 切换按钮 (📊 柱状 / 📈 折线)
- **刷新按钮**: 手动刷新练习数据
- 所有字体大小统一为 15px

### 6. 验证 ✅
- 后端应用正常加载，6个 practice 端点全部注册
- DSL 已同步，12 项变更入 `.vtj/files/mjvdqdu1.json`

## 涉及文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| backend/app/models/models.py | 修改 | 新增 subject_id/type_id/practice_date, Date导入 |
| backend/app/api/v1/practice.py | 重写 | 修正字段名+3个新端点 |
| backend/app/main.py | 修改 | 新增 practice_record 自动迁移 |
| src/views/exercise.vue | 修改 | 新增 submitPracticeRecords 方法 |
| .vtj/vue/mjvdqdu1.vue | 修改 | 重写练习记录面板模板+方法+CSS |
| .vtj/files/mjvdqdu1.json | 同步 | 12项变更已同步 |

## API 端点列表

| 端点 | 方法 | 说明 |
|------|------|------|
| /api/practice/record | POST | 单条练习记录 |
| /api/practice/batch-record | POST | 批量练习记录（新增） |
| /api/practice/records | GET | 查询练习历史 |
| /api/practice/type-summary | GET | 按类型统计完成/未完成（新增） |
| /api/practice/stats-card | GET | 统计卡片+7天趋势（新增） |
| /api/stats/practice-trend | GET | 原有趋势端点 |
