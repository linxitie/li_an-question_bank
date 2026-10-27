# 砺安题库 - 试卷管理与题目管理优化规格文档

**版本**: 1.0  
**日期**: 2025-08-23  
**状态**: 已批准，待实施  

---

## 1. 项目背景与目标

### 1.1 项目架构
- **前端**: VTJ (Vue 3 + TypeScript + Vite)，低代码设计器生成页面
- **后端**: Python FastAPI + SQLite/MySQL
- **认证**: 共享模块 `window.__VTJ_AUTH__` + JWT
- **部署**: Vite Dev Server (9527) → Proxy → FastAPI (8000)

### 1.2 核心目标
解决试卷管理和题目管理模块的 7 个核心问题，提升数据准确性、用户体验和功能完整性。

---

## 2. 问题清单与解决方案

### 2.1 试卷管理模块 (4个问题)

#### 问题 P1: 试卷名称和科目判定不准确
**现状**: 题目文档显示"公安专业考试"，试卷管理显示"行测"  
**方案**: 优化检测算法 + 人工确认环节

| 组件 | 改进内容 |
|------|----------|
| 标题解析 | 移除 `UTB[a-f0-9]{16}` 系统ID，提取有效名称 |
| 科目识别 | 关键词库匹配：公安专业考试/行测/申论/公基/面试 |
| 权重算法 | 标题权重 0.7 + 内容权重 0.3，输出置信度 0-1 |
| 人工确认 | 导入对话框显示提取结果，教师可修改后确认 |

**数据库新增字段** (`papers` 表):
```sql
original_title TEXT COMMENT '原始文档标题',
subject_confidence DECIMAL(3,2) COMMENT '科目识别置信度',
is_manually_confirmed BOOLEAN DEFAULT FALSE COMMENT '是否人工确认',
detected_subject VARCHAR(50) COMMENT '系统识别的科目'
```

#### 问题 P2: 发布试卷后需要删除功能
**现状**: 无删除按钮，错误发布无法撤销  
**方案**: 已发布试卷也可删除

- **删除逻辑**: 事务内删除 `paper_question` 关联 + 删除 `papers` 记录
- **权限控制**: 教师仅删自己创建的，管理员删所有
- **确认机制**: 二次确认对话框，已发布试卷显示警告提示
- **审计日志**: 记录操作人、时间、试卷名称

#### 问题 P3: 题目总数不一致 (教师端 912 vs 学生端 895)
**现状**: 不同端口径不一致  
**方案**: 统一统计服务，按角色差异化过滤

| 角色 | 统计口径 |
|------|----------|
| 教师/管理员 | `is_deleted = FALSE` (所有题目) |
| 学生 | `is_deleted = FALSE AND status = 'published' AND is_available = TRUE` |

**前端显示**: 明确标注口径差异，如"共 912 道题，学生可练习 895 道"

#### 问题 P4: 学生端试卷预览/开始考试失败
**现状**: 预览显示"即将上线"，考试显示"失败"  
**方案**: 实现完整的预览和考试 API

**预览 API** `GET /api/papers/{id}/preview`:
- 返回题目列表，**不含答案和解析**
- 包含题目类型、分值、选项

**考试 API** `POST /api/exams/start`:
- 创建 `ExamRecord` 记录
- 加载题目（支持随机/顺序）
- 返回考试 ID、题目列表、时间限制
- 支持继续未完成的考试

---

### 2.2 题目管理模块 (3个问题)

#### 问题 Q1: 题目显示异常 (含系统ID UTBxxx)
**现状**: 题干显示 `UTB7df857a7 第5题：...`  
**方案**: 前后端双重过滤

- **前端**: `utils/questionFilter.js` 正则移除 `UTB[a-f0-9]{16}`
- **后端**: `questions` 表新增 `clean_content TEXT` 存储清洗后内容
- **迁移时**: 批量更新现有数据

#### 问题 Q2: 题型分类不准确 (单选/多选被识别为论述题)
**现状**: 混合判定逻辑有缺陷  
**方案**: 多维度判定 + 置信度 + 人工修正

**判定维度**:
1. 选项数量: 4个→单选倾向，>4个→多选倾向
2. 答案格式: 单字母→单选，多字母→多选，对/错→判断题
3. 题干关键词: "下列...正确"→选择题，"判断/是否"→判断题，"论述/分析"→论述题

