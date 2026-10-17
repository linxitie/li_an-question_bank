# 教师端题目管理全面问题分析与解决方案

> 创建时间: 2026-08-22
> 状态: 待用户审核

---

## 一、问题概述

| # | 问题 | 影响范围 | 优先级 | 根因确认 |
|---|------|---------|--------|---------|
| 1 | 题目管理中UTB ID残留未清除 | 教师端题目管理列表+详情+编辑 | P0 | ✅ 已确认 |
| 2 | 非题目图片（二维码/收款码）混入题目 | 全部题目显示 | P0 | ✅ 已确认 |
| 3 | 单选题被错误判定为论述题 | 导入题型自动分类 | P0 | ✅ 已确认 |
| 4 | 前端导入工具函数未使用 | questionFilter.js | P1 | ✅ 已确认 |
| 5 | 后端编辑接口未清洗UTB | teacher.py update_question | P1 | ✅ 已确认 |

---

## 二、根因分析（深度挖掘）

### 问题1: UTB ID残留 — 三重断裂

**断裂点1: 后端API层无清洗**
```
teacher.py _format_question()
  → question_content = q.question_content (原样返回)
  → full_content = q.question_content (原样返回)
  → 无任何清洗调用 ❌
```

**断裂点2: 前端导入未使用**
```
teacher_questions.vue 第211行:
  import { filterQuestionContent } from '@/utils/questionFilter';
  → 从未调用 ❌
```

**断裂点3: 详情弹窗直接显示原始内容**
```
teacher_questions.vue 第99行:
  v-html="currentQuestion.full_content || currentQuestion.question_content"
  → 无清洗处理 ❌
```

**关键证据**:
- `question_import.py` 第1323行: `clean_content = clean_question_text(content)` ✅ 导入时清洗
- `teacher.py` 全文搜索: 无 `clean_question_text` 调用 ❌
- `questionFilter.js` 第11行: `export function filterQuestionContent(content)` ✅ 已有清洗函数
- `teacher_questions.vue` 第211行: `import { filterQuestionContent }` ❌ 导入未使用

### 问题2: 非题目图片 — 过滤机制断裂

**断裂点1: 导入时过滤仅检查文件名**
```
ContentCleaner.is_irrelevant_image(filename, position_ratio)
  → 只检查文件名模式
  → 不检查图片内容（二维码/收款码）
  → 不检查图片尺寸（小图标）
```

**断裂点2: 历史数据未清理**
```
数据库中已存在的图片:
  → 无批量清理机制
  → 无定期巡检机制
```

**断裂点3: 文档末尾图片归属错误**
```
docx导入时:
  → 独立图片段落归属到最后一题
  → 末尾二维码被错误保存为题目图片
```

### 问题3: 单选题误判 — 选项文本污染

**污染链**:
```
导入时:
  选项文本 = "UTB7df857a7-选项A-5"
  → len("UTB7df857a7-选项A-5") = 22 > 30? No, 但清洗后长度变化
  → 维度5: short_opts = sum(1 for o in options if len(str(o)) < 30)
  → 如果选项含UTB, len(str(o)) 可能 > 30
  → 维度5不加分
  → 论述题关键词"正确的是"权重相对更高
  → 最终判定为论述题
```

**验证数据**:
- 题干: "人民警察基本素养测试要点5的表述正确的是？"
- 选项: ["UTB7df857a7-选项A-5", "UTB7df857a7-选项B-5", ...]
- 答案: "UTB7df857a7 A"
- 期望: 单选题
- 实际: 论述题

---

## 三、解决方案设计

### 方案1: UTB ID清除 — 三层清洗策略

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

#### 3.1.2 后端API层清洗（teacher.py）

修改 `_format_question()` 函数：

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

#### 3.1.3 前端详情弹窗清洗

修改 `teacher_questions.vue` 第99行：

```html
<!-- 修改前 -->
<div class="detail-content" v-html="currentQuestion.full_content || currentQuestion.question_content"></div>

<!-- 修改后 -->
<div class="detail-content" v-html="cleanHtmlContent(currentQuestion.full_content || currentQuestion.question_content)"></div>
```

新增清洗函数：

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

---

### 方案2: 非题目图片过滤 — 三层防线

#### 3.2.1 导入时增强过滤（question_import.py）

在 `_extract_text_from_docx` 中增加图片过滤：

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

---

### 方案3: 题型判定增强 — 选项预清洗 + 权重调整

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
