# 砺安题库 - 试卷管理与题目管理优化设计方案

> 基于 VTJ 前端架构和 FastAPI 后端的深度分析设计

---

## 一、问题分析与根因定位

### 1.1 试卷管理模块问题

| 问题编号 | 问题描述 | 根因定位 | 涉及文件 |
|---------|---------|---------|---------|
| **P1** | 导入题目文档判定为试卷时，名称显示"分离导入试卷"而非文档标题 | `question_import.vue:2261` 仅在合并模式提取标题，分离导入用默认值 | `.vtj/vue/question_import.vue`<br>`backend/app/api/v1/question_import.py` |
| **P2** | 科目类型判定不准确：文档是"公安专业考试"显示为"行测" | `text_parser.py:2335` `detect_subject_category` 关键词权重不足，"行测"词汇泛化 | `backend/app/services/text_parser.py` |
| **P3** | 发布后无删除功能，防止误发布 | `papers.py:100` delete API + `teacher_papers.vue` deletePaper 方法限制了已发布试卷 | `backend/app/api/v1/papers.py`<br>`.vtj/vue/teacher_papers.vue` |
| **P4** | 教师端题目总数912 vs 学生端895 不一致 | 教师端统计所有状态试卷题目，学生端仅统计已发布试卷 | `backend/app/api/v1/teacher.py`<br>`backend/app/api/v1/exams.py` |
| **P5** | 学生端预览显示"即将上线"、开始考试失败 | `student_papers.vue:170` previewPaper 硬编码提示；考试API路由/权限问题 | `.vtj/vue/student_papers.vue`<br>`backend/app/api/v1/exams.py` |

### 1.2 题目管理模块问题

| 问题编号 | 问题描述 | 根因定位 | 涉及文件 |
|---------|---------|---------|---------|
| **Q1** | 题干出现系统ID"UTB7df857a7 第5题：..." | 导入时未清洗题目内容；前端显示未过滤 | `question_import.py` 导入逻辑<br>`.vtj/vue/teacher_questions.vue` 显示逻辑 |
| **Q2** | 题型分类不准：单选题被识别为论述题 | `text_parser.py` `_detect_question_type` 判定逻辑缺陷 | `backend/app/services/text_parser.py` |
| **Q3** | 题目缺失答案解析 | 导入时答案解析提取逻辑不完善 | `question_import.py` 解析逻辑<br>`text_parser.py` 解析函数 |

---

## 二、解决方案设计

### 2.1 核心设计原则

1. **最小侵入性**：优先修复现有逻辑，避免大规模重构
2. **数据源头治理**：在导入环节清洗数据，而非显示层补丁
3. **统一统计口径**：定义明确的"题目总数"计算规则
4. **VTJ 规范遵循**：只改 script，UI 调整走设计器，修改后必同步 DSL
5. **向后兼容**：不破坏现有 API 契约，新增字段默认值处理

---

### 2.2 详细技术方案

#### 方案 P1：修复导入试卷名称提取

**后端修改** (`question_import.py`)：
```python
# 在统一导入入口增加文档标题提取
def extract_paper_title_from_document(content: str, mode: str) -> str:
    """从文档内容中提取试卷标题"""
    # 1. 优先使用用户手动输入的 batchPaperName
    # 2. 从文档首行/标题区域提取
    # 3. 合并模式：使用现有逻辑
    # 4. 分离导入模式：从题目文档标题提取（新增）
```

**前端修改** (`.vtj/vue/question_import.vue`)：
```typescript
// 移除第2261行硬编码默认值
// 统一使用：this.state.batchPaperName || extractedTitle || '未命名试卷'
// 在预览阶段显示提取的标题供用户确认
```

**验收标准**：分离导入模式下，上传"2024年公安专业考试真题.docx"，试卷名称自动识别为"2024年公安专业考试真题"

---

#### 方案 P2：优化科目类型判定算法

**后端修改** (`text_parser.py:2335`)：
```python
SUBJECT_KEYWORDS = {
    '公专': ['公安专业', '公安基础', '警务实务', '公安专业知识', '警察', '执法', '治安管理', '刑事侦查', ...],
    '申论': [...],
    '行测': [...],
}

def detect_subject_category(text: str) -> str:
    if not text:
        return '行测'
    
    scores = {'行测': 0, '申论': 0, '公专': 0}
    text_sample = text[:3000]  # 扩大采样范围
    
    # 权重加成：专业词汇权重更高
    for subject, keywords in SUBJECT_KEYWORDS.items():
        for kw in keywords:
            count = text_sample.count(kw)
            if count > 0:
                # 专业词汇加倍权重
                weight = 2 if subject == '公专' and kw in ['公安专业', '警务实务', '公安基础'] else 1
                scores[subject] += count * weight
    
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else '行测'
```

