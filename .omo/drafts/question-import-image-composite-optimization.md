# Draft: 题目导入功能模块 — 图片端到端 + 复合题 + 合并导入全面优化

## 任务性质
- 类型：Refactoring + Build from Scratch 混合（对既有题目导入模块做全方位优化）
- 交付物：**完整优化方案文档**（经用户同意后才实施）
- 存档要求：用户要求存 `solve_problems_files/`，但 Prometheus 约束只能写 `.omo/*.md`；v1 方案已有先例（归档动作列为执行阶段 0 第一项，由执行代理复制）

## 项目现状（已确认）
- 技术栈：VTJ 前端（Vue3 + Element Plus + Ant Design Vue）+ Python FastAPI 后端 + SQLite(WAL)
- 前端题目导入页：`.vtj/vue/question_import.vue`（167579 字节，raw:true）+ `.vtj/files/question_import.json`（DSL）
- 后端核心：`backend/app/api/v1/question_import.py`（264566 字节）+ `text_parser.py`（226208 字节）
- 数据库：`backend/data/question_bank.db`（148.6MB，73 表）

## 题库文档格式（已确认）
- **申论**：国考（题目+答案+解析合并 PDF）+ 省考（题目.pdf + 答案.pdf 分离，按省份子目录）
- **行测**：题本.pdf + 答案解析.pdf 分离（按省份子目录，170+ 份 PDF，100% 含文本层）
- **公安题目（打印）**：题目文档（37 docx + 10 pdf，分离导入的"题目"侧）
- **答案解析（不用打印）**：答案+解析文档（46 pdf，分离导入的"答案"侧）

## 数据库现状快照（v1 方案 2026-10-04 实测）
- question_bank: 2583 题，全部 subject_id=3（公专），行测/申论 = 0 题
- question_groups: 21 组，仅 20 题带 group_id
- requirements 非空: 0 行（申论"题目要求"从未落库）
- question_import_record: PREVIEW 429 条堆积，最后一次成功入库是 5 天前

## 历史方案（已读）
1. `题目导入模块全面修复与满血优化方案_v1.md`（2026-10-04，1160 行）— 最全
   - RC-1~RC-10 十条根因（轮询超时/入库计数读错字段/confirm丢改/confirmed_items未定义/batch-parsed丢字段/文件头嗅探/MinerU第三级兜底/复合题预览4处各写/巨型文件/文档债）
   - 模块 A~J（上传轮询/入库链路/三科识别/MinerU分层/复合题预览/学生端/运维/门禁网/拆分/三处下钻）
   - J-1 申论材料图片→小题定位：shared_content 存 [IMAGE:...] 但图片从未为题组落盘 → 裂图
   - J-2 行测资料分析跨页材料表错位
   - J-3 Excel 列名容错字典
   - 六层门禁网 L0~L6 + 9 个真实语料 Playwright（S1~S9）
2. `题目复合题型导入识别方案.md`（v1.1）— 复合题"题组"三级结构（共享内容→母题→小题）

## 用户本次诉求（5 个问题 + 9 条全局要求）
### 问题（相对 v1 方案的深化与聚焦）
1. **图片问题（核心）**：分离导入识别匹配后，题干/选项/答案解析中的图片（word/pdf扫描件/pdf）只显示路径不显示实际图片；答案解析中想添加图片无法实现
2. **合并导入**：严格对标分离导入的多内容格式，完整准确分割题目+答案+解析
3. **申论复合题**：认定复合题（一材料分多子题），同框展示所有题目不分割，答案解析紧跟子题（含图片+文字）
4. **行测答案图片**：答案文档含图片需增强识别，图片准确映射到对应答案解析位置
5. **复合题历史数据修复**：现有题库复合题被分割，三端无法完整查看，修复+三端合理展示

### 全局要求（关键点）
- 要求 1/2：完整方案 → 展示 → 同意后才实施 → 存档 solve_problems_files
- 要求 3：代码编写前多角度思考（为什么/好处/安全/运维/文件位置/后端字段/路由注册/前端显示/vtj版本一致）
- 要求 4/5：严格 VTJ 规则 + 精准定位前端文件
- 要求 6：分析已有算法去粗取精，不胡乱新建
- 要求 7：遵循 Opencode执行命令工作流.md
- 要求 8：子代理超时切主代理
- 要求 9：分析所有题目文档格式，全面修复

