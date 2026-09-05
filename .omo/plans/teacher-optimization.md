# 教师端深度优化解决方案

## TL;DR

> **快速摘要**: 针对教师端题目导入和题目管理功能的深度优化，解决编辑功能失效、文档识别不准确、答案解析缺失、图片路径错误和试卷自动创建等问题。
>
> **交付物**:
> - 恢复题目导入页面的完整编辑功能
> - 优化文档识别算法，提高准确率
> - **优化PDF扫描件识别能力**
> - 实现答案解析补充和提示机制
> - 增强图片路径引用的健壮性
> - **在题目管理编辑中支持图片上传**
> - 修复试卷自动创建空试卷的问题
>
> **预计工作量**: 中等
> **并行执行**: 是 - 3个阶段
> **关键路径**: 基础修复 → 功能增强 → 训练优化

---

## Context

### 原始需求
用户提出教师端7个核心问题需要深度优化：
1. 题目导入后答案解析缺失题目无法编辑
2. 文档识别能力需要优化
3. **优化PDF扫描件识别能力**
4. 答案解析缺失的题目需要补充
5. 图片路径引用出错导致无法显示
6. **在题目管理编辑中支持图片上传**
7. 每次导入都会自动创建空试卷

### 研究发现
- 项目使用VTJ.PRO + Vue 3 + Element Plus + FastAPI
- 题目导入页面ID: `question_import`，题目管理页面ID: `teacher_questions`
- 这些页面都是raw: true，由开发者维护
- 后端API在 `backend/app/api/v1/question_import.py` 和 `teacher.py`
- 图片存储在 `backend/static/questions/` 目录

---

## Work Objectives

### 核心目标
恢复和完善教师端题目导入和管理功能，确保系统稳定运行。

### 具体交付物
1. 完整的题目编辑功能
2. 优化的文档识别算法
3. **优化的PDF扫描件识别能力**
4. 答案解析补充机制
5. 健壮的图片路径处理
6. **题目管理中的图片上传功能**
7. 智能的试卷创建逻辑

### 完成定义
- [ ] 所有编辑功能正常工作
- [ ] 文档识别准确率提升
- [ ] **PDF扫描件识别能力增强**
- [ ] 缺失解析的题目能够被识别和补充
- [ ] 图片正确显示
- [ ] **题目管理中支持图片上传**
- [ ] 不再创建空试卷

### Must Have
- 题目编辑功能完整可用
- 图片路径正确引用
- 试卷创建有内容验证
- **PDF扫描件能够正确识别**
- **题目管理中支持图片上传**

### Must NOT Have
- 不影响其他功能模块
- 不破坏现有数据结构
- 不改变系统整体架构

---

## Verification Strategy

### 测试决策
- **基础设施存在**: 是
- **自动化测试**: 是（测试后）
- **框架**: pytest + Vue Test Utils

### QA策略
每个任务都包含代理执行的QA场景。
证据保存到 `.omo/evidence/task-{N}-{scenario-slug}.{ext}`。

---

## Execution Strategy

### 并行执行波次

```
Wave 1 (立即开始 - 基础修复):
├── Task 1: 恢复题目导入编辑功能 [deep]
├── Task 2: 增强图片路径处理 [quick]
└── Task 3: 优化试卷创建条件 [quick]

Wave 2 (Wave 1完成后 - 功能增强):
├── Task 4: 实现答案解析补充接口 [unspecified-high]
├── Task 5: 优化文档识别算法 [deep]
├── Task 6: 添加缺失解析提示功能 [quick]
├── Task 7: 优化PDF扫描件识别能力 [deep]
└── Task 8: 在题目管理编辑中支持图片上传 [unspecified-high]

Wave 3 (Wave 2完成后 - 训练优化):
├── Task 9: 建立文档识别训练机制 [deep]
└── Task 10: 添加识别结果反馈系统 [unspecified-high]

Wave FINAL (所有任务完成后):
├── Task F1: 计划合规审计 [oracle]
├── Task F2: 代码质量审查 [unspecified-high]
├── Task F3: 实际QA测试 [unspecified-high]
└── Task F4: 范围保真检查 [deep]
```

