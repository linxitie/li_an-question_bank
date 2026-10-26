## 一、四项探查结果汇总
1. opencode 与项目中 MCP-server 现状
项	现状
全局 opencode 配置	~/.config/opencode/opencode.jsonc 近乎空白，仅 $schema，未预置 model/skills
项目级 opencode 配置	.opencode/opencode.jsonc 已配置 vtj MCP server（node vtj-mcp-server/vtj-mcp-server.js，cwd=.，VTJ_PROJECT_ROOT=.，已启用），并预置 start-work 命令模板（按 li-an-workflow 五步流程执行已审核计划）
.mcp.json	同配置 vtj MCP server（stdio/JSON-RPC）
VTJ MCP Server	vtj-mcp-server/ 提供 19 个工具 + 3 个资源，桥接与 VTJ.PRO 低代码平台。核心铁律：只改 .vue <script> 逻辑，UI 结构由设计器拖拽；改后必须 vtj_sync_vue_to_dsl 同步 DSL；raw: true 页面受保护；所有写操作支持 dryRun 预览并自动备份 .bak；内置 123 个测试用例
.claude/settings.local.json	权限白名单（允许 python、claude mcp、node vtj-mcp-server、git add、mcp__vtj__* 等），enableAllProjectMcpServers=true，仅启用 vtj
.agent/README.md	vtj-mcp-server/、.agents/skills/、.omo/、.opencode/、.claude/ 均为活动工具链，禁止移动（Windows 下会 Permission denied）

2. 现使用的高效 skills
- skills-lock.json 锁定 36 个技能（主要来自 mattpocock/skills），覆盖 codebase-design、diagnose、domain-modeling、implement、tdd、review、prototype、grill-me、grilling、to-prd、to-issues、zoom-out、ask-matt 等。
- 超powers 技能（已安装）：superpowers-brainstorming、superpowers-writing-plans、superpowers-executing-plans、superpowers-subagent-driven-development、superpowers-using-superpowers、superpowers-verification-before-completion。
- 项目自有 opencode-project 技能：li-an-workflow（五步强制流程，先规划人工审核再执行）、vtj-frontend（VTJ 页面改动，raw 页面保护）、plan-first-workflow、completion-verifier、fact-guard、instruction-source-guard、intent-clarifier、scope-guard、token-budget-controller、token-optimization、code-asset-treasury 等。
- .claude/资源优化skills/：CLAUDE.md 模板、output-quality-skills、plan-control-skills、resource-skills、token-optimization-skills。

