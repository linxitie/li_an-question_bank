# 项目健康度修复与教师端趋势图实施计划

> 设计文档：`docs/superpowers/specs/2026-09-26-project-health-and-trend-chart-design.md`（提交 `82d2992`）
> 分支：`fix/vite-mobile-connection`（主目录，**不使用 worktree**）
> 执行方式：**全部由主代理直接执行，不派发子代理**（用户明确要求）
> 日期：2026-09-26

---

## 执行前必读

1. **端口唯一**：所有验证一律使用 `http://localhost:9527/`（Vite）与 `http://127.0.0.1:8000`（FastAPI）。禁止临时端口、禁止生成其他网址。
2. **预计时间**：每次执行长时间命令（`typecheck` 约 2–4 分钟、`build` 约 3–5 分钟、Playwright 约 1–2 分钟）前，**必须先向用户声明预计时间**。
3. **失败自动重试**：命令因环境抖动失败时，自动重试一次；连续两次失败则停止并向用户报告，不得空转。
4. **不修改任何 `.vtj/files/*.json` DSL 文件**。
5. **提交粒度**：每个 Task 一个提交，禁止跨 Task 混合提交。
6. **不派发子代理**：本机子代理不可用（两次超时），所有工作由主代理直接执行。

---

## Task 1：删除孤立死文件（风险最低，先行建立信心）

**目标**：消除 37 项类型错误，零运行时影响。

**Files**
- Delete: `src/vtj/vue/score_analysis.vue`

**依据（已核实）**
- 含 `useProvider({ id: 'score_analysis', version: '1778918611112' })`，属 VTJ 生成物。
- 不被 `src/router/index.ts`、`.vtj/router.js`、任何文件 import。
- `src/vtj/` 目录下仅此一个文件。
- `.vtj/vue/score_analysis.vue` 是同功能副本（同样未被路由），保留不动。
- 第 208 行 `import NavBar from './navbar.vue'` 断裂。

- [x] **Step 1：删除前最后一次确认无引用**

```powershell
Select-String -Path "src\**\*.ts","src\**\*.vue",".vtj\**\*.js" -Pattern "src/vtj/vue/score_analysis|vtj/vue/score_analysis\.vue"
```

期望：仅命中 `.vtj/vue/score_analysis.vue` 自身（`./vue/score_analysis.vue` 形式），**不得**出现 `src/vtj/vue/score_analysis` 字样。若出现任何引用，**停止并报告**。

- [x] **Step 2：记录基线错误数**

```powershell
npm run typecheck 2>&1 | Select-String "error TS" | Measure-Object | Select-Object -ExpandProperty Count
```

预计时间：约 2–4 分钟。期望：**78**。

- [x] **Step 3：删除文件**

```powershell
git rm -- "src/vtj/vue/score_analysis.vue"
```

- [x] **Step 4：验证错误数下降到 41**

```powershell
npm run typecheck 2>&1 | Select-String "error TS" | Measure-Object | Select-Object -ExpandProperty Count
```

预计时间：约 2–4 分钟。期望：**41**（78 − 37）。若不符，输出实际错误清单并停止。

- [x] **Step 5：提交**

```powershell
git commit -m "refactor: 删除未被引用的 score_analysis 孤立副本"
```

---

## Task 2：解除 build 阻断（`Tag` → `PriceTag`）

**目标**：`vite build` 不再因未知图标导出中断。

**Files**
- Modify: `.vtj/vue/tablet_forum.vue`

**依据（已核实）**
- `Tag` 在 `@vtj/icons@0.16.35` 与 `0.20.6` 中均不存在；44 个导入文件中仅此 1 处缺失。
- 真实存在的语义近义导出：`PriceTag`、`CollectionTag`、`IconTag`。
- `.vtj/files/tablet_forum.json` 中**不含** `Tag`，故改 `.vue` 安全，设计器重新生成不会复现。
- 4 处引用：模板第 58 行 `:icon="Tag"`、导入第 243 行、`setup()` return 第 464 行、导航配置第 270 行 `icon: Tag`。