**新增置信度返回**：
```python
def detect_subject_category_with_confidence(text: str) -> tuple[str, float]:
    """返回 (subject, confidence)"""
    # 计算各科目得分
    # 返回最高分科目及置信度(0-1)
    pass
```

**验收标准**：上传"2024年公安专业考试真题"，自动识别为"公专"，置信度>0.8

---

#### 方案 P3：发布试卷删除功能

**后端 API** (`papers.py`) - 已有基础，需放宽限制：
```python
@router.delete("/{paper_id}")
async def delete_paper(paper_id: int, current_user: SysUser, db: Session):
    paper = db.query(ExamPaper).filter(ExamPaper.paper_id == paper_id).first()
    if not paper:
        raise HTTPException(404, "试卷不存在")
    
    # 权限：教师删自己，管理员删所有
    if current_user.user_type == "teacher" and paper.creator_id != current_user.user_id:
        raise HTTPException(403, "无权删除")
    
    # 已发布试卷：软删除(标记 ENDED)而非硬删除
    if paper.paper_type == "PUBLISHED":
        paper.paper_type = "ENDED"
        paper.publish_time = None
        db.commit()
        return {"message": "已发布试卷已下架至回收站"}
    
    # 其他状态：硬删除
    # ... 现有删除逻辑
```

**前端修改** (`.vtj/vue/teacher_papers.vue`)：
```typescript
// deletePaper 方法移除 paper_type === 'PUBLISHED' 的限制
// 确认对话框区分：草稿/待审批="删除"，已发布="下架至回收站"
// 列表操作列：PUBLISHED 状态显示"下架"图标，其他显示"删除"
```

**验收标准**：教师可下架已发布试卷，试卷进入回收站(ENDED状态)，不影响学生已开始的考试记录

---

#### 方案 P4：统一题目总数统计口径

**定义统计规则**：
| 场景 | 统计范围 | API |
|------|---------|-----|
| 教师端/管理端题库管理 | 该教师创建的所有题目(含草稿、审核中) | `/api/teacher/questions` |
| 学生端题库练习 | 全平台已审核通过、状态正常的题目 | `/api/questions` (学生权限) |
| 试卷管理题目数 | 该试卷关联的题目数(paper.question_count) | 试卷详情 API |

**后端修改**：
```python
# teacher.py - 添加统计接口
@router.get("/questions/stats")
async def get_question_stats(current_user, db):
    return {
        "total": db.query(QuestionBank).filter(QuestionBank.creator_id == current_user.user_id).count(),
        "published": db.query(QuestionBank).filter(
            QuestionBank.creator_id == current_user.user_id,
            QuestionBank.status == 1, QuestionBank.audit_status == 1
        ).count(),
    }

# exams.py - 学生端列表已按 PUBLISHED 过滤，保持一致
```

**前端显示优化**：
- 教师端题目管理：显示"共 912 道题（其中 895 道已发布可练习）"
- 学生端题库：显示"可练习题目 895 道"

**验收标准**：教师端、管理端、学生端三处题目总数口径一致，UI 明确标注统计范围

---

#### 方案 P5：学生端预览与开始考试

**预览功能实现** (`.vtj/vue/student_papers.vue`)：
```typescript
// 替换 previewPaper 方法
async function previewPaper(p: any) {
  const auth = (window as any).__VTJ_AUTH__
  try {
    const res = await auth.apiFetch(`/api/exams/preview/${p.paper_id}`)
    const data = await res.json()
    if (data.success) {
      // 打开预览弹窗，显示题目列表(不含答案)
      showPreviewModal.value = true
      previewPaper.value = data.paper
      previewQuestions.value = data.questions
    } else {
      ElMessage.error(data.message || '预览失败')
    }
  } catch (e) {
    ElMessage.error('预览失败：' + e.message)
  }
}
```

**开始考试修复** - 检查路由一致性：
```typescript
// student_papers.vue startExam 方法
// 确认使用 /api/exams/start (新接口) 而非 /api/exams/{paper_id}/start (旧接口)
// 两个接口功能重复，建议统一到 /api/exams/start
```

