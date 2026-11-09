# 考试评分口径 `is_scored` 统一 · 交付记录 v1

> 方案：[`考试评分口径_is_scored统一_方案_v1.md`](./考试评分口径_is_scored统一_方案_v1.md)
> 用户 2026-11-09 拍板三条：**① 语义选 A；② 三个派生字段要加；③ 数据回填现在做**。
> 本文记录落地范围、实测证据与回滚办法。分支 `feat/material-multi-format-import`，**未碰 main**。

---

## 1. 落地的口径（A）

```
is_scored = 1  <=>  已交卷（is_completed=1） 且 不存在 exam_answer_detail.is_correct IS NULL 的明细
```

含义从"提交过"变成**"分数已完全确定"**。主观题（`question_type.is_objective=0`）作答后
`is_correct` 留空 → 该卷 `is_scored=0`，直到人工评分。

配套三个派生字段（只增不改）：

| 字段 | 含义 | 来源 |
|---|---|---|
| `manual_pending_count` | 待人工评分题数 | `is_correct IS NULL` 的明细数 |
| `answered_count` | 已作答题数 | `student_answer` 非空的明细数 |
| `question_total` | 本卷题数（分母） | `exam_paper.question_count`，为 0 时退化为明细条数 |

---

## 2. 改了什么（7 个文件）

| 文件 | 改动 |
|---|---|
| `backend/app/services/exam_scoring.py` | **新增**：`scoring_flags()` 纯函数 + `finalize_record()` 唯一写点 |
| `backend/app/models/models.py` | `ExamRecord` 加 3 列（含口径注释） |
| `backend/scripts/migrate/migrate_add_exam_scoring_fields.py` | **新增**：SQLite `ADD COLUMN` 迁移（dry-run 默认 / `--apply` / 自动备份 / integrity 校验；**只用 ASCII 标记**，避免 GBK 控制台 emoji 崩） |
| `backend/app/api/v1/exam/exams.py` | 交卷端点：删掉恒真式 `1 if scored_count == len(questions) else 0`，改 `finalize_record()`；回包 + 记录序列化补 4 个字段 |
| `backend/app/api/v1/exam/smart_exam.py` | 智能组卷交卷：不再建记录即写 `is_scored=1`，改 `finalize_record()` |
| `backend/app/services/exam_service.py` | `submit_exam`（当前无调用方）同样收口，避免将来复用踩坑 |
| `backend/app/schemas/schemas.py` | `ExamRecordResponse` + 3 个可选字段（默认 0，老调用方无感） |
| `backend/tests/test_exam_scoring_semantics.py` | **新增 8 例**（5 纯函数 + 3 接口级） |

---

## 3. 实测证据

### 3.1 迁移（先加列，再加代码）

```
数据库: backend/data/question_bank.db
待加列: ['manual_pending_count', 'answered_count', 'question_total']
[BAK] 备份: backend/data/backups/before_exam_scoring_fields_20261109_192848.db
  [ADD] 加列 manual_pending_count / answered_count / question_total
[迁移后] exam_record 列(17): … is_scored, submit_time, is_late, attempt_count, create_time,
         manual_pending_count, answered_count, question_total
  integrity_check = ok
```

### 3.2 数据回填（dry-run → apply）

```
前: #1 paper=5 明细=97 → answered_count: 0->2, question_total: 0->97
[BAK] backend/data/backups/before_backfill_is_scored_20261109_193035.db
后: #1: {'is_scored': 1, 'manual_pending_count': 0, 'answered_count': 2, 'question_total': 97}
剩余不一致行 = 0，integrity_check = ok
```

> 解读：这条记录正是你 11-09 那次交卷（97 题只答 2 题）。`is_scored` 前后都是 1
> （全客观题、无待评项），真正被补上的是"答了 2 题 / 共 97 题"这两个信息。

### 3.3 测试

| 范围 | 结果 |
|---|---|
| 新增 `test_exam_scoring_semantics.py` | **8 passed**（全客观全答 / 只答 1 题也算已评分 / 含主观题→未评分且待评 1 / 未完成→未评分 / 写入 4 字段 / 3 条接口级） |
| 回归 `pytest -k "exam or paper"` | **200 passed**（原基线 192 + 新增 8） |

### 3.4 门禁

```
PASS L0 / L3 / L1 / L1-H / L2 / L4 / L5 / L6 / L7
FAIL L1-G（既有基线红，与本次无关）: 公专 397 题（下限 3085）、总数 397（下限 3632）
gate_all: 9/10 通过
```

### 3.5 线上接口实测（重启 8001 后，学生账号 202516001）

```
GET /api/exams/records?page=1&page_size=3
  => record=1 is_scored=1 pending=0 answered=2 total=97      （列表序列化已补 3 字段）

GET /api/exams/records/1
  => is_scored=True pending=0 answered=2 total=97
     duration=9 score=0.0/97.0 details=97                     （详情同口径，与结果页一致）
```

---

## 4. 回滚

| 粒度 | 做法 |
|---|---|
| 代码 | revert 本提交；`exam_scoring.py` 删除、三处调用点还原、schema 三字段还原 |
| 数据（回填） | 用 `backend/data/backups/before_backfill_is_scored_2026*.db` 顶回 |
| 表结构 | 3 列只是多出来的空列，**不回滚也不影响旧代码**；要彻底删需重建表（不建议） |

## 5. 已知边界

- `ExamService.submit_exam` 是死代码，虽已收口但没有测试覆盖（无调用方无法走接口）；
- 学情 `agent_router.py:470` 仍按 `is_scored == 1` 取模考成绩：A 口径下等于"分数已定"，**行为今天不变**；若将来希望"有分就进学情"，需另改；
- 前端仍没有展示这三个新字段（`is_scored` 前端全仓 0 引用）；结果页要用 `answered_count/question_total` 时直接取即可。