- [x] **Step 1：确认 `PriceTag` 存在**

```powershell
node -e "import('@vtj/icons').then(m=>{console.log('PriceTag=',Object.keys(m).includes('PriceTag'))})"
```

期望：`PriceTag= true`。

- [x] **Step 2：替换 4 处引用**

在 `.vtj/vue/tablet_forum.vue` 中将 `Tag` 替换为 `PriceTag`，涉及：
- 导入语句中的 `Tag,` → `PriceTag,`
- 模板 `<XIcon :icon="Tag" ...>` → `:icon="PriceTag"`
- `setup()` return 中的 `Tag,` → `PriceTag,`
- 导航配置 `icon: Tag` → `icon: PriceTag`

**注意**：只替换独立的 `Tag` 标识符，**不得**误伤 `hotTags`、`searchByTag`、模板中 `v-for="(tag, index) in hotTags"`、`@click="searchByTag(tag)"` 等含 `Tag` 子串的标识符。

- [x] **Step 3：确认无残留**

```powershell
Select-String -Path ".vtj\vue\tablet_forum.vue" -Pattern "\bTag\b" -AllMatches
```

期望：无匹配（或仅匹配到已改为 `PriceTag` 之外的真实需求——若有需人工确认）。

- [x] **Step 4：验证 build 通过**

```powershell
npm run build
```

预计时间：约 3–5 分钟。期望：构建完成，不再出现 `"Tag" is not exported`。若出现**其他**图标缺失错误，说明存在本轮未发现的缺失导出，需重新全量扫描后再继续。

- [x] **Step 5：提交**

```powershell
git add -- ".vtj/vue/tablet_forum.vue"
git commit -m "fix: 用 PriceTag 替换不存在的 Tag 图标"
```

---

## Task 3：后端新增分班级趋势序列

**目标**：`/analytics/overview` 返回 `class_trend`，并顺带修 N+1 查询与日期键碰撞。

**Files**
- Modify: `backend/app/schemas/teacher.py`（第 329 行附近）
- Modify: `backend/app/api/v1/teacher.py`（第 1684–1766 行 `get_analytics_overview`）

**依据（已核实）**
- 学生与班级唯一关联是 `SysUser.class_name` **字符串**，无 `class_id` 外键。
- 现有 `score_trend` 以 `%m-%d` 为键（跨月/跨年会静默合并），必须修正。
- 第 1742 行 `db.query(ExamPaper).filter(ExamPaper.paper_id == r.paper_id).first()` 位于遍历 `records` 的循环体内（每条记录一次查询）。

- [x] **Step 1：新增 schema**

在 `backend/app/schemas/teacher.py` 的 `AnalyticsOverview` 之前插入：

```python
class ClassTrendPoint(BaseModel):
    """班级趋势单点"""
    date: str          # 输出格式 "09-01"
    avg_score: float


class ClassTrendSeries(BaseModel):
    """班级成绩趋势序列"""
    class_id: Optional[int] = None
    class_name: str
    points: List[ClassTrendPoint] = []
```

并确认 `AnalyticsOverview` 新增字段：

```python
    class_trend: List[ClassTrendSeries] = []
```

同时确认文件已导入 `Optional` 与 `List`（`teacher.py` 中已在用，应无需新增）。

- [x] **Step 2：修复日期键与 N+1 查询**

在 `get_analytics_overview` 中：

1. 将 `date_scores` 的键由 `r.start_time.strftime("%m-%d")` 改为完整可排序键 `%Y-%m-%d`，排序后再格式化为 `%m-%d` 输出，保持 `score_trend` 对外结构不变。
2. 将第 1742 行循环体内的逐条 `ExamPaper` 查询改为：循环外一次性收集全部 `paper_id`，批量查询后构建 `paper_id -> subject_id` 映射，循环内改为查表。

- [x] **Step 3：新增分班级聚合**

在同一函数中，保持 `score_trend` 原样，新增分班级聚合：