### 依赖矩阵
- **1-3**: 立即开始
- **4-8**: 依赖1-3完成
- **9-10**: 依赖4-8完成
- **F1-F4**: 依赖所有任务完成

---

## TODOs

- [ ] 1. 恢复题目导入编辑功能

  **What to do**:
  - 在`question_preview_list.vue`组件中添加完整的编辑功能
  - 为每道题目添加编辑按钮，点击后弹出编辑对话框
  - 支持编辑：题目内容、选项、答案、答案解析、难度等
  - 确保编辑后的数据能够正确保存并导入

  **Must NOT do**:
  - 不修改组件的整体结构
  - 不影响现有的导入功能
  - 不改变数据格式

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: 需要修改Vue组件，涉及前端UI交互
  - **Skills**: [`vue3`, `element-plus`]
    - `vue3`: 需要修改Vue 3组件
    - `element-plus`: 使用Element Plus组件库

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2, 3)
  - **Blocks**: Tasks 4, 5, 6
  - **Blocked By**: None (can start immediately)

  **References**:
  - `.vtj/vue/question_preview_list.vue` - 当前预览列表组件
  - `.vtj/vue/question_import.vue` - 题目导入页面
  - `src/components/` - 参考其他组件的编辑对话框实现

  **Acceptance Criteria**:
  - [ ] 编辑按钮正常显示
  - [ ] 编辑对话框能够正确打开
  - [ ] 能够编辑题目内容、选项、答案、解析
  - [ ] 保存后数据正确更新
  - [ ] 编辑功能不影响导入流程

  **QA Scenarios**:
  ```
  Scenario: 编辑题目功能测试
    Tool: Playwright
    Preconditions: 已导入题目，预览列表显示
    Steps:
      1. 点击题目卡片上的编辑按钮
      2. 验证编辑对话框弹出
      3. 修改题目内容
      4. 修改答案
      5. 点击保存按钮
      6. 验证数据更新成功
    Expected Result: 编辑对话框正常打开，数据保存成功
    Evidence: .omo/evidence/task-1-edit-functionality.png

  Scenario: 编辑后导入测试
    Tool: Playwright
    Preconditions: 已编辑题目
    Steps:
      1. 编辑题目答案
      2. 点击导入按钮
      3. 验证题目导入成功
      4. 检查数据库中的数据
    Expected Result: 编辑后的数据正确导入
    Evidence: .omo/evidence/task-1-edit-import.png
  ```

  **Commit**: YES
  - Message: `feat(question-import): 恢复题目编辑功能`
  - Files: `.vtj/vue/question_preview_list.vue`
  - Pre-commit: `npm run lint`

---