**输出**: `(question_type, confidence)` 置信度 < 0.5 标记待确认

**批量修改界面**: 选择多题 → 统一修改题型 → 记录历史

#### 问题 Q3: 题目缺失答案解析
**现状**: 导入文档有解析但未提取，或原文档无解析  
**方案**: 多格式提取 + 手工补充 + 批量操作

**支持格式**:
- `解析：xxx` / `答案解析：xxx`
- `【解析】xxx` / `详解：xxx`

**功能**:
- 导入时自动提取
- 编辑对话框手工补充
- 批量添加解析
- 缺失解析提醒

---

## 3. 技术补充项 (3项关键基建)

### 3.1 数据库迁移 (Alembic) - 3个脚本

| 文件 | 内容 | 回滚 |
|------|------|------|
| `20250823_001_add_paper_fields.py` | papers表新增4字段+索引 | ✅ |
| `20250823_002_add_question_fields.py` | questions表新增3字段+清洗数据+索引 | ✅ |
| `20250823_003_add_operation_log.py` | 新建operation_logs表 | ✅ |

**执行命令**:
```bash
cd backend && alembic upgrade head
# 回滚: alembic downgrade -1
```

### 3.2 VTJ版本同步自动化

**核心规则**: 修改 `.vtj/vue/*.vue` 的 `<script>` 后，**必须**同步更新 `.vtj/files/*.json` 的 `__VERSION__`，且 `useProvider({version})` 保持一致。

**自动化方案**:
1. **Pre-commit钩子** (强制): `scripts/vtj_version_sync.py` 自动同步版本号
2. **VS Code Task** (辅助): 手动触发同步
3. **CI检查** (门禁): PR 检查版本一致性，不一致阻断合并

### 3.3 核心算法单元测试

| 测试文件 | 覆盖算法 | 用例数 | 覆盖率目标 |
|----------|----------|--------|------------|
| `test_exam_detector.py` | 标题解析、科目识别 | 8 | >90% |
| `test_question_classifier.py` | 题型分类 | 8 | >85% |
| `test_explanation_extractor.py` | 解析提取 | 6 | >80% |
| `test_question_filter.js` | 前端内容过滤 | 6 | >90% |

**运行**: `pytest tests/unit -v --cov=backend.services`

---

## 4. API 契约

### 4.1 试卷管理

| 端点 | 方法 | 说明 | 权限 |
|------|------|------|------|
| `/api/papers/{id}` | DELETE | 删除试卷(含已发布) | 教师/管理员 |
| `/api/papers/{id}/preview` | GET | 预览试卷(无答案) | 学生/教师 |
| `/api/papers/import` | POST | 导入试卷(含确认步骤) | 教师 |
| `/api/papers/stats` | GET | 统计题目总数(按角色) | 全部 |

### 4.2 考试管理

| 端点 | 方法 | 说明 | 权限 |
|------|------|------|------|
| `/api/exams/start` | POST | 开始/继续考试 | 学生 |
| `/api/exams/{id}/submit` | POST | 提交考试 | 学生 |
| `/api/exams/{id}/progress` | PUT | 保存答题进度 | 学生 |

### 4.3 题目管理

| 端点 | 方法 | 说明 | 权限 |
|------|------|------|------|
| `/api/questions/{id}/type` | PATCH | 修改题型 | 教师/管理员 |
| `/api/questions/batch-type` | PATCH | 批量修改题型 | 教师/管理员 |
| `/api/questions/{id}/explanation` | PATCH | 更新解析 | 教师/管理员 |
| `/api/questions/batch-explanation` | POST | 批量添加解析 | 教师/管理员 |

---

## 5. 前端组件变更 (VTJ页面)

### 5.1 涉及的 VTJ 页面

| 页面 | 文件 | raw标记 | 主要变更 |
|------|------|---------|----------|
| 题目导入 | `questionImport.vue` | ✅ | 新增确认对话框、科目选择、置信度显示 |
| 试卷管理 | `paperManage.vue` | ✅ | 新增删除按钮、确认对话框、统计口径显示 |
| 题目管理 | `questionManage.vue` | ✅ | 内容过滤显示、批量修改题型/解析、置信度标记 |
| 学生端预览 | `examPreview.vue` | ✅ | 新建页面，仅显示题目 |
| 学生端考试 | `examStart.vue` | ✅ | 新建页面，计时、答题、提交 |