**后端预览接口** (`exams.py` 已有 `/preview/{paper_id}`)：
```python
@router.get("/preview/{paper_id}")
async def preview_exam(paper_id: int, db: Session):
    paper = db.query(ExamPaper).filter(
        ExamPaper.paper_id == paper_id,
        ExamPaper.paper_type == "PUBLISHED"
    ).first()
    if not paper:
        raise HTTPException(404, "试卷不存在或未发布")
    
    relations = db.query(PaperQuestionRelation).filter(
        PaperQuestionRelation.paper_id == paper_id
    ).order_by(PaperQuestionRelation.question_order).all()
    
    questions = []
    for rel in relations:
        q = db.query(QuestionBank).filter(QuestionBank.question_id == rel.question_id).first()
        if q:
            questions.append({
                "question_id": q.question_id,
                "question_order": rel.question_order,
                "type_name": q.type.type_name if q.type else "",
                "question_content": q.question_content,  # 不含答案
                "options": q.options,
                "score": float(rel.question_score),
            })
    
    return {"paper": paper, "questions": questions}
```

**验收标准**：学生端点击预览 → 弹窗显示题目列表(无答案/解析)；点击开始考试 → 正常跳转答题页面

---

#### 方案 Q1：清洗题目内容中的 UTB ID

**后端导入时清洗** (`question_import.py`)：
```python
import re

UTB_PATTERN = re.compile(r'UTB[a-f0-9]{8,}[\s\-]?')  # 匹配 UTBxxxxxxxx 格式

def clean_question_content(content: str) -> str:
    """清洗题目内容中的系统生成ID"""
    if not content:
        return content
    # 移除 UTBxxxxxxxx 及其变体
    cleaned = UTB_PATTERN.sub('', content)
    # 移除残留的"第X题："前缀(如果是系统生成的)
    cleaned = re.sub(r'^第\s*\d+\s*题[：:]\s*', '', cleaned)
    return cleaned.strip()

# 在创建 QuestionBank 时应用
question_content = clean_question_content(raw_content)
```

**前端显示兜底过滤** (`.vtj/vue/teacher_questions.vue`)：
```typescript
// 新增过滤函数
function cleanDisplayContent(text: string): string {
  if (!text) return ''
  return text
    .replace(/UTB[a-f0-9]{8,}[-\s]?/gi, '')  // 移除UTB ID
    .replace(/^第\s*\d+\s*题[：:]\s*/, '')     // 移除题号前缀
    .trim()
}

// 在 renderSummary、详情弹窗中应用
function renderSummary(q: any) {
  const text = q.question_content || ''
  const cleaned = cleanDisplayContent(text)
  return cleaned.length > 80 ? cleaned.substring(0, 80) + '...' : cleaned
}
```

**验收标准**：题目列表、详情弹窗均不显示"UTB7df857a7"等系统ID

---

#### 方案 Q2：修复题型分类判定

**后端修改** (`text_parser.py` `_detect_question_type`)：
```python
def _detect_question_type(content: str, options: List, answer: str) -> str:
    """
    多维度判定题型：
    1. 选项数量：2个→判断题，4个→单选/多选，0个→主观题
    2. 答案格式：单字母→单选，多字母→多选，对/错→判断
    3. 题干关键词：'下列...正确'→选择题，'判断'→判断题，'论述/分析'→主观题
    """
    option_count = len(options) if options else 0
    answer = (answer or '').strip().upper()
    
    # 维度1：选项数量
    if option_count == 2:
        # 可能是判断题，进一步看答案
        if answer in ['A', 'B', '正确', '错误', '对', '错', 'TRUE', 'FALSE']:
            return '判断题'
        return '单选题'
    
    if option_count >= 4:
        # 选择题，看答案区分单/多选
        if re.match(r'^[A-D]([，,][A-D])*$', answer):
            return '多选题' if ',' in answer or '，' in answer else '单选题'
        return '单选题'  # 默认单选
    
    if option_count == 0:
        # 无选项：主观题
        if any(kw in content for kw in ['论述', '分析', '阐述', '说明', '简述', '论证', '评述', '写作']):
            return '论述题' if '写作' not in content else '写作题'
        return '简答题'
    
    # 兜底：单选题
    return '单选题'
```

**验收标准**：
- 4选项+单字母答案 → 单选题
- 4选项+多字母答案(A,B) → 多选题  
- 2选项+对/错答案 → 判断题
- 无选项+论述关键词 → 论述题

---

#### 方案 Q3：补全答案解析提取