- [ ] 2. 增强图片路径处理

  **What to do**:
  - 在`teacher_questions.vue`中添加图片路径标准化函数
  - 添加图片加载错误处理
  - 支持多种路径格式的自动转换
  - 添加图片占位符和降级处理

  **Must NOT do**:
  - 不改变图片存储结构
  - 不影响现有图片显示
  - 不删除现有图片文件

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 相对简单的路径处理函数添加
  - **Skills**: [`javascript`, `html`]
    - `javascript`: 需要添加JavaScript函数
    - `html`: 需要处理HTML中的图片标签

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 3)
  - **Blocks**: Tasks 4, 5, 6
  - **Blocked By**: None (can start immediately)

  **References**:
  - `.vtj/vue/teacher_questions.vue` - 题目管理页面
  - `backend/static/questions/` - 图片存储目录
  - `backend/app/api/v1/question_import.py:1107-1256` - 图片保存逻辑

  **Acceptance Criteria**:
  - [ ] 图片路径标准化函数正常工作
  - [ ] 图片加载失败时显示占位符
  - [ ] 支持相对路径和绝对路径
  - [ ] 支持URL格式的图片路径
  - [ ] 不影响现有图片显示

  **QA Scenarios**:
  ```
  Scenario: 图片路径处理测试
    Tool: Playwright
    Preconditions: 题目包含图片
    Steps:
      1. 打开题目管理页面
      2. 查看包含图片的题目
      3. 验证图片正确显示
      4. 模拟图片路径错误
      5. 验证显示占位符
    Expected Result: 图片正确显示或显示占位符
    Evidence: .omo/evidence/task-2-image-path.png

  Scenario: 不同路径格式测试
    Tool: Playwright
    Preconditions: 准备不同格式的图片路径
    Steps:
      1. 测试相对路径 ./static/questions/1/img.png
      2. 测试绝对路径 /static/questions/1/img.png
      3. 测试URL路径 http://example.com/img.png
      4. 验证所有格式都能正确解析
    Expected Result: 所有路径格式都能正确处理
    Evidence: .omo/evidence/task-2-path-formats.png
  ```

  **Commit**: YES
  - Message: `fix(teacher-questions): 增强图片路径处理`
  - Files: `.vtj/vue/teacher_questions.vue`
  - Pre-commit: `npm run lint`

---

- [ ] 3. 优化试卷创建条件

  **What to do**:
  - 修改`_get_or_create_import_paper`函数
  - 添加题目数量阈值检查（至少5题）
  - 添加试卷内容验证（确保有实际题目内容）
  - 支持用户选择是否创建试卷

  **Must NOT do**:
  - 不改变试卷数据结构
  - 不影响现有试卷管理
  - 不删除现有试卷

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 后端逻辑修改，相对简单
  - **Skills**: [`python`, `fastapi`]
    - `python`: 需要修改Python代码
    - `fastapi`: 需要理解FastAPI路由

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2)
  - **Blocks**: Tasks 4, 5, 6
  - **Blocked By**: None (can start immediately)

  **References**:
  - `backend/app/api/v1/question_import.py:1043-1104` - 试卷创建逻辑
  - `backend/app/api/v1/question_import.py:2281-2392` - 批量导入逻辑
  - `backend/app/models/models.py` - 试卷数据模型

  **Acceptance Criteria**:
  - [ ] 题目数量不足时不创建试卷
  - [ ] 内容不完整时不创建试卷
  - [ ] 用户可以选择是否创建试卷
  - [ ] 现有试卷不受影响
  - [ ] 导入流程正常工作

  **QA Scenarios**:
  ```
  Scenario: 试卷创建条件测试
    Tool: Bash (curl)
    Preconditions: 准备测试数据
    Steps:
      1. 导入4道题目（低于阈值）
      2. 验证不创建试卷
      3. 导入6道题目（高于阈值）
      4. 验证创建试卷
    Expected Result: 只有满足条件时才创建试卷
    Evidence: .omo/evidence/task-3-paper-creation.png

  Scenario: 内容验证测试
    Tool: Bash (curl)
    Preconditions: 准备包含无效内容的题目
    Steps:
      1. 导入包含空题干的题目
      2. 验证不创建试卷
      3. 导入有效题目
      4. 验证创建试卷
    Expected Result: 内容有效时才创建试卷
    Evidence: .omo/evidence/task-3-content-validation.png
  ```

  **Commit**: YES
  - Message: `fix(question-import): 优化试卷创建条件`
  - Files: `backend/app/api/v1/question_import.py`
  - Pre-commit: `python -m pytest tests/`

---