### 5.2 新增通用组件

| 组件 | 用途 |
|------|------|
| `ExamConfirmDialog.vue` | 试卷导入确认 |
| `DeleteConfirmDialog.vue` | 删除确认(含已发布警告) |
| `BatchEditTypeDialog.vue` | 批量修改题型 |
| `ExplanationEditDialog.vue` | 编辑解析 |
| `QuestionContentFilter.vue` | 题目内容过滤显示 |

### 5.3 VTJ 同步清单 (每个修改页面必做)

- [ ] 修改 `.vtj/vue/xxx.vue` 的 `<script>` (methods/state/lifeCycles)
- [ ] 运行 `python scripts/vtj_version_sync.py .vtj/vue/xxx.vue`
- [ ] 验证 `.vtj/files/xxx.json` 的 `__VERSION__` 与 `useProvider({version})` 一致
- [ ] 提交两个文件

---

## 6. 后端服务新增/修改

### 6.1 新增服务文件

```
backend/services/
├── exam_detector.py          # 试卷检测: 标题解析、科目识别
├── question_classifier.py    # 题型分类: 多维度判定、置信度
├── explanation_extractor.py  # 解析提取: 多格式支持
├── question_stats.py         # 统一统计服务: 按角色差异化
└── exam_service.py           # 考试业务: 开始、提交、进度
```

### 6.2 修改的路由文件

| 文件 | 变更 |
|------|------|
| `routers/papers.py` | 新增 DELETE、preview、import确认、stats |
| `routers/exams.py` | 新增 start、submit、progress |
| `routers/questions.py` | 新增 批量修改题型、批量解析 |

---

## 7. 数据模型变更

### 7.1 papers 表
```sql
-- 新增字段
original_title TEXT,
subject_confidence DECIMAL(3,2),
is_manually_confirmed BOOLEAN DEFAULT FALSE,
detected_subject VARCHAR(50),
-- 新增索引
INDEX idx_papers_subject_status (subject, status),
INDEX idx_papers_created_by_status (created_by, status)
```

### 7.2 questions 表
```sql
-- 新增字段
clean_content TEXT,
type_confidence DECIMAL(3,2),
is_type_confirmed BOOLEAN DEFAULT FALSE,
-- 新增索引
INDEX idx_questions_subject_status (subject, status),
INDEX idx_questions_created_by_status (created_by, status)
```

### 7.3 新建 operation_logs 表
```sql
CREATE TABLE operation_logs (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    action VARCHAR(50) NOT NULL,
    target_type VARCHAR(50) NOT NULL,
    target_id INT,
    details TEXT,
    ip_address VARCHAR(45),
    user_agent VARCHAR(500),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_action_time (user_id, action, created_at)
);
```

---

## 8. 算法详细设计

### 8.1 科目识别算法
```python
SUBJECT_KEYWORDS = {
    "公安专业考试": ["公安", "警察", "执法", "警务"],
    "行政职业能力测验": ["行测", "行政职业", "能力测验", "判断推理"],
    "申论": ["申论", "写作", "论述"],
    "公共基础知识": ["公基", "公共基础", "基础知识"],
    "面试": ["面试", "结构化", "无领导小组"]
}

def identify_subject(title: str, content: str) -> (str, float):
    scores = {}
    for subject, kws in SUBJECT_KEYWORDS.items():
        scores[subject] = sum(kw in title for kw in kws) * 0.7
        scores[subject] += sum(kw in content[:500] for kw in kws) * 0.3
    best = max(scores, key=scores.get)
    return best, min(scores[best] / 3, 1.0)
```