**后端增强** (`text_parser.py` 新增函数)：
```python
def extract_answer_analysis(text: str) -> str:
    """从文本中提取答案解析"""
    # 支持多种格式：解析：xxx / 答案解析：xxx / 【解析】xxx / 详解：xxx
    patterns = [
        r'解析[：:]\s*(.+?)(?=\n\n|\n\d+[\.、]|\Z)',
        r'答案解析[：:]\s*(.+?)(?=\n\n|\n\d+[\.、]|\Z)',
        r'【解析】\s*(.+?)(?=\n\n|\n\d+[\.、]|\Z)',
        r'详解[：:]\s*(.+?)(?=\n\n|\n\d+[\.、]|\Z)',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(1).strip()
    return ''

# 在导入流程中应用
for q in parsed_questions:
    if not q.get('answer_analysis'):
        q['answer_analysis'] = extract_answer_analysis(raw_text)
```

**前端编辑支持** (`.vtj/vue/teacher_questions.vue`)：
```typescript
// 编辑弹窗中 answer_analysis 字段改为 textarea
// 批量导入预览阶段显示解析提取结果，允许用户手动补充
```

**验收标准**：导入含解析的文档，题目自动带出解析；无解析题目可在编辑时补充

---

## 三、数据库变更

### 3.1 新增字段（如需要）

```sql
-- ExamPaper 表：无需新增，复用 paper_type=ENDED 作为回收站状态

-- QuestionBank 表：建议新增清洗后内容字段（可选，用于显示加速）
ALTER TABLE question_bank ADD COLUMN clean_content TEXT COMMENT '清洗后的题目内容(用于显示)';

-- 操作日志表（已存在 OperationLog）
-- 删除试卷时记录：action='delete_paper', details='下架试卷: {paper_name}'
```

### 3.2 索引优化

```sql
-- 学生端试卷列表查询优化
CREATE INDEX idx_exam_paper_published ON exam_paper(paper_type, publish_time DESC) 
WHERE paper_type = 'PUBLISHED';

-- 教师题目统计
CREATE INDEX idx_question_bank_creator_status ON question_bank(creator_id, status, audit_status);
```

---

## 四、前端 VTJ 页面修改清单

| 页面 | 修改内容 | 涉及方法/状态 | 需同步DSL |
|------|---------|-------------|----------|
| `question_import.vue` | 1. 统一试卷名称提取逻辑<br>2. 预览阶段显示提取标题<br>3. 分离导入模式显示文档标题 | `state.batchPaperName` 计算逻辑<br>`importSummary.paperName` 显示 | ✅ 是 |
| `teacher_papers.vue` | 1. 删除/下架按钮区分状态<br>2. 列表操作列动态图标<br>3. 题目统计显示双口径 | `deletePaper` 方法<br>`statusLabel` 扩展<br>新增统计显示 | ✅ 是 |
| `student_papers.vue` | 1. 实现 previewPaper 预览功能<br>2. 修正 startExam 调用新 API<br>3. 新增预览弹窗 UI | `previewPaper` 重写<br>`startExam` API 调整<br>新增 `showPreviewModal` 等状态 | ✅ 是 |
| `teacher_questions.vue` | 1. 题目内容显示过滤 UTB ID<br>2. 题型分类显示修正<br>3. 编辑弹窗答案解析字段 | `renderSummary`/`stripPromoText` 增强<br>`typeDisplayName` 修正<br>`editForm.answer_analysis` 字段 | ✅ 是 |

---

## 五、API 变更清单

| 接口 | 变更类型 | 说明 |
|------|---------|------|
| `POST /api/questions/import/*` | 优化 | 返回提取的试卷标题、检测科目及置信度 |
| `DELETE /api/papers/{id}` | 放宽 | 允许 PUBLISHED 状态删除(软删除 ENDED) |
| `GET /api/teacher/questions/stats` | 新增 | 返回总数/已发布数双口径统计 |
| `GET /api/exams/preview/{paper_id}` | 确认 | 已存在，确保学生端可调用 |
| `POST /api/exams/start` | 统一 | 学生端统一使用此接口，废弃 `/api/exams/{id}/start` |

---

## 六、实施顺序与风险控制

### 6.1 实施阶段

| 阶段 | 任务 | 预估工时 | 依赖 |
|------|------|---------|------|
| **阶段1：数据清洗与核心算法** | P1/P2/Q1/Q2/Q3 后端逻辑 | 2天 | 无 |
| **阶段2：API 调整与新增** | P3/P4/P5 后端接口 | 1天 | 阶段1 |
| **阶段3：前端页面修改** | 4个 VTJ 页面 script 修改 | 2天 | 阶段1-2 |
| **阶段4：VTJ 同步与联调** | DSL 同步、缓存清理、全流程测试 | 1天 | 阶段3 |
| **阶段5：验收与文档** | 验收测试、更新文档 | 0.5天 | 阶段4 |