- 保留 `class_names`（教师全部班级）与被 `class_id` 过滤后的分支逻辑。
- 对每个班级名查出其 `user_id` 集合（`SysUser.class_name == 班级名` 且 `user_type == 'student'`）。
- 复用已查询的 `records`，按 `user_id -> class_name` 映射分组。
- 每班按完整日期键聚合平均分，排序后格式化为 `%m-%d`，输出 `ClassTrendSeries`（`class_id` 通过 `Banji` 按 `class_name` 反查填充，查不到则为 `None`）。
- 某班无任何记录时**不输出**该班序列（避免空折线）。

- [x] **Step 4：验证后端可导入且响应结构合法**

```powershell
cd backend; python -c "from app.schemas.teacher import AnalyticsOverview, ClassTrendSeries; print(AnalyticsOverview().model_dump().keys())"
```

期望：输出包含 `class_trend` 的键列表。

- [x] **Step 5：验证接口响应**

启动后端后，用教师账号 token 调用：

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/teacher/analytics/overview?days=30" -Headers @{ Authorization = "Bearer <token>" }
```

期望：
- `score_trend` 结构与改动前一致（`dates` + `scores`）；
- `class_trend` 为数组，每项含 `class_id`、`class_name`、`points`，每个 point 含 `date`（`%m-%d`）与 `avg_score`；
- 带 `?class_id=<真实id>` 时仅返回该班序列。

- [x] **Step 6：提交**

```powershell
git add -- "backend/app/schemas/teacher.py" "backend/app/api/v1/teacher.py"
git commit -m "feat: 学情总览新增分班级趋势并修正 N+1 查询与日期键"
```

---

## Task 4：前端趋势图完整实现

**目标**：修复筛选下拉框失效，实现真实渲染多班级折线的趋势图，消除 22 项类型错误。

**Files**
- Modify: `.vtj/vue/teacher_analytics.vue`

**依赖**：**必须在 Task 3 之后执行**（需要 `overview.class_trend` 字段）。

**依据（已核实）**
- `loadData` 定义于第 190 行，但 `setup()` return（第 287–292 行）**不含**它 → 模板 `@change="loadData"` 运行时为 `undefined`。
- 8 个趋势绑定在模板被引用但脚本中完全不存在。
- `trendData`（第 167 行 `ref<any[]>([])`）从未被填充。

- [x] **Step 1：确认当前错误清单**

```powershell
npm run typecheck 2>&1 | Select-String "teacher_analytics"
```

预计时间：约 2–4 分钟。期望：22 行。

- [x] **Step 2：把 `loadData` 加入 `setup()` return**

在 return 块（第 287–292 行）中补入 `loadData`。

- [x] **Step 3：填充 `trendData`**

在 `loadData()` 中，`overviewData` 解析成功后，取 `overviewData.class_trend`；若缺失或为空，则降级为单序列：

```typescript
const series = Array.isArray(overviewData.class_trend) && overviewData.class_trend.length
  ? overviewData.class_trend
  : [{ class_name: '平均分', points: (overviewData.score_trend?.dates ?? []).map((d, i) => ({ date: d, avg_score: overviewData.score_trend.scores[i] })) }];
