# 招考信息多源扩充 — 架构设计与实施计划 v1

> **状态**：🟡 **方案已定稿，6 项裁决全部锁定，待你书面批准**
> **前置依赖**：本计划依赖 `recruitment-daily-refresh-fix.md`（方案 v2）的 **P0 阶段**（`publish_date` 列 + 真实排序）。**必须先完成 v2 的 P0**，否则多源数据同样会排序错乱。
> **生成日期**：2026-10-09
> **已锁定裁决**：Q1=手写预览组件（已实证安全） / Q2=首批仅 M0+M1 / Q3=20MB·2GB / Q4=先单窗口 / Q5=接受省市卫健委 / Q6=6 类全做但分批
> **执行分支**：`feat/recruitment-daily-refresh`（与 v2 同一分支，共用基线 tag）

---

## 〇、实证验证结论（Playwright + HTTP 实测，非推断）

### 0.1 已验证可用的源站

| 分类 | 源站 | URL | 渲染 | 最新内容 | 距今 | 抓取方式 |
|---|---|---|---|---|---|---|
| **事业单位** | 中国公共招聘网·事业单位公开招聘 | `job.mohrss.gov.cn/cjobs/institution/listInstitution` | 服务端 | **2026-09-24** | **15天** | requests + BS4 |
| **国考** | 中央机关及其直属机构考试录用公务员专题 | `bm.scs.gov.cn/pp/gkweb/core/web/ui/business/home/gkhome.html` | **纯 JS** | 招考公告 2026-05-07 / 公示 2026-08-06 | 64天 | **Playwright** |
| 企业 | 国家大学生就业服务平台 | `ncss.cn/student/jobs/index.html`（110KB） | 服务端 | 待接入时验证 | — | requests |
| 企业 | 国聘网 | `iguopin.com`（**仅 1363B SPA 壳**） | 纯 JS | 待验证 | — | Playwright / 其 JSON API |
| 教师 | 北京市教委 | `jw.beijing.gov.cn`（103KB） | 服务端 | 待验证 | — | requests |
| 教师 | 山东省教育厅 | `edu.shandong.gov.cn`（55KB） | 服务端 | 待验证 | — | requests |
| 三支一扶 | 河南省人社厅 | `hrss.henan.gov.cn`（106KB） | 服务端 | 待验证 | — | requests |
| 三支一扶 | 山东省人社厅 | `hrss.shandong.gov.cn`（110KB） | 服务端 | 待验证 | — | requests |
| 医疗 | 广东省卫健委 | `wsjkw.gd.gov.cn`（94KB） | 服务端 | 待验证 | — | requests |
| 医疗 | 保留 | `www.rszk.net/yiliao/` | 服务端 | 2026-10-09 已更新 | — | requests（**保留**） |

### 0.2 不可用 / 需替代的源

| 源站 | 实测结果 | 处置 |
|---|---|---|
| `www.21wellyan.com` 中国卫生人才网 | **ConnectionError**（连接失败） | ❌ 放弃，改用省/市卫健委 |
| `www.nhc.gov.cn` 国家卫健委 | **HTTP 412**（反爬拦截） | ❌ 放弃或仅用 Playwright 尝试 |
| `job.dxy.cn` 丁香人才 | 302 跳转到 `dxy.cn/bbs`（非招聘站） | ❌ 放弃 |
| `rscn` 探测 `ncss.cn` 首页 | 检出 `captcha` 特征 | ⚠️ 接入时需 Playwright 兜底 |

### 0.3 事业单位源逐条满足你的要求 #5（实测原文）

| 你的要求 | 实测证据 |
|---|---|
| 招考日期（开始-结束） | `报名时间：2026年10月10日8:00至10月26日18:00，逾期不可补报。` |
| 文档附件→超链接 | `附件下载：` → `附件1.2027年度中国地震局局属单位事业人员公开招聘岗位信息表.xlsx`（`./P020260923584424851622.xlsx`）、`附件2.笔试大纲.docx` |
| 具体招考内容要求 | 招聘计划 / 报考程序 / 笔试内容 / 面试确认 完整正文 |
| 过滤无关字段 | 现有爬虫**只过滤标题噪音，正文未过滤** → 本计划补齐 |

