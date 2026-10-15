# 学生端容器化与模块化设计规格 v2.0

## 1. 文档说明

| 项 | 内容 |
|---|---|
| 文档版本 | v2.0 |
| 编写日期 | 2026-10-15 |
| 适用分支 | `feat/student-containerization`（基于 `cb63045`） |
| 取代文档 | `solve_problems_files/学生端容器化模块化设计方案_v1.md`（v2.0 草案，1591 行） |
| 适用对象 | 系统架构师、运维工程师、前后端开发人员 |
| 编写依据 | 全部结论来自对本仓库与生产库的**实测**，未经实测的推断一律不写入本规格 |

### 1.1 本规格的目标

为「砺安题库」学生端设计一套可在学校服务器部署的**容器化 + 模块化**方案，满足：

1. 容器化后**零功能破坏**——重构前后 API 行为完全一致；
2. 各业务模块**可独立升级**——升级某模块不影响其他模块；
3. 模块间**低耦合**——跨模块写操作必须走公开契约；
4. 目录分层**干净整洁**——脚本、文档、AI 工具记录各有其位，冗余可证可清。

### 1.2 为什么必须重写 v1 草案

v1 草案基于**假设的系统形态**编写，而非实际代码。经三轮实测核对，v1 草案在容器数量、数据库类型、模块拆分必要性、徽章服务存在性、健康检查存在性五个方面与系统实际**全部不符**。逐条对照见 §2.3。

---

## 2. 现状实测基线

> 本节所有数字均来自对仓库与生产库的直接测量。测量脚本与原始输出保留在 `backend/data/refactor_baseline/`。

### 2.1 后端实测

| 项 | 实测值 | 证据位置 |
|---|---|---|
| 架构形态 | **单一 FastAPI 单体**，38 处 `include_router` 注册 | `backend/app/main.py:594-631` |
| API 模块数 | 37 个（`feedback.py` 注册两个 router：`router` + `admin_router`，故注册数 38） | `backend/app/api/v1/` |
| API 端点总数 | **343** | `refactor_baseline/api_surface.json` |
| ORM 模型 | **71 个类**，集中在 `models.py` 单文件 **1668 行 / 94 KB** | `backend/app/models/models.py` |
| 生产库表数 | **72 张** | `sqlite_master` 查询 |
| 数据库 | **SQLite**（WAL 模式），**不是 PostgreSQL** | `core/config.py:15` `DB_TYPE` 默认 `"sqlite"`；`:124-127` 返回 `sqlite:///` 或 `mysql+pymysql://` |
| 生产库体积 | `backend/data/question_bank.db` = **292 MB** | 文件实测 |
| 前端托管 | **FastAPI 自身已托管 SPA**：`app.mount("/assets", StaticFiles(...))` + `@app.get("/{full_path:path}")` 返回 `dist/index.html` | `main.py:654-672` |
| 端口 | 前后端**同端口 8000** | `start_system.bat`：`python -m uvicorn app.main:app --host 0.0.0.0 --port 8000` |
| 健康检查 | `/health` **已存在** | `main.py:633` |
| 指标端点 | `/metrics`、`/metrics/system`、`/metrics/endpoints` **已存在** | `main.py:644,648,674` |
| 优雅关闭 | `lifespan` 异步上下文管理器**已实现** | `main.py` FastAPI 构造参数 |
| 静态挂载 | 4 处：`/uploads`、`/static/questions`、`/static/question-groups`、`/static/images` | `main.py:577,582,588,592` |
| CORS | `allow_origins=["*"]` 且 `allow_credentials=True` | `main.py:568` |
| 技术栈 | Python 3.13.5、FastAPI>=0.104、Uvicorn>=0.24、SQLAlchemy>=2.0、Pydantic>=2.5、redis>=5、APScheduler>=3.10、playwright>=1.48、opencv-python>=4.8、Pillow>=10、pdfplumber、python-docx、openpyxl | `backend/requirements.txt` |

### 2.2 前端实测

前端代码位于**仓库根目录**（无 `frontend/` 子目录）：`src/`、`.vtj/`、`dist/`、`proxy.config.ts`、`package.json`、`vite.config.ts`。

| 项 | 实测值 |
|---|---|
| 形态 | **VTJ 低代码 + 手写 Vue 混合** |
| 版本 | `@vtj/cli` 0.12.19、`@vtj/web` 0.16.35、Vue 3.5.34、Vite 6.3.7、TypeScript 5.9.3 |
| UI 库 | Element Plus 2.13.7 + ant-design-vue 4.2.6 |
| 状态/路由 | Pinia 3.0.4、vue-router 4.6.4（**hash 路由** `createWebHashHistory`） |
| HTTP | axios 1.13.6 |
| VTJ 项目 ID | `linxitie.policy-exam-bank`，开发端口 9527 |
| 页面数 | **47 个**（VTJ 项目配置登记），其中 **45 个 `raw: true` 手写页**、2 个生成页 |
| DSL 文件 | `.vtj/files/*.json` 共 **73 个** → **26 个为孤儿**（未在项目配置中登记） |
| `raw` 标记位置 | **不在 DSL JSON 中**，而在 VTJ 项目配置内（不可 grep DSL 获取） |
| `.vtj/vue/` 磁盘文件 | 75 个 `.vue` |
| **冻结证据（决定性）** | `src/router/index.ts` 共 628 行，含 **92 处** `import('$vtj/vue/<id>.vue')` 硬绑定 |
| `src/views/` | **27 个**手写页（多为 `mobile_*`），**平铺、无功能域分组** |
| `src/components/` | 4 个 |
| `src/utils/` | **7 个** |
| `src/layouts/` | 2 个（`AdminLayout.vue`、`TeacherLayout.vue`） |
| 角色权限 | `src/router/index.ts` 已按 学生端/教师端/管理端 分节，并已有 `meta: { roles: ['student'] }` 门控 |
| 开发代理 | `proxy.config.ts` 代理 `/api`、`/ws`、`/static`、`/uploads` → `http://127.0.0.1:8000` |
| 微前端 | **完全没有**——无 qiankun、无 Module Federation、无 wujie |
| 同级空项目 | `linxitie.policy-exam-bank-mobile`、`linxitie.policy-exam-bank-tablet` 两个 VTJ 项目目录，**均为空（0 页面）** |

### 2.3 v1 草案与实测的逐条对照

