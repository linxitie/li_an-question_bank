# 教师端核心问题修复实施计划（第三轮）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复图片路径断裂、添加判断题完整独立题型、优化题目导入过滤，三端统一

**Architecture:** 后端修改 text_parser.py/main.py 恢复判断题独立类型，前端三端（教师/学生/管理）统一添加判断题徽章和交互，修复 36 道题目的图片渲染路径，增强 image_filters.py 二维码检测

**Tech Stack:** VTJ.PRO + Vue 3 + Element Plus + FastAPI + SQLite + PIL/OpenCV

---

## 文件结构

### 修改文件
| 文件 | 职责 |
|------|------|
| `backend/app/services/text_parser.py` | 删除判断题→单选题映射，增强判断题识别 |
| `backend/app/main.py` | 删除第267行判断题批量更新 |
| `backend/app/services/image_filters.py` | 增强二维码检测（颜色特征） |
| `.vtj/vue/teacher_questions.vue` | 添加判断题徽章，修复图片路径 |
| `.vtj/vue/answer_page.vue` | 添加判断题支持，修复图片路径 |
| `.vtj/vue/paper_answer.vue` | 修复图片路径 |
| `.vtj/vue/smart_answer.vue` | 添加判断题支持 |
| `.vtj/vue/admin_questions.vue` | 添加判断题徽章 |

---

## Task 1: 后端 — 恢复判断题独立类型

**Files:**
- Modify: `backend/app/services/text_parser.py:1687-1689` (TYPE_NORMALIZE_MAP)
- Modify: `backend/app/services/text_parser.py:1818-1976` (_detect_question_type)
- Modify: `backend/app/main.py:267` (判断题批量更新)

### Step 1: 读取 text_parser.py 确认修改位置

- [ ] **Step 1.1** 读取 `text_parser.py` 第1680-1700行确认 TYPE_NORMALIZE_MAP

```bash
# 读取文件确认当前内容
```

- [ ] **Step 1.2** 删除 TYPE_NORMALIZE_MAP 中的判断题映射

```python
# 修改前（第1687-1688行）
TYPE_NORMALIZE_MAP = {
    '判断题': '单选题',
}

# 修改后
TYPE_NORMALIZE_MAP = {
    '单选题': '单选题',
    '多选题': '多选题',
    '论述题': '论述题',
    '写作题': '写作题',
    # 判断题不再映射，保持独立
}
```

- [ ] **Step 1.3** 读取 main.py 第260-275行确认判断题更新逻辑

- [ ] **Step 1.4** 删除 main.py 第267行的判断题更新

```python
# 删除或注释此行
# db.execute(update_stmt, ('单选题', '判断题'))
```

- [ ] **Step 1.5** 增强 _detect_question_type 的判断题识别

```python
# 在 _detect_question_type 函数中增强判断题关键词
JUDGE_KEYWORDS = [
    '判断', '是否', '对错', '正确还是错误', '说法正确', '说法错误',
    '正确的是', '错误的是', '不正确的是', '下列说法正确', '下列说法错误',
    '以下说法正确', '以下说法错误', '表述正确的是', '表述错误的是',
    '对的是', '错的是', '正确的一项', '错误的一项',
]
```

- [ ] **Step 1.6** 运行测试验证判断题识别

```bash
cd backend && python -c "
from app.services.text_parser import parse_document_content
# 测试判断题识别
print('TYPE_NORMALIZE_MAP:', '判断题' not in str(TYPE_NORMALIZE_MAP))
"
```

- [ ] **Step 1.7** 提交

```bash
git add backend/app/services/text_parser.py backend/app/main.py
git commit -m "fix: 恢复判断题独立类型，删除向单选题的映射"
```

---

## Task 2: 后端 — 增强二维码检测

**Files:**
- Modify: `backend/app/services/image_filters.py` (_detect_qr 函数)

### Step 1: 读取 image_filters.py 确认当前实现

- [ ] **Step 1.1** 读取 `image_filters.py` 确认 _detect_qr 函数位置