### 0.4 发现的真实反爬（你要求 #2 的实证案例）

`www.mohrss.gov.cn`（人社部主站，事业单位详情页所在域）部署 **JS Cookie 质询**：

```javascript
document.cookie = "__tst_status=...";
location.href = location.href.replace(/[?|&]tads/, '')
```

- 纯 `requests` → 只得 **988 字节**质询页
- `Playwright` 执行 JS 后 → **正常渲染**（已实测拿到完整正文与附件）

**结论**：必须"列表页 requests + 详情页 Playwright 兜底"的**混合策略**。

### 0.5 技术底座已完备（无需新增依赖）

| 层 | 已有依赖 | 用途 |
|---|---|---|
| 后端 | `requests` / `httpx` / `beautifulsoup4` / `lxml` | 常规抓取 |
| 后端 | **`playwright>=1.48.0`** + **`playwright-stealth>=1.0.6`** | JS 渲染 + 反检测（v5 改用 requests 后被闲置，**正好复用**） |
| 前端 | **`docx-preview`** + **`mammoth`** + **`xlsx`** | 应用内附件预览（你的选择） |

---

## 一、核心问题诊断：现有爬虫为何无法扩展

### 1.1 站点特定逻辑与通用逻辑**混在一个函数里**

```python
# recruitment_scraper.py 当前结构（硬编码）
LIST_CONTAINER  = 'div.fxlist_Conday'          # ← 站点特定
LIST_ITEMS      = 'div.fxlist_Conday ul li'    # ← 站点特定
PAGINATION      = 'div.new_pagediv'             # ← 站点特定
DETAIL_TITLE    = 'div.channel-main.clearfix h1'# ← 站点特定
DETAIL_BODY     = 'div.channel-text.pb30'       # ← 站点特定
DETAIL_DATE     = 'div.channel-laiyuan p.fl span'# ← 站点特定
CATEGORY_CONFIG = {6 个分类的 rszk.net 固定 URL} # ← 站点特定
```

而以下**全部是通用的**（与站点无关，可 100% 复用）：
- `_extract_time_range()` — 报名起止时间提取
- `_detect_tag()` — 状态标签判定
- 考试方式 / 联系方式 / 发布单位 / 地区 的正则提取（`_parse_detail_page` L288-311）
- `_process_content_links()` — 附件链接化 + 非附件链接清洗
- `NOISE_TITLE_KEYWORDS` 噪音过滤
- `_replace_category()` — 逐分类事务替换

**每加一个站点就复制一遍全部逻辑 = 必然出现"改了一处漏了三处"，这正是历史上 5 次修复失效的结构性原因（见 `recruitment-daily-refresh-fix.md` §〇）。**

### 1.2 其他缺口

| 缺口 | 现状 |
|---|---|
| 无内容级噪音过滤 | 只有标题黑名单，正文的「登录/注册/关注公众号」等未过滤 |
| 附件只能新窗口跳转 | xlsx/docx 浏览器无法预览，触发下载后离开本站 |
| 附件未代理缓存 | 每次点击都直连源站，反复消耗源站资源且慢 |
| 无 URL 级去重 | 实测事业单位源存在**重复条目**（t20260818_582359 出现 2 次，t20260818_582358 出现 2 次） |
| 无分页发现通用能力 | 分页解析仅针对 `div.new_pagediv` |
| 无编码自适应 | rszk 需 GBK，mohrss 需 UTF-8，硬编码易错 |
| 无源站健康度与降级 | 某源失败只记日志，前端无感知 |

---

## 二、目标架构：适配器模式（去粗取精）