| # | v1 草案主张 | 实测结果 | 结论 |
|---|---|---|---|
| 1 | 13 个后端微服务 + 5 个前端微应用 = 18 个容器 | FastAPI 已自托管 `dist/`，前后端同端口 8000 | **只需 3 个容器**，v1 多算 15 个 |
| 2 | PostgreSQL 主库 + 从库 | SQLite 292 MB（WAL 模式），`DB_TYPE` 默认 sqlite | **保留 SQLite**，换库会引入零收益的迁移风险 |
| 3 | 拆出 `coin-service`/`task-service`/`goal-service`/`achievement-service`/`forum-service` | 这些功能**已存在**为 `api/v1/coins.py`、`tasks.py`、`goals.py`、`achievements.py`、`forum.py` | 拆进程即「无理由切分」，**改为域内模块化** |
| 4 | 新建 `badge-service`（含徽章生成器） | **不存在**：`api/v1/` 无 `badge.py`，`achievements.py` 仅 3 个 GET 端点 | **不建**，本次不纳入范围 |
| 5 | 新建健康检查端点 | `main.py:633` `/health` **已存在** | 复用，不重写 |
| 6 | 新建优雅关闭机制 | `lifespan` **已实现** | 复用，不重写 |
| 7 | 新建 Redis Stream 事件总线 | `redis>=5` 已是依赖，`core/redis_client.py` 已存在 | 基于既有 redis 扩展，**不引入新组件** |
| 8 | 引入 qiankun 微前端基座 | 系统中**零微前端基础设施** | 引入代价远超收益，**改为 `src/` 内部分层** |
| 9 | 拆 `models.py` 为多文件 | `models.py` 1668 行 / 71 模型，确实需拆 | **该条成立，予以采纳** |

**结论**：v1 草案在 9 条主张中 8 条与系统实际不符，仅第 9 条成立。v1 的业务功能设计（金币档位、任务生成算法、目标评估权重、徽章渲染等）属于**产品需求**而非**容器化模块化需求**，其中「徽章生成」对应的功能尚不存在，不应混入本次重构。

### 2.4 耦合热点实测

| 耦合源 | 被谁调用 | 跨域数 |
|---|---|---|
| `services/achievement_service.py` | 9 个 api 模块：`auth`、`wrong_questions`、`practice`、`stats`、`forum`、`quotes`、`collection`、`notes`、`achievements` | **8 个跨域** |
| `services/growth_service.py` 的 `add_growth()` | `practice.py`、`stats.py`（exam 域）跨域；`tasks.py`、`goals.py`、`achievement_service.py` 为 growth 域内部 | **2 个跨域** |
| 直接写他域数据表 `CoinRecord` | **15 处 `check_and_grant` 调用点，横跨 8 个模块**（`goals.py:382`、`shop.py:116`、`tasks.py:318`、`stats.py:655`、`achievement_service.py:235` 等） | **全部跨域违规** |
| `SysUser`（用户主表） | **全部 37 个模块**均引用 | 事实上的「上帝表」 |

原始数据：`refactor_baseline/coupling.json`、`table_usage.json`、`api_surface.json`、`model_map.json`、`db_tables.json`、`summary.json`。

### 2.5 语料完整性探测

`backend/scripts/probe_xingce_corpus.py` 实测：

```
files=170  QB=85  ANS=85  pairs=85  broken=0
section_head_hit=100%  answer_anchor_hit=100%  kao_hit=100%  material_hit=100%
qnums_contiguous=63.53%   total_materials=364
section_vocab={'言语理解与表达':85,'数量关系':85,'判断推理':85,'资料分析':85,
               '常识判断':84,'政治理论':25,'科学推理':4,'常识':1}
```

**结论**：85 套行测语料配对完整、无破损，分节/答案锚点/考点/材料识别**全部 100% 命中**。但**题号连续性仅 63.53%**，意味着重导时约 36% 的题号存在跳号，必须以 `qnums_contiguous` 作为导入完整性门禁指标，不可只看总数。

### 2.6 行测题库缺口（业务级发现）

按 `question_bank` 表逐时点统计有效题（`status=1`）：

| 时间点 | 总题 | 行测 | 公专 | 申论 |
|---|---:|---:|---:|---:|
| 2026-10-01 / 10-02 | 2,478 | 0 | 2,478 | 0 |
| 2026-10-03（85 套导入完成） | 12,496 | 10,018 | 2,478 | 0 |
| **2026-10-04 擦除前** | **12,649** | **10,171** | 2,478 | 0 |
| 2026-10-04 擦除后 | 2,478 | 0 | 2,478 | 0 |
| 2026-10-14 | 3,074 | 110 | 2,952 | 12 |
| **生产库（今）** | **3,126** | **233** | **2,877** | **16** |

*注：3,126 为 `status=1` 有效行；含 `status=0` 的物理行共 3,353（+227）。*

**行测重导进度：233 / 10,171 ≈ 2.3%。**

**该次清空是有意操作，不是误删**，依据两条实测证据：

1. `solve_problems_files/行测题目导入优化方案.md` §7.1「T16 阻塞：行测去重会静默丢题」——131 道图形推理题中 79 道被误判为重复而静默丢弃；
2. 提交 `328b0b0 feat(xingce): dedup 行测 by question number and source` 用「题号 + 来源」替换了原先的「文本相似度」去重逻辑。

**处置结论：不把备份中的行测题合并回生产库。** 理由：旧管线数据自带已知缺陷（题型误判、答案截断），合并会违反项目总原则「宁可阻断，不许静默丢题」；且 `题库/行测/` 原始 PDF 语料完整保留，随时可用新管线重导。`solve_problems_files/题目导入模块全面修复与满血优化方案_v1.md:408` 已明确定调：`backend/data/*.bak*` → **禁止清理（回滚依赖）**。

### 2.7 备份库一致性审计

对 `backend/data` 下**全部 118 个数据库文件（6,502.5 MB）**做 SHA-256 全量比对：

| 分类 | 数量 | 体积 |
|---|---:|---:|
| 主库文件（`.db`/`.sqlite`） | 56 | 6,501.6 MB |
| 旁挂 `-wal`（**全部为 0 字节**，哈希 `e3b0c442…` 即空文件 SHA-256） | 31 | 0 MB |
| 旁挂 `-shm`（全部同哈希） | 31 | 0 MB |
| **去重后不同内容（必须保留）** | **41** | **5,089.6 MB** |
| **可归并冗余（哈希可证）** | **77** | **可释放 1,411.9 MB** |

哈希相同的重复组：

| 组哈希 | 份数 | 保留 | 释放 |
|---|---:|---|---:|
| `7635f3145d90` | 8 × 120.0 MB | `question_bank.db.bak_sc_kexue_20261003_172156` | 840.2 MB |
| `f8e302615725` | 3 × 102.9 MB | `backup_pre_typefix_20260928_170408.db` | 205.9 MB |
| `12a1f716f0e2` | 4 × 67.0 MB | `backup_pre_fix_single_20260830_202447.sqlite` | 201.0 MB |
| `56e2e71a1058` | 3 × 54.8 MB | `backup_pre_backfill_20260825_062857.sqlite` | 109.6 MB |
| `fc197ded8a10` | 2 × 55.4 MB | `backup_pre_qgroup_20260825_113920.sqlite` | 55.4 MB |

