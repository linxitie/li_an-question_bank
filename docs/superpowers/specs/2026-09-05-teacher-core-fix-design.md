# 教师端核心功能修复 - 规格文档

## 1. 项目概述

### 1.1 项目名称
教师端核心功能修复（Teacher Core Fix）

### 1.2 项目目标
解决教师端三个核心问题，提升用户体验和系统稳定性：
1. 恢复题目图片路径显示
2. 优化空试卷创建机制
3. 实现缺失信息补充功能

### 1.3 技术栈
- **前端**: VTJ.PRO + Vue 3 + Element Plus
- **后端**: FastAPI + SQLAlchemy + MySQL
- **图片存储**: 本地文件系统 + 静态文件服务

### 1.4 工作区
- **分支**: `feat/teacher-core-fix`
- **工作区根目录**: `D:\砺安题库\砺安题库`

---

## 2. 功能需求

### 2.1 任务1: 恢复题目图片路径

#### 2.1.1 功能描述
修复数据库中题目图片路径断裂问题，确保前端能正确显示题目图片。

#### 2.1.2 详细需求

**后端需求**:
1. **路径标准化函数** (`image_service.py`):
   - 添加 `normalize_image_path(path, question_id)` 函数
   - 支持多种路径格式转换为统一格式 `/static/questions/{qid}/{filename}`
   - 支持 `[IMAGE:xxx]` 占位符转换
   - 支持相对路径转绝对路径

2. **数据迁移脚本** (`scripts/fix_image_paths.py`):
   - 扫描 `question_bank` 表中含图片的题目
   - 检查图片文件是否存在
   - 从 `question_images` 表查找有效路径
   - 修复路径格式不一致的问题
   - 支持 `--dry-run` 模式预览

3. **API接口增强** (`teacher.py`):
   - 添加 `GET /api/teacher/images/health` 接口
   - 返回图片健康统计（总数、缺失数、修复数）

**前端需求**:
1. **图片加载失败处理** (`teacher_questions.vue`):
   - 增强 `handleImageError()` 函数
   - 添加多级重试机制（去参数→转绝对路径→重新获取）
   - 显示占位图作为最终兜底

2. **图片健康监控** (`teacher_questions.vue`):
   - 添加图片健康状态指示器
   - 显示图片显示率统计

#### 2.1.3 验收标准
- [ ] 所有含图片的题目在前端正确显示图片
- [ ] 图片路径格式统一为 `/static/questions/{qid}/{filename}`
- [ ] 图片加载失败时显示占位图
- [ ] 数据迁移脚本可正常运行

---

### 2.2 任务2: 优化空试卷创建机制

#### 2.2.1 功能描述
修改试卷创建逻辑，避免每次导入都自动创建空试卷。

#### 2.2.2 详细需求

**后端需求**:
1. **阈值检查** (`question_import.py`):
   - 修改 `_get_or_create_import_paper()` 函数
   - 添加 `question_count` 参数
   - 至少5道题才自动创建试卷
   - 少于5题只入库不建卷

2. **同名复用增强** (`question_import.py`):
   - 添加 `_normalize_paper_name()` 函数
   - 添加 `_is_similar_name()` 函数
   - 名称相似度>80%时复用已有试卷

3. **延迟创建策略** (`question_import.py`):
   - 预览阶段（`/parse`端点）不创建试卷
   - 确认导入阶段（`/confirm`端点）才创建试卷
   - 避免预览后取消导致的空试卷

**前端需求**:
1. **试卷创建状态显示** (`question_import.js`):
   - 显示是否创建了新试卷
   - 显示关联的题目数量

#### 2.2.3 验收标准
- [ ] 导入少于5题时不创建试卷
- [ ] 同名试卷复用而非新建
- [ ] 预览阶段不创建试卷
- [ ] 试卷管理中无空试卷

---

### 2.3 任务3: 补充缺失信息弹窗设置

#### 2.3.1 功能描述
在题目导入预览阶段，实现缺失信息的编辑和补充功能。

#### 2.3.2 详细需求

**前端需求**:
1. **修复编辑保存流程** (`question_preview_list.vue`):
   - 修改 `saveEdit()` 函数
   - 确保数据正确写回 `questions` 数组
   - 使用 `emit('edit-question', { index, data })` 通知父组件

2. **增强编辑界面** (`question_preview_list.vue`):
   - 添加缺失字段的视觉提示（红色边框）
   - 必填字段验证（答案不能为空）
   - 支持选项的添加和删除

3. **自动检测缺失信息** (`question_preview_list.vue`):
   - 添加 `missingStats` 计算属性
   - 统计缺失答案、解析、选项的题目数量
   - 在顶部统计栏显示缺失信息

4. **批量编辑功能** (`question_preview_list.vue`):
   - 添加 `batchEditMissing()` 函数
   - 支持批量补充缺失答案
   - 支持批量补充缺失解析

**后端需求**:
1. **缺失信息统计接口** (`teacher.py`):
   - 添加 `GET /api/teacher/questions/missing-stats` 接口
   - 返回缺失答案、解析的题目数量