- [ ] 4. 实现答案解析补充接口

  **What to do**:
  - 在`teacher.py`中添加获取缺失解析题目的接口
  - 添加补充答案解析的接口
  - 添加批量补充功能
  - 在前端添加答案解析补充界面

  **Must NOT do**:
  - 不改变现有题目数据结构
  - 不影响题目导入功能
  - 不删除现有答案解析

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: 需要修改后端API和前端界面
  - **Skills**: [`python`, `vue3`, `element-plus`]
    - `python`: 需要添加FastAPI接口
    - `vue3`: 需要修改Vue组件
    - `element-plus`: 使用Element Plus组件库

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential
  - **Blocks**: Tasks 5, 6
  - **Blocked By**: Tasks 1, 2, 3

  **References**:
  - `backend/app/api/v1/teacher.py:1-200` - 教师端API结构
  - `backend/app/models/models.py` - 题目数据模型
  - `.vtj/vue/teacher_questions.vue` - 题目管理页面

  **Acceptance Criteria**:
  - [ ] 能够获取缺失解析的题目列表
  - [ ] 能够补充单个题目的答案解析
  - [ ] 能够批量补充答案解析
  - [ ] 前端界面正常工作
  - [ ] 数据正确保存到数据库

  **QA Scenarios**:
  ```
  Scenario: 获取缺失解析题目测试
    Tool: Bash (curl)
    Preconditions: 数据库中有缺失解析的题目
    Steps:
      1. 调用GET /api/teacher/questions/missing-analysis
      2. 验证返回正确的题目列表
      3. 检查题目确实缺失解析
    Expected Result: 正确返回缺失解析的题目
    Evidence: .omo/evidence/task-4-missing-analysis.png

  Scenario: 补充答案解析测试
    Tool: Bash (curl)
    Preconditions: 有缺失解析的题目
    Steps:
      1. 调用PUT /api/teacher/questions/{id}/analysis
      2. 传入答案解析内容
      3. 验证返回成功
      4. 检查数据库中的数据
    Expected Result: 答案解析成功保存
    Evidence: .omo/evidence/task-4-update-analysis.png
  ```

  **Commit**: YES
  - Message: `feat(teacher): 实现答案解析补充接口`
  - Files: `backend/app/api/v1/teacher.py`, `.vtj/vue/teacher_questions.vue`
  - Pre-commit: `python -m pytest tests/`

---

- [ ] 5. 优化文档识别算法

  **What to do**:
  - 优化题目块识别正则表达式
  - 增强选项识别的容错性
  - 支持更多题目格式
  - 添加图像预处理功能

  **Must NOT do**:
  - 不改变文档解析的整体架构
  - 不影响现有识别结果
  - 不降低识别速度

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: 需要深入理解文档解析算法
  - **Skills**: [`python`, `regex`, `ocr`]
    - `python`: 需要修改Python代码
    - `regex`: 需要优化正则表达式
    - `ocr`: 需要理解OCR识别逻辑

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential
  - **Blocks**: Tasks 6, 7, 8
  - **Blocked By**: Tasks 1, 2, 3, 4

  **References**:
  - `backend/app/api/v1/question_import.py:340-413` - 题目解析逻辑
  - `backend/app/services/text_parser.py` - 文本解析服务
  - `backend/app/services/mineru_service.py` - MinerU服务

  **Acceptance Criteria**:
  - [ ] 题目块识别准确率提升
  - [ ] 选项识别容错性增强
  - [ ] 支持更多题目格式
  - [ ] 图像预处理功能正常
  - [ ] 不影响现有识别结果

  **QA Scenarios**:
  ```
  Scenario: 题目识别准确率测试
    Tool: Bash (python)
    Preconditions: 准备测试文档
    Steps:
      1. 准备包含各种格式的测试文档
      2. 调用解析函数
      3. 统计识别准确率
      4. 与优化前对比
    Expected Result: 识别准确率提升
    Evidence: .omo/evidence/task-5-recognition-accuracy.png

  Scenario: 选项识别测试
    Tool: Bash (python)
    Preconditions: 准备包含特殊格式选项的题目
    Steps:
      1. 测试带括号的选项 (A) xxx
      2. 测试带特殊符号的选项 A．xxx
      3. 测试同行多选项 A.xxx B.xxx C.xxx D.xxx
      4. 验证所有格式都能正确识别
    Expected Result: 所有选项格式都能正确识别
    Evidence: .omo/evidence/task-5-option-recognition.png
  ```

  **Commit**: YES
  - Message: `feat(question-import): 优化文档识别算法`
  - Files: `backend/app/api/v1/question_import.py`, `backend/app/services/text_parser.py`
  - Pre-commit: `python -m pytest tests/`

