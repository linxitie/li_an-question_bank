# 论坛 AI 言论审核 · 知识库接入方案 v3（addendum to v2）

> 状态：**待用户批准**
> 日期：2026-11-05
> 前序：`论坛AI言论审核_分层多Agent_设计方案_v2.md`（架构）
> 本文回答一个问题：**仓库能不能直接用 `D:\个人知识库\AI舆情审核知识库` 里的知识？**
> 答案：**能，且编译器已在仓库里；但当前只能编译 21/29 条，且关键正例漏检。**

---

## 1. 知识库实测概况

| 项 | 实测 |
|---|---|
| 路径 | `D:\个人知识库\AI舆情审核知识库\AI舆情审核知识库`（**注意目录名重复两层**） |
| 规模 | 69 个文件，174.5 KB |
| 政策卡 | 29 张，覆盖 10 域（违法违规 6 / 侮辱攻击 4 / 虚假信息 3 / 校园敏感 3 / 未成年人保护 3 / 色情低俗 2 / 广告引流 2 / 有害思想 2 / 数据隐私 2 / 自伤危机 2） |
| 案例卡 | 3 张（边界 / 误判 / 对抗） |
| 契约 | frontmatter 契约 + 标签体系 + 4 套模板 |
| 判定与处置 | 动作梯度卡（A0–A5）、仲裁与申诉 |
| 模型与规则 | 规则 DSL 与编译、黄金集与红队 |
| 可视化 | 4 张 Canvas + 2 个仪表盘 |
| 流水线 | 收件箱（提案 T-2026-1104-001 等）/ 产出 |
| 铁律 | 机器只读编译产物 `ruleset.json`，**不读本库正文** |

---

## 2. 仓库已有的接入能力（不用重写）

`app/services/policy_compiler.py`（481 行）已经实现了 v3 需要的大部分：

| 函数 | 作用 |
|---|---|
| `resolve_policy_root(vault_dir)` | 定位 `<vault>/AI舆情审核知识库/政策库` |
| `load_library(vault_dir)` | 扫描政策卡 → `Library(policies, issues, scanned, skipped)` |
| `parse_policy_file` | frontmatter + `policy_dsl` 解析 |
| `compile_ruleset(library)` | 生成 ruleset（含 `ruleset_hash`、条款、所需词表） |
| `score_text(text, ruleset, scope, enforce_block)` | 运行时打分 → `bucket`（allow/hold/mask/block） |

配置项：`MODERATION_VAULT_DIR`（默认 `D:\Obsidian仓库`，**需改为实际路径**）、`MODERATION_VAULT_WRITE`（默认 False）。

---

## 3. 真实编译结果（实测，2026-11-05）

```text
解析到的政策库根: D:\个人知识库\AI舆情审核知识库\AI舆情审核知识库\政策库
扫描 30 个文件，生效 21 条，跳过 9，问题 49
```

**试判（真实跑 score_text，enforce_block=False）：**

| 输入 | 结果 | 期望（按政策卡） |
|---|---|---|
| 楼主就是个智障，脑子进水了吧 | **allow，score 0.0，无命中** | hold（P-03-001 正例） |
| 这题设计得真够蠢的，出题人怕不是没睡醒 | allow 0.0 | allow（反例，正确） |
| 我真是个废物，这道题又错了 | allow 0.0 | allow（自嘲反例，正确） |
| 加我微信，内部真题包过，不过退款 | **hold 0.68**，命中 P-01-005 + P-06-002 | hold（正确） |
| 今天食堂的菜挺好吃的 | allow 0.0 | allow（正确） |

**结论**：regex 类规则能跑通，**lexicon 类规则全部空转**（正例漏检）。

---

## 4. 契约偏差清单（49 个编译问题的归类）

| # | 偏差 | 数量级 | 根因 | 影响 |
|---|---|---|---|---|
| D1 | DSL 算子超出编译器白名单：`pattern` / `intent` / `object_in` / `multimodal` 等 | 多条 | 库按"规格 DSL"写，编译器只认 `lexicon/regex/ner_target/ner_org/keyword_all/keyword_any` | 该条规则被跳过 |
| D2 | `target` 顶层字段不被支持 | P-03-001 等 | 编译器 `DSL_TOP_KEYS` 没包含 `target` | 人身攻击的"必须指向具体人"约束丢失 |
| D3 | `scope: forum.media` 不支持 | P-02-001 等 | 编译器 scope 枚举只有 post/comment/all | 多模态条款整条跳过 |
| D4 | 阈值缺 `mask` 档 | 多条 | 部分卡只写 allow/hold/block | 该条被判为不完整 |
| D5 | **21 个 lexicon 无词表定义** | 全局 | 库只引用词表名（`insult_zh_v1` 等），vault 与仓库都没有词表文件 | **lexicon 算子永不命中 → 正例漏检** |
| D6 | severity 枚举不一致 | 29 条全部 | 契约写 `1–5`，卡片写 `critical/high/medium/low` | 编译器按字符串处理（实际是对的），契约文档需修正 |
| D7 | 上下文条件未注册 | 多条 | `is_reporting_or_help_seeking` 等条件名未在编译器实现 | 修饰项被忽略（不致命） |