```
backend/app/services/recruitment/
├── __init__.py
├── engine.py              【新增·核心】抓取引擎：编排、限速、重试、状态机
├── extractors.py          【新增·通用】字段提取（从现 _parse_detail_page 抽离）
│                            报名时间/考试方式/联系方式/发布单位/地区/状态标签
├── cleaner.py             【新增·通用】正文清洗：噪音过滤 + 附件结构化
├── attachments.py         【新增·通用】附件抽取 + 代理下载 + 缓存
├── fetchers.py            【新增】抓取器：RequestsFetcher / PlaywrightFetcher（混合策略）
├── sources/               【新增·每站一个文件】
│   ├── base.py            Source 抽象基类（声明式契约）
│   ├── rszk.py            现有 rszk.net（迁移，行为保持不变）
│   ├── mohrss.py          中国公共招聘网·事业单位
│   ├── scs_gk.py          中央公务员专题
│   ├── ncss.py            国家大学生就业服务平台
│   ├── iguopin.py         国聘网
│   ├── edu_bj.py / edu_sd.py  教师（省市教育厅）
│   ├── hrss_henan.py / hrss_shandong.py  三支一扶
│   └── wsjkw_guangdong.py 医疗
├── registry.py            【新增】源注册表：分类 → 源列表（配置化）
└── scraper.py             【重写】对外入口 scrape_all_recruitment()（保持签名兼容）
```

### 2.1 Source 抽象基类（新增站点 = 一个声明式文件）

```python
class Source:
    key: str                    # 唯一标识
    name: str                   # 展示名
    category: str               # 归属分类（国考省考/事业单位/…）
    base_url: str
    encoding: str = "utf-8"     # 显式声明，避免猜错
    engine: str = "requests"    # "requests" | "playwright"
    list_selector: str = ""     # 列表条目 CSS
    detail_title_selector: str = ""
    detail_body_selector: str = ""
    detail_date_selector: str = ""
    pagination_selector: str = ""
    max_pages: int = 5
    # 声明式规则，无需为每站写解析函数
    date_from_list: bool = True # 列表页是否自带日期（mohrss=True，rszk=True）
    detail_need_playwright: bool = False   # mohrss 详情页 = True
```

**收益**：新增一个站点 = 新建一个约 40 行的声明式文件，**不碰引擎、不碰通用提取器**。彻底消除"改一处漏三处"。

### 2.2 混合抓取策略（`fetchers.py`）

| 场景 | 策略 |
|---|---|
| 列表页（服务端渲染） | `RequestsFetcher`：UA 轮换 + 随机延迟 2–4s + 指数退避重试（复用现 `scraper_utils.safe_request`） |
| 详情页（JS 质询 / JS 渲染） | `PlaywrightFetcher`：**单浏览器实例复用**（非每页新建），`playwright-stealth` 反检测，串行执行 |
| 降级链 | Playwright 失败 → 重试 1 次 → 仍失败则**保留该分类旧数据**（沿用 v6 策略），并记入源健康度 |

> ⚠️ **性能红线**：Playwright 单实例常驻约 200–400MB。**全流程只允许 1 个实例**，且仅用于确需 JS 的站点；总量控制在 **≤ 5 个源**。若首日耗时 > 90 分钟，必须拆分到凌晨多时段窗口执行。

### 2.3 通用提取器（`extractors.py`）—— 从现有代码原样抽离

保持行为完全一致，避免回归：
- `_extract_time_range(full_text)` → 报名起止
- `_detect_tag(start, end, text)` → 状态标签 + 颜色
- 考试方式（笔试/面试组合）
- 联系方式 / 发布单位 / 地区 正则
- `NOISE_TITLE_KEYWORDS` 标题噪音

### 2.4 正文清洗器（`cleaner.py`）—— **新需求**

**噪音黑名单（你要求 #5）**，作用于**正文**而非仅标题：

| 类别 | 匹配内容 | 处置 |
|---|---|---|
| 账号类 | 登录、注册、账号、密码、找回密码、立即登录 | 移除该节点 |
| 社交引流 | 关注微信公众号、扫码关注、加入微信群、QQ群 | 移除该节点 |
| 付费引导 | 付费二维码、扫码付费、VIP会员、购买课程 | **移除该节点（含图片）** |
| 导航残留 | 上一篇/下一篇/返回顶部/打印本页/字号：大 中 小 | 移除 |
| 无意义 | 分享到、责任编辑、来源：xxx（保留来源但去噪） | 清理 |