---

- [ ] 6. 添加缺失解析提示功能

  **What to do**:
  - 在题目管理页面标记缺失解析的题目
  - 提供重新导入功能
  - 支持手动补充解析
  - 添加批量操作功能

  **Must NOT do**:
  - 不改变题目列表的显示结构
  - 不影响其他筛选功能
  - 不删除现有题目

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 相对简单的UI添加
  - **Skills**: [`vue3`, `element-plus`]
    - `vue3`: 需要修改Vue组件
    - `element-plus`: 使用Element Plus组件库

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential
  - **Blocks**: Tasks 7, 8
  - **Blocked By**: Tasks 1, 2, 3, 4, 5

  **References**:
  - `.vtj/vue/teacher_questions.vue` - 题目管理页面
  - `backend/app/api/v1/teacher.py` - 教师端API
  - `backend/app/models/models.py` - 题目数据模型

  **Acceptance Criteria**:
  - [ ] 缺失解析的题目正确标记
  - [ ] 重新导入功能正常工作
  - [ ] 手动补充解析功能正常
  - [ ] 批量操作功能正常
  - [ ] 不影响其他筛选功能

  **QA Scenarios**:
  ```
  Scenario: 缺失解析标记测试
    Tool: Playwright
    Preconditions: 数据库中有缺失解析的题目
    Steps:
      1. 打开题目管理页面
      2. 查看缺失解析的题目
      3. 验证正确显示标记
      4. 点击筛选按钮
      5. 验证能正确筛选
    Expected Result: 缺失解析的题目正确标记和筛选
    Evidence: .omo/evidence/task-6-missing-analysis-mark.png

  Scenario: 手动补充解析测试
    Tool: Playwright
    Preconditions: 有缺失解析的题目
    Steps:
      1. 点击缺失解析题目的补充按钮
      2. 输入答案解析内容
      3. 点击保存按钮
      4. 验证保存成功
      5. 检查数据库中的数据
    Expected Result: 答案解析成功保存
    Evidence: .omo/evidence/task-6-manual-analysis.png
  ```

  **Commit**: YES
  - Message: `feat(teacher-questions): 添加缺失解析提示功能`
  - Files: `.vtj/vue/teacher_questions.vue`
  - Pre-commit: `npm run lint`

---

