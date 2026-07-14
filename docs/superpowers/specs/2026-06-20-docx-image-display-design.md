# DOCX图片获取与答题卡展示 — 设计文档

## Context
测试DOCX文件（2016年公务员联考《公安基础知识》试卷）包含11张图片，分布在题目题干和选项中。当前后端已能提取图片（12个PNG文件已保存到`static/questions/`），但前端无法正确渲染——题干用`{{ }}`文本插值（HTML被转义），选项完全不做IMAGE标记替换。

## 修改清单

### 后端：修正图片保存路径

**文件**: `backend/app/api/v1/question_import.py` — `_extract_text_from_docx()`

**问题**: `img_dir` 通过 `os.path.dirname(__file__)` 计算，但作为被导入模块时路径不可靠。

**修复**: 使用与 `main.py` 一致的绝对路径计算方式。`main.py` 第197行已正确计算：
```python
_img_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'questions')
```
在 `_extract_text_from_docx` 中复用相同逻辑。

### 前端1：选项文本也做IMAGE替换

**文件**: `.vtj/vue/ujvdv5fe.vue` — `loadQuestions()`

**当前**: 只对 `stem` 做 `[IMAGE:qn_seq]` → `<img>` 替换（第319行）。`parsedOpts` 不做替换。

**修复**: 在构建 `parsedOpts` 后，对每个选项文本执行相同的 IMAGE 替换。

```javascript
// 对每个选项做IMAGE替换
parsedOpts = parsedOpts.map(function(opt) {
    if (typeof opt === 'string') {
        return opt.replace(/\[IMAGE:(\d+)_(\d+)\]/g, function(m, qn, idx) {
            return '<img src="/static/questions/' + qn + '_' + idx + '.png" class="q-img" loading="lazy" onerror="this.style.display=none" />';
        });
    }
    return opt;
});
```

### 前端2：模板改用 v-html 渲染

**文件**: `.vtj/vue/ujvdv5fe.vue` — template

**改动**:
- 第98-100行：`{{ q.stem }}` → `v-html="q.stem"`（题干图片能渲染）
- 第120行：`{{ opt }}` → `v-html="opt"`（选项图片能渲染）

⚠️ XSS注意：题干和选项文本来自数据库，由后端控制，风险可控。

### 前端3：选项图片CSS

**文件**: `.vtj/vue/ujvdv5fe.vue` — `<style>`

新增 `.option-text :deep(img.q-img)` 样式：
- `max-width: 100%; max-height: 150px`（比题干图片小）
- `display: block; margin: 6px 0`（左对齐）
- `border-radius: 6px`

题干图片保持现有样式（max-height: 300px, 居中）。

## 数据流

```
DOCX文件
  → _extract_text_from_docx() 提取图片 → static/questions/{qn}_{seq}.png
  → 文本中插入 [IMAGE:qn_seq] 占位
  → extract_question_blocks() 解析为结构化数据
  → 导入DB（content和options含IMAGE标记）
  → /api/questions/random 返回（标记透传）
  → 前端 loadQuestions() 替换标记为 <img> 标签
  → v-html 渲染HTML
```

## 验证
1. 导入测试DOCX → 确认 `static/questions/` 有12个PNG文件
2. `curl /api/questions/random` → question_content和options含 `[IMAGE:...]` 标记
3. 浏览器答题卡 → 题干中图片居中展示，选项中图片嵌入展示
4. 图片加载失败时 `onerror` 隐藏，不显示破图