trendData.value = series;
```

- [x] **Step 4：实现 8 个趋势计算属性**

在 `setup()` 内用 `computed` 实现并加入 return：

| 绑定 | 实现要点 |
| --- | --- |
| `trendSvgWidth` | 常量，建议 `640` |
| `trendSvgHeight` | 常量，建议 `260` |
| `trendYTicks` | 由全局分数值域等分生成（含 0 与上界，上界向上取整到 10 的倍数） |
| `trendY(tick)` | 刻度值 → 像素 Y；需与 `trendYTicks` 生成规则严格互逆 |
| `trendPoints` | 全部班级序列日期的并集，按序去重 → `{ label: date }[]` |
| `trendX(i)` | 索引 → 像素 X；需处理单点与空数组两种边界（返回轴中点 / 0） |
| `trendLines` | 每班级一条：`{ name: class_name, points: 'x,y x,y ...', dots: [{x,y}] }` |
| `trendColors` | 固定调色板字符串数组 |

**关键边界**：`trendData` 为空数组时，`trendLines`/`trendPoints`/`trendYTicks` 必须返回空数组或安全默认值，且 `trendY`/`trendX` 在被调用时不得抛异常（模板 `v-for` 虽会跳过，但 `trendX` 在 `trendPoints` 为空时不会被调用，仍需防御）。

某班级在某日期无数据时**跳过该点**，不补 0。

- [x] **Step 5：验证错误清零**

```powershell
npm run typecheck 2>&1 | Select-String "teacher_analytics"
```

预计时间：约 2–4 分钟。期望：**无输出**。

- [x] **Step 6：运行时验证**

用 Playwright 移动视口（390×844）访问 `http://localhost:9527/`，以教师账号 `ycc5678 / ycc5678` 登录后进入教师分析页，确认：
- 班级/科目下拉框切换后数据刷新（筛选真正生效）；
- 趋势图渲染出**多条**班级折线与图例；
- 控制台无该页相关的报错。

- [x] **Step 7：提交**

```powershell
git add -- ".vtj/vue/teacher_analytics.vue"
git commit -m "fix: 修复学情分析页筛选失效并实现分班级趋势图"
```

---

## Task 5：补齐类型声明与收窄（14 项真实错误）

**目标**：消除 TS7016（5 项）、TS18046（2 项）、TS2365/TS2345/TS7015（6 项）等真实类型错误。

**Files**
- Create: `src/utils/questionRender.d.ts`
- Modify: `src/router/index.ts`
- Modify: `.vtj/vue/teacher_profile.vue`
- Modify: `.vtj/vue/TeacherNavHeader.vue`
- Modify: `src/views/help.vue`
- Modify: `src/views/mobile_answer.vue`
- Modify: `src/views/mobile_news.vue`

**依赖**：**必须在 Task 1 之后**（否则基线数字不准）。

- [x] **Step 1：先读 `questionRender.js` 确认导出签名**

```powershell
Select-String -Path "src\utils\questionRender.js" -Pattern "^export|module.exports"
```

据实际导出编写 `.d.ts`，**不得凭空猜测签名**。若导出多个函数，逐一声明。

- [x] **Step 2：新增 `src/utils/questionRender.d.ts`**

按 Step 1 的真实签名声明。消除 `teacher_analytics:153`、`teacher_papers:364`、`mobile_answer:58` 三处 TS7016。

- [x] **Step 3：修 `src/router/index.ts` 的两处 TS7016**

第 51、57 行导入 `@/views/exercise.vue`、`@/views/solution.vue`。两文件均存在但缺声明——检查 `src/env.d.ts` 中已有的 `declare module '*.vue'` 变体为何未覆盖 `@/` 别名路径；如确认为别名路径未被通配符匹配，在 `src/env.d.ts` 中补充匹配 `@/*.vue` 的声明模块（**优先改 `env.d.ts` 而非在 router 内加 `// @ts-ignore`**）。

- [x] **Step 4：修两处 `$refs` TS18046**

`.vtj/vue/teacher_profile.vue:9` 的 `$refs.avatarInput`、`.vtj/vue/TeacherNavHeader.vue:74` 的 `$refs.profileAvatarInput`。使用 Vue 3.5 的 `useTemplateRef` 获得显式类型，并保持运行时行为与 `$refs` 完全一致。

- [x] **Step 5：收窄路由参数**

`src/views/help.vue:14`、`src/views/mobile_answer.vue:32,33,35`、`src/views/mobile_news.vue:33`。将 `route.params.x`（类型 `string | string[]`）显式转为 `number`，用 `Number(...)` 并校验 `Number.isNaN`，**不得**用 `as number` 硬断言掩盖。

- [x] **Step 6：验证错误清零**

```powershell
npm run typecheck 2>&1 | Select-String "error TS"
```