**D5 是致命项**：它让"人身攻击"这类最核心的条款完全失效，而 `pattern` 正则只覆盖了 4 个词。

---

## 5. 修复方案（按优先级）

### P0（不修就不能上线）

| 项 | 做法 | 验收 |
|---|---|---|
| D5 词表落地 | 新建 `vault/模型与规则/词表/<name>.yaml`，或把仓库 `cg_term`(88 条) 导出为词表；`lexicon` 算子接词表加载 | P-03-001 两条正例必须命中 |
| D1/D2/D4 编译器对齐 | 扩展算子白名单（`pattern`→`regex`、`intent`/`object_in` 至少支持枚举匹配）、加 `target`、阈值缺省补齐 | 29 条全部零 error |
| D3 scope | 增加 `forum.media`（映射为 comment+media 标记） | P-02-001 可编译 |
| 路径 | `MODERATION_VAULT_DIR` 改为 `D:\个人知识库\AI舆情审核知识库` | `resolve_policy_root` 命中 |

### P1（可追溯与门禁）

| 项 | 做法 |
|---|---|
| 黄金集 | 从 29 张卡的正反例自动生成初始黄金集（29×2=58 条），达到"50 条"下限 |
| 四项门禁 | F1≥0.90、误杀≤0.5%、漏放≤3%、P99≤80ms，接入 `compile` 流程 |
| 版本与回滚 | ruleset 保留 10 版，切指针回滚 |
| 审计 | 编译写 `cg_audit_event`（ruleset_hash + source_commit） |

### P2（与 v2 架构合流）

| 项 | 做法 |
|---|---|
| L1 语义 Agent 引用条款 | 专项 Agent 的 prompt 直接注入命中条款的 `title + 一句话定义 + 正反例`，输出必须带条款 ID |
| 仲裁证据链 | 用 ruleset 的 `bucket` + L1 置信度 + 案例库相似案例 |
| 红队 | 按"红队八种手法"生成样本，命中率 <80% 开提案 |
| 沉淀 | 误判 → 案例卡（复用 `案例卡模板`）→ 提案 → 编译 → 灰度 |

---

## 6. 与 v2 架构的接口

```
Obsidian 政策卡（人写）
   │  load_library + compile_ruleset（仓库已有）
   ▼
ruleset.json（sha256 + 版本）
   │  写入 cg_policy.compiled_dsl / cg_sync_state
   ▼
content_guard.engine（快筛 L0）
   │  命中 → 条款 ID + bucket
   ▼
L1 专项 Agent（引用条款全文 + 正反例，输出域标签 + 置信度）
   ▼
L3 仲裁（条款优先级 × 校准置信度 × 相似案例）
   ▼
动作：A0 放行 / A1 标记 / A2 HOLD（首月上限）
```

**铁律对齐**（来自库内 `动作梯度卡`）：
- LLM 永远无权执行 A3 及以上；
- 首月只写 A0/A1，M1 起才开 A2；
- 黄金集 <50 条禁止从影子切到 HOLD。

---

## 7. 待确认

| # | 决策 | 建议 |
|---|---|---|
| K1 | 词表来源 | **A. 先在 vault 建 `词表/` 从 cg_term 88 条导出（推荐）** / B. 另建人工词表 |
| K2 | 契约以谁为准 | **A. 改契约文档（severity 用 critical/high/medium/low，与编译器一致，推荐）** / B. 改 29 张卡为 1–5 |
| K3 | `target`/`intent` 算子 | **A. 本期实现 target + 枚举类算子，`intent` 依赖 L1 后置（推荐）** / B. 本期全部实现 |
| K4 | 路径配置 | **A. 改默认值为实际路径 + 支持环境变量覆盖（推荐）** / B. 只改环境变量 |
| K5 | 编译触发 | **A. 手动/POST 触发 + 每日定时对账（推荐）** / B. 文件变更自动编译 |