**实现**：基于 `cleaner.py` 的 DOM 级过滤（`decompose()` 整个节点），而非正则删字符串 —— 避免破坏正文结构。过滤规则**以配置列表形式集中管理**，便于按源增删。

### 2.5 附件处理（`attachments.py`）—— **新需求**

| 能力 | 设计 |
|---|---|
| 抽取 | 从正文识别附件链接（扩展名 + 锚文本双条件，沿用现 `ATTACHMENT_EXTENSIONS`） |
| 结构化 | 抽取为 `[{name, url, ext, size?}]`，存 `recruitment_attachment` 表（新建） |
| **代理下载** | 后端 `GET /api/recruitment/attachment/{id}` → 校验白名单 → 代理源站下载 → 落 `backend/data/attachments/` → 返回 |
| **本地缓存** | 以 URL 的 MD5 为文件名；**命中缓存直接返回，不回源**（省源站资源） |
| 安全 | 仅代理 `sources` 注册表中登记过的域；仅允许 `xlsx/xls/doc/docx/pdf/zip`；**禁止任意 URL 代理**（防 SSRF） |

**前端交互**（你的选择：应用内弹窗预览）：

| 附件类型 | 预览方式 | 依赖 |
|---|---|---|
| `.docx` | `mammoth` 转 HTML 或 `docx-preview` 渲染 | 已有 |
| `.xlsx/.xls` | `xlsx` 解析为 HTML 表格 | 已有 |
| `.pdf` | `<iframe>` 内嵌（浏览器原生） | — |
| `.zip` 及未知 | 下载（不预览） | — |

> ⚠️ **VTJ 约束**：附件预览弹窗是**新增 UI 结构**。按 `CLAUDE.md/vtj.md`，模板结构须由设计器产出。但 `recruitment_info` 等为 `raw:true` 手写页，**在设计器中改动风险高**。建议：
> - **方案 A（已裁决 ✅）**：新增**手写预览组件** `src/components/AttachmentPreview.vue`（`script setup`，不受 raw/DSL 规则约束），由各页面 `<script>` 挂载调用 → 不碰 `.vtj` 模板
> - 方案 B：走 VTJ 设计器拖拽 → 需用户手动操作，且 raw 页有被覆盖风险
>
> **Q1 已裁决：方案 A**。你的顾虑（「手写组件会不会导致 VTJ 版本不一致而无法更新最新修改效果」）经实证为**否**，见下方 §2.6。

### 2.6 为什么手写组件不会导致 VTJ 版本不一致（实证）

**VTJ 版本一致性校验的适用边界**：它校验的是 `.vtj/vue/*.vue` 中 **`useProvider({ id, version })` 的 version 参数** 与 `.vtj/files/*.json` 的 `__VERSION__` 是否一致。**该校验只对调用了 `useProvider()` 的 VTJ 托管组件生效。**

手写组件**不调用 `useProvider()`** → 不存在 version 参数 → **VTJ 运行时根本不会去校验它，也不会覆盖它**。

**本项目已有大量现成先例（实测扫描 `.vtj/vue/*.vue` 的 import 语句）**：

| 手写组件 | 自身 `useProvider` 次数 | 已被哪些 `.vtj` 页面引用（实测） |
|---|---|---|
| `src/components/MobileTabBar.vue` | **0** | **5 个**：`mobile_home.vue:180`、`mobile_forum.vue:124`、`mobile_practice.vue:177`、`mobile_profile.vue:278`、`mobile_question_bank.vue:142` |
| `src/components/RecentPracticeRecords.vue` | **0** | **2 个**：`mobile_home.vue:180`、`tablet_profile.vue:269` |
| `src/components/VtjErrorBoundary.vue` | **0** | 全局错误边界 |
| `src/views/profile.vue` | **0** | 手写 `<script setup>` 页面，正常运行 |