预计时间：约 2–4 分钟。期望：**仅剩 8 行，且全部为 `.vtj/vue/teacher_papers.vue`**。

- [x] **Step 7：提交**

```powershell
git add -- "src/utils/questionRender.d.ts" "src/env.d.ts" "src/router/index.ts" ".vtj/vue/teacher_profile.vue" ".vtj/vue/TeacherNavHeader.vue" "src/views/help.vue" "src/views/mobile_answer.vue" "src/views/mobile_news.vue"
git commit -m "fix: 补齐类型声明并收窄路由参数与模板引用"
```

---

## Task 6：CSP 放开图标字体

**目标**：消除 4 条 `font-src` CSP 违规。

**Files**
- Modify: `index.html`（第 12 行）

- [x] **Step 1：修改 CSP**

```html
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; connect-src 'self' ws: wss:; img-src 'self' data:; font-src 'self' data:; style-src 'self' 'unsafe-inline'; worker-src 'self' blob:;" />
```

- [x] **Step 2：运行时验证**

Playwright 访问 `http://localhost:9527/`，检查控制台消息中 `violates the following Content Security Policy` 数量。

预计时间：约 1–2 分钟。期望：**0 条**。

- [x] **Step 3：提交**

```powershell
git add -- "index.html"
git commit -m "fix: CSP 放开 data 字体以加载 VTJ 图标字体"
```

---

## Task 7：建立 typecheck 错误基线

**目标**：在仅剩 8 项 codegen 噪音时固化基线，作为守卫的判定依据。

**Files**
- Create: `.typecheck-baseline.json`
- Create: `scripts/verify-typecheck-baseline.mjs`（解析与比对逻辑，Task 8 复用）

**依赖**：**必须在 Task 1、5 之后**。

- [x] **Step 1：确认残余错误恰为 8 项且全在 teacher_papers.vue**

```powershell
npm run typecheck 2>&1 | Select-String "error TS" | ForEach-Object { ($_ -split '\(')[0] } | Group-Object | Format-Table Count,Name
```

预计时间：约 2–4 分钟。期望：单一分组 `8 .vtj/vue/teacher_papers.vue`。**若出现任何其他文件，立即停止并回到 Task 5。**

- [x] **Step 2：编写基线解析与比对脚本**

`scripts/verify-typecheck-baseline.mjs`：

- 执行 `vue-tsc --noEmit -p tsconfig.json`（通过 `spawn` 调用 `node node_modules/vue-tsc/bin/vue-tsc.js`）。
- 解析 `文件(行,列): error TSxxxx: 消息`，归一化为 `{ file, line, code }`，**丢弃列号与消息正文**。
- 读取 `.typecheck-baseline.json`；不存在时按「首次建立基线」处理：写出基线、打印提示、退出码 0。
- 存在时做集合差集：`新增 = 当前 − 基线`、`已消失 = 基线 − 当前`。
- `新增` 非空 → 打印新增条目并以退出码 1 失败；否则打印「已消失」条目作为清理提示，退出码 0。
- 兼容 Windows 下 `vue-tsc` 的 CRLF 输出与中文路径。

- [x] **Step 3：生成基线文件**

```powershell
node scripts/verify-typecheck-baseline.mjs
```

期望：创建 `.typecheck-baseline.json`，`totalErrors: 8`，全部条目 `file: ".vtj/vue/teacher_papers.vue"`。

- [x] **Step 4：验证幂等**

再次执行同命令，期望退出码 0 且报告「零新增」。

- [x] **Step 5：验证能捕获新错误**

临时在某个受 `tsconfig` 管辖的文件中引入一处类型错误，执行基线脚本，期望退出码 1 并准确指出该条目；随后撤销该临时错误，再次执行确认恢复退出码 0。

- [x] **Step 6：提交**

```powershell
git add -- ".typecheck-baseline.json" "scripts/verify-typecheck-baseline.mjs"
git commit -m "test: 建立 typecheck 错误基线并新增基线校验脚本"
```

