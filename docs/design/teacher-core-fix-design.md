# 教师端核心问题修复设计文档

## 项目概述

**项目名称**: 公安联考题库系统 - 教师端核心问题修复  
**技术栈**: VTJ.PRO + Vue 3 + Element Plus + FastAPI（后端Python）  
**设计日期**: 2026年9月6日  
**设计目标**: 解决图片路径断裂、判断题缺失、题目导入优化三个核心问题

---

## 问题清单

### 问题1: 图片路径断裂
**现象**: 数据库中 `[IMAGE:hash_idx]` 格式的占位符无法显示图片  
**根因**: 图片文件以扁平格式存储（`static/questions/hash_idx.png`），但前端渲染时使用目录格式（`/static/questions/hash/hash_idx.png`）  
**影响范围**: 36道题目（占总题目2363的1.5%）  
**优先级**: 🔴 高

### 问题2: 判断题缺失
**现象**: 公安联考中的判断题无法正确识别和显示  
**根因**: 
- `TYPE_NORMALIZE_MAP` 将判断题映射为单选题
- `main.py` 批量将数据库中判断题更新为单选题
- 前端三端缺少判断题的徽章样式和交互  
**影响范围**: 所有判断题  
**优先级**: 🔴 高

### 问题3: 题目导入优化
**现象**: 导入时无法高效识别判断题，且无关图片过滤不完善  
**根因**: 
- 判断题识别关键词不够全面
- 二维码检测缺少颜色特征分析
- 缺少收款码、公众号码等具体场景的过滤  
**影响范围**: 题目导入模块  
**优先级**: 🟡 中

---

## 详细设计

### 任务1: 修复图片路径断裂

#### 1.1 修复前端渲染逻辑

**修改文件**: `.vtj/vue/teacher_questions.vue`

**修改内容**: 
- `cleanHtmlContent` 函数将 `[IMAGE:hash_idx]` 转为正确的扁平路径
- 添加 `onerror` 兜底显示占位图

**实现**:
```javascript
// 修复前
cleaned = cleaned.replace(/\[IMAGE:(\d+)_(\d+)\]/g, function(_match, qid, idx) {
  return '<img src="/static/questions/' + qid + '/' + qid + '_' + idx + '.png" ...>';
});

// 修复后
cleaned = cleaned.replace(/\[IMAGE:([a-fA-F0-9]+)_(\d+)\]/g, function(_match, hash, idx) {
  return '<img src="/static/questions/' + hash + '_' + idx + '.png" ...>';
});
```

#### 1.2 修复其他前端文件

**修改文件**: 
- `.vtj/vue/answer_page.vue`
- `.vtj/vue/paper_answer.vue`

**修改内容**: 同样修复图片路径格式

---

### 任务2: 添加判断题完整支持

#### 2.1 后端修改

**修改文件**: `backend/app/services/text_parser.py`

**修改内容**:
1. 删除 `TYPE_NORMALIZE_MAP` 中的判断题→单选题映射
2. 添加判断题专属徽章颜色
3. 增强判断题识别逻辑

**实现**:
```python
# 修复前
TYPE_NORMALIZE_MAP = {
    '判断题': '单选题',  # 删除此行
}

# 修复后
TYPE_NORMALIZE_MAP = {
    '单选题': '单选题',
    '多选题': '多选题',
    '论述题': '论述题',
    '写作题': '写作题',
    # 判断题不再映射，保持独立
}

TYPE_BADGE_COLORS = {
    '单选题': '#409EFF',
    '多选题': '#67C23A',
    '判断题': '#8B5CF6',  # 新增紫色
    '论述题': '#E6A23C',
    '写作题': '#F56C6C',
}
```

**修改文件**: `backend/app/main.py`

**修改内容**: 删除第267行将判断题更新为单选题的逻辑

#### 2.2 前端修改

**修改文件**: `.vtj/vue/teacher_questions.vue`

**修改内容**:
- `typeBadgeClass` 添加判断题样式
- 添加 `.badge-judge` CSS

**实现**:
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

```css
.badge-judge { background: #8B5CF6; }
```

**修改文件**: `.vtj/vue/answer_page.vue`

**修改内容**:
- `getTypeLabel` 添加判断题
- `getTypeClass` 添加判断题
- 添加判断题的"对/错"二选一交互
- 添加 `.q-type-badge.judge` CSS

**实现**:
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

```css
.q-type-badge.judge { background: #8B5CF6; }
```

**修改文件**: `.vtj/vue/smart_answer.vue`

**修改内容**: 添加判断题支持