> **决定性证据**：`RecentPracticeRecords.vue` 是一个 `useProvider` 次数为 **0** 的手写组件（`<script setup lang="ts">`），**内部已在第 130/134 行使用 `window.addEventListener('__VTJ_SYNC__', onSync)`**，并被 2 个 `.vtj` 页面正常引用与渲染。
> **即：「手写组件 + `__VTJ_SYNC__` 订阅」这套组合在本项目中已跑通并上线。**

**结论**：新增 `AttachmentPreview.vue` 采用完全相同的模式（`useProvider` 0 次 + `<script setup lang="ts">` + 由 `.vtj` 页面的 `components` 选项引入），**不会触发任何版本校验，不会被设计器覆盖，且修改后立即生效**（与手写页面 `src/views/**` 同等热更新待遇）。

---

## 三、数据模型扩充

| 表 | 变更 | 说明 |
|---|---|---|
| `recruitment_info` | 沿用 v2 的 `publish_date` | — |
| `recruitment_info` | **新增 `source_key`** | 标识来源站点，用于去重、统计、健康度 |
| `recruitment_source_health` | **新建** | `{source_key, last_run_at, last_success_at, status, item_count, error_msg, consecutive_failures}` |
| `recruitment_attachment` | **新建** | `{id, recruitment_id, name, ext, source_url, cached_path, size, created_at}` |

> 去重键升级：`(source_key, url_hash)` 或 `(category, publish_date, title)` —— 解决实测发现的**事业单位源重复条目**问题。

---

## 四、分批实施路线（务实拆解）

> 你要求 6 类全做。**20+ 站点无法一次交付**，按"框架 + 分批接入"推进，每批独立可验收、可回滚。

| 批次 | 内容 | 站点数 | 预估 | 价值 |
|---|---|---|---|---|
| **M0 框架** | 适配器架构 + 抽离通用逻辑 + `rszk` 迁移（**行为零变化**） | 0 | 中 | 解锁后续所有批次 |
| **M1 事业单位** | `mohrss.py`（含 Playwright 详情页兜底）+ 附件抽取 + 正文噪音清洗 | 1 | 中 | **最高**：15天新鲜度、17.4万岗位、含附件与报名起止 |
| **M2 国考** | `scs_gk.py`（Playwright 列表 + 点击解析 `javascript:void`） | 1 | 中高 | 权威源 |
| **M3 附件与清洗** | `attachments.py` + `cleaner.py` + 前端预览组件 | 0 | 中 | 满足要求 #5 |
| **M4 企业** | `ncss.py` + `iguopin.py` | 2 | 中 | 国企招聘分类补充 |
| **M5 教师** | `edu_bj.py` + `edu_sd.py`（+ 可扩展省模板） | 2 | 中 | 教师招聘 |
| **M6 三支一扶** | `hrss_henan.py` + `hrss_shandong.py` | 2 | 中 | 三支一扶 |
| **M7 医疗** | `wsjkw_guangdong.py`（+ 省卫健委模板） | 1 | 中 | 医疗（rszk 保留） |
| **M8 调度与健康度** | 源级重试/降级、`crawl-status` 扩展到源级 | 0 | 中 | 稳定性 |

**关键约束**：
- **M0 必须先做且行为零变化** —— 用 `rszk` 作为回归基准，M0 完成后招考数据应与改造前**完全一致**
- M1–M7 每批独立 commit + 独立验收
- **rszk.net 全程保留**（你的要求），仅作为 `sources/rszk.py` 之一继续贡献数据

---

## 五、验收标准

### M0 框架验收
| # | 项 | 判据 |
|---|---|---|
| 1 | rszk 行为零变化 | 改造前后 `scrape_all_recruitment()` 产出的 `(title, url, category)` 三元组**完全一致** |
| 2 | 通用逻辑已抽离 | `extractors.py` / `cleaner.py` 存在且被 `rszk.py` 复用，无重复实现 |
| 3 | 现有测试通过 | `pytest backend/tests/` 基线不劣化 |