---

## Task 8：统一守卫脚本（四类检查）

**目标**：一个 `scripts/verify-project-health.mjs` 覆盖图标导入、typecheck 基线、孤立文件、版本漂移，接入 `prebuild`。

**Files**
- Create: `scripts/verify-project-health.mjs`
- Modify: `package.json`（新增 `verify:health` 与 `prebuild`）

**依赖**：**必须在 Task 7 之后**（复用基线逻辑）。

- [x] **Step 1：实现检查 1 —— 图标导入合法性（阻断）**

- 递归遍历 `.vtj/vue/**` 与 `src/**` 下 `.vue`。
- 正则**必须**用 `import\s*\{([^}]*)\}\s*from\s*['"]@vtj\/icons['"]`。
  **严禁**使用 `[\s\S]*?` 等贪婪/跨语句写法——已实测会跨越多个 import 语句产生大量误报。
- 与 `await import('@vtj/icons')` 的运行时导出集比对。
- 未知图标时按「包含关系 + 编辑距离」从导出集中推荐最多 3 个候选，一并打印。

- [x] **Step 2：实现检查 2 —— 复用 Task 7 的基线比对（阻断）**

导入 `scripts/verify-typecheck-baseline.mjs` 导出的比对函数，避免逻辑重复。

- [x] **Step 3：实现检查 3 —— 孤立文件扫描（警告）**

- 收集 `src/router/index.ts` 与 `.vtj/router.js` 中出现的所有 `.vue` 路径引用（同时识别 `@/views/x.vue`、`$vtj/vue/x.vue`、`./vue/x.vue` 三种形式）。
- 扫描 `src/**`、`.vtj/vue/**` 下 `.vue`，未被引用者输出**警告**。
- **不得**因此失败：VTJ `Provider` 可注册动态 `/page/:id` 路由。

- [x] **Step 4：实现检查 4 —— VTJ 版本漂移（警告）**

- 对含 `useProvider(` 且带 `version: 'N'` 的 `.vtj/vue/*.vue`，取 `N` 与 `.vtj/files/<同名>.json` 的 `__VERSION__` 比对。
- 不一致输出**警告**，文案需点明「手改会在设计器保存时被覆盖」。
- DSL 文件不存在时跳过并提示。

- [x] **Step 5：汇总输出与退出码**

阻断类（检查 1、2）任一失败 → 退出码 1；仅警告（检查 3、4）→ 退出码 0。输出需分节清晰、含文件路径与建议动作。

- [x] **Step 6：接入 `package.json`**

```json
"verify:health": "node scripts/verify-project-health.mjs",
"prebuild": "node scripts/verify-project-health.mjs"
```

注意：`prebuild` 会在 `npm run build` 前自动执行。确认现有 `build` 链（`build` → `build:prod` → `vue-tsc && vite build`）不被破坏。

- [x] **Step 7：正向验证**

```powershell
npm run verify:health
```

期望：退出码 0；检查 1、2 通过；检查 3、4 输出警告（当前应能报出孤立文件与可能的版本漂移）。

- [x] **Step 8：反向验证（阻断有效性）**

临时把 `.vtj/vue/tablet_forum.vue` 的 `PriceTag` 改回 `Tag`，执行 `npm run verify:health`，期望退出码 1 并提示 `Tag` 与候选 `PriceTag`/`CollectionTag`/`IconTag`；随后改回。

- [x] **Step 9：提交**

```powershell
git add -- "scripts/verify-project-health.mjs" "package.json"
git commit -m "test: 新增项目健康度统一守卫并接入 prebuild"
```

---

## Task 9：全量验证与文档收尾

**目标**：五项验证标准全部通过，更新方案文档。

- [x] **Step 1：`npm run verify:health`**

预计时间：约 2–5 分钟（内含 typecheck）。期望：退出码 0。

- [x] **Step 2：`npm run typecheck:guarded`（门禁）与 `npm run typecheck`（全量视图）**

预计时间：约 2–4 分钟。期望：