**关键：`question_bank.db.bak_pre_wipe_20261004_102517`（148.5 MB）是全系统唯一存世的 10,171 道行测题副本，严禁删除。**

### 2.8 目录卫生实测

| 项 | 实测 |
|---|---|
| Git 跟踪文件总数 | **5,424** |
| `题库/` | 662 MB 原始 PDF 语料（唯一事实来源） |
| `backend/data/` | 7.4 GB |
| `backend/app/static/` | 4.3 GB（题图在库） |
| `backend/uploads/` | 702 MB |
| `.worktrees/` | 2.46 GB（含 `badge-engine-v4` 工作树） |
| `node_modules/` | 657 MB |
| `.opencode/` | 52.6 MB（AI 工具运行时目录） |
| `solve_problems_files/` | **134 个平铺 .md**，版本爆炸严重（题目导入 v1~v9 + 全面修复 + 完整修复 = 11 份；手机端 v1/v3.0/v4.0 + 问题呈现 v1/v2/v3 = 6 份；错题集 v2~v5 = 4 份；招考 v2/v3/v4 = 4 份） |
| `backend/scripts/` | **90 个 .py 平铺**：9 `gate_*`、约 30 `cleanup/clean/purge/repair/regroup/dedup/normalize`、约 25 `verify_*`、约 12 `fix_*`、约 9 `migrate_*`、约 10 `probe/diag/_*` 临时件 |
| 重复脚本 | `regroup_composite.py`、`regroup_composite_questions.py`、`fix_composite_groups_r8.py` 是**同一件事的 3 份** |
| 空文件 | `backend/scripts/题库.db` = 0 字节 |
| `docs/superpowers/{specs,plans}/` | 已有 32 份结构规范的文档——**这是本仓库已有的正确范式，应推广** |
| AI/工具目录 | 分散于 `.agents/`(63)、`.claude/`(17)、`.omo/`(152)、`.opencode/`(52.6 MB)、`.superpowers/`(12)、`.sisyphus/`(3)，外加 `scripts/omo_*.{html,py,ps1}` |
| 命名冲突 | **`CLAUDE.md` 是目录而非文件**，与工具约定的 `CLAUDE.md` 文件名冲突 |
| `.opencode/` 等 | `backend/data/` 仅 10 个文件被 Git 跟踪 → **L2 归档不得入库** |

### 2.9 测试基线实测

`pytest` 收集 297 项，结果：**17 failed / 227 passed / 1 xfailed / 52 errors**。

根因分类：

| 根因 | 数量 | 性质 |
|---|---:|---|
| **测试 fixture 幂等缺陷**：`sqlite3.OperationalError: index idx_import_status already exists`（建索引未用 `IF NOT EXISTS`） | **52 errors** | 测试基建问题，**非产品缺陷** |
| MinerU / OCR 依赖缺失 | 2 | 环境依赖，见 §9.3 |
| Playwright 环境缺失（无浏览器/网络） | 4 | 环境问题，非逻辑缺陷 |
| `test_security.py`（token/限流/熔断/权限） | 8 | 需逐个确认（疑似 mock 随签名变更失效） |
| 公专回归 / 资料管理 / 监控 | 3 | 真实待查 |

**52 个 error 集中在 1 个根因**，修复成本低。门禁套件共 **8 个脚本**（L0、L1-G、L1、L1-H、L2、L3、L4、L5），由 `backend/scripts/gate_all.py` 编排。

### 2.10 部署阻塞实测

| # | 问题 | 位置 |
|---|---|---|
| 1 | `MINERU_PYTHON` 默认 `r"C:\mineru_env\Scripts\python.exe"` | `core/config.py:71`；经 `subprocess` 调用于 `services/mineru_service.py:62,85,134` |
| 2 | `OCR_PYTHON` 默认 `r"D:\ocr-env\Scripts\python.exe"` | `core/config.py:84` |
| 3 | `DB_PASSWORD` 默认 `"123456"` | `core/config.py:19` |
| 4 | `JWT_SECRET_KEY` 默认 `"your-secret-key-here-must-be-at-least-32-characters"` | `core/config.py:33` |
| 5 | `DEBUG` 默认 `True` | `core/config.py:43` |
| 6 | 系统级 `ffmpeg` 依赖 | `core/config.py:52` |
| 7 | `NEWS_BROWSER="chromium"` 需 Playwright 浏览器 | `core/config.py:63` |

`core/config.py` 注释进一步说明：MinerU 需要 **Python 3.11** 虚拟环境，OCR 需要 **<3.12**。因此 `python:3.13-slim` 镜像**无法在进程内承载**这两个解析器，必须保留既有的外部子进程设计。

`backend/README.md` 明确 WAL 备份铁律：**必须用 `sqlite3.backup()` API，`shutil.copy2` 在 WAL 模式下被禁止**；回滚时须覆盖主库**并同时删除 `-wal` 与 `-shm`**。

### 2.11 安全事件（实测）

| # | 事项 | 证据 |
|---|---|---|
| 1 | `.omo/plans/configure-deepseek-api.md` 内含**硬编码的 DeepSeek API 密钥 `sk-9a2e…`（已掩码）**，且**已随提交 `4a18f89` 进入 Git 历史**，文件处于 Git 跟踪状态 | `git show HEAD:.omo/plans/configure-deepseek-api.md` 已验证 |
| 2 | `admin_token.txt`（167 字节）位于仓库根目录且**已被 Git 跟踪** | `git ls-files admin_token.txt` |

**轮换密钥是唯一彻底解法**——改写 Git 历史只是附加项，且不能撤销已泄露的密钥。

---

## 3. 设计决策与依据

### 3.1 决策一：容器技术选型 = Docker Compose，3 个容器

**约束**：目标学校服务器尚未确定（可能 Linux / 可能受限 / 可能换机器），故同一套配置必须同时适配开发机与学校服务器。

| 维度 | Docker Compose | Podman | Swarm / K8s | systemd 直装 |
|---|---|---|---|---|
| 单机部署 | ✅ 标准解 | ✅ | ⚠️ 杀鸡用牛刀 | ✅ |
| 无 root 环境 | ❌ | ✅ rootless | ❌ | ✅ |
| 发版方式 | 换 tag + `up -d`，**回滚 = 换回旧 tag** | 同左 | 需编排层 | 手动装依赖 |
| 环境一致性 | ✅ 镜像固化 | ✅ | ✅ | ❌ 易漂移 |
| 学校运维门槛 | 低（一条命令） | 中（需换命令） | **高**（须先维护控制面） | 低 |
| 开发机↔服务器一致 | ✅ | ⚠️ | ✅ | ❌ |

