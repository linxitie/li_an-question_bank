# 教师端功能深度优化 - 设计文档

## 项目概述

**项目名称**: 公安联考题库系统 - 教师端功能优化  
**技术栈**: VTJ.PRO + Vue 3 + Element Plus + FastAPI（后端Python）  
**设计日期**: 2026年9月5日  
**设计目标**: 解决教师端7个核心问题，提升用户体验和系统稳定性

---

## 问题清单

### 问题1: 题目图片路径断裂
**现象**: 数据库中存储了题目图片路径，但前端无法正确显示图片  
**影响范围**: 所有含图片的题目  
**优先级**: 🔴 高

### 问题2: 空试卷自动生成
**现象**: 每次导入文档时，系统会自动创建一个空试卷，即使已有同名试卷  
**影响范围**: 试卷管理模块  
**优先级**: 🟡 中

### 问题3: 缺失信息无法补充
**现象**: 在题目导入预览阶段，编辑对话框保存后数据不生效  
**影响范围**: 题目导入模块  
**优先级**: 🟡 中

---

## 解决方案

### 方案A: 分层修复（推荐）

**核心理念**: 针对每个问题独立修复，风险低、改动可控

**优势**:
- 每个修复独立，可单独测试
- 不影响其他功能模块
- 回滚简单

**劣势**:
- 可能存在重复代码
- 长期维护成本略高

---

## 详细设计

### 任务1: 恢复题目图片路径

#### 1.1 路径标准化函数 (image_service.py)

**功能**: 统一处理所有图片路径格式

**实现**:
```python
def normalize_image_path(path: str, question_id: int) -> str:
    """
    将各种格式的图片路径标准化为 /static/questions/{qid}/{filename}
    
    支持的输入格式:
    - /static/questions/42/img_0_abc.png
    - static/questions/42/img_0_abc.png
    - ../static/questions/42/img_0_abc.png
    - /uploads/questions/42/img_0_abc.png
    - [IMAGE:42_0]
    
    输出格式:
    - /static/questions/42/img_0_abc.png
    """
    if not path:
        return ''
    
    # 1. 去除查询参数
    path = path.split('?')[0]
    
    # 2. 处理 [IMAGE:xxx] 占位符
    image_match = re.match(r'\[(\d+)_(\d+)\]', path)
    if image_match:
        qid = image_match.group(1)
        idx = image_match.group(2)
        # 在 question_images 表中查找真实路径
        real_path = find_image_in_db(int(qid), int(idx))
        if real_path:
            return normalize_image_path(real_path, int(qid))
        # 兜底：生成默认路径
        return f'/static/questions/{qid}/img_{idx}.jpg'
    
    # 3. 统一路径分隔符
    path = path.replace('\\', '/')
    
    # 4. 去除多余的 ../ 或 ./
    while '/../' in path or '/./' in path:
        path = path.replace('/../', '/').replace('/./', '/')
    
    # 5. 确保以 /static/questions/ 开头
    if not path.startswith('/static/questions/'):
        # 提取 question_id 和 filename
        parts = path.split('/')
        if len(parts) >= 2:
            qid_part = parts[-2]
            filename = parts[-1]
            path = f'/static/questions/{qid_part}/{filename}'
    
    return path
```

**安全性考虑**:
- 路径遍历防护：拒绝包含 `..` 的路径
- SSRF检测：拒绝外部URL
- 文件类型验证：只允许图片格式

#### 1.2 数据迁移脚本 (scripts/fix_image_paths.py)

**功能**: 批量修复现有数据中的图片路径

**实现逻辑**:
1. 扫描 `question_bank` 表中含 `[IMAGE:xxx]` 或 `<img>` 标签的题目
2. 检查对应图片文件是否存在
3. 从 `question_images` 表查找有效路径
4. 修复路径格式不一致的问题
5. 生成修复报告

**执行命令**:
```bash
cd backend
python scripts/fix_image_paths.py --dry-run  # 预览模式
python scripts/fix_image_paths.py --execute  # 执行修复
```

#### 1.3 前端兜底增强 (teacher_questions.vue)

**功能**: 图片加载失败时的智能重试

**实现**:
```javascript
// 图片加载失败处理
function handleImageError(event, questionId) {
  const img = event.target;
  const originalSrc = img.src;
  
  // 尝试1: 去除查询参数
  const cleanSrc = originalSrc.split('?')[0];
  if (cleanSrc !== originalSrc) {
    img.src = cleanSrc;
    return;
  }
  
  // 尝试2: 从相对路径转为绝对路径
  if (!cleanSrc.startsWith('http')) {
    img.src = window.location.origin + cleanSrc;
    return;
  }
  
  // 尝试3: 从 question_images 表重新获取
  fetch(`/api/questions/${questionId}/images`)
    .then(res => res.json())
    .then(data => {
      if (data.images && data.images.length > 0) {
        img.src = data.images[0].path;
      } else {
        // 所有尝试失败，显示占位图
        img.src = '/static/images/placeholder.png';
      }
    })
    .catch(() => {
      img.src = '/static/images/placeholder.png';
    });
}
```