- [ ] 7. 优化PDF扫描件识别能力

  **What to do**:
  - 优化PDF扫描件的OCR识别流程
  - 改进图像预处理（去噪、增强对比度、倾斜校正）
  - 优化文字区域检测和分割算法
  - 支持多种PDF格式和扫描质量
  - 添加识别结果置信度评估

  **Must NOT do**:
  - 不影响现有PDF识别功能
  - 不降低识别速度
  - 不改变整体架构

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: 需要深入理解OCR和图像处理算法
  - **Skills**: [`python`, `ocr`, `image-processing`]
    - `python`: 需要修改Python代码
    - `ocr`: 需要理解PaddleOCR和MinerU
    - `image-processing`: 需要理解图像预处理

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 4, 5, 6, 8)
  - **Blocks**: Tasks 9, 10
  - **Blocked By**: Tasks 1, 2, 3

  **References**:
  - `backend/app/api/v1/question_import.py:542-607` - PDF解析逻辑
  - `backend/app/api/v1/question_import.py:610-733` - 扫描件OCR处理
  - `backend/app/services/mineru_service.py` - MinerU服务
  - `backend/app/services/ocr_worker.py` - OCR worker进程

  **Acceptance Criteria**:
  - [ ] PDF扫描件识别准确率提升
  - [ ] 支持多种扫描质量（低分辨率、倾斜、噪点）
  - [ ] 图像预处理功能正常
  - [ ] 识别结果置信度评估正常
  - [ ] 不影响现有识别功能

  **QA Scenarios**:
  ```
  Scenario: PDF扫描件识别测试
    Tool: Bash (python)
    Preconditions: 准备不同质量的PDF扫描件
    Steps:
      1. 准备低分辨率扫描件（150dpi）
      2. 准备倾斜扫描件（10度倾斜）
      3. 准备有噪点的扫描件
      4. 调用PDF解析函数
      5. 统计识别准确率
      6. 与优化前对比
    Expected Result: 各种质量的扫描件都能正确识别
    Evidence: .omo/evidence/task-7-pdf-scanned-recognition.png

  Scenario: 图像预处理测试
    Tool: Bash (python)
    Preconditions: 准备需要预处理的图像
    Steps:
      1. 测试去噪功能
      2. 测试对比度增强
      3. 测试倾斜校正
      4. 验证预处理效果
    Expected Result: 图像预处理功能正常
    Evidence: .omo/evidence/task-7-image-preprocessing.png
  ```

  **Commit**: YES
  - Message: `feat(question-import): 优化PDF扫描件识别能力`
  - Files: `backend/app/api/v1/question_import.py`, `backend/app/services/ocr_worker.py`
  - Pre-commit: `python -m pytest tests/`

---

- [ ] 8. 在题目管理编辑中支持图片上传

  **What to do**:
  - 在题目管理编辑对话框中添加图片上传功能
  - 支持多图片上传和预览
  - 实现图片存储和路径管理
  - 支持图片删除和替换
  - 在题目内容中插入图片引用

  **Must NOT do**:
  - 不改变题目数据结构
  - 不影响现有图片显示
  - 不删除现有图片文件

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: 需要修改前端界面和后端API
  - **Skills**: [`vue3`, `element-plus`, `python`]
    - `vue3`: 需要修改Vue组件
    - `element-plus`: 使用Element Plus组件库
    - `python`: 需要添加图片上传API

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 4, 5, 6, 7)
  - **Blocks**: Tasks 9, 10
  - **Blocked By**: Tasks 1, 2, 3

  **References**:
  - `.vtj/vue/teacher_questions.vue` - 题目管理页面
  - `backend/app/api/v1/teacher.py` - 教师端API
  - `backend/app/api/v1/question_import.py:1107-1256` - 图片保存逻辑
  - `backend/static/questions/` - 图片存储目录

  **Acceptance Criteria**:
  - [ ] 编辑对话框中显示图片上传区域
  - [ ] 能够上传单张或多张图片
  - [ ] 图片预览正常显示
  - [ ] 能够删除已上传的图片
  - [ ] 图片正确保存到服务器
  - [ ] 图片路径正确插入到题目内容

  **QA Scenarios**:
  ```
  Scenario: 图片上传功能测试
    Tool: Playwright
    Preconditions: 打开题目编辑对话框
    Steps:
      1. 点击编辑按钮打开编辑对话框
      2. 找到图片上传区域
      3. 选择一张图片上传
      4. 验证图片预览显示
      5. 点击保存按钮
      6. 验证图片保存成功
    Expected Result: 图片上传功能正常
    Evidence: .omo/evidence/task-8-image-upload.png

  Scenario: 多图片管理测试
    Tool: Playwright
    Preconditions: 题目已有多张图片
    Steps:
      1. 打开编辑对话框
      2. 查看已上传的图片列表
      3. 删除一张图片
      4. 上传新图片
      5. 验证图片列表更新
      6. 保存并验证
    Expected Result: 多图片管理功能正常
    Evidence: .omo/evidence/task-8-multi-image-management.png
  ```

  **Commit**: YES
  - Message: `feat(teacher-questions): 在编辑中支持图片上传`
  - Files: `.vtj/vue/teacher_questions.vue`, `backend/app/api/v1/teacher.py`
  - Pre-commit: `python -m pytest tests/`