**采纳 Docker Compose**，理由直接对应「便于正常使用、开发人员接收意见、系统更新发布」：

- **Podman** 记为备案预案——仅在学校机房封禁 Docker 时启用；
- **Swarm / K8s** 否决——在单机上需先运维一个集群，与「一台学校服务器」直接矛盾；
- **systemd** 否决——无法交付可复现环境，与「容器化」诉求相悖。

**容器拓扑（3 个，而非 v1 的 18 个）**：

```
nginx      TLS 终止 / 反向代理 / 静态缓存头          ← 唯一对外发布端口
  └── backend   FastAPI（内含 dist 静态托管）
        │          · SQLite 主库
        │          · uploads 用户上传
        │          · 题图 static（4.3 GB，卷挂载）
        └── redis   缓存 / 事件总线（未启用则不启动）
```

**数据库决策：保留 SQLite。** 理由：

- 单写入者特性导致 SQLite **无法多副本**，但本方案是单容器部署，该限制**不产生任何代价**；
- 备份即「拷 `.db` + 处理 `-wal`/`-shm`」，比 PostgreSQL 主从简单得多；
- 换库的**出口已预留**：`core/config.py:124-127` 已实现 `mysql+pymysql` 分支，日后只需改 `DB_TYPE` 与连接串，**无需改动任何业务代码**。

### 3.2 决策二：十个业务域，按能力划分而非按端划分

**这是防止「无脑切分」的第一道闸门。**

| 方案 | 后果 |
|---|---|
| 按端分域（学生端模块 / 教师端模块 / 管理端模块） | 「题库」被劈成三份，改一处题型逻辑，三端都动 ❌ |
| **按能力分域**（题库域 / 考试域 / 金币域…） | 三端是**消费视角**，同一份能力被复用 ✅ |

采用后者。域的划分依据是**数据归属 + 变更节奏**，**不是文件数量**。

| # | 域 | 承载能力 | 由现有文件迁入 | 模块数 | 端点数 | 学生 | 教师 | 管理 |
|---|---|---|---|---:|---:|:-:|:-:|:-:|
| 1 | `identity` | 登录/鉴权/设备 | `auth` `auth_qrcode` `devices` | 3 | 16 | ✅ | ✅ | ✅ |
| 2 | `catalog` | 题目/试卷/错题/导入 | `questions` `question_actions` `question_import` `wrong_questions` `papers` `paper_generation` | 6 | 78 | ✅ | ✅ | ✅ |
| 3 | `exam` | 练习/模考/成绩 | `practice` `quick_practice` `smart_exam` `exams` `exam_records` `stats` | 6 | 54 | ✅ | ✅ | ✅ |
| 4 | `reward` | 金币/商城 | `coins` `shop` `admin_shop` | 3 | 9 | ✅ | — | ✅ |
| 5 | `growth` | 任务/目标/成就 | `tasks` `goals` `achievements` | 3 | 19 | ✅ | — | ✅ |
| 6 | `community` | 论坛/金句 | `forum` `quotes` | 2 | 19 | ✅ | ✅ | — |
| 7 | `library` | 备考资料/视频/媒体 | `materials` `videos` `media` | 3 | 31 | ✅ | — | ✅ |
| 8 | `content` | 新闻/招考/日历 | `news` `recruitment` `calendar` | 3 | 13 | ✅ | — | ✅ |
| 9 | `personal` | 收藏/笔记 | `collection` `notes` | 2 | 14 | ✅ | — | — |
| 10 | `platform` | 管理/教师/反馈/WS/AI | `admin` `admin_approval` `teacher` `feedback` `websocket` `llm` | 6 | 90 | — | ✅ | ✅ |
| | **合计** | | | **37** | **343** | | | |

`llm.py`（`/api/llm/chat`，联考小智，1 个端点）当前未归域，**并入 `platform`**。不为单个端点新开第 11 个域——这正是「无脑切分」的表现。

**这一划分是后续教师端、管理员端方案的结构性保证**：那两个方案只会在同一批 10 个域内扩展 router，不会产生新的割裂。

### 3.3 决策三：跨模块通信契约（写走契约、读可控开放、异步走事件）

用户明确要求：模块可独立升级、升级后互不影响，但**跨模块通信必须保持一致**。据此定三条规则：

1. **跨域写操作**必须调用对方公开的 `contract.py`
   例：`from modules.reward.contract import grant_coins`。
   `goals.py` 不得再 `import CoinRecord` 后直接写表——§2.4 列出的 **15 处 `check_and_grant` 调用点就是改造清单**。
2. **跨域读操作**允许直读对方表。
   依据：`SysUser` 被全部 37 个模块引用（§2.4），全面禁止跨域读会造成大量无谓的接口层膨胀。此项受红线约束，见 §5.2。
3. **异步副作用**统一走事件总线（`core/events.py`，Redis Streams）。`redis>=5` 已是依赖，**不引入新组件**。

### 3.4 决策四：目录清理分三级

- **L1** 可直接删除（零风险，不影响运行）
- **L2** 归档而非删除
- **L3** 必须获得用户明确授权（涉及凭据与历史改写）

详见 §7。

### 3.5 决策五：以事件契约消除耦合热点

§2.4 实测显示 `achievement_service` 被 8 个跨域模块直接调用，是最大的耦合源。按决策三改造后：

| 事件 | 生产方 | 替代的现有直调 |
|---|---|---|
| `user.action` | 各域自身 | 消除 8 处跨域 `achievement_service` 调用 |
| `growth.awarded` | `growth` 域 | — |
| `achievement.unlocked` | `growth` 域 | — |

改造完成后，`growth` 域成为**纯事件生产方**，其余域不再 import 它。

---

## 4. 目标架构

### 4.1 后端目录

```
backend/app/
├── main.py                    # 唯一入口，只做装配（约 10 行 include_router）
├── core/                      # 平台内核，零业务
│   ├── config.py              # 现有
│   ├── database.py            # 现有
│   ├── security.py            # 现有
│   ├── redis_client.py        # 现有
│   ├── events.py              # 【新】统一事件总线（Redis Stream）
│   ├── contracts.py           # 【新】跨域公开契约的类型与注册
│   └── module_registry.py     # 【新】域清单：路由/表/事件/契约 一处声明
├── modules/                   # 【新】业务域，每个域自包含
│   ├── __init__.py
│   └── reward/                # 示例域
│       ├── __init__.py        # 只导出 router 与 contract
│       ├── router.py          # /api/v1/coins/*、/api/v1/shop/*（路径不变）
│       ├── schema.py          # Pydantic 入参出参
│       ├── models.py          # CoinRecord / ShopProduct 从 God-file 迁入
│       ├── service.py         # 仅域内可见
│       └── contract.py        # 【新】对外唯一写入口
├── shared/                    # 【新】跨域基础件，非业务
│   └── (由 services/ 中 parser、scraper、ocr、image 等迁入)
├── services/                  # 保留：过渡期兼容
├── static/                    # 题图（容器化后为卷）
├── uploads/                   # 用户上传（容器化后为卷）
├── schemas/                   # 保留：平台级共享 schema
├── data/                      # SQLite 主库（容器化后为卷）
└── cache.py  canal_client.py  db_router.py  exceptions.py
    grpc_service.py  middleware.py  monitoring.py  scheduler.py  seed.py
```

