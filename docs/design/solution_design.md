# 三大问题解决方案设计文档

> 创建时间: 2026-08-22
> 状态: 待用户审核

---

## 一、问题概述

| # | 问题 | 影响范围 | 优先级 |
|---|------|---------|--------|
| 1 | 题目管理中UTB ID残留未清除 | 教师端题目管理列表+详情 | P0 |
| 2 | 非题目图片（二维码/收款码）混入题目 | 全部题目显示 | P0 |
| 3 | 单选题被错误判定为论述题 | 导入题型自动分类 | P0 |

---

## 二、根因分析

### 问题1: UTB ID残留

**根因链**:
1. 数据库 `question_bank.question_content` 中已存储的题目包含 UTB ID（如 `UTB7df857a7`）
2. 后端 `teacher.py` 的 `_format_question()` 函数直接返回原始 `question_content`，未调用清洗函数
3. 前端 `teacher_questions.vue` 的 `renderSummary()` 调用了 `cleanQuestionContent()` 清洗列表摘要
4. **但** 详情弹窗（第99行）使用 `v-html="currentQuestion.full_content || currentQuestion.question_content"` 直接显示原始内容，未清洗
5. `full_content` 在后端（teacher.py第53行）就是 `q.question_content` 的原值

**关键代码路径**:
```
数据库(question_content 含UTB ID)
  → teacher.py _format_question() (原样返回)
    → 前端列表 renderSummary() (清洗后显示 ✅)
    → 前端详情 v-html (原样显示 ❌)
```

### 问题2: 非题目图片

**根因链**:
1. `ContentCleaner.is_irrelevant_image()` 已定义黑名单（二维码/微信/淘宝等）
2. 但该函数只在**新导入时**由 `_extract_and_save_images` 间接调用
3. 数据库中已存在的图片未经过过滤
4. 文档末尾的图片（position_ratio > 0.85）被标记为广告但未实际移除
5. 导入时图片按题号归属，但文档末尾的独立二维码/收款码可能被错误归属到最后一题

**关键代码路径**:
```
docx导入 → _extract_text_from_docx() → 图片按段落归属
  → is_irrelevant_image() 检查 (新导入有效)
  → 但已入库的图片无此过滤 (历史数据污染)
```

### 问题3: 单选题误判为论述题

**根因链**:
1. `_detect_question_type()` 维度5依赖选项文本长度：`len(str(o)) < 30` → 选择题加分
2. 当选项文本包含 UTB ID 残留（如 `UTB7df857a7-选项A-5`）时，选项文本变长超过30字符
3. 维度5无法加分，导致"正确的是"等关键词的论述题权重相对更高
4. 虽然维度6（答案字母一致性）有单选加分，但当答案字段也含UTB残留时，`^[A-D]$` 正则匹配失败
5. 最终论述题得分最高，被错误分类

**关键代码路径**:
```
题目("人民警察基本素养测试要点5的表述正确的是？")
  + 选项("UTB7df857a7-选项A-5") → len > 30 → 维度5不加分
  + 答案("UTB7df857a7 A") → ^[A-D]$ 不匹配 → 维度1不加分
  + 题干含"正确的是" → +2单选 vs +2论述 → 平局
  → 论述题关键词"表述"可能触发论述加分 → 论述题胜出
```

---

## 三、解决方案设计

### 方案1: UTB ID 清除（数据库修复 + 前端双重清洗）

#### 3.1.1 数据库批量清洗脚本

```python
# solve_problems_files/fix_utb_in_db.py
"""
一次性脚本：清洗数据库中所有题目内容的UTB ID
策略：直接更新 question_bank.question_content 和 answer_analysis 字段
"""
import re
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.core.database import SessionLocal
from app.models.models import QuestionBank

UTB_PATTERN = re.compile(r'UTB[a-f0-9]{8,}(?:[-－]\s*选项[A-D]\s*\d*)?', re.IGNORECASE)
UTB_OPTION_PATTERN = re.compile(r'UTB[a-f0-9]{8,}[-－]\s*选项[A-D][-－]?\d*', re.IGNORECASE)
QNUM_PREFIX = re.compile(r'^第\s*\d+\s*题[：:]\s*')

def clean_text(text: str) -> str:
    if not text:
        return text
    text = UTB_PATTERN.sub('', text)
    text = UTB_OPTION_PATTERN.sub('', text)
    text = QNUM_PREFIX.sub('', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def main():
    db = SessionLocal()
    try:
        # 批量查询含UTB的题目
        questions = db.query(QuestionBank).filter(
            QuestionBank.question_content.like('%UTB%')
        ).all()
        
        updated = 0
        for q in questions:
            old_content = q.question_content or ''
            new_content = clean_text(old_content)
            if new_content != old_content:
                q.question_content = new_content
                updated += 1
            
            # 同时清洗答案解析
            if q.answer_analysis and 'UTB' in q.answer_analysis:
                q.answer_analysis = clean_text(q.answer_analysis)
            
            # 清洗answer字段中的UTB残留
            if q.answer and 'UTB' in q.answer:
                # 只清理UTB部分，保留正确答案字母
                q.answer = UTB_PATTERN.sub('', q.answer).strip()
        
        db.commit()
        print(f"清洗完成: 共扫描 {len(questions)} 题, 更新 {updated} 题")
    except Exception as e:
        db.rollback()
        print(f"错误: {e}")
    finally:
        db.close()

if __name__ == '__main__':
    main()
```