3. 现使用的 AI 系统约束词（AGENTS.md 长期强制规则）
工程红线 R1–R12（违反即破坏性改动）：
- R1 .vtj/ 禁止移动、改名、删除（92 处 import('$vtj/vue/<id>.vue') 硬绑定）
- R2 raw: true 页面禁止 vtj_sync_vue_to_dsl
- R3 .vtj/ 页面 <template> 禁止 AI 直接改（仅改 script，先 dryRun: true）
- R4 src/utils/device.ts 与 resolveDevicePath() 原样保留
- R5 mobile_*、tablet_* 文件名前缀不重命名
- R6 题库/（662 MB PDF 语料）禁止删除或移动
- R7 backend/app/static/（4.3 GB 题图）禁止删除
- R8 backend/data/*.bak* 禁止清理
- R9 backend/data/audit/ 与 待推断题目清单_*.csv 不是垃圾
- R10 数据库备份禁用 shutil.copy2，须用 sqlite3.backup() API
- R11 API 路径 /api/v1/ 冻结（343 个端点已记录于 api_surface.json）
- R12 不为平板新建手机页重复副本
技术栈基线：VTJ 低代码 + Vue 3.5.34 + Vite 6.3.7 + Element Plus + Pinia + hash 路由；角色（student/teacher/admin）× 设备（pc/tablet/mobile）双轴；.vtj/vue 75 页（PC 61 / 平板 7 / 手机 7）；FastAPI 单体 38 处 include_router、37 个 api/v1 模块、343 个端点；SQLite WAL（292 MB）；models.py 1668 行 / 71 个模型；8 个门禁脚本由 gate_all.py 编排。
目录分层重构进行中（P0→P6，当前分支 feat/student-containerization）。用户后续的教师端题目导入改造与三端「导入—展示—通信」数据一致性工作，必须在 P3B 完成后再启动，否则冲突不可控。
凭据处理：禁止将真实密钥写入 .md / 源码 / 提交信息；.env 禁止入 Git，须配 .gitignore + .env.example；已泄露密钥须轮换（backend/.env JWT_SECRET_KEY 待轮换）。

4. deepseek-harness 内部结构与能力（公开文档摘要）
- 定位：DeepSeek AI 开源 Agent Harness，everything-is-a-plugin 架构，基于 Cordis（时空可组合编程范式）。
- 核心包（ctx 服务模型）：core/session（仅追加 SessionEvent 日志+内存存储）、core/system-prompt（提示词片段+工具 schema 组装）、core/tools（作用域化工具注册表+带把关执行流水线）、core/agent（Agent 接口+活跃注册表）、core/agent-loop（默认驱动器）、core/scope（按 agent 作用域的注册原语）、llm/llm（消息与流式词汇表+适配器 seam，ctx.llm）。
- LLM 层：ctx.llm.stream(options) 流式模型调用，返回 block-start/text-delta/tool-call-delta/finish 等 raw chunk；registerAdapter/listProviders/resolveModelInfo/resolveCallConfig/prepareCall；适配器如 llm-deepseek（deepseek-official 直连+SSE）、llm-pi-ai（多提供商网关）；llm-retry 精确提供商重试；BlockAssembler 将 chunks 组装为块/消息。请求按模型能力校验（context window、output default、reasoning effort、输入模态、systemPromptUpdate 模式），输入 deep-frozen。
- 面向模型工具：shell、terminal、fs、lsp、web、attachment 等能力 seam。
- 技能系统：skill service，发现优先级、session-prefix 目录、模型面向的 skill 加载。
- 子代理/工作流/计划：subagent（命名提供商注册表、start-time vs runtime 能力拆分）、workflow（worker 线程引擎、workflow/ralph 工具）、plan（Plan 协作状态、审核退出弧）、preset（按会话组装 agent）。
- 持久化与检索：session JSONL/SQLite 后端、session projection、基于日志的标题、session-query（语义过滤、SQLite 全文搜索、血缘），settings/credentials/storage/workspace 等 seam。
- 人机协作：approval（一击用户批准 seam）、user-questions（问答 seam）、命令、权限预设。
- 宿主/客户端：web 宿主（API 网关+HTTP 路由）、web 客户端（浏览器半侧、UI 插件、Conversation assembly）。
- PTC 模式：packages/ptc-runtime/（PtcRunRequest/Result，binding namespaces，captured logs，PtcRunFailure 税收），可用于代码执行与计算密集型任务。
关于 DeepInfer（你提到的开源推理框架）：公开文档中未直接出现 DeepInfer。建议你确认其具体 API 与部署方式；若已有本地 DeepInfer 推理服务，可将其作为 dsh 的自定义 llm-adapter 接入，用于 token 高效推理。

## 二、deepseek-harness 多角色系统设计方案框架
2.1 角色–dsh subagent 分配矩阵
角色	dsh 映射	职责
系统总设计师 / 架构师	dsh Lead agent（agent-team 隐式 Lead）	全局架构决策、边界划分、角色间契约定义、技术选型签栁
前端页面建模师	dsh teammate + vtj-frontend skill	VTJ DSL 生成、Vue <script> 业务逻辑、dryRun 预览、DSL-Vue 一致性检查
后端建模师	dsh teammate	FastAPI 路由与模型、SQLite WAL 表设计、gate_all.py 门禁对接
接口建模师	dsh teammate	/api/v1/ 契约测试、OpenAPI/JSON Schema 生成、端点一致性比对
系统管理师	dsh teammate + 门禁脚本	健康检查 /health、凭据管理（.env.example、轮换）、备份策略、日志审计
功能测试师	dsh teammate + workflow/plan	测试用例生成、端到端流程执行、回归测试、问题反馈闭环
问题反馈师	dsh teammate + approval/user-questions	缺陷记录、优先级分类、人工确认（approval seam）、修复验证
dsh agent-team 支持隐式 Lead 身份、命名可继续的队友、直接 peer inbox 投递、共享 task DAG。适合上述多角色并行与协作。
2.2 dsh 插件扩展架构（系统总设计师视角）
基于 dsh everything-is-a-plugin 与 Cordis service 模型，为题库系统构建四层插件：
题库系统 dsh 插件套件
├── ctx.llm adapter (DeepInfer / deepseek-official) —— 模型调用层，支持标准/创造/PTC 模式切换
├── ctx.tools 工具层 —— 包装 vtj-mcp-server、后端 API 调用、数据库备份、测试执行
├── ctx.skill 技能层 —— 加载 li-an-workflow、vtj-frontend、token-optimization 等 project skills
├── subagent/team 层 —— 上述 6 角色的 agent 分配与协作编排
- 适配器注册：ctx.llm.registerAdapter 注册 DeepInfer 本地推理适配器与 deepseek-official 云端适配器，按模式路由（标准→云端/本地混合；创造→云端高创造力模型；PTC→本地 DeepInfer 代码执行推理）。
- 水fal 中间件：利用 llm/stream 水流中间件做 token 统计、缓存命中记录、请求冻结校验。
- 会话持久化：dsh session JSONL/SQLite 后端记录所有设计与测试轨迹，支持 session-query 语义检索与血缘追溯。
2.3 模式调用体系（标准 / 创造 / PTC）
模式	dsh 对应能力	适用场景	token 策略
标准模式	ctx.llm.stream + llm-retry（正常重试）	常规开发、测试用例生成、接口契约比对	上下文压缩（compaction）、session 缓存、非关键请求走本地 DeepInfer
创造模式	ctx.llm.stream + 高 reasoning effort 模型 + llm-pi-ai 多提供商 fallback	系统架构创新、新页面设计、复杂算法（组卷、智能判题）	仅在设计阶段启用，产出后归档至 docs/superpowers/specs/，避免重复生成
PTC 模式	packages/ptc-runtime（PtcRunRequest/Result，binding namespaces）	试题数据批量处理、统计分析、代码沙箱执行、接口压力测试	本地 DeepInfer 推理 + 沙箱隔离，不占用云端 token
2.4 Token 高效率与高质量使用策略（DeepInfer + skills）

1. DeepInfer 作为本地推理后端：
- 接入 dsh ctx.llm 自定义 adapter，处理标准模式与 PTC 模式的大部分请求，降低云端 DeepSeek 调用成本。
- 对重复性强的设计/测试文本（如 DSL 模板、接口 Schema 模板）使用 DeepInfer 本地生成，仅关键架构决策走云端。

2. project skills 联合节省：
- token-optimization：控制 prompt 前缀稳定、结果缓存、模型路由、错峰调度。
- context-minimal-loader：仅加载当前任务必需的最小文件集合，禁止一次性读取整个项目目录。
- completion-verifier：在宣称完成前运行实际验证，避免因虚假完成导致的返工 token 浪费。
- scope-guard：拦截超出已批准脑暴/设计范围的操作，防止需求蔓延。

3. dsh 原生机制：
- session compaction：压缩长会话日志，保留关键 decision 与 artifact。
- spill / attachment：大文件（如 4.3 GB 题图索引、662 MB 语料目录）不重复传入模型，仅传递引用与元数据。
- BlockAssembler：流式 chunk 组装，避免重复拼接与重传。
2.5 MCP-server 与 skills 集成点
集成对象	在方案中的作用	受 AGENTS.md 约束
vtj-mcp-server	前端页面建模师专用读写通道（19 工具 + 3 资源）	R1/R2/R3：raw 页面保护、template 不直接改、dryRun 预览
待扩展 backend-mcp-server	后端建模师调用 FastAPI 端点、执行数据库备份 sqlite3.backup()	R7/R8/R10：禁止删除静态资源与备份，备份须用 sqlite3 API
待扩展 test-mcp-server	功能测试师自动化测试执行与结果回传	R11：/api/v1/ 端点冻结，契约测试须与 api_surface.json 比对
li-an-workflow skill	五步强制执行流程（计划→复述→VTJ 技能→逐步验证→输出摘要）	所有人工审核节点不可跳过
vtj-frontend skill	VTJ 页面改动守护，raw 页面禁止 DSL 同步	R2/R3

## 三、2–3 种方案对比与推荐
方案 A：dsh 全栈 Agent（推荐）
- 定位：dsh 作为系统总设计师 + 各领域子代理，深度嵌入题库系统开发与测试全周期。
- 优点：角色清晰、子代理并行、dsh 插件可复用、与 VTJ/技能体系天然集成；PTC 模式适合试题数据处理；DeepInfer 本地推理显著节省 token。
- 缺点：初期需投入构建 dsh 插件套件与子代理编排。