#### 2.3.3 验收标准
- [ ] 编辑对话框能正常打开和保存
- [ ] 保存后数据在前端正确显示
- [ ] 缺失字段有视觉提示
- [ ] 必填字段验证生效
- [ ] 缺失信息统计准确

---

## 3. 技术实现方案

### 3.1 图片路径标准化

```python
# backend/app/services/image_service.py

def normalize_image_path(path: str, question_id: int) -> str:
    """
    将各种格式的图片路径标准化为 /static/questions/{qid}/{filename}
    
    支持的输入格式:
    - /static/questions/42/img_0_abc.png
    - static/questions/42/img_0_abc.png
    - ../static/questions/42/img_0_abc.png
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
        return f'/static/questions/{qid}/img_{idx}.jpg'
    
    # 3. 统一路径分隔符
    path = path.replace('\\', '/')
    
    # 4. 确保以 /static/questions/ 开头
    if not path.startswith('/static/questions/'):
        parts = path.split('/')
        if len(parts) >= 2:
            qid_part = parts[-2]
            filename = parts[-1]
            path = f'/static/questions/{qid_part}/{filename}'
    
    return path
```

### 3.2 试卷创建阈值检查

```python
# backend/app/api/v1/question_import.py

def _get_or_create_import_paper(db, user, auto_tags, filename, question_count=0):
    """
    根据检测到的标签自动创建或查找ExamPaper
    
    新增参数:
        question_count: 导入的题目数量
    
    阈值规则:
        - question_count < 5: 不创建试卷，只入库
        - question_count >= 5: 正常创建试卷
    """
    MIN_QUESTION_COUNT = 5
    if question_count < MIN_QUESTION_COUNT:
        logger.info(f"[import-paper] 题目数量({question_count})少于阈值({MIN_QUESTION_COUNT})，跳过试卷创建")
        return None
    
    # ... 原有逻辑保持不变 ...
```

### 3.3 编辑保存流程修复

```javascript
// .vtj/vue/question_preview_list.vue

const saveEdit = function() {
  // 必填字段验证
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

---

## 4. 文件修改清单

### 4.1 后端文件

| 文件路径 | 修改内容 | 优先级 |
|---------|---------|--------|
| `backend/app/services/image_service.py` | 添加 `normalize_image_path()` 函数 | 🔴 高 |
| `backend/scripts/fix_image_paths.py` | 新建数据迁移脚本 | 🔴 高 |
| `backend/app/api/v1/question_import.py` | 优化 `_get_or_create_import_paper()` 函数 | 🟡 中 |
| `backend/app/api/v1/teacher.py` | 添加图片健康检查接口 | 🟡 中 |

### 4.2 前端文件

| 文件路径 | 修改内容 | 优先级 |
|---------|---------|--------|
| `.vtj/vue/question_preview_list.vue` | 修复编辑保存流程 + 增强编辑界面 | 🟡 中 |
| `.vtj/vue/teacher_questions.vue` | 增强图片加载失败处理 | 🟡 中 |

---

## 5. 安全性考虑

### 5.1 路径遍历防护
- 拒绝包含 `..` 的路径
- 验证路径格式符合规范

### 5.2 SSRF检测
- 拒绝外部URL（http/https开头的非本站地址）
- 只允许站内图片路径

### 5.3 文件类型验证
- 只允许图片格式（jpg, png, gif, webp）
- 验证文件大小（不超过5MB）

### 5.4 SQL注入防护
- 使用参数化查询
- 对用户输入进行转义

---

## 6. 测试计划

### 6.1 单元测试
- `normalize_image_path()` 函数测试
- `_get_or_create_import_paper()` 函数测试
- 编辑保存流程测试

### 6.2 集成测试
- 图片显示完整流程测试
- 试卷创建完整流程测试
- 编辑信息补充完整流程测试

### 6.3 用户验收测试
- 验证图片能正确显示
- 验证试卷不会重复创建
- 验证编辑保存后数据生效

---

## 7. 验收标准

### 7.1 任务1验收标准
- [ ] 所有含图片的题目在前端正确显示图片
- [ ] 图片路径格式统一为 `/static/questions/{qid}/{filename}`
- [ ] 图片加载失败时显示占位图
- [ ] 数据迁移脚本可正常运行

### 7.2 任务2验收标准
- [ ] 导入少于5题时不创建试卷
- [ ] 同名试卷复用而非新建
- [ ] 预览阶段不创建试卷
- [ ] 试卷管理中无空试卷

### 7.3 任务3验收标准
- [ ] 编辑对话框能正常打开和保存
- [ ] 保存后数据在前端正确显示
- [ ] 缺失字段有视觉提示
- [ ] 必填字段验证生效
- [ ] 缺失信息统计准确

---

## 8. 实施步骤

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

## 9. 风险评估

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

**文档版本**: v1.0
**最后更新**: 2026年9月5日
**作者**: Superpowers Agent