#### 3.1.2 后端 API 层清洗（teacher.py）

修改 `_format_question()` 函数，对返回内容做清洗：

```python
# teacher.py 修改
from ...services.text_parser import clean_question_text

def _format_question(q: QuestionBank) -> dict:
    """格式化题目信息（含内容清洗）"""
    raw_content = q.question_content or ''
    return {
        # ... 其他字段不变 ...
        "question_content": clean_question_text(raw_content)[:120],
        "full_content": clean_question_text(raw_content),
        # ... 其他字段不变 ...
    }
```

#### 3.1.3 前端双重保险（teacher_questions.vue）

详情弹窗也加清洗：

```html
<!-- 修改前 -->
<div class="detail-content" v-html="currentQuestion.full_content || currentQuestion.question_content"></div>

<!-- 修改后 -->
<div class="detail-content" v-html="cleanHtmlContent(currentQuestion.full_content || currentQuestion.question_content)"></div>
```

新增清洗函数（处理HTML中的UTB）：

```javascript
function cleanHtmlContent(text: string) {
  if (!text) return '';
  // 移除UTB ID（含HTML标签中的）
  let cleaned = text.replace(/UTB[a-f0-9]{8,}[-－]?\s*选项?[A-H]?[-－]?\d*/gi, '');
  // 移除题号前缀
  cleaned = cleaned.replace(/第\s*\d+\s*题[：:]\s*/g, '');
  return cleaned.trim();
}
```

### 方案2: 非题目图片过滤

#### 3.2.1 导入时增强过滤（question_import.py）

在 `_extract_text_from_docx` 中增加图片过滤逻辑：

```python
# 在图片归属判定时增加无关图片过滤
from ...services.text_parser import ContentCleaner

# 在图片保存前检查
for rId in rids:
    img_filename = f'{session_id}_{current_qn}_{seq}.png'
    position_ratio = current_qn / total_paragraphs  # 近似位置
    
    if ContentCleaner.is_irrelevant_image(img_filename, position_ratio):
        logger.debug(f"[import] 过滤无关图片: {img_filename} (位置={position_ratio:.2f})")
        continue  # 跳过不保存
    
    # 正常保存图片...
```

#### 3.2.2 数据库修复脚本

```python
# solve_problems_files/fix_irrelevant_images.py
"""
清理数据库中已存在的无关图片
策略：检查图片文件名和路径，匹配黑名单则标记/删除
"""
import re
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.core.database import SessionLocal
from app.models.models import QuestionBank, QuestionImage

IRRELEVANT_PATTERNS = [
    re.compile(r'(?:qr|qrcode|二维码|erweima)', re.IGNORECASE),
    re.compile(r'(?:wechat|weixin|微信)', re.IGNORECASE),
    re.compile(r'(?:taobao|淘宝|拼多多|京东|闲鱼|天猫)', re.IGNORECASE),
    re.compile(r'(?:广告|ad|promo|推广)', re.IGNORECASE),
    re.compile(r'(?:公众号|订阅号|gzh)', re.IGNORECASE),
]

def main():
    db = SessionLocal()
    try:
        images = db.query(QuestionImage).all()
        removed = 0
        for img in images:
            path = img.image_path or ''
            basename = os.path.basename(path)
            for pattern in IRRELEVANT_PATTERNS:
                if pattern.search(basename):
                    # 从题目内容中移除对应img标签
                    q = db.query(QuestionBank).filter(
                        QuestionBank.question_id == img.question_id
                    ).first()
                    if q and q.question_content:
                        # 移除img标签
                        new_content = re.sub(
                            r'<img[^>]*src=["\'][^"\']*' + re.escape(basename) + r'[^"\']*["\'][^>]*/?>',
                            '', q.question_content
                        )
                        q.question_content = new_content
                    
                    # 删除图片记录和文件
                    full_path = os.path.join('backend', 'app', path)
                    if os.path.exists(full_path):
                        os.remove(full_path)
                    db.delete(img)
                    removed += 1
                    break
        
        db.commit()
        print(f"清理完成: 共检查 {len(images)} 张图片, 移除 {removed} 张无关图片")
    except Exception as e:
        db.rollback()
        print(f"错误: {e}")
    finally:
        db.close()

if __name__ == '__main__':
    main()
```

