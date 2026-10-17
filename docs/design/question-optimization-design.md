# 题目系统深度优化设计文档

## 项目概述

**项目名称**: 公安联考题库系统 - 题目系统深度优化  
**技术栈**: VTJ.PRO + Vue 3 + Element Plus + FastAPI（后端Python）  
**设计日期**: 2026年9月6日  
**设计目标**: 优化题型识别机制、删除不完整题目、深度优化题目导入功能

---

## 问题清单

### 问题1: 题型识别机制不精确
**现象**: 单选题被认定为判断题，多选题被认定为判断题等随意认定题目类型的情况  
**根因**: 
- 判断题识别过于宽松（`opt_count == 2` 加3分）
- 判断题关键词与单选题关键词重叠
- 缺少排除条件  
**影响范围**: 所有题目的类型判定  
**优先级**: 🔴 高

### 问题2: 不完整题目需要清理
**现象**: 数据库中存在选项缺失、解析缺失、图片占位符等不完整的题目  
**根因**: 历史导入时未进行完整性校验  
**影响范围**: 60道选项缺失 + 274道解析缺失 + 36道图片占位符 = 370道不完整题目  
**优先级**: 🔴 高

### 问题3: 题目导入功能需要深度优化
**现象**: 导入时无法高效识别题型，解析提取不完整，图片处理不完善  
**根因**: 
- 题型识别规则不够精确
- 解析提取逻辑不够完善
- PDF扫描件和图片识别能力不足  
**影响范围**: 题目导入模块  
**优先级**: 🟡 中

---

## 详细设计

### 任务1: 优化题型识别机制

#### 1.1 判断题识别规则优化

**修改文件**: `backend/app/services/text_parser.py`

**修改内容**:
1. 收紧判断题识别条件
2. 增加排除条件
3. 增强多选题识别

**实现**:

```python
# === 维度2: 选项数量分析（优化版）===
if opt_count == 2:
    # ★ 判断题识别收紧：必须同时满足以下条件
    # 1. 选项内容包含判断词（对/错/正确/错误）
    # 2. 答案为A或B
    has_judge_opts = False
    for opt in cleaned_options:
        if any(kw in opt for kw in ['对', '错', '正确', '错误', 'True', 'False']):
            has_judge_opts = True
            break
    
    if has_judge_opts and answer in ['A', 'B', '对', '错', '正确', '错误', 'TRUE', 'FALSE', 'T', 'F']:
        scores['判断题'] += 5  # 强判断题倾向
    else:
        scores['单选题'] += 3  # 普通2选项题视为单选
        scores['多选题'] += 1
elif opt_count == 4:
    # 4选项默认单选，但题干含多选关键词时倾向多选
    if any(re.search(kw, content_text) for kw in MULTI_CHOICE_KEYWORDS):
        scores['多选题'] += 3
        scores['单选题'] -= 1
    else:
        scores['单选题'] += 3
        scores['多选题'] += 1
elif opt_count > 4:
    scores['多选题'] += 4  # 增强多选倾向
elif opt_count == 0:
    scores['论述题'] += 2
    scores['简答题'] += 2
    scores['填空题'] += 1
```

#### 1.2 答案格式分析优化

```python
# === 维度1: 答案格式分析（优化版）===
if answer:
    # ★ 多选题答案：强制认定
    if re.match(r'^[A-D]([，,][A-D])+$', answer):
        scores['多选题'] += 8  # 强多选倾向
    elif re.fullmatch(r'[A-D]{2,4}', answer):
        scores['多选题'] += 8  # 连写多字母答案
    # 单选题答案
    elif re.match(r'^[A-D]$', answer):
        scores['单选题'] += 5
    # 判断题答案：必须是明确的判断词
    elif answer in ['正确', '错误', '对', '错', 'TRUE', 'FALSE', 'T', 'F']:
        scores['判断题'] += 5
    # 主观题答案
    elif len(answer) > 20:
        scores['论述题'] += 3
        scores['简答题'] += 2
    elif len(answer) > 5:
        scores['简答题'] += 2
```

#### 1.3 增加排除条件

```python
# === 维度7: 排除条件（新增）===
# 如果答案为单个字母且选项>=3，强制排除判断题
if answer and re.match(r'^[A-D]$', answer) and opt_count >= 3:
    scores['判断题'] = 0  # 强制排除判断题
    scores['单选题'] += 3

# 如果答案为多个字母，强制排除单选题和判断题
if answer and re.match(r'^[A-D]([，,][A-D])+$', answer):
    scores['单选题'] = 0
    scores['判断题'] = 0
    scores['多选题'] += 5
```

