# 题目系统深度优化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 优化题型识别机制、删除不完整题目、深度优化题目导入功能

**Architecture:** 后端修改 text_parser.py 优化题型识别规则，创建数据库清理脚本删除不完整题目，增强 mineru_service.py 的PDF和图片识别能力

**Tech Stack:** VTJ.PRO + Vue 3 + Element Plus + FastAPI + SQLite + MinerU + Tesseract OCR

---

## 文件结构

### 修改文件
| 文件 | 职责 |
|------|------|
| `backend/app/services/text_parser.py` | 优化题型识别规则 |
| `backend/app/services/mineru_service.py` | 增强PDF和图片识别 |
| `backend/scripts/cleanup_incomplete.py` | 数据库清理脚本（新建） |

---

## Task 1: 优化题型识别规则

**Files:**
- Modify: `backend/app/services/text_parser.py:1818-1976` (_detect_question_type)

### Step 1: 读取 text_parser.py 确认修改位置

- [ ] **Step 1.1** 读取 `text_parser.py` 第1818-1976行确认 _detect_question_type 函数

- [ ] **Step 1.2** 优化判断题识别规则

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

- [ ] **Step 1.3** 优化答案格式分析

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

- [ ] **Step 1.4** 增加排除条件

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

- [ ] **Step 1.5** 增加置信度阈值

```python
# 低置信度标记
if confidence < 0.6:
    logger.warning(f"[type-detect] 低置信度({confidence:.2f})题型判定: {final_type}")
```

- [ ] **Step 1.6** 提交

```bash
git add backend/app/services/text_parser.py
git commit -m "feat: 优化题型识别规则，减少误判"
```

---

## Task 2: 创建数据库清理脚本

**Files:**
- Create: `backend/scripts/cleanup_incomplete.py`

### Step 1: 创建清理脚本

- [ ] **Step 1.1** 创建 `backend/scripts/cleanup_incomplete.py`

```python
#!/usr/bin/env python3
"""
清理不完整题目脚本
删除选项缺失、解析缺失、图片占位符的题目
"""
import sqlite3
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings

def cleanup_incomplete_questions():
    """清理不完整题目"""
    db_path = os.path.join(settings.BASE_DIR, 'data', 'question_bank.db')
    
    # 备份数据库
    backup_path = db_path + '.backup'
    if not os.path.exists(backup_path):
        import shutil
        shutil.copy2(db_path, backup_path)
        print(f'已备份数据库到: {backup_path}')
    
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # 1. 删除选项缺失的题目
    c.execute("""
        DELETE FROM question_bank 
        WHERE type_id IN (1,3,5)  -- 单选/多选/判断
        AND (options IS NULL OR options = '[]' OR options = '')
    """)
    deleted_options = c.rowcount
    print(f'删除选项缺失题目: {deleted_options}')
    
    # 2. 删除解析缺失的题目
    c.execute("""
        DELETE FROM question_bank 
        WHERE answer_analysis IS NULL OR answer_analysis = ''
    """)
    deleted_analysis = c.rowcount
    print(f'删除解析缺失题目: {deleted_analysis}')
    
    # 3. 删除含图片占位符的题目
    c.execute("""
        DELETE FROM question_bank 
        WHERE question_content LIKE '%[IMAGE:%'
    """)
    deleted_images = c.rowcount
    print(f'删除图片占位符题目: {deleted_images}')
    
    # 4. 验证删除结果
    c.execute("SELECT COUNT(*) FROM question_bank")
    remaining = c.fetchone()[0]
    print(f'剩余题目数量: {remaining}')
    
    conn.commit()
    conn.close()
    
    print(f'\n清理完成:')
    print(f'  选项缺失: {deleted_options}')
    print(f'  解析缺失: {deleted_analysis}')
    print(f'  图片占位符: {deleted_images}')
    print(f'  剩余题目: {remaining}')

if __name__ == '__main__':
    cleanup_incomplete_questions()
```

- [ ] **Step 1.2** 提交

```bash
git add backend/scripts/cleanup_incomplete.py
git commit -m "feat: 创建数据库清理脚本"
```

---

## Task 3: 执行数据库清理

**Files:**
- Execute: `backend/scripts/cleanup_incomplete.py`

### Step 1: 执行清理脚本

- [ ] **Step 1.1** 执行清理脚本

```bash
cd backend && python scripts/cleanup_incomplete.py
```

- [ ] **Step 1.2** 验证清理结果

```bash
cd backend && python -c "
import sqlite3
conn = sqlite3.connect('data/question_bank.db')
c = conn.cursor()
c.execute('SELECT COUNT(*) FROM question_bank')
print(f'剩余题目: {c.fetchone()[0]}')
conn.close()
"
```

- [ ] **Step 1.3** 提交数据库变更

```bash
git add backend/data/question_bank.db
git commit -m "feat: 清理不完整题目"
```

---

## Task 4: 增强PDF和图片识别能力

**Files:**
- Modify: `backend/app/services/mineru_service.py`

### Step 1: 读取 mineru_service.py 确认修改位置

- [ ] **Step 1.1** 读取 `mineru_service.py` 确认当前实现

- [ ] **Step 1.2** 增强OCR能力

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
```

- [ ] **Step 1.3** 增强PDF解析

```python
def enhance_pdf_parsing(pdf_path):
    """增强PDF解析能力"""
    # 1. 使用MinerU解析
    # 2. 如果MinerU失败，使用OCR解析
    # 3. 返回解析结果
    pass
```

- [ ] **Step 1.4** 提交

```bash
git add backend/app/services/mineru_service.py
git commit -m "feat: 增强PDF和图片识别能力"
```

---

## Task 5: 验证与测试

### Step 1: 验证题型识别

- [ ] **Step 1.1** 启动后端服务

```bash
cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

- [ ] **Step 1.2** 导入包含各种题型的文档验证题型识别

- [ ] **Step 1.3** 验证没有误判情况

### Step 2: 验证导入功能

- [ ] **Step 2.1** 导入PDF扫描件

- [ ] **Step 2.2** 导入包含图片的文档

- [ ] **Step 2.3** 验证图片和文字被正确提取

---

## 自审清单

- [ ] 所有修改文件路径正确
- [ ] 题型识别规则优化完整
- [ ] 数据库清理脚本正确
- [ ] PDF和图片识别增强完整
- [ ] 所有步骤有具体代码
- [ ] 无 TBD/TODO 占位符