#### 3.2.3 前端图片占位（teacher_questions.vue）

列表中对含图片的题目显示图标提示：

```javascript
function renderSummary(q: any) {
  const text = q.question_content || '';
  const cleaned = stripPromoText(text);
  const cleanText = cleanQuestionContent(cleaned);
  // 替换img标签为[图片]占位
  const withPlaceholders = cleanText.replace(/<img[^>]*\/?>/g, '[📷图片]');
  const truncated = withPlaceholders.length > 80 
    ? withPlaceholders.substring(0, 80) + '...' 
    : withPlaceholders;
  return truncated;
}
```

### 方案3: 题型判定增强

#### 3.3.1 选项文本预清洗（text_parser.py）

在 `_detect_question_type` 中先清洗选项再判定：

```python
def _detect_question_type(content: str, options: List[str], answer: str = '') -> tuple[str, float]:
    # ... 前面不变 ...
    
    # ★ 新增：清洗选项文本中的UTB残留后再分析
    cleaned_options = []
    for o in (options_list or []):
        o_str = str(o) if o else ''
        o_str = UTB_PATTERN.sub('', o_str).strip()  # 清洗UTB ID
        o_str = re.sub(r'^[A-H]\s*[.、．）\]]\s*', '', o_str).strip()  # 清理选项标签
        cleaned_options.append(o_str)
    
    # 清洗答案中的UTB残留
    clean_answer = UTB_PATTERN.sub('', answer).strip()
    
    # ★ 清洗题干中的UTB残留
    clean_content = UTB_PATTERN.sub('', content_text).strip()
    
    # 使用清洗后的数据进行判定
    opt_count = len([o for o in cleaned_options if o])
    answer = clean_answer.upper()
    content_lower = clean_content.lower()
    
    # ... 后续评分逻辑不变，但使用清洗后的数据 ...
```

#### 3.3.2 增强关键词权重

```python
# 维度4 增强：当有选项时，选择题关键词权重提升
CHOICE_KEYWORDS = ['下列', '以下', '正确的是', '错误的是', '不正确的是', 
                   '属于的是', '不属于的是', '表述正确', '说法正确']

if opt_count >= 2:  # ★ 有选项时选择题关键词加分翻倍
    if any(kw in content_lower for kw in CHOICE_KEYWORDS):
        scores['单选题'] += 4  # 原来+2，提升到+4
        scores['多选题'] += 2  # 原来+1，提升到+2
```

---

## 四、修改文件清单

| 文件 | 修改类型 | 说明 |
|------|---------|------|
| `backend/app/services/text_parser.py` | 增强 | `_detect_question_type` 增加选项预清洗 |
| `backend/app/api/v1/teacher.py` | 增强 | `_format_question` 增加内容清洗 |
| `backend/app/api/v1/question_import.py` | 增强 | 导入时过滤无关图片 |
| `.vtj/vue/teacher_questions.vue` | 增强 | 详情弹窗UTB清洗 + 图片占位 |
| `solve_problems_files/fix_utb_in_db.py` | 新建 | 数据库UTB批量清洗脚本 |
| `solve_problems_files/fix_irrelevant_images.py` | 新建 | 数据库无关图片清理脚本 |

---

## 五、验证方案

1. **UTB清洗**: 运行 `fix_utb_in_db.py`，验证教师端题目列表和详情不再显示UTB ID
2. **图片过滤**: 运行 `fix_irrelevant_images.py`，验证二维码/收款码图片已移除
3. **题型判定**: 导入含"正确的是"的单选题文档，验证不再误判为论述题
4. **回归测试**: 验证原有正常题目不受影响

---

## 六、风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| 数据库清洗脚本误删有效内容 | 低 | 高 | 脚本先备份再执行 |
| 题型判定过度修正 | 中 | 中 | 保守加分策略，不减少现有权重 |
| 前端清洗遗漏 | 低 | 低 | 后端+前端双重清洗 |

---

**等待用户审核确认后开始实施**