### 4.2 前端目录

**仅重组 `src/`。`.vtj/` 完全冻结**——`src/router/index.ts` 中 92 处硬绑定 `import('$vtj/vue/<id>.vue')` 是不可逾越的约束。

```
src/
├── router/index.ts            # 主路由表（import 路径更新，API 不变）
├── views/
│   ├── student/               # 学生端手写页（现 27 个中的学生侧部分）
│   ├── teacher/               # 教师端手写页
│   ├── admin/                 # 管理端手写页
│   └── shared/                # 三端共用
├── components/
│   ├── common/                # 跨域通用组件
│   └── domain/                # 域内专用组件
├── services/
│   └── api/<domain>.ts        # 前端 API 调用按域归口
├── layouts/                   # AdminLayout / TeacherLayout 保留
└── utils/                     # 7 个工具
```

### 4.3 VTJ 纪律（不可违反）

| 规则 | 原因 |
|---|---|
| **禁止移动 `.vtj/vue/<id>.vue`** | 92 处路由硬绑定 + 设计器按 id 读写 |
| **`raw: true` 页禁止 `vtj_sync_vue_to_dsl`** | 同步器提取不到的手写方法会丢失，设计器回存再覆盖回来；工具会返回 `RAW_PAGE_PROTECTED` |
| **`<template>` 变更须由用户在设计器完成** | 设计器地址 `http://localhost:9527/__vtj__/`（端口来自 `vite.config.ts` 的 `DEV_PORT`，`strictPort: true`，不要用 5173） |
| **`<script>` 可程序化修改，但必须先 `dryRun: true`** | 写操作会自动生成 `.bak` |
| **页面 ID 保持语义化** | 有效 ID 示例 `home_page`、`question_bank`、`gold_purchase`、`mobile_home` |

---

## 5. 模块边界与契约规则

### 5.1 三件套强制机制

**① `contract.py` 作为唯一写入口**

每个域导出本域允许被外部调用的写接口。域 A 修改域 B 的数据，只能 `from modules.B.contract import X`，不得 import `modules.B.service` 或 `modules.B.models`。

**② 域边界红线 + 自动检查**

新增 `scripts/check_module_boundary.py`，用 AST 静态扫描，命中以下任一即失败：

- `modules/X/` 内出现 `from modules.Y.service import ...`
- `modules/X/` 内出现 `from modules.Y.models import ...`
- 跨域直接写入他域 ORM 表（白名单外的 `session.add/flush` 目标表不属于本域）

该检查纳入门禁网（挂到 L4/L5），本地与 CI 同规则。

**③ 统一事件总线**

`core/events.py` 定义事件契约。域只发布事件，不直接调用其他域。

### 5.2 跨域读写规则

| 操作 | 规则 | 依据 |
|---|---|---|
| 读他域表 | **允许** | `SysUser` 被 37 个模块引用 |
| 读本域表 | 允许 | — |
| 写本域表 | 允许 | — |
| **写他域表** | **禁止**，必须走 `contract.py` | §2.4 的 15 处违规 |

### 5.3 兼容性保证

- **API 路径 `/api/v1/...` 全程冻结**。343 个端点已记录于 `refactor_baseline/api_surface.json`，重构后须逐条比对一致；
- **`.vtj/` 页面零改动**，前端无需与后端同步修改；
- 因此重构可**逐域推进**，任一域失败即可回退该域而不影响其他域。

### 5.4 事件契约演进规则

1. API 路径冻结；
2. 事件 schema 带版本号，形如 `user.action.v1`，字段**只增不删不改语义**；
3. 新增域在 `core/module_registry.py` 一处登记，不改动既有域；
4. 契约破坏性变更必须新增版本号，旧版本保留兼容期；
5. 边界检查在 L4/L5 门禁中强制执行。

---

## 6. 容器化落地方案

### 6.1 后端 Dockerfile

```dockerfile
FROM python:3.13-slim

# 系统依赖：
#   ffmpeg            —— config.py:52 视频/音频处理必需
#   libgl1/libglib2.0-0 —— opencv-python 运行库
#   curl              —— HEALTHCHECK 使用
RUN apt-get update && apt-get install -y --no-install-recommends \
      ffmpeg libgl1 libglib2.0-0 curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
 && playwright install --with-deps chromium

COPY app ./app
# 门禁基线必须随镜像走：否则 L0~L5 红线与基线无法在 CI 与其他机器复现
COPY data/gates ./data/gates

ENV PYTHONUNBUFFERED=1 TZ=Asia/Shanghai

EXPOSE 8000

# 复用既有 /health（main.py:633），不新写健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]
```

**重要**：MinerU 与 OCR **不进入本镜像**。二者分别需要 Python 3.11 与 <3.12 虚拟环境（`core/config.py` 注释），`python:3.13-slim` 无法在进程内承载；现有的 `subprocess` 外部调用设计必须保留，子解释器另行提供。若学校服务器不需要扫描件解析，可将 `MINERU_ENABLED` 置为 `false` 降级。

### 6.2 docker-compose.yml

```yaml
services:
  backend:
    build: ./backend
    image: liankao/backend:${APP_VERSION:-dev}
    restart: unless-stopped
    env_file:
      - .env.${DEPLOY_ENV}          # 环境分离的唯一开关
    volumes:
      - db_data:/app/data           # SQLite 主库 + 归档
      - uploads:/app/uploads        # 用户上传 702 MB
      - qimg:/app/app/static        # 题图 4.3 GB —— 绝不进镜像
    depends_on:
      redis:
        condition: service_healthy
    networks: [liankao]

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD}
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "ping"]
      interval: 10s
      timeout: 5s
      retries: 10
      start_period: 10s
    networks: [liankao]

  nginx:
    image: nginx:alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./deploy/nginx.conf:/etc/nginx/conf.d/default.conf:ro
      - ./deploy/ssl:/etc/nginx/ssl:ro
    depends_on:
      backend:
        condition: service_healthy
    networks: [liankao]

volumes:
  db_data: {}
  uploads: {}
  qimg: {}

networks:
  liankao:
    driver: bridge
```

> Redis 的去留：`redis>=5` 虽是既有依赖、`core/redis_client.py` 已存在，但需确认当前是否已有调用方。若确认仅用于 §5.1 的事件总线且无其他消费者，实施时可将其降级为 backend 容器内的库依赖（`redis-py` 直连），从而把容器数从 3 减到 2。此项不影响其余设计。