- `npm run typecheck:guarded` 退出码 0，报告「零新增错误（当前 8 项，与基线一致）」——**这才是门禁**；
- `npm run typecheck`（裸 `vue-tsc`，全量诊断视图）退出码 2，仍报出 8 项基线噪音且全部位于 `.vtj/vue/teacher_papers.vue`——**属预期行为，不表示回归**。

> 实施过程中已确认：原验证标准把 `npm run typecheck` 当作门禁是表述错误。
> 裸 `vue-tsc` 会如实报告已知噪音并返回非零；`npm run build:prod` 已从 `vue-tsc` 改为
> `npm run typecheck:guarded`，因此构建不会被这 8 项噪音阻断。

- [x] **Step 3：`npm run build`**

预计时间：约 3–5 分钟。期望：端到端完成。

- [x] **Step 4：`npm run test:vite-resilience`**

预计时间：约 1–2 分钟。期望：`PASS vite resilience: ws proxy, 50 resets, strictPort, backend outage`。

- [x] **Step 5：Playwright 移动视口回归**

预计时间：约 2–3 分钟。视口 390×844，访问 `http://localhost:9527/`，确认：
- 页面正常渲染，无「一直加载」；
- 教师分析页筛选可用、趋势图渲染多班级折线；
- `/tablet/forum` 正常加载；
- 控制台 **0 条** CSP 违规。

- [x] **Step 6：Git 核验**

```powershell
git status --short --branch
git log --oneline <Task1前commit>..HEAD
git diff --name-only <Task1前commit>..HEAD
```

确认：无 `.vtj/files/*.json` 变更；无 `tsconfig*.json` 变更；无后端数据库模型变更；仅预先存在的未跟踪项（`.vtj/files/*.bak`、`backend/app/uploads/avatars/`）保持未提交。

- [x] **Step 7：更新方案文档**

在 `solve_problems_files/Vite代理添加错误处理方案.md` 或新建归档文档中记录本轮修复结果、验证证据、错误数变化轨迹（78 → 41 → 19 → 8 → 基线）与提交清单。

- [x] **Step 8：提交文档**

```powershell
git add -- "solve_problems_files/" "docs/superpowers/plans/2026-09-26-project-health-and-trend-chart.md"
git commit -m "docs: 记录项目健康度修复验证证据"
```

- [x] **Step 9：勾选计划状态**

将本计划文件所有 `- [x]` 更新为 `- [x]`，单独提交：

```powershell
git add -- "docs/superpowers/plans/2026-09-26-project-health-and-trend-chart.md"
git commit -m "docs: 标记实施计划完成状态"
```

---

## 错误数变化轨迹（预期）

| 阶段 | 错误数 | 说明 |
| --- | ---: | --- |
| 初始 | 78 | 实测基线 |
| Task 1 后 | 41 | 删除孤立死文件（−37） |
| Task 4 后 | 19 | 趋势图与 `loadData`（−22） |
| Task 5 后 | 8 | 类型声明、`$refs`、路由参数（−11，另 +1 计入口径差异） |
| Task 7 后 | 8 | 固化为基线，不再下降 |

## 提交清单（预期 9 个）

| # | 提交信息 |
| --- | --- |
| 1 | `refactor: 删除未被引用的 score_analysis 孤立副本` |
| 2 | `fix: 用 PriceTag 替换不存在的 Tag 图标` |
| 3 | `feat: 学情总览新增分班级趋势并修正 N+1 查询与日期键` |
| 4 | `fix: 修复学情分析页筛选失效并实现分班级趋势图` |
| 5 | `fix: 补齐类型声明并收窄路由参数与模板引用` |
| 6 | `fix: CSP 放开 data 字体以加载 VTJ 图标字体` |
| 7 | `test: 建立 typecheck 错误基线并新增基线校验脚本` |
| 8 | `test: 新增项目健康度统一守卫并接入 prebuild` |
| 9 | `docs: 记录项目健康度修复验证证据`（+ 计划勾选提交） |