---

- [ ] 9. 建立文档识别训练机制

  **What to do**:
  - 创建文档识别训练模块
  - 支持用户上传样本进行模型微调
  - 建立识别结果反馈机制
  - 添加训练数据管理功能

  **Must NOT do**:
  - 不影响现有识别功能
  - 不降低系统性能
  - 不改变系统架构

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: 需要深入理解机器学习和文档识别
  - **Skills**: [`python`, `machine-learning`, `ocr`]
    - `python`: 需要实现训练逻辑
    - `machine-learning`: 需要理解模型训练
    - `ocr`: 需要理解OCR识别

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential
  - **Blocks**: Task 10
  - **Blocked By**: Tasks 1, 2, 3, 4, 5, 6, 7, 8

  **References**:
  - `backend/app/services/mineru_service.py` - MinerU服务
  - `backend/app/services/text_parser.py` - 文本解析服务
  - `backend/app/api/v1/question_import.py` - 导入API

  **Acceptance Criteria**:
  - [ ] 训练模块正常工作
  - [ ] 能够上传样本数据
  - [ ] 能够进行模型微调
  - [ ] 识别结果反馈机制正常
  - [ ] 训练数据管理功能正常

  **QA Scenarios**:
  ```
  Scenario: 训练模块测试
    Tool: Bash (python)
    Preconditions: 准备训练数据
    Steps:
      1. 上传训练样本
      2. 启动训练任务
      3. 监控训练进度
      4. 验证训练完成
    Expected Result: 训练模块正常工作
    Evidence: .omo/evidence/task-9-training-module.png

  Scenario: 模型微调测试
    Tool: Bash (python)
    Preconditions: 有训练好的模型
    Steps:
      1. 上传新的训练样本
      2. 进行模型微调
      3. 测试微调后的模型
      4. 对比微调前后的效果
    Expected Result: 模型微调提升识别准确率
    Evidence: .omo/evidence/task-9-model-finetuning.png
  ```

  **Commit**: YES
  - Message: `feat(question-import): 建立文档识别训练机制`
  - Files: `backend/app/services/training_service.py`, `backend/app/api/v1/training.py`
  - Pre-commit: `python -m pytest tests/`

---

- [ ] 10. 添加识别结果反馈系统

  **What to do**:
  - 创建识别结果反馈界面
  - 支持用户标记识别错误
  - 建立反馈数据收集机制
  - 添加反馈数据统计分析

  **Must NOT do**:
  - 不影响现有识别流程
  - 不降低系统性能
  - 不改变用户操作习惯

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: 需要修改前端界面和后端API
  - **Skills**: [`python`, `vue3`, `element-plus`]
    - `python`: 需要添加反馈API
    - `vue3`: 需要添加反馈界面
    - `element-plus`: 使用Element Plus组件库

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential
  - **Blocks**: None
  - **Blocked By**: Tasks 1, 2, 3, 4, 5, 6, 7, 8, 9

  **References**:
  - `backend/app/api/v1/question_import.py` - 导入API
  - `.vtj/vue/question_preview_list.vue` - 预览列表组件
  - `backend/app/models/models.py` - 数据模型

  **Acceptance Criteria**:
  - [ ] 反馈界面正常工作
  - [ ] 能够标记识别错误
  - [ ] 反馈数据正确收集
  - [ ] 统计分析功能正常
  - [ ] 不影响现有识别流程

  **QA Scenarios**:
  ```
  Scenario: 反馈界面测试
    Tool: Playwright
    Preconditions: 有识别结果
    Steps:
      1. 打开题目预览界面
      2. 点击反馈按钮
      3. 选择错误类型
      4. 提交反馈
      5. 验证反馈成功
    Expected Result: 反馈界面正常工作
    Evidence: .omo/evidence/task-10-feedback-interface.png

  Scenario: 反馈数据统计测试
    Tool: Bash (python)
    Preconditions: 有反馈数据
    Steps:
      1. 调用统计API
      2. 获取反馈统计数据
      3. 验证数据正确
    Expected Result: 统计数据正确
    Evidence: .omo/evidence/task-10-feedback-statistics.png
  ```

  **Commit**: YES
  - Message: `feat(question-import): 添加识别结果反馈系统`
  - Files: `backend/app/api/v1/feedback.py`, `.vtj/vue/question_preview_list.vue`
  - Pre-commit: `python -m pytest tests/`