### M1–M7 源站验收（每源重复）
| # | 项 | 判据 |
|---|---|---|
| 4 | 可抓取 | 手动触发该源，产出条目数 > 0 |
| 5 | 字段完整 | 新增记录 `publish_date` 非空；`registration_start`/`registration_end` 在源站有值时非空 |
| 6 | 无重复 | `source_key+url_hash` 唯一，无重复条目（实测事业单位源原本有重复） |
| 7 | 噪音过滤生效 | 抽查 20 条详情，正文无「登录/注册/关注公众号/付费二维码」 |
| 8 | 附件可点 | 附件超链接可点击，应用内弹窗成功预览 xlsx/docx |
| 9 | 不影响其他源 | rszk 及其他已接入源产出不变 |
| 10 | 源健康度可见 | `crawl-status` 返回每源 `last_success_at` / `status` / `item_count` |

### 性能红线
| # | 项 | 判据 |
|---|---|---|
| 11 | 单次全量耗时 | ≤ 90 分钟（超则拆分窗口） |
| 12 | 内存峰值 | Playwright 单实例，进程 RSS ≤ 1.5GB |
| 13 | 源站请求频率 | ≥ 2s/请求，单源串行，遵守 `robots.txt` |

---

## 六、风险与回滚

| 风险 | 等级 | 缓解 |
|---|---|---|
| **M0 重构引入回归** | **高** | rszk 作为回归基准；M0 独立 commit；验收 1 逐条比对 |
| **gov 站点封禁 IP** | **高** | ≥2s 间隔 + UA 轮换 + 指数退避 + 每日总量上限；命中 403/412 立即停止该源当日抓取并告警 |
| **Playwright 内存/超时** | 中 | 单实例复用；`timeout` 硬上限；失败降级为"保留旧数据" |
| **源站改版导致解析失效** | 中 | `recruitment_source_health` 连续失败计数；前端"数据可能过期"提示 |
| **附件代理 SSRF** | **高** | 严格域白名单（仅 sources 注册表登记域）+ 扩展名白名单 + 禁止内网地址 |
| **附件存储膨胀** | 中 | 按 URL MD5 去重缓存；单文件上限（建议 20MB）；总量上限可配 |
| **工作量失控** | **高** | 严格按 M0–M8 分批；每批独立验收；**未验收不进入下一批** |

### 合规边界（明确写入代码注释与本文档）
- 仅抓取**公开可见**页面，不绕过登录、不破解验证码
- 遵守各站 `robots.txt`；`Disallow` 的路径不抓
- 控制频率，避免给源站造成压力
- 抓取内容仅用于本系统展示，不二次分发
- **政府网站内容的著作权归属原作者**，页面需标注来源链接（现有 `url` 字段已满足）

---

## 七、裁决结果（2026-10-09 已锁定）

| # | 问题 | **裁决** | 落地要点 |
|---|------|----------|----------|
| **Q1** | 附件预览落地方式 | ✅ **方案 A：手写组件** | 新建 `src/components/AttachmentPreview.vue`（`useProvider` 0 次 + `<script setup lang="ts">`）。**已实证不会触发 VTJ 版本校验、不会被设计器覆盖**（§2.6，含 4 个现成先例） |
| **Q2** | 首批范围 | ✅ **M0 + M1** | 先做适配器框架（rszk 行为零变化）+ 事业单位源，用最小代价验证架构与真实收益，再决定 M2 之后 |
| **Q3** | 附件缓存上限 | ✅ **单文件 20MB / 总量 2GB** | 仅代理 `sources` 注册表登记域 + 扩展名白名单（防 SSRF） |
| **Q4** | 抓取时间窗 | ✅ **先单窗口** | 维持 00:05 一次跑完；实测 >90 分钟再拆分为多时段 |
| **Q5** | 医疗替代源 | ✅ **接受「省市卫健委 + rszk 保留」** | 以广东省卫健委（94KB，已验证）为模板，其他省市复制配置；`rszk.net/yiliao` 持续贡献 |
| **Q6** | 首批源站范围 | ✅ **6 类全做**（用户选择） | 但按 M0–M8 分批推进，**本轮仅执行 M0+M1**，M2–M8 待 M1 验收后再启动 |