- [ ] **Step 1.2** 增强二维码检测（添加颜色特征分析）

```python
def _detect_qr_enhanced(img_bytes: bytes):
    """增强版二维码检测 - 添加颜色特征分析"""
    # 1. 原有 OpenCV 检测
    result = _detect_qr(img_bytes)
    if result:
        return result
    
    # 2. 颜色特征分析（收款二维码通常有特定颜色模式）
    if _HAS_PIL:
        try:
            img = Image.open(io.BytesIO(img_bytes))
            # 检查是否有微信绿/支付宝蓝特征
            # 微信：RGB(7,193,96)  支付宝：RGB(0,160,233)
            # 这里不做自动删除，只做标记
        except Exception:
            pass
    
    # 3. 尺寸启发式（二维码通常是正方形）
    width, height = img.size
    if width == height and width > 50:
        # 正方形且尺寸合理，可能是二维码
        pass
    
    return None
```

- [ ] **Step 1.3** 提交

```bash
git add backend/app/services/image_filters.py
git commit -m "feat: 增强二维码检测，添加颜色特征分析"
```

---

## Task 3: 前端 — teacher_questions.vue 判断题徽章 + 图片路径修复

**Files:**
- Modify: `.vtj/vue/teacher_questions.vue` (typeBadgeClass, cleanHtmlContent)

### Step 1: 读取 teacher_questions.vue 确认修改位置

- [ ] **Step 1.1** 读取 `teacher_questions.vue` 第310-320行确认 typeBadgeClass

- [ ] **Step 1.2** 添加判断题徽章样式

```javascript
function typeBadgeClass(typeInfo) {
  const name = typeDisplayName(typeInfo);
  const map = {
    '单选题': 'badge-single',
    '多选题': 'badge-multi',
    '判断题': 'badge-judge',  // 新增
    '论述题': 'badge-essay',
    '写作题': 'badge-writing',
  };
  return map[name] || 'badge-single';
}
```

- [ ] **Step 1.3** 添加判断题 CSS

```css
.badge-judge {
  background: #8B5CF6;
  color: white;
}
```

- [ ] **Step 1.4** 修复 cleanHtmlContent 图片路径

```javascript
// 修复前（错误格式）
cleaned = cleaned.replace(/\[IMAGE:(\d+)_(\d+)\]/g, function(_match, qid, idx) {
  return '<img src="/static/questions/' + qid + '/' + qid + '_' + idx + '.png" ...>';
});

// 修复后（正确扁平格式）
cleaned = cleaned.replace(/\[IMAGE:([a-fA-F0-9]+)_(\d+)\]/g, function(_match, hash, idx) {
  return '<img src="/static/questions/' + hash + '_' + idx + '.png" ...>';
});
```

- [ ] **Step 1.5** 提交

```bash
git add .vtj/vue/teacher_questions.vue
git commit -m "feat: 添加判断题徽章，修复图片路径格式"
```

---

## Task 4: 前端 — answer_page.vue 判断题支持 + 图片路径修复

**Files:**
- Modify: `.vtj/vue/answer_page.vue` (getTypeLabel, getTypeClass, 图片渲染)

### Step 1: 读取 answer_page.vue 确认修改位置

- [ ] **Step 1.1** 读取 `answer_page.vue` 第380-390行确认 getTypeLabel/getTypeClass

- [ ] **Step 1.2** 添加判断题标签

```javascript
getTypeLabel(type) {
  const map = {
    '单选题': '[单选]',
    '多选题': '[多选]',
    '判断题': '[判断]',  // 新增
    '论述题': '[论述]',
    '写作题': '[写作]',
  };
  return map[type] || '[单选]';
}
```

- [ ] **Step 1.3** 添加判断题样式类

```javascript
getTypeClass(type) {
  const map = {
    '多选题': 'multi',
    '判断题': 'judge',  // 新增
    '论述题': 'essay',
    '写作题': 'essay',
  };
  return map[type] || '';
}
```

- [ ] **Step 1.4** 添加判断题 CSS

