# AI 讲师（需求④）开工可行性评估 v1

> 状态：评估（未动代码、未建分支）
> 问题：原来设计的 AI 能否在现有 `main` 上开分支开始构建？还是已经有搭好的分支？
> 基线：`main = b78c351`（2026-11-04）；全部结论均为 `git` / 代码 / 数据库实测

---

## 0. 一句话回答

**没有现成的 AI 讲师分支**（唯一相关的 `feature/ai-assistant` 是对话助手、且已并入 main）；本地那个 `-ai-lecturer` 占位分支**落后 main 209 个提交**，不能直接用。
**但可以在现有 `main` 上开分支开始构建**——而且**第一步（契约 + 任务表 + 状态机 + 讲稿生成）不依赖任何外部服务**，现在就能写、能测；只有第二、三步（TTS、数字人/视频合成）需要你提供可用服务。

---

## 1. 分支现状（实测）

| 分支 | 位置 | 结论 |
|---|---|---|
| 本地 `feat/Study-Material-Management-ai-lecturer` | `e3e2e54`（2026-11-02） | **空占位**，落后 `main` **209 个提交** → 不建议在其上开发，建议从 main 重新切 |
| 远端 `feature/ai-assistant` | `de68f4a` | **已并入 main**（`de68f4a..main` behind=0），是「联考小智」对话助手，不是讲师 |
| 远端其它分支 | 27 个 | 无 `ai-lecturer` / `lecturer` / `video-gen` 相关分支 |
| 代码里的讲师痕迹 | — | `ai-lecture` / `lectureProvider` / `render_job` **命中 0**；需求④ 当时完成度 **0%** |

---

## 2. main 上已经具备的基建（可直接复用）

| 能力 | 位置 | 对 AI 讲师的价值 |
|---|---|---|
| **LLM 客户端** | [`backend/app/services/llm_client.py`](../../backend/app/services/llm_client.py) | `chat()` / `chat_plan()`；OpenAI Chat Completions 兼容（默认 DeepSeek）；3 个场景 prompt（心理/答疑/规划） |
| **LLM 接口 6 个** | [`platform/llm.py`](../../backend/app/api/v1/platform/llm.py) | `POST /api/llm/chat`（多轮 + scene + agent）、`/api/llm/sessions*`、`GET /api/llm/context/assemble`（把用户档案/记忆装配进上下文） |
| **会话持久化** | `ChatSession` / `ChatMessage` 表 | 讲稿多轮打磨、任务历史可直接复用 |
| **知识图谱 14 端点** | [`knowledge.py`](../../backend/app/api/v1/knowledge.py) | 按考点取节点/关系，做「讲稿分段 + 知识点锚点」的素材来源（专利要点③的双向锚点靠它） |
| **Agent 6 端点** | [`agent.py`](../../backend/app/api/v1/agent.py)、`services/agent_router.py`、`services/plan_agent.py` | 任务化编排（`/api/agent/run`、`/tasks`、`/trajectory`）可承载「生成讲稿→配音→合成」的长任务 |
| **视频资源 8 端点** | [`library/videos.py`](../../backend/app/api/v1/library/videos.py) | `list / {id} / upload / chunk / complete / stream / delete`；表 `video_resource`、`video_watch_record` 已建 |
| **媒体资产 F3** | [`services/media_service.py`](../../backend/app/services/media_service.py) | 音频/封面可走对象存储（`MEDIA_STORE_ENABLED=true` 已开） |
| **前端参照页** | `.vtj/vue/ai_chat.vue`（2519 行）、`study_plan.vue`、`knowledge_view.vue` | 聊天式讲师的交互/样式可直接参考 |
| **讲稿素材** | 102 篇备考资料（99 卡 + 3 篇科目说明）、110 条分类规则、考点表 | 讲稿「按科目/考点生成」的输入已齐 |

---

## 3. 缺口（需求④ 真正要新建的东西）