**修改文件**: `.vtj/vue/admin_questions.vue`

**修改内容**: `typeBadgeClass` 添加判断题样式

#### 2.3 统一识别机制

**设计原则**:
- 后端 `text_parser.py` 的 `_detect_question_type` 作为唯一识别入口
- 前端三端统一使用后端返回的 `type_name` 字段
- 删除前端重复的题型识别逻辑

---

### 任务3: 优化题目导入

#### 3.1 增强判断题识别

**修改文件**: `backend/app/services/text_parser.py`

**修改内容**:
- 添加更多公安联考特有的判断题关键词
- 添加"对/错"二选一的选项模式识别
- 添加答案格式分析（A/B 对应对/错）

**实现**:
```python
# 判断题关键词（增强版）
JUDGE_KEYWORDS = [
    '判断', '是否', '对错', '正确还是错误', '说法正确', '说法错误',
    '正确的是', '错误的是', '不正确的是', '下列说法正确', '下列说法错误',
    '以下说法正确', '以下说法错误', '表述正确的是', '表述错误的是',
    '对的是', '错的是', '正确的一项', '错误的一项',
]
```

#### 3.2 增强二维码检测

**修改文件**: `backend/app/services/image_filters.py`

**修改内容**:
- 添加颜色特征分析（收款二维码通常有特定颜色模式）
- 添加尺寸启发式（二维码通常是正方形）
- 添加文字密度分析（二维码区域文字密度低）
- 添加"收款码"、"微信码"、"支付宝码"等关键词

**实现**:
```python
def _detect_qr_enhanced(img_bytes: bytes):
    """增强版二维码检测"""
    # 1. 原有 OpenCV 检测
    result = _detect_qr(img_bytes)
    if result:
        return result
    
    # 2. 颜色特征分析
    if _HAS_PIL:
        try:
            img = Image.open(io.BytesIO(img_bytes))
            # 收款二维码通常有红色/蓝色元素
            # 微信二维码是绿色，支付宝是蓝色
            # 但这里不做自动删除，只做标记
        except Exception:
            pass
    
    # 3. 尺寸启发式
    # 二维码通常是正方形，宽高比接近1:1
    
    return None
```

#### 3.3 优化无关图片过滤

**修改文件**: `backend/app/services/text_parser.py`

**修改内容**:
- 增强 `is_irrelevant_image` 函数
- 添加"收款码"、"微信码"、"支付宝码"等关键词
- 添加文档末尾图片的自动过滤

**实现**:
```python
IRRELEVANT_IMAGE_PATTERNS = [
    # ... 现有模式
    re.compile(r'(?:收款|支付|微信支付|支付宝)', re.IGNORECASE),
    re.compile(r'(?:扫码付款|付款码|收款码)', re.IGNORECASE),
]
```

---

## 文件变更清单

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `backend/app/services/text_parser.py` | 修改 | 删除判断题映射，增强识别逻辑 |
| `backend/app/main.py` | 修改 | 删除判断题批量更新逻辑 |
| `backend/app/services/image_filters.py` | 修改 | 增强二维码检测 |
| `.vtj/vue/teacher_questions.vue` | 修改 | 添加判断题徽章，修复图片路径 |
| `.vtj/vue/answer_page.vue` | 修改 | 添加判断题支持，修复图片路径 |
| `.vtj/vue/paper_answer.vue` | 修改 | 修复图片路径 |
| `.vtj/vue/smart_answer.vue` | 修改 | 添加判断题支持 |
| `.vtj/vue/admin_questions.vue` | 修改 | 添加判断题徽章 |

---

## 验证方案

1. **图片路径验证**:
   - 检查数据库中 36 道包含 `[IMAGE:]` 的题目
   - 验证前端能正确显示图片或显示占位图

2. **判断题验证**:
   - 导入包含判断题的文档
   - 验证三端能正确显示判断题徽章
   - 验证学生端能正确选择"对/错"

3. **导入优化验证**:
   - 导入包含二维码的PDF
   - 验证二维码被正确过滤
   - 验证判断题被正确识别

---

## 风险评估

1. **数据库兼容性**: 删除判断题→单选题映射可能影响已有数据
   - 缓解：保留数据库中已有的判断题类型，不进行批量更新

2. **前端兼容性**: 添加判断题徽章可能影响现有样式
   - 缓解：使用独立的 CSS 类名，不影响其他题型

3. **导入兼容性**: 增强识别逻辑可能影响已有导入流程
   - 缓解：保持向后兼容，新增逻辑不影响原有流程