### 本轮（首批）实际交付边界
| 项 | 内容 |
|---|---|
| 交付 | M0 适配器框架（rszk 行为零变化）+ M1 事业单位源（mohrss）+ 附件抽取与噪音清洗**后端部分** |
| **不交付** | 前端附件预览弹窗 UI（M3）、国考（M2）、企业（M4）、教师（M5）、三支一扶（M6）、医疗（M7）、源健康度面板（M8） |
| 验收门槛 | M0 的「rszk 行为零变化」为**硬门槛**，不通过则不得进入 M1 |

### 后续批次启动条件
M0+M1 全部验收项通过后，我会向你汇报实测收益（新增条数、新鲜度提升、耗时、内存），由你决定是否继续 M2 及之后。

---

## 附录：实证原文摘录

### A.1 中国公共招聘网事业单位列表（服务端渲染，结构规整）
```
1 | 中国地震局2027年度事业单位公开招聘公告        | 2026-09-24
  https://www.mohrss.gov.cn/SYrlzyhshbzb/fwyd/SYkaoshizhaopin/zyhgjjgsydwgkzp/zpgg/202609/t20260923_584466.html
2 | 司法部机关服务中心面向社会公开招聘工作人员的公告 | 2026-09-24
3 | 市场监管总局直属事业单位2026年度第二批公开招聘公告 | 2026-09-21
...
12 | 中国藏学研究中心所属事业单位...公开招聘工作人员公告  | 2026-08-21
14 | 中国藏学研究中心所属事业单位...公开招聘工作人员公告？ | 2026-08-19   ← 与 12 同 URL（重复）
13 | 中国新闻社2026年度面向社会公开招聘工作人员公告        | 2026-08-21
15 | 中国新闻社2026年度面向社会公开招聘工作人员公告        | 2026-08-19   ← 与 13 同 URL（重复）
```
→ **去重必需**，去重键建议 `(source_key, url_hash)`。

### A.2 事业单位详情页（Playwright 突破 JS 质询后）
```
标题：中国地震局2027年度事业单位公开招聘公告中华人民共和国人力资源和社会保障部
报名时间：2026年10月10日8:00至10月26日18:00，逾期不可补报。
附件下载:
  附件1.2027年度中国地震局局属单位事业人员公开招聘岗位信息表.xlsx  ./P020260923584424851622.xlsx
  附件2.笔试大纲.docx                                                    ./P020260923584424958593.docx
```

### A.3 mohrss 反爬（requests 失败）
```
GET https://www.mohrss.gov.cn/.../t20260923_584466.html  → HTTP 200, 988 bytes
<script>function a(a){...}...document.cookie="__tst_status=...";location.href=location.href.replace(/[?|&]tads/,'')</script>
```

### A.4 现有爬虫中「通用 vs 站点特定」切分点（源码行号）
| 通用（应抽离） | 行号 | 站点特定（应声明化） |
|---|---|---|
| `_extract_time_range` 报名起止 | L156-177 | `LIST_ITEMS` L49 |
| `_detect_tag` 状态标签 | L177-200 | `DETAIL_TITLE` L53 |
| 考试方式判定 | L288-293 | `DETAIL_BODY` L54 |
| 联系方式正则 | L296-299 | `DETAIL_DATE` L55 |
| 发布单位正则 | L302-305 | `PAGINATION` L51 |
| 地区正则 | L308-311 | `CATEGORY_CONFIG` L31-42 |
| `_process_content_links` 附件 | L~150 | `MAX_PAGES_PER_CATEGORY` L59 |
| `NOISE_TITLE_KEYWORDS` | L62-65 | |
| `_replace_category` 事务替换 | L536-564 | |

---

> **本轮执行范围（Q2 裁决）**：**仅 M0 + M1**。M2–M8 列为后续批次，待 M0+M1 验收汇报后由你决定是否继续。
> **执行方式**：批准后 `/start-work`，在 `feat/recruitment-daily-refresh` 分支上依次完成 v2 的 P0 → 本计划 M0 → M1。