### 8.2 题型分类算法
```python
def classify(question_data) -> (str, float):
    scores = {"single_choice":0, "multiple_choice":0, "true_false":0, "essay":0}
    opts = question_data.get("options", [])
    ans = question_data.get("answer", "")
    content = question_data.get("content", "")
    
    if len(opts) == 4: scores["single_choice"] += 3
    elif len(opts) > 4: scores["multiple_choice"] += 3
    if re.match(r'^[A-D]$', ans): scores["single_choice"] += 2
    elif re.match(r'^[A-D,，]+$', ans): scores["multiple_choice"] += 2
    elif ans in ["正确","错误","对","错","T","F"]: scores["true_false"] += 3
    if "下列" in content and "正确" in content:
        scores["single_choice"] += 1; scores["multiple_choice"] += 1
    if "判断" in content or "是否" in content: scores["true_false"] += 2
    if "论述" in content or "分析" in content: scores["essay"] += 2
    
    best = max(scores, key=scores.get)
    total = sum(scores.values())
    return best, scores[best]/total if total > 0 else 0
```

### 8.3 前端内容过滤
```javascript
// utils/questionFilter.js
export function filterQuestionContent(content) {
    if (!content) return '';
    return content
        .replace(/UTB[a-f0-9]{16}/g, '')  // 移除系统ID
        .replace(/^第\d+题[：:]\s*/, '')   // 移除题号前缀
        .replace(/\s+/g, ' ')              // 合并空白
        .trim();
}
```

---

## 9. 实施计划概览

### Phase 1: 基础设施 (第1周)
- [ ] 数据库迁移脚本编写与测试
- [ ] VTJ版本同步脚本 + pre-commit配置
- [ ] 核心算法单元测试编写

### Phase 2: 后端API (第2-3周)
- [ ] 试卷删除、预览、统计API
- [ ] 考试开始/提交/进度API
- [ ] 题目批量修改题型/解析API
- [ ] 试卷导入确认流程API

### Phase 3: 前端页面 (第3-4周)
- [ ] 试卷导入确认对话框
- [ ] 试卷管理删除功能
- [ ] 题目管理过滤显示、批量操作
- [ ] 学生端预览页面
- [ ] 学生端考试页面
- [ ] VTJ版本同步验证

### Phase 4: 集成测试与部署 (第5周)
- [ ] 端到端测试
- [ ] 性能测试 (912题目列表加载)
- [ ] 生产环境部署验证

---

## 10. 验收标准

### 10.1 功能验收
- [ ] 导入"公安专业考试"文档，试卷名称正确提取，科目识别为"公安专业考试"
- [ ] 发布后的试卷可删除，删除后试卷管理列表不再显示
- [ ] 教师端显示"共912道题"，学生端显示"可练习895道题"，口径明确
- [ ] 学生端点击预览：显示题目列表，无答案
- [ ] 学生端点击开始考试：正常进入答题界面，可计时、提交
- [ ] 题目列表不再显示 `UTBxxx` 系统ID
- [ ] 单选/多选/判断题分类准确率 > 95%
- [ ] 缺失解析的题目可批量补充

### 10.2 技术验收
- [ ] 所有数据库迁移可正向执行、可回滚
- [ ] VTJ版本同步：pre-commit自动修复，CI检查通过
- [ ] 单元测试覆盖率达标，`pytest` 全绿
- [ ] 无 TypeScript 编译错误，无 ESLint 警告
- [ ] 页面加载性能 < 2秒 (912题目虚拟滚动)

---

## 11. 风险与应对

| 风险 | 影响 | 应对 |
|------|------|------|
| VTJ版本不同步导致代码被覆盖 | 高 | Pre-commit强制同步 + CI门禁 |
| 数据库迁移生产环境失败 | 高 | 测试环境全量演练 + 快照备份 |
| 题目分类算法误判现有数据 | 中 | 置信度<0.5标记人工确认 + 批量修正工具 |
| 学生端考试并发性能 | 中 | Redis缓存题目 + 分页加载 |

---

## 12. 附录

### 12.1 相关文档
- VTJ开发规范: `CLAUDE.md/vtj.md`
- VTJ MCP服务器: `vtj-mcp-server.md`
- 项目结构: `.vtj/projects/linxitie.policy-exam-bank.json`

### 12.2 关键文件路径
- 后端入口: `backend/main.py`
- 前端入口: `src/main.ts`
- 路由配置: `src/router/index.ts`
- VTJ页面: `.vtj/vue/*.vue`
- VTJ DSL: `.vtj/files/*.json`

---

**文档结束**  
*本规格文档经确认后将作为实施依据，实施过程中如需变更请更新本文档。*