### 6.3 环境分离

| 文件 | 用途 |
|---|---|
| `.env.development` | 开发机：DEBUG=True、SQLite 本地路径、日志 DEBUG |
| `.env.school` | 学校服务器：DEBUG=False、独立 `JWT_SECRET_KEY`、日志 INFO |
| `.env.example` | 模板，入库；真实 `.env.*` 不入库 |

切换环境只改一个变量：`DEPLOY_ENV=development|school`。

必须由 `.env` 覆盖的高危默认值（见 §2.10）：

```
DEBUG=False
DB_PASSWORD=<强口令>
JWT_SECRET_KEY=<至少 32 字节随机串>
```

**未覆盖 `JWT_SECRET_KEY` 意味着任何人可用默认密钥伪造管理员 JWT。** 这是上线前的硬性阻断项。

### 6.4 数据矩阵

| 数据 | 仓库位置 | 体积 | 容器化后 |
|---|---|---:|---|
| SQLite 主库 | `backend/data/question_bank.db` | 292 MB | `db_data` 卷 |
| 归档备份 | `backend/data/{backups,snapshots}/` + 41 份唯一备份 | 5,089.6 MB | `db_data` 卷 |
| 题目图片 | `backend/app/static/` | 4.3 GB | `qimg` 卷 |
| 用户上传 | `backend/uploads/` | 702 MB | `uploads` 卷 |
| 门禁基线 | `backend/data/gates/*.json` | 5.3 MB | **进镜像**（CI 复现必需） |

### 6.5 备份与恢复（WAL 铁律）

**禁止 `shutil.copy2`**——WAL 模式下只拷主库无法保证完整性。必须走 SQLite 备份 API：

```python
import sqlite3, datetime, pathlib
ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
archive = pathlib.Path('data/archive'); archive.mkdir(parents=True, exist_ok=True)
src = sqlite3.connect('data/question_bank.db')
dst = sqlite3.connect(str(archive / f'question_bank_{ts}.db'))
with dst:
    src.backup(dst)          # 一致性快照
dst.close(); src.close()
```

**回滚**：覆盖主库，**并同时删除 `-wal` 与 `-shm`**。

**保留策略**：最近 7 天 + 每周一份。该策略以 §2.7 实测的 **41 份唯一内容**为基线设定——低于此数即意味着有唯一内容被覆盖。

### 6.6 发版与回滚

```
改代码 → 8 道门禁全绿 → docker compose build → 镜像打 tag
→ docker compose up -d → /health 探活
→ 失败则把 APP_VERSION 改回上一 tag → compose up -d
```

回滚只换镜像 tag，**数据卷不动**。这正是选 Compose 而非裸装的核心价值。

### 6.7 上线前门禁

| 门禁 | 脚本 | 覆盖 |
|---|---|---|
| L0 | `gate_l0_redlines.py` | 红线 |
| L1 | `gate_l1_parser.py` | 解析指纹 |
| L1-G | `gate_l1g_field_fingerprint.py` | 字段指纹 |
| L1-H | `gate_l1h_composite_material.py` | 复合题材料边界 |
| L2 | `gate_l2_matching.py` | 匹配配对 |
| L3 | `gate_l3_ingest.py` | 落库链路 |
| L4 | `gate_l4_api_contract.py` | API 契约 |
| L5 | `gate_l5_frontend_contract.py` | 前端数据契约 |

一键执行：`python scripts/gate_all.py`（`--quick` 只跑 L0+L1+L1-G+L1-H）。

**前置修复**：§2.9 的 fixture 幂等缺陷必须先修（`CREATE INDEX IF NOT EXISTS`），否则 52 个 error 会让门禁失去红绿信号意义。

---

## 7. 目录清理方案

### 7.1 L1 · 可直接删除（零风险）

| 目标 | 体积 | 说明 |
|---|---:|---|
| 77 个哈希可证冗余的数据库文件 | **1,411.9 MB** | §2.7 五组重复 + 31 个空 `-wal` + 31 个 `-shm` |
| `backend/data/` 散落 `xingce_regression_*` / `type_repair_*.log` | ~40 个 | 一次性产物 |
| `temp_pdf_images/` | 26 MB | 41 个 PNG 临时提取图 |
| `tmp/` | 1.2 MB | 语料探测产物 |
| `git_diff_qi.txt` | 732 KB | 根目录临时 diff |
| `frontend_run.err` / `frontend_run.log` | 525 B | 根目录运行日志 |
| `src/router/index.ts.bak` | — | 路由备份 |
| `src/.DS_Store` | — | macOS 垃圾 |
| `backend/scripts/题库.db` | 0 B | 空库 |
| 26 个孤儿 `.vtj/files/*.json` | — | 未在 VTJ 项目配置登记（删除前须确认无引用） |

### 7.2 L2 · 归档而非删除

| 目标 | 处置 |
|---|---|
| **41 份唯一数据库备份（5,089.6 MB）** | **严禁删除**。`bak_pre_wipe_20261004_102517` 是全系统唯一存世的 10,171 道行测题副本。按 §6.5 保留策略移入 `data/archive/`。**不入库 Git**（`backend/data/` 仅 10 文件被跟踪） |
| `solve_problems_files/` 134 个平铺 md | 迁入 `docs/{design,plans,ops,archive}/`。规则：**同一主题只留终版在 `design/`，历史版本进 `archive/`**。仅题目导入 v1~v9 即有 11 份，按此规则收敛为 2 份 |
| `backend/scripts/` 90 个平铺 | 按 §7.5 分类 |
| 3 份重复 regroup 脚本 | 合并为 1 份 |
| `.opencode/`(52.6 MB)、`.claude/`(17)、`.omo/`(152)、`.agents/`(63)、`.superpowers/`(12)、`.sisyphus/`(3) | 归入 `.agent/` 单一目录：`.agent/{skills,tools}/` + `README.md` 索引 |
| `CLAUDE.md/`（目录） | 重命名为 `docs/ai-commands/`，消除与工具约定文件名的冲突 |

### 7.3 L3 · 需用户明确授权

| 事项 | 说明 |
|---|---|
| 轮换已泄露的 DeepSeek API 密钥 | §2.11；**唯一彻底解法**，与代码无关 |
| `admin_token.txt` 移出 Git 跟踪 | §2.11 |
| 是否用 `git filter-repo` 改写历史清除密钥 | 改写历史影响所有协作者，需明示 |

### 7.4 🚫 红线（禁止删除或移动）