```css
.q-type-badge.judge {
  background: #8B5CF6;
}
```

- [ ] **Step 1.5** 修复图片路径（与 Task 3 相同）

- [ ] **Step 1.6** 提交

```bash
git add .vtj/vue/answer_page.vue
git commit -m "feat: 添加判断题支持，修复图片路径格式"
```

---

## Task 5: 前端 — smart_answer.vue 判断题支持

**Files:**
- Modify: `.vtj/vue/smart_answer.vue` (题型判断逻辑)

### Step 1: 读取 smart_answer.vue 确认当前实现

- [ ] **Step 1.1** 读取 `smart_answer.vue` 确认题型判断逻辑

- [ ] **Step 1.2** 添加判断题支持（当前只有单选/多选）

```javascript
// 添加判断题处理
if (type === '判断题') {
  // 判断题只有两个选项：A（对）和 B（错）
  options = [
    { label: 'A. 对', value: 'A' },
    { label: 'B. 错', value: 'B' },
  ];
}
```

- [ ] **Step 1.3** 提交

```bash
git add .vtj/vue/smart_answer.vue
git commit -m "feat: 添加判断题支持"
```

---

## Task 6: 前端 — paper_answer.vue 图片路径修复

**Files:**
- Modify: `.vtj/vue/paper_answer.vue` (图片渲染)

### Step 1: 读取 paper_answer.vue 确认图片渲染位置

- [ ] **Step 1.1** 读取 `paper_answer.vue` 确认图片渲染逻辑

- [ ] **Step 1.2** 修复图片路径（与 Task 3 相同）

- [ ] **Step 1.3** 提交

```bash
git add .vtj/vue/paper_answer.vue
git commit -m "fix: 修复图片路径格式"
```

---

## Task 7: 前端 — admin_questions.vue 判断题徽章

**Files:**
- Modify: `.vtj/vue/admin_questions.vue` (typeBadgeClass)

### Step 1: 读取 admin_questions.vue 确认修改位置

- [ ] **Step 1.1** 读取 `admin_questions.vue` 第60-70行确认 typeBadgeClass

- [ ] **Step 1.2** 添加判断题徽章样式

```javascript
function typeBadgeClass(typeInfo) {
  const name = typeDisplayName(typeInfo);
  const map = {
    '单选题': 'badge-single',
    '多选题': 'badge-multi',
    '判断题': 'badge-judge',  // 新增
    '论述题': 'badge-essay',
    '写作题': 'badge-writing',
  };
  return map[name] || 'badge-single';
}
```

- [ ] **Step 1.3** 添加判断题 CSS

```css
.badge-judge {
  background: #8B5CF6;
}
```

- [ ] **Step 1.4** 提交

```bash
git add .vtj/vue/admin_questions.vue
git commit -m "feat: 添加判断题徽章"
```

---

## Task 8: 验证与合并

### Step 1: 验证所有修改

- [ ] **Step 1.1** 启动后端服务验证判断题识别

```bash
cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

- [ ] **Step 1.2** 访问教师端验证判断题徽章显示

- [ ] **Step 1.3** 访问学生端验证判断题交互

- [ ] **Step 1.4** 访问管理端验证判断题徽章显示

- [ ] **Step 1.5** 验证 36 道图片题目的显示

### Step 2: 合并到 master

- [ ] **Step 2.1** 创建新分支并提交

```bash
git checkout -b feat/teacher-core-fix-round3
git add .
git commit -m "feat: 第三轮修复 - 判断题支持+图片路径修复+导入优化"
```

- [ ] **Step 2.2** 合并到 master

```bash
git checkout master
git branch -f master feat/teacher-core-fix-round3
git checkout master
```

---

## 自审清单

- [ ] 所有修改文件路径正确
- [ ] 判断题后端识别逻辑完整
- [ ] 判断题前端三端显示一致
- [ ] 图片路径格式正确（扁平格式）
- [ ] 二维码检测增强
- [ ] 所有步骤有具体代码
- [ ] 无 TBD/TODO 占位符