### 6.2 风险点与应对

| 风险 | 影响 | 应对策略 |
|------|------|----------|
| VTJ 版本号不一致导致代码被覆盖 | 高 | 每次修改后强制执行 `vtj_sync_vue_to_dsl`，CI 增加一致性检查 |
| 科目判定算法改动影响历史数据 | 中 | 新增置信度字段，低置信度(<0.6)标记人工复核 |
| 删除已发布试卷影响学生考试记录 | 高 | 软删除(ENDED)，不删除 exam_record 关联数据 |
| 学生端预览/考试接口权限问题 | 中 | 复用现有认证中间件，确保 student 角色可访问 |
| 导入清洗逻辑误删有效内容 | 低 | UTB 正则精确匹配，保留中文题号"第5题：" |

---

## 七、验收标准

### 7.1 功能验收清单

- [ ] **P1** 分离导入上传"2024公安专业考试.docx"，试卷名自动识别为"2024公安专业考试"
- [ ] **P2** 上传公安专业考试文档，科目自动识别为"公专"，置信度>0.8
- [ ] **P3** 教师端已发布试卷显示"下架"按钮，点击后试卷进入回收站(ENDED)
- [ ] **P4** 教师端显示"共912道题(含895道已发布)"，学生端显示"可练习895道"
- [ ] **P5** 学生端点击预览→弹窗显示题目列表(无答案)；点击开始考试→正常跳转答题页
- [ ] **Q1** 题目列表/详情不再显示"UTB7df857a7"等系统ID
- [ ] **Q2** 4选项单字母答案→单选题；2选项对错→判断题；无选项论述→论述题
- [ ] **Q3** 导入含解析文档自动提取解析；编辑弹窗可维护解析字段

### 7.2 技术验收

- [ ] 所有修改的 `.vtj/vue/*.vue` 执行 `vtj_sync_vue_to_dsl` 同步，版本号一致
- [ ] 无 TypeScript/Lint 错误
- [ ] 单元测试覆盖核心算法(`detect_subject_category`、`_detect_question_type`、`clean_question_content`)
- [ ] 性能：学生端试卷列表<500ms，预览接口<300ms

---

## 八、模糊点确认（需用户决策）

| 待确认项 | 选项 | 建议 |
|---------|------|------|
| **P3 删除策略** | A. 已发布试卷软删除(ENDED)<br>B. 已发布试卷硬删除+级联删除考试记录 | **A** - 保留数据完整性 |
| **P4 统计口径** | A. 教师端显示双数值(总数/已发布)<br>B. 统一按"已发布可练习"统计 | **A** - 信息更全面 |
| **Q1 清洗时机** | A. 导入入库时清洗(推荐)<br>B. 前端显示时过滤 | **A** - 一劳永逸 |
| **Q2 题型判定** | A. 仅修正算法<br>B. 算法+人工复核标记(低置信度) | **B** - 更稳健 |

---

> **下一步**：用户确认上述模糊点后，我将按阶段执行实施。
<tool_call>
<function=question>
<parameter=questions>
[{"question": "关于 P3 删除策略：已发布试卷是软删除(标记 ENDED 进入回收站)还是硬删除？硬删除会级联删除学生考试记录。", "header": "P3删除策略", "options": [{"label": "软删除(ENDED) - 推荐", "description": "已发布试卷下架至回收站，保留考试记录，教师可恢复"}, {"label": "硬删除", "description": "彻底删除试卷及关联数据，学生考试记录也将丢失"}]}, {"question": "关于 P4 统计口径：教师端题目总数如何展示？", "header": "P4统计口径", "options": [{"label": "双数值展示 - 推荐", "description": "显示'共912道题(其中895道已发布可练习)'，信息更全面"}, {"label": "统一已发布口径", "description": "教师端也只统计已发布题目，与学生端完全一致"}]}, {"question": "关于 Q1 UTB ID 清洗时机：在导入入库时清洗，还是前端显示时过滤？", "header": "Q1清洗时机", "options": [{"label": "导入时清洗 - 推荐", "description": "入库前清洗，存储干净数据，前端直接显示无需额外处理"}, {"label": "前端显示过滤", "description": "数据库保留原始数据，前端渲染时过滤显示"}]}, {"question": "关于 Q2 题型判定：是否增加低置信度人工复核标记？", "header": "Q2题型判定", "options": [{"label": "算法+低置信度标记 - 推荐", "description": "置信度<0.6标记'需复核'，题目管理列表高亮提醒教师"}, {"label": "仅修正算法", "description": "优化判定逻辑，不增加复核机制"}]}]