#### 1.4 增加置信度阈值

```python
# 低置信度标记
if confidence < 0.6:
    logger.warning(f"[type-detect] 低置信度({confidence:.2f})题型判定: {final_type}")
    # 可选：标记为待审核
```

---

### 任务2: 删除不完整题目

#### 2.1 删除范围

| 类型 | 数量 | 删除条件 |
|------|------|----------|
| 选项缺失 | 60 | 选择题（单选/多选/判断）且options为空或[] |
| 解析缺失 | 274 | 所有题型且answer_analysis为空 |
| 图片占位符 | 36 | question_content包含[IMAGE: |

#### 2.2 删除流程

```python
# 1. 创建备份表
CREATE TABLE question_bank_backup AS SELECT * FROM question_bank;

# 2. 删除选项缺失的题目
DELETE FROM question_bank 
WHERE type_id IN (1,3,5)  -- 单选/多选/判断
AND (options IS NULL OR options = '[]' OR options = '');

# 3. 删除解析缺失的题目
DELETE FROM question_bank 
WHERE answer_analysis IS NULL OR answer_analysis = '';

# 4. 删除含图片占位符的题目
DELETE FROM question_bank 
WHERE question_content LIKE '%[IMAGE:%';

# 5. 验证删除结果
SELECT COUNT(*) FROM question_bank;
```

---

### 任务3: 深度优化题目导入功能

#### 3.1 增强题型识别

- 使用优化后的规则
- 增加置信度阈值
- 低置信度时标记为待审核

#### 3.2 增强图片提取

- 修复图片路径格式
- 确保图片能正确保存到 `static/questions/` 目录
- 添加图片完整性校验

#### 3.3 增强答案匹配

- 支持更多答案格式（如"答案：A"、"正确答案：ACD"）
- 支持答案和解析在同一行的情况
- 支持多答案格式（如"1.A 2.B 3.C"）

#### 3.4 增强解析生成

- 自动从答案文档中提取解析
- 支持"解析："、"分析："等关键词
- 支持多行解析

#### 3.5 增强PDF扫描件和图片识别能力

**修改文件**: `backend/app/services/mineru_service.py`

**修改内容**:
1. 增强OCR能力（使用Tesseract作为备用）
2. 增强图片文字提取
3. 增强PDF解析
4. 增强图片内容理解

**实现**:

```python
# 增强OCR能力
try:
    import pytesseract
    from PIL import Image
    
    def extract_text_from_image(image_path):
        """使用Tesseract提取图片中的文字"""
        img = Image.open(image_path)
        # 图片预处理
        img = img.convert('L')  # 转灰度
        # 二值化
        threshold = 128
        img = img.point(lambda p: p > threshold and 255)
        # 提取文字
        text = pytesseract.image_to_string(img, lang='chi_sim+eng')
        return text
except ImportError:
    logger.warning("pytesseract未安装，图片文字提取功能不可用")

# 增强PDF解析
def enhance_pdf_parsing(pdf_path):
    """增强PDF解析能力"""
    # 1. 使用MinerU解析
    # 2. 如果MinerU失败，使用OCR解析
    # 3. 返回解析结果
    pass
```

---

## 文件变更清单

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `backend/app/services/text_parser.py` | 修改 | 优化题型识别规则 |
| `backend/app/services/mineru_service.py` | 修改 | 增强PDF和图片识别 |
| `backend/data/question_bank.db` | 修改 | 删除不完整题目 |

---

## 验证方案

1. **题型识别验证**:
   - 导入包含各种题型的文档
   - 验证题型被正确识别
   - 验证没有误判情况

2. **不完整题目删除验证**:
   - 备份数据库
   - 执行删除脚本
   - 验证删除结果

3. **导入功能验证**:
   - 导入PDF扫描件
   - 导入包含图片的文档
   - 验证图片和文字被正确提取

---

## 风险评估

1. **数据丢失风险**: 删除不完整题目可能导致数据丢失
   - 缓解：创建备份表后再执行删除

2. **识别准确率风险**: 优化后的规则可能仍有误判
   - 缓解：增加置信度阈值，低置信度时标记为待审核

3. **兼容性风险**: 修改可能影响现有功能
   - 缓解：保持向后兼容，新增逻辑不影响原有流程