## 与 v1 方案的关系（关键判断）
- v1 方案已诊断 RC-1~RC-10，但状态"待审核"，**尚未实施**（数据库现状 0 题行测/申论可证）
- 用户本次诉求 = v1 方案的**深化 + 聚焦**，特别是：
  - 图片端到端（v1 只讲了"材料图片裂图"，未深入"答案解析加图"和"行测答案图映射到解析位置"）
  - 复合题历史数据修复（v1 提到但用户强调"现有题库"的修复）
- 需确认：用户是否知道 v1 方案存在？本次是要在 v1 基础上增量，还是重新聚焦？

## 代码级根因发现（主代理自主探索，2026-10-10）
> 子代理 30 分钟超时（印证用户警告），已全部取消，切换主代理自主探索。

### 重要事实修正：v1 方案已部分实施（非"完全未实施"）
- `backend/app/services/question_ingest/images.py` 已存在 → J-1-1 题组图片落盘已做（save_images_for_group）
- `backend/app/services/image_service.py` 10 层防线已做（含 question-groups 前缀解析）
- `backend/README.md` 已重写；六层门禁脚本（gate_l0~l5 + gate_all.py）已建
- `composite_matcher.py` 已完整（层1规则 + 层2语义 + 行测材料块归组）

### 图片链路现状（核心）
1. **自动提取已实现**：`_extract_and_save_images`（question_import.py:1648）扫描范围含 answer/analysis（:2273-2277 落库 scope + :1889-1895 回写 answer_analysis），注释明确"254 份申论 118 份含图，绝大多数在答案区"
2. **题组材料图片已修复**：save_images_for_group + image_service._resolve_abs_path 支持 /static/question-groups/
3. **手动加图未实现（问题1核心根因）**：
   - attach-image 端点（question_import.py:3547）硬编码 `target not in ('content','option')` 直接拒绝
   - 前端 question_preview_list.vue 只有题干(:73 pickImage idx 'content')和选项(:96 pickImage idx 'option')有加图按钮，答案(:103)/解析(:108)无按钮
4. **前端渲染**：renderQuestionContent（src/utils/questionRender.js）是单一事实来源，处理 [IMAGE:] → sanitizeHtml 白名单 → onerror 兜底；依赖后端已把占位符转 <img>，未转换的裸占位符前端剔除（宁可少图不裂图）

### 复合题现状
- composite_matcher.py 完整：层1（range/material/scenario/passage）+ 层2（上下文继承/序列挖掘/相似度）+ 行测 match_xingce_material_groups
- question_groups 表 + group_id/parent_id/question_level/sort_order/question_number/requirements 字段已建（models.py）
- 但 DB 现状：question_groups 21 组仅 20 题带 group_id → 历史复合题大多未重组

### 合并导入 vs 分离导入现状
- 两条路径都存在：import_mode='combined'（默认）/ 'separate'
- 分离导入有专门端点：separate_match_endpoint（申论三方交叉校验）+ _separate_match_xingce（行测分节安全网）
- 合并导入（combined）需确认在多内容格式（图片/材料题/复合题）上是否完整对标分离导入

### 关键文件清单
- 后端：question_import.py(5683行)、text_parser.py、composite_matcher.py、image_service.py、image_filters.py、question_ingest/images.py、models.py
- 前端：.vtj/vue/question_import.vue(167KB)、question_preview_list.vue(1111行)、teacher_questions.vue、admin_questions.vue、answer_page.vue、src/utils/questionRender.js

## 已确认决策（用户 2026-10-10 答复）
1. **方案基础**：在 v1 基础上深化（v1 作为底层参考，本次聚焦 5 个新问题做增量）
2. **解析加图方式**：自动提取为主（导入时从答案/解析文档提取图片并映射到对应解析位置）+ 手动补充为辅（教师可在预览/编辑界面手动上传/粘贴图片）
3. **历史修复范围**：导入修复 + 历史重组同批做（既修导入识别，也对存量被分割的复合题做扫描+重组，需审核界面兜底）

## 开放问题（待澄清）
1. 历史复合题重组的目标形态：是否沿用 v1.1 的"题组"三级结构（共享内容→母题→小题）？2583 题中需重组的复合题大概多少？
2. 合并导入的优先级：公专（题目+答案+解析同一 docx）还是申论（国考合并 PDF）先行？
3. 测试策略：v1 方案的六层门禁网 + 9 真实语料 Playwright 是否沿用？
4. 手动补图的前端入口：是在 question_import.vue 预览界面，还是 teacher_questions.vue 编辑界面，还是两者都要？