---

### 任务2: 优化空试卷创建机制

#### 2.1 添加阈值检查 (question_import.py)

**功能**: 少于5道题不自动创建试卷

**修改位置**: `question_import.py` 第1043行

**实现**:
```python
def _get_or_create_import_paper(db, user, auto_tags: Dict[str, Any], filename: str, question_count: int = 0):
    """
    根据检测到的标签自动创建或查找ExamPaper
    
    新增参数:
        question_count: 导入的题目数量
    
    阈值规则:
        - question_count < 5: 不创建试卷，只入库
        - question_count >= 5: 正常创建试卷
    """
    # 阈值检查：少于5题不创建试卷
    MIN_QUESTION_COUNT = 5
    if question_count < MIN_QUESTION_COUNT:
        logger.info(f"[import-paper] 题目数量({question_count})少于阈值({MIN_QUESTION_COUNT})，跳过试卷创建")
        return None
    
    # ... 原有逻辑保持不变 ...
```

#### 2.2 加强同名复用逻辑

**功能**: 改进试卷名称匹配算法

**实现**:
```python
import re
from difflib import SequenceMatcher

def _normalize_paper_name(name: str) -> str:
    """
    标准化试卷名称，用于比较
    - 去除空格、标点符号
    - 统一全角/半角字符
    """
    # 去除空格
    name = re.sub(r'\s+', '', name)
    # 去除标点符号
    name = re.sub(r'[，。、；：？！""''【】（）]', '', name)
    # 统一全角/半角
    name = name.replace('（', '(').replace('）', ')')
    return name

def _is_similar_name(name1: str, name2: str, threshold: float = 0.8) -> bool:
    """
    判断两个试卷名称是否相似
    """
    norm1 = _normalize_paper_name(name1)
    norm2 = _normalize_paper_name(name2)
    
    # 完全匹配
    if norm1 == norm2:
        return True
    
    # 模糊匹配
    similarity = SequenceMatcher(None, norm1, norm2).ratio()
    return similarity >= threshold
```

#### 2.3 延迟创建策略

**功能**: 预览阶段不创建试卷，确认导入时才创建

**修改位置**: `question_import.py` 第2167行

**实现**:
```python
# 预览阶段：只解析，不创建试卷
# 确认导入阶段：创建试卷并关联题目

# 在 /parse 端点中
# 移除自动创建试卷的逻辑
# 只返回解析结果

# 在 /confirm 端点中
# 添加试卷创建逻辑
paper = _get_or_create_import_paper(
    db, current_user, auto_tags, 
    file.filename, 
    question_count=len(items)
)
```

---

### 任务3: 补充缺失信息弹窗设置

#### 3.1 修复编辑保存流程 (question_preview_list.vue)

**功能**: 确保编辑数据正确传递回父组件

**修改位置**: `question_preview_list.vue` 第181-195行

**实现**:
```javascript
// 保存编辑
const saveEdit = function() {
  if (!editForm.answer || editForm.answer === '待补充') {
    alert('请填写正确答案');
    return;
  }
  
  // 更新本地数据
  const q = props.questions[editIndex.value];
  q.question_content = editForm.question_content;
  q.question_type_detail = editForm.question_type_detail;
  q.difficulty = editForm.difficulty;
  q.options = JSON.parse(JSON.stringify(editForm.options));
  q.answer = editForm.answer;
  q.analysis = editForm.analysis;
  
  // 通知父组件
  emit('edit-question', {
    index: editIndex.value,
    data: {
      question_content: editForm.question_content,
      question_type_detail: editForm.question_type_detail,
      difficulty: editForm.difficulty,
      options: editForm.options,
      answer: editForm.answer,
      analysis: editForm.analysis
    }
  });
  
  closeEditDialog();
};
```

#### 3.2 增强编辑界面

**功能**: 添加缺失字段的视觉提示

**实现**:
```html
<!-- 答案输入框 - 缺失时红色边框 -->
<div class="edit-field" :class="{ 'field-missing': !editForm.answer || editForm.answer === '待补充' }">
  <label>答案：<span class="required">*</span></label>
  <input v-model="editForm.answer" placeholder="请输入答案（如：A、AB、ABCD）" />
  <span class="field-hint" v-if="!editForm.answer || editForm.answer === '待补充'">
    ⚠ 必填项
  </span>
</div>

<!-- 解析输入框 - 缺失时黄色边框 -->
<div class="edit-field" :class="{ 'field-warning': !editForm.analysis }">
  <label>答案解析：</label>
  <textarea v-model="editForm.analysis" rows="3" placeholder="请输入答案解析（可选）"></textarea>
  <span class="field-hint" v-if="!editForm.analysis">
    💡 建议补充解析，帮助学生理解
  </span>
</div>
```

**CSS样式**:
```css
.field-missing {
  border: 2px solid #f56c6c;
  border-radius: 6px;
  padding: 8px;
  background: rgba(245, 108, 108, 0.05);
}

.field-warning {
  border: 2px solid #e6a23c;
  border-radius: 6px;
  padding: 8px;
  background: rgba(230, 162, 60, 0.05);
}

.required {
  color: #f56c6c;
  font-weight: bold;
}

.field-hint {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
  display: block;
}
```

