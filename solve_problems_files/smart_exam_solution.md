# 智能组卷功能 — 实施方案文档

## 概述
为公安联考预备警官实现的智能组卷核心功能，支持行测/申论/公专/混合四种组卷模式。

## 修改文件清单

### 后端 (4个文件)
| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/app/models/models.py` | 修改 | 扩展 composition_method 枚举 + 新增 SmartExamRecord 模型 |
| `backend/app/schemas/schemas.py` | 修改 | 新增智能组卷 Pydantic Schema |
| `backend/app/api/v1/smart_exam.py` | 新增 | 智能组卷路由模块 (10个端点) |
| `backend/app/main.py` | 修改 | 注册 smart_exam 路由 |

### 前端 (6个文件)
| 文件 | 操作 | 说明 |
|------|------|------|
| `.vtj/vue/smart_exam.vue` | 新增 | 三步组卷流程页面 |
| `.vtj/files/smart_exam.json` | 新增 | VTJ DSL 定义 |
| `.vtj/vue/smart_answer.vue` | 新增 | 答题卡页面 |
| `.vtj/files/smart_answer.json` | 新增 | VTJ DSL 定义 |
| `src/router/index.ts` | 修改 | 注册 /smart-exam 和 /smart-answer 路由 |
| `.vtj/vue/app_navigation.vue` | 修改 | 添加导航入口 |
| `.vtj/vue/question_bank.vue` | 修改 | 更新智能组卷按钮逻辑 |

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/smart-exam/generate` | 智能组卷生成 |
| POST | `/api/smart-exam/{paper_id}/replace/{qid}` | 替换题目 |
| GET | `/api/smart-exam/{paper_id}/preview` | 试卷预览 |
| POST | `/api/smart-exam/{paper_id}/confirm` | 确认试卷 |
| POST | `/api/smart-exam/{paper_id}/start` | 开始答题 |
| POST | `/api/smart-exam/{paper_id}/save-progress` | 保存进度 |
| POST | `/api/smart-exam/{paper_id}/submit` | 提交+评分+同步自测 |
| GET | `/api/smart-exam/records` | 记录列表 |
| GET | `/api/smart-exam/records/{id}` | 记录详情 |
| DELETE | `/api/smart-exam/records/{id}` | 删除记录 |

## 数据库变更
- 扩展 `exam_paper.composition_method` 枚举: `AUTO, MANUAL, TEMPLATE, SMART`
- 新增 `smart_exam_record` 表

## 成绩同步
提交时自动创建 `ExamRecord(exam_type=SELF_TEST)` → 自动出现在「成绩分析→自测」