| # | 缺什么 | 影响 |
|---|---|---|
| 1 | **契约**：`POST /api/materials/{id}/ai-lecture` → `{job_id, status}`、`GET …/ai-lecture/{job_id}` | 原方案 §6.2 的「第①步」一行代码都还没有 |
| 2 | **任务表 + 状态机**：`ai_lecture_job`（material_id/style/status/script/audio_url/video_id/error） | 长任务必需 |
| 3 | **provider seam**：`lectureProvider`（默认 null → 501 降级） | 没有它就只能硬编码外部服务 |
| 4 | **TTS / 数字人 / 视频合成 provider** | 本机 **ffmpeg 未安装**；`config.FFMPEG_PATH` 只是占位；代码里无任何 tts/ffmpeg 调用 |
| 5 | **LLM key** | `backend/.env` 不存在，仅 `.env.example`；实测 `settings.LLM_API_KEY = None` → 现在 `/api/llm/chat` 调不通（401） |
| 6 | **视频数据** | `video_resource` **0 行**、`study_material.video_id` **0 条使用** → 无真实素材可对照 |

---

## 4. 结论：能开工，但要分三步（第①步不依赖外部）

沿用总体方案 §6.2 的三步走，现在的依赖情况：

| 步骤 | 内容 | 外部依赖 | 现在能否做 |
|---|---|---|---|
| **①** | 契约 + `ai_lecture_job` 表 + 状态机 + **讲稿生成**（调 `llm_client`，按科目/考点分段） + 501 降级 | 只要一个 **LLM key** | ✅ **能，且可本地全测** |
| **②** | TTS 配音（音频先行，成本最低） + 字幕时间码 | 需要 TTS 服务（云 TTS 或本地） | ⏳ 需你提供 |
| **③** | 数字人 + 视频合成（ffmpeg 拼接/合成） | 数字人/视频服务 + 本地 ffmpeg | ⏳ 需你提供 + 装 ffmpeg |

---

## 5. 建议的分支与首批任务

**分支**：从 `main` 新切（把旧占位分支指过来即可，别在旧分支上开发）

```powershell
git switch -c feat/ai-lecturer main
# 或者复用旧名字：
# git branch -f feat/Study-Material-Management-ai-lecturer main
```

**首批任务（第①步，纯本地可完成）**

1. `backend/app/api/v1/library/ai_lecture.py`：`POST /api/materials/{id}/ai-lecture`、`GET /api/materials/ai-lecture/{job_id}`
2. 迁移 `YYYYMMDD_00x_ai_lecture_job.sql`：任务表（`status ∈ queued|scripting|tts|rendering|done|failed`）
3. `backend/app/services/lecture_service.py`：`generate_script(material, subject, points)` → 分段讲稿 JSON（复用 `llm_client.chat`，新增 `lecture` 场景 prompt）
4. provider seam：`settings.LECTURE_PROVIDER`（默认 `null` → 返回 501/仅图文讲稿降级）
5. 端点登记：`backend/tests/test_api_surface.py` 白名单（R11）+ 页面/端点计数同步（L6/L7）
6. 前端：资料详情页加「AI 讲解」按钮（`.vtj` 页守 R3 → 用 DOM 注入或设计器拖） + 任务轮询 + 音频/视频播放器

**专利材料要留的锚点**（总体方案 §6.3）：讲稿分段 ↔ 考点节点、视频时间码 ↔ 卡片背面知识点、风格参数（语速/停顿/强调）映射表。

---

## 6. 需要你确认/提供

1. **LLM key**：不加 key 连第①步的讲稿生成都跑不通（当前 `LLM_API_KEY` 为空）。
2. **TTS 服务**：用哪家（云厂商/本地模型）？决定第②步。
3. **数字人/视频合成**：是否有可用服务或预算？决定第③步；没有的话可先只做「图文讲稿 + 音频」。
4. 是否需要我**现在就开分支、把第①步（契约+任务表+状态机+讲稿生成+501 降级+测试）做完**。