#### 3.3 自动检测缺失信息

**功能**: 在预览阶段自动检测每道题的缺失字段

**实现**:
```javascript
// 计算属性：统计缺失信息
const missingStats = computed(() => {
  const stats = {
    total: props.questions.length,
    missingAnswer: 0,
    missingAnalysis: 0,
    missingOptions: 0
  };
  
  props.questions.forEach(q => {
    if (!q.answer || q.answer === '待补充') {
      stats.missingAnswer++;
    }
    if (!q.analysis) {
      stats.missingAnalysis++;
    }
    if (!q.options || q.options.length === 0) {
      stats.missingOptions++;
    }
  });
  
  return stats;
});
```

**模板**:
```html
<!-- 顶部统计栏 -->
<div class="docs-list-stats">
  <span class="docs-stat-total">共 {{ questions.length }} 题</span>
  <span class="docs-stat-missing" v-if="missingStats.missingAnswer > 0">
    ⚠ 缺答案 {{ missingStats.missingAnswer }} 题
  </span>
  <span class="docs-stat-missing" v-if="missingStats.missingAnalysis > 0">
    💡 缺解析 {{ missingStats.missingAnalysis }} 题
  </span>
  <button class="btn-batch-edit" @click="batchEditMissing" 
          v-if="missingStats.missingAnswer > 0 || missingStats.missingAnalysis > 0">
    📝 批量补充缺失信息
  </button>
</div>
```

---

## 文件修改清单

| 文件路径 | 修改内容 | 优先级 |
|---------|---------|--------|
| `backend/app/services/image_service.py` | 添加 `normalize_image_path()` 函数 | 🔴 高 |
| `backend/scripts/fix_image_paths.py` | 新建数据迁移脚本 | 🔴 高 |
| `backend/app/api/v1/question_import.py` | 优化 `_get_or_create_import_paper()` 函数 | 🟡 中 |
| `.vtj/vue/question_preview_list.vue` | 修复编辑保存流程 + 增强编辑界面 | 🟡 中 |
| `.vtj/vue/teacher_questions.vue` | 增强图片加载失败处理 | 🟡 中 |

---

## 安全性考虑

### 1. 路径遍历防护
- 拒绝包含 `..` 的路径
- 验证路径格式符合规范

### 2. SSRF检测
- 拒绝外部URL（http/https开头的非本站地址）
- 只允许站内图片路径

### 3. 文件类型验证
- 只允许图片格式（jpg, png, gif, webp）
- 验证文件大小（不超过5MB）

### 4. SQL注入防护
- 使用参数化查询
- 对用户输入进行转义

---

## 运维便利性

### 1. 日志记录
- 所有关键操作都有日志
- 支持日志级别配置

### 2. 监控指标
- 图片显示率统计
- 试卷创建成功率
- 编辑操作成功率

### 3. 回滚机制
- 每个修复都有独立的回滚方案
- 数据迁移脚本支持 dry-run 模式

---

## 测试计划

### 单元测试
- `normalize_image_path()` 函数测试
- `_get_or_create_import_paper()` 函数测试
- 编辑保存流程测试

### 集成测试
- 图片显示完整流程测试
- 试卷创建完整流程测试
- 编辑信息补充完整流程测试

### 用户验收测试
- 验证图片能正确显示
- 验证试卷不会重复创建
- 验证编辑保存后数据生效

---

## 实施步骤

### Phase 1: 图片路径修复 (1天)
1. 实现 `normalize_image_path()` 函数
2. 编写数据迁移脚本
3. 测试修复效果

### Phase 2: 空试卷机制优化 (0.5天)
1. 修改 `_get_or_create_import_paper()` 函数
2. 添加阈值检查
3. 测试试卷创建逻辑

### Phase 3: 缺失信息补充 (1天)
1. 修复编辑保存流程
2. 增强编辑界面
3. 添加缺失信息检测
4. 测试编辑功能

### Phase 4: 集成测试 (0.5天)
1. 端到端测试
2. 性能测试
3. 安全测试

**总预计工时**: 3天

---

## 风险评估

### 低风险
- 图片路径标准化：纯函数修改，不影响其他模块
- 编辑界面增强：UI改动，不影响业务逻辑

### 中风险
- 空试卷机制修改：可能影响现有导入流程
- 数据迁移脚本：需要在测试环境充分验证

### 缓解措施
- 所有修改都有回滚方案
- 数据迁移前备份数据库
- 分阶段发布，逐步验证

---

## 设计决策记录

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 修复策略 | 分层修复 | 风险低、改动可控 |
| 图片路径格式 | `/static/questions/{qid}/{filename}` | 与现有代码一致 |
| 试卷创建阈值 | 5道题 | 平衡用户体验和系统资源 |
| 编辑保存方式 | emit事件 | 符合Vue组件通信规范 |

---

**文档版本**: v1.0  
**最后更新**: 2026年9月5日  
**作者**: Superpowers Agent