| 禁动项 | 体积 | 理由 |
|---|---:|---|
| `题库/` | 662 MB | 原始 PDF 语料，唯一事实来源；行测重导依赖它 |
| `.vtj/` | — | 92 处路由硬绑定 + 45 个 raw 手写页 + 设计器按 id 读写 |
| `backend/app/static/` | 4.3 GB | 题图在库，删除即全站裂图 |
| `backend/data/question_bank.db` | 292 MB | 生产库 |
| `backend/data/gates/*.json` | 5.3 MB | 门禁基线，已 `.gitignore` 反选入库 |

### 7.5 `backend/scripts/` 分类

```
backend/scripts/
├── gates/     gate_all gate_l0_redlines gate_l1_parser gate_l1g_field_fingerprint
│              gate_l1h_composite_material gate_l2_matching gate_l3_ingest
│              gate_l4_api_contract gate_l5_frontend_contract    ← 8 个一套
├── migrate/   migrate_*.py + add_user_role_field.py
├── repair/    repair_* fix_* cleanup_* purge_* regroup_* dedup_* normalize_*
├── probe/     probe_* diag* _analyze _check + test_*             ← 保留可复跑
├── admin/     init_super_admin seed_admin clean_test_users
└── verify/    verify_*.py
```

命名收敛为 `{类别}_{对象}_{动作}.py`。**`probe/` 必须保留且保证可复跑**——它是本次重构全部实测结论的唯一来源；`_analyze_t3.py`、`_check_db.py`、`_essay_check.py`、`_verify_7rows.py` 等下划线开头的临时件归入此目录作为探测脚本，不删除。

### 7.6 预期效果

| 项 | 当前 | 清理后 |
|---|---|---|
| `backend/data` | 7.4 GB | ~6.0 GB（归并 1.4 GB；归档不计） |
| AI 工具目录 | 散落 6 处 | `.agent/` 单一目录 |
| `backend/scripts` | 90 平铺 | 6 类分目录 |
| 方案文档 | 134 平铺 | 4 层分类 |
| `题库/备考资料` | — | 保留 165 MB 新增语料 |

---

## 8. 三端统筹与端到端通信

### 8.1 三端是消费视角

沿用 §3.2 的十域。三端对域的依赖矩阵（实测端点数）：

| 域 | 模块 | 端点 | 学生 | 教师 | 管理 |
|---|---:|---:|:-:|:-:|:-:|
| `platform` | 6 | 90 | — | ✅ | ✅ |
| `catalog` | 6 | 78 | ✅ | ✅ | ✅ |
| `exam` | 6 | 54 | ✅ | ✅ | ✅ |
| `library` | 3 | 31 | ✅ | — | ✅ |
| `growth` | 3 | 19 | ✅ | — | ✅ |
| `community` | 2 | 19 | ✅ | ✅ | — |
| `identity` | 3 | 16 | ✅ | ✅ | ✅ |
| `personal` | 2 | 14 | ✅ | — | — |
| `content` | 3 | 13 | ✅ | — | ✅ |
| `reward` | 3 | 9 | ✅ | — | ✅ |

后续教师端、管理员端方案**只在这 10 个域内扩展 router**。例如教师端新增「试卷审批加速」属于 `exam` 域的扩展，管理员端新增「商城对账」属于 `reward` 域的扩展——不新增域，不打破边界。

### 8.2 跨端通信一致性

| 通道 | 用途 | 保证 |
|---|---|---|
| `/api/v1/**` | 同步查询与操作 | 路径冻结；`api_surface.json` 逐条比对 |
| Redis Stream | 异步事件（成就发放、徽章生成、金币变动） | 事件 schema 版本化 `x.v1`，只增不删 |
| WebSocket | 实时推送（练习同步、金币变动通知） | `api/v1/websocket.py` 已存在，不改协议 |

### 8.3 端到端链路示例

以「学生答题 → 金币变动 → 成就解锁」为例，改造后的完整链路：

```
学生答题
  → POST /api/v1/practice/submit        （exam 域，本域写 PracticeRecord）
  → 发布事件 user.action{answer_correct}（core/events.py）
  → growth 域消费 → 判定任务完成 → 发布 growth.awarded
  → reward 域消费 → 调 contract.grant_coins()（**写操作走契约**）
  → reward 域写 CoinRecord（本域写，合规）
  → 发布 coin.granted → WebSocket 推送给前端
  → growth 域消费 → 成就判定 → 发布 achievement.unlocked
```

改造前，这条链路上 `practice.py` 会直接 `import CoinRecord` 并写表、`import achievement_service` 并调用——**两处跨域写违规**。改造后全部经事件与契约，三端中任一端改动不影响其余两端。

---

## 9. 落地阻塞项与决策请求

> 以下 5 项**需用户决策或授权**，无法由实施方自行决定。

### 9.1 🔴 DeepSeek API 密钥已泄露（最高优先级）

**事实**：`.omo/plans/configure-deepseek-api.md` 含硬编码密钥 `sk-9a2e…`（已掩码），已随提交 `4a18f89` 进入 Git 历史，文件处于跟踪状态。`admin_token.txt` 亦被跟踪。

**请求**：
1. **立即在 DeepSeek 控制台吊销该密钥并签发新密钥**——这是唯一彻底解法，可立即执行，与本项目无关；
2. 是否将新密钥改写入配置而非文档；
3. 是否授权用 `git filter-repo` 改写历史（影响所有协作者，需明示）；
4. 是否授权将 `admin_token.txt` 移出 Git 跟踪并轮换其内容。

**影响面**：一旦学校服务器部署且仓库被他人访问，密钥可被直接利用产生费用。

### 9.2 🔴 默认密钥与调试开关必须覆盖

`core/config.py` 的 `JWT_SECRET_KEY="your-secret-key-here-must-be-at-least-32-characters"`、`DB_PASSWORD="123456"`、`DEBUG=True` 均为**可直接利用的默认值**。任何人用默认密钥签发的 JWT 都能通过管理员鉴权。

**请求**：确认由 `.env.school` 强制覆盖，且 `DEBUG=False`。此项无需用户决策即可实施，但需确认学校服务器的密钥保管方式。

### 9.3 🟠 MinerU 与 OCR 的 Windows 绝对路径

`MINERU_PYTHON=C:\mineru_env\Scripts\python.exe`、`OCR_PYTHON=D:\ocr-env\Scripts\python.exe` 在 Linux 容器内必然失效。且配置注释说明二者分别需 Python 3.11 与 <3.12，**无法在 `python:3.13-slim` 进程内承载**。

**请求**（三选一）：
- **A**：学校服务器不需要扫描件 PDF 解析 → `MINERU_ENABLED=false` 降级，OCR 同样关闭（最简）
- **B**：需要 → 在服务器单独建两个 venv（Python 3.11 / 3.11），容器内通过 `MINERU_PYTHON`/`OCR_PYTHON` 指向其绝对路径
- **C**：需要 → 将二者独立为两个容器（偏离「单容器」决策，需重新评估）

