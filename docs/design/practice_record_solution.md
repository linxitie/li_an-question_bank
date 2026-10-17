# 练习记录模块重构方案

## 问题诊断

### 问题1: 无独立练习记录模块
当前练习记录功能分散在：
- 题库页面 (mjvdqdu1) 右侧面板 — 仅显示简单计数
- 成绩分析页 (sjvdul3v) — 聚合统计，无单次记录
- 首页签到卡 (wjve09k1) — 仅签到数据

用户无法查看"今天做了多少题""哪些题型未完成"。

### 问题2: PracticeRecord 模型字段不匹配
| API 使用的字段 | 模型实际字段 | 状态 |
|---------------|-------------|------|
| `answer_detail` | `answer` | 不匹配 |
| `source` | `source_type` | 不匹配 |
| `practice_date` | 不存在 | 缺失 |
| `subject_id` | 不存在 | 缺失 |
| `type_id` | 不存在 | 缺失 |

### 问题3: 练习路径A不提交记录
`exercise.vue` 在交卷时仅使用 sessionStorage，不调用 POST /api/practice/record。

### 问题4: "累计"统计对象错误
显示的是题目导入数量而非用户实际做题数量。

---

## 解决方案

### 后端修复

#### 1. PracticeRecord 模型补全 (models.py)
添加缺失字段：subject_id, type_id, practice_date
统一字段名：answer_detail → answer, source → source_type

#### 2. Practice API 修复 (practice.py)
- 修正 POST/GET 端点中的字段名
- 新增 GET /api/practice/type-summary — 按题目类型统计

#### 3. Stats API 增强 (stats.py)
新增 GET /api/stats/practice-by-type — 按科目+子科目分组统计

#### 4. Exercise.vue 修复
在 handleSubmit() 中添加 POST /api/practice/record 批量提交

### 前端重构

#### 练习记录卡片 (题库页面右侧面板)
- 今日/本周/累计统计卡片
- 题目类型胶囊徽章（红色=未完成，绿色=已完成）
- 点击胶囊跳转对应答题页
- 本周趋势图表（柱状图/折线图可切换）

---

## 涉及文件

| 文件 | 操作 | 说明 |
|------|------|------|
| backend/app/models/models.py | 修改 | 补全PracticeRecord字段 |
| backend/app/api/v1/practice.py | 修改 | 修正字段名+新增端点 |
| backend/app/api/v1/stats.py | 修改 | 新增practice-by-type端点 |
| src/views/exercise.vue | 修改 | 添加提交记录逻辑 |
| .vtj/vue/mjvdqdu1.vue | 修改 | 重写右侧练习记录面板 |
| .vtj/files/mjvdqdu1.json | 同步 | DSL一致性 |