---

## Final Verification Wave

- [ ] F1. **Plan Compliance Audit** — `oracle`
  读取计划端到端。对于每个"Must Have"：验证实现存在（读取文件、curl端点、运行命令）。对于"Must NOT Have"：搜索代码库中的禁止模式——如果找到则拒绝并给出file:line。检查.evidence目录中的证据文件。将交付物与计划对比。

- [ ] F2. **Code Quality Review** — `unspecified-high`
  运行`tsc --noEmit` + linter + `bun test`。审查所有更改的文件：`as any`/`@ts-ignore`、空catch、console.log、注释掉的代码、未使用的导入。检查AI slop：过度注释、过度抽象、通用名称。

- [ ] F3. **Real Manual QA** — `unspecified-high`
  从干净状态开始。执行每个任务的每个QA场景——按照确切步骤、捕获证据。测试跨任务集成。测试边缘情况：空状态、无效输入、快速操作。

- [ ] F4. **Scope Fidelity Check** — `deep`
  对于每个任务：读取"做什么"，读取实际diff。验证1:1——规范中的所有内容都已构建（无缺失），规范之外的内容未构建（无蔓延）。检查"Must NOT do"合规性。

---

## Commit Strategy

- **1**: `feat(question-import): 恢复题目编辑功能` - `.vtj/vue/question_preview_list.vue`
- **2**: `fix(teacher-questions): 增强图片路径处理` - `.vtj/vue/teacher_questions.vue`
- **3**: `fix(question-import): 优化试卷创建条件` - `backend/app/api/v1/question_import.py`
- **4**: `feat(teacher): 实现答案解析补充接口` - `backend/app/api/v1/teacher.py`, `.vtj/vue/teacher_questions.vue`
- **5**: `feat(question-import): 优化文档识别算法` - `backend/app/api/v1/question_import.py`, `backend/app/services/text_parser.py`
- **6**: `feat(teacher-questions): 添加缺失解析提示功能` - `.vtj/vue/teacher_questions.vue`
- **7**: `feat(question-import): 优化PDF扫描件识别能力` - `backend/app/api/v1/question_import.py`, `backend/app/services/ocr_worker.py`
- **8**: `feat(teacher-questions): 在编辑中支持图片上传` - `.vtj/vue/teacher_questions.vue`, `backend/app/api/v1/teacher.py`
- **9**: `feat(question-import): 建立文档识别训练机制` - `backend/app/services/training_service.py`, `backend/app/api/v1/training.py`
- **10**: `feat(question-import): 添加识别结果反馈系统` - `backend/app/api/v1/feedback.py`, `.vtj/vue/question_preview_list.vue`

---

## Success Criteria

### 验证命令
```bash
# 前端构建检查
npm run build

# 后端测试
python -m pytest tests/

# 代码质量检查
npm run lint
python -m flake8 backend/

# 类型检查
npm run type-check
```

### 最终检查清单
- [ ] 所有"Must Have"都存在
- [ ] 所有"Must NOT Have"都不存在
- [ ] 所有测试通过
- [ ] 代码质量检查通过
- [ ] 文档更新完成