### 9.4 🟠 行测题库重导进度 2.3%

行测有效题 **233 道**，历史峰值为 **10,171 道**，缺口约 **9,900 道**。已确认 `题库/行测/` 原始 PDF 完整保留，可用新管线重导。

**请求**：行测重导**是否需要在本方案落地之前完成**？这决定学校服务器上线时的可用内容量。请注意：重导是**数据任务**，不是本次代码重构的一部分。

### 9.5 🟡 测试 fixture 幂等缺陷

52 个 error 同源于 `index idx_import_status already exists`（建索引未用 `IF NOT EXISTS`）。**在修复前，门禁的红绿信号不可信**。

**请求**：确认将此项修复排在重构之前（实施方建议如此，无异议则按此执行）。

---

## 10. 风险与缓解

| # | 风险 | 影响 | 缓解 |
|---|---|---|---|
| 1 | **SQLite 单写入者** | 无法多副本、无法水平扩展 | 已定单容器部署，限制不产生代价；`DB_TYPE` 已预留 MySQL 出口 |
| 2 | **4.3 GB 题图卷** | 镜像若误含题图将膨胀到 5 GB+ | 明确列为 volume，`docker-compose.yml` 中不 COPY；加 `.dockerignore` |
| 3 | **VTJ 设计器锁定**（92 处硬绑定） | 任何移动 `.vtj/vue/` 的操作会 404 并破坏设计器 | 列为红线；`vtj-frontend` 技能已有铁律；写入门禁检查 |
| 4 | **空的手机端/平板端项目目录** | 可能是待建脚手架，也可能是废弃物 | 本次不动；在 §9 之外单独确认去留 |
| 5 | **`.worktrees/badge-engine-v4` 在制工作** | 徽章功能开发中，可能与本次重构冲突 | 徽章明确不在本次范围；两者域归属需后续协调 |
| 6 | **41 份唯一备份占 5 GB** | 磁盘占用 | 按 §6.5 保留策略归档，不删除 |
| 7 | **8 处跨域 `achievement_service` 调用** | 改造工作量大 | 事件契约一次性消除；`growth` 域独立改造后可单独验证 |
| 8 | **`.worktrees/` 2.46 GB + `node_modules/` 657 MB** | 开发盘占用 | 已被 `.gitignore` 覆盖；清理动作属 L1 之外，建议单独处理 |

---

## 11. 验收标准

以下均为**可证伪断言**，非描述性文字。

### 11.1 容器化

| # | 断言 | 验证方式 |
|---|---|---|
| 1 | `docker compose up -d` 后全部服务健康 | `docker compose ps` 全部 `healthy` |
| 2 | 后端健康端点返回 200 | `curl -f http://localhost:8000/health` |
| 3 | 容器镜像**不含**题图 | 镜像体积检查，`/app/app/static` 为空目录 |
| 4 | 环境切换仅改 `DEPLOY_ENV` | 修改该变量后 `compose up -d` 即生效 |
| 5 | `DEBUG=False`、`JWT_SECRET_KEY` 非默认值 | 容器内 `env` 检查 + `/docs` 不暴露敏感配置 |

### 11.2 模块化

| # | 断言 | 验证方式 |
|---|---|---|
| 6 | **343 个 API 端点与重构前逐条一致** | `api_surface.json` 前后 diff 为空 |
| 7 | **`.vtj/` 零改动** | `git diff --stat -- .vtj/` 输出为空 |
| 8 | `models.py` 不再是单文件 71 模型 | `app/modules/<domain>/models.py` 各自成立，`models.py` 被删除或仅留 `Base` |
| 9 | 边界检查通过 | `python scripts/check_module_boundary.py` 退出码 0 |
| 10 | 跨域写违规归零 | 15 处 `check_and_grant` 调用点全部改为契约调用或事件 |
| 11 | 跨域 `achievement_service` 直接 import 归零 | `refactor_baseline/coupling.json` 对比：跨域条目清空 |

### 11.3 数据

| # | 断言 | 验证方式 |
|---|---|---|
| 12 | 41 份唯一备份**全部存在** | 逐份校验 SHA-256 |
| 13 | 77 份冗余文件已归并 | `backend/data` 体积下降 ≥ 1,411.9 MB |
| 14 | 备份可用 SQLite API 恢复并通过门禁 | `sqlite3.backup()` 产出副本后 `gate_all.py` 全绿 |
| 15 | `题库/`、`backend/data/gates/*.json` 完好 | 存在性 + Git 跟踪状态检查 |

### 11.4 上线

| # | 断言 | 验证方式 |
|---|---|---|
| 16 | 8 道门禁全绿 | `python scripts/gate_all.py` 退出码 0 |
| 17 | 测试基线不再有 fixture 诱发的 error | `pytest tests` 的 error 数为 0 |
| 18 | 回滚可在 5 分钟内完成 | 改 `APP_VERSION` 至上一 tag → `up -d` → `/health` 200 |
| 19 | 已泄露密钥已吊销 | DeepSeek 控制台确认（人工核验） |

---

## 12. 明确不在本次范围

| 项 | 理由 |
|---|---|
| **徽章生成服务** | 功能不存在（`api/v1/` 无 `badge.py`），属新增功能而非重构；`.worktrees/badge-engine-v4` 另有在制工作 |
| **行测题重导** | 属数据任务，原始 PDF 完整可用新管线重导，与代码重构解耦 |
| **教师端 / 管理员端详细方案** | 待用户后续提供；本规格已预留十域结构与之对接 |
| **换用 PostgreSQL / MySQL** | 单容器部署下 SQLite 无损失；`DB_TYPE` 已预留出口 |
| **引入微前端（qiankun 等）** | 收益远低于成本；改为 `src/` 内部分层 |
| **`.vtj/` 目录重组** | 92 处路由硬绑定，物理不可行 |
| **空的手机端/平板端项目目录处置** | 需用户单独确认去留 |
| **多副本 / 高可用** | 单机部署无此需求 |

---

## 附：本次实测产生的可复用资产

| 资产 | 路径 | 用途 |
|---|---|---|
| 架构基线（6 份 JSON） | `backend/data/refactor_baseline/` | API 快照、模型映射、耦合图、表使用、库表清单、汇总 |
| 备份审计报告 | `backend/data/backup_audit_report.json` | 逐库表数、行数、结构指纹、冗余清单 |
| 语料探测器 | `backend/scripts/probe_xingce_corpus.py` | 85 套行测配对、分节命中率、题号连续性 |
| 重构基线采集器 | 可复用（本次以临时脚本执行） | AST 提取端点/模型/耦合/表使用 |

> 重构基线 JSON 目前位于 `.gitignore` 覆盖范围内。若需随分支流转，须 `git add -f` 强制入库，否则其他机器无法复现门禁比对。

---

**文档结束**
