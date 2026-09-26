# 项目健康度修复与教师端趋势图设计文档

> 版本：v1.0（已获用户逐项确认）
> 工作目录：`D:\砺安题库\砺安题库`（主仓库，不使用 worktree）
> 分支：`fix/vite-mobile-connection`
> 技术栈：Vue 3 + Vite 6 + VTJ 低代码平台 + FastAPI
> 端口：Vite/HMR **9527**（`strictPort: true`）、FastAPI **8000**
> 包管理：npm（不迁移 pnpm）
> 日期：2026-09-26

---

## 一、背景与问题现状

在已完成 Vite 启动失败、`/ws` 代理缺失、端口漂移与 CSP `connect-src` 修复（提交 `011ace3` ~ `df86052`）之后，仍遗留三个历史问题。经逐项实测与全量扫描，根因已完全定位。

### 1.1 `vite build` 端到端失败

`vite build` 在转换 3909 个模块后中断：

```text
.vtj/vue/tablet_forum.vue?vue&type=script&lang.ts (13:2): "Tag" is not exported by
"node_modules/@vtj/icons/dist/index.mjs", imported by ".vtj/vue/tablet_forum.vue..."
11:   Plus,
12:   Grid,
13:   Tag,
14:   TrendCharts,
15:   View,
```

实测结论：

- `Tag` 在 `@vtj/icons@0.16.35`（当前锁定版本）与 `@vtj/icons@0.20.6`（npm latest）中**均不存在**；运行时导出集共 819 个名称，无 `Tag`。因此**不是版本锁定引入的回归**。
- 对全部 44 个导入 `@vtj/icons` 的 `.vue` 文件做全量比对，**有且仅有 1 处缺失导出**：`.vtj/vue/tablet_forum.vue` 的 `Tag`。其余 43 个文件完全正常。
- `Tag` 用于「资料分享」分类的 `XIcon` 字形：模板第 58 行 `:icon="Tag"`、导入第 243 行、`setup()` return 第 464 行、导航配置第 270 行 `{ key: 'resource', name: '资料分享', icon: Tag, count: 19 }`。
- 语义最接近且真实存在的导出：`PriceTag`、`CollectionTag`、`IconTag`。
- 路由 `/tablet/forum` 在 `.vtj/router.js` 中注册，**对外可达**。
- **关键**：`.vtj/files/tablet_forum.json`（VTJ DSL，设计器唯一事实来源）中**不含任何 `Tag` 字符串**。该导入由提交 `f7f9123` 手工补入，故直接修改 `.vue` 安全——设计器重新生成时不会复现 `Tag`。

### 1.2 `vue-tsc --noEmit` 报 78 项错误

| 文件 | 错误数 | 性质 |
| --- | ---: | --- |
| `src/vtj/vue/score_analysis.vue` | 37 | 孤立死文件 |
| `.vtj/vue/teacher_analytics.vue` | 22 | **真实功能缺陷** |
| `.vtj/vue/teacher_papers.vue` | 9 | 1 项真实 + 8 项 codegen 噪音 |
| `src/views/mobile_answer.vue` | 4 | 真实 |
| `src/router/index.ts` | 2 | 真实（缺声明） |
| `.vtj/vue/teacher_profile.vue` | 1 | 真实 |
| `src/views/mobile_news.vue` | 1 | 真实 |
| `.vtj/vue/TeacherNavHeader.vue` | 1 | 真实 |
| `src/views/help.vue` | 1 | 真实 |
| **合计** | **78** | |

#### (A) 37 项 —— 孤立死文件 `src/vtj/vue/score_analysis.vue`

- 含 `useProvider({ id: 'score_analysis', version: '1778918611112' })`，属 VTJ 生成物。
- **不被** `src/router/index.ts` 引用、**不被** `.vtj/router.js` 引用、**不被任何文件 import**（grep 全量核实）。
- `src/vtj/` 目录下**仅有此一个文件**。
- 是 `.vtj/vue/score_analysis.vue` 的重复副本（后者同样未被路由）。
- 第 208 行 `import NavBar from './navbar.vue'` 断裂——该文件不存在于 `src/vtj/vue/`，仅存在于 `.vtj/vue/navbar.vue`。
- 错误构成：18 项 TS2339（图标未注册到实例）、10 项 `never` 上的 TS2339、1 项 TS2307 缺 `./navbar.vue`、1 项 TS2322 EChartsOption，另有 TS7006/TS18046/TS7005。

**结论：直接删除，运行时零影响。**

#### (B) 22 项 —— `.vtj/vue/teacher_analytics.vue` 的真实功能缺陷

该文件无 `useProvider`，属手写覆盖页，经 `src/router/index.ts:163` 对外可达，可安全直接编辑。

1. **`loadData` 未从 `setup()` return**：`loadData` 定义于第 190 行，但 `setup()` 的 return 块在第 287–292 行，**不含 `loadData`**。模板第 8、12 行使用 `@change="loadData"` → 运行时该处理器为 `undefined`，**班级/科目筛选下拉框完全失效**。
2. **趋势图 8 个绑定完全不存在**：`trendSvgWidth`、`trendSvgHeight`、`trendYTicks`、`trendY`、`trendPoints`、`trendX`、`trendLines`、`trendColors` 在模板中被引用，但脚本中**根本没有定义** → 趋势图 SVG 彻底损坏（`viewBox` 变为 `"0 0 undefined undefined"`）。
3. **`trendData` 从未被填充**：第 167 行声明为 `ref<any[]>([])`，而 `loadData()` 只拉取 `overview`、`knowledge-mastery`、`question-usage` 三个接口，**没有任何趋势数据来源**。

趋势图模板契约（`.vtj/vue/teacher_analytics.vue` 第 51–71 行）：

```html
<svg :viewBox="'0 0 ' + trendSvgWidth + ' ' + trendSvgHeight">
  <line v-for="tick in trendYTicks" :x1="40" :y1="trendY(tick)" :x2="trendSvgWidth - 10" :y2="trendY(tick)" />
  <text v-for="tick in trendYTicks" :y="trendY(tick) + 4">{{ tick }}</text>
  <text v-for="(pt, i) in trendPoints" :x="trendX(i)" :y="trendSvgHeight - 4">{{ pt.label }}</text>
  <g v-for="(line, li) in trendLines">
    <polyline :points="line.points" :stroke="trendColors[li % trendColors.length]" />
    <circle v-for="(pt, pi) in line.dots" :cx="pt.x" :cy="pt.y" :fill="trendColors[li % trendColors.length]" />
  </g>
  <g v-for="(line, li) in trendLines">
    <rect :x="60 + li * 120" :y="6" :fill="trendColors[li % trendColors.length]" />
    <text :x="76 + li * 120" y="16">{{ line.name }}</text>
  </g>
</svg>
```

#### (C) 9 项 —— `.vtj/vue/teacher_papers.vue`（设计器生成，DSL 同步，`src/router/index.ts:145` 可达）

- 1 项 TS7016：`@/utils/questionRender` 缺声明（真实，由全局 `.d.ts` 修复）。
- 8 项 TS2365/TS2345，位于模板第 113、116、117、137、228、230、231、327 行，例如 `{{ idx + 1 }}` 被报为 `Operator '+' cannot be applied to types 'string | number' and 'number'`。根因是 VTJ codegen 产出无类型 `reactive({...})`，导致模板类型推断退化。**运行时正常**。

#### (D) 9 项真实错误

- 3 项 TS7016 `@/utils/questionRender`（`src/utils/questionRender.js` 为无类型 JS；被 `teacher_analytics:153`、`teacher_papers:364`、`mobile_answer:58` 引用）
- 2 项 TS7016 `src/router/index.ts:51,57`，指向 `@/views/exercise.vue`、`@/views/solution.vue`（两文件均存在）
- 2 项 TS18046：`'$refs.avatarInput' is of type 'unknown'`（`.vtj/vue/teacher_profile.vue:9`）、`'$refs.profileAvatarInput' is of type 'unknown'`（`.vtj/vue/TeacherNavHeader.vue:74`）
- 6 项 TS2365/TS2345/TS7015 路由参数 `string | number` 算术：`src/views/help.vue:14`、`src/views/mobile_answer.vue:32,33,35`、`src/views/mobile_news.vue:33`

修复全部真实缺陷后，**残余约 8 项错误**，全部集中在 `teacher_papers.vue` 的模板类型推断噪音。

### 1.3 `font-src` CSP 拦截图标字体

`index.html` 第 12 行当前 CSP：

```text
default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; connect-src 'self' ws: wss:; img-src 'self' data:; style-src 'self' 'unsafe-inline';
```

未设置 `font-src`，回退到 `default-src 'self'`。`node_modules/@vtj/icons/dist/style.css` 内嵌 4 个 base64 字体（`data:font/woff2`、`data:font/woff`、`data:font/ttf`、`data:application/x-font-woff2`）→ 全部被拦截，浏览器控制台出现 4 条 CSP 违规。页面实际渲染正常（图标可显示），属告警级问题。

---

## 二、目标与非目标

### 2.1 目标

1. `npm run build` 端到端通过（当前在 3909 模块后中断）。
2. typecheck 达到「零新增错误」状态，且对新增错误具备自动拦截能力。门禁命令为 `npm run typecheck:guarded`；裸 `npm run typecheck` 保留为全量诊断视图（会如实报出已知噪音并返回退出码 2）。
3. 修复 `teacher_analytics` 页面的**真实功能缺陷**：筛选下拉框可用、趋势图正确渲染。
4. 趋势图展示**真实的分班级多序列**数据（与模板既有设计一致）。
5. 消除全部 CSP 告警。
6. 建立长期守卫机制，防止同类问题复发且不会被设计器覆盖冲掉。
7. 顺带消除两处既有后端稳定性隐患（N+1 查询、日期键碰撞）。

### 2.2 非目标（明确不做）

- 不修改任何 `.vtj/files/*.json` DSL 文件（避免触发设计器重生成）。
- 不修复 `teacher_papers.vue` 的 8 项模板推断噪音（进错误基线）。
- 不迁移到 pnpm。
- 不改动题库、认证逻辑、数据库结构。
- 不使用 `// @ts-nocheck` 整文件屏蔽。
- 不引入进程级异常兜底。
- 不新增子代理执行（用户已明确要求全部由主代理直接执行）。

---

## 三、方案设计

### 3.1 后端：分班级趋势序列

#### 3.1.1 数据模型事实（已核实）

- 端点：`backend/app/api/v1/teacher.py:1684`，装饰器 `@router.get("/analytics/overview")`，函数 `get_analytics_overview`，参数 `class_id: Optional[int] = Query(None)`、`days: int = Query(30, ge=1, le=365)`，依赖 `get_current_teacher` + `get_db`。
- 教师班级通过 `db.query(Banji.class_name).filter(Banji.teacher_id == current_user.user_id)` 取得。
- **学生与班级的唯一关联是 `SysUser.class_name` 字符串**，`SysUser` 上没有 `class_id` 外键。
- 考试记录：`ExamRecord`，过滤条件 `user_id IN user_ids`、`is_completed == 1`、`start_time >= since`。
- 现有聚合（第 1726–1736 行）：以 `r.start_time.strftime("%m-%d")` 为键构造 `date_scores`，`trend_dates = sorted(...)`，`trend_scores = [各日期均值]`，以 `score_trend={"dates": ..., "scores": ...}` 返回。
- Schema：`backend/app/schemas/teacher.py:329` `class AnalyticsOverview(BaseModel)`，字段 `total_students: int = 0`、`total_exams: int = 0`、`avg_score: float = 0`、`pass_rate: float = 0`、`score_trend: dict = {}`、`subject_comparison: List[dict] = []`。

#### 3.1.2 Schema 变更

`backend/app/schemas/teacher.py` 新增：

```python
class ClassTrendPoint(BaseModel):
    date: str          # 输出格式 "09-01"
    avg_score: float


class ClassTrendSeries(BaseModel):
    class_id: Optional[int] = None
    class_name: str
    points: List[ClassTrendPoint] = []
```

`AnalyticsOverview` 新增字段：

```python
class_trend: List[ClassTrendSeries] = []
```

#### 3.1.3 端点变更

在 `get_analytics_overview` 中：

1. **保留 `score_trend` 原样输出**，确保向后兼容，不破坏既有消费方。
2. **新增分班级聚合**：以 `class_names` 分组查出各班 `user_id` 集合 → 各自聚合 `ExamRecord` → 输出 `class_trend`。分组键使用 `SysUser.class_name` 字符串；`class_id` 通过 `Banji` 反查填充。
3. **修复 N+1 查询**：现第 1742 行在遍历 `records` 的循环体内逐条执行 `db.query(ExamPaper).filter(ExamPaper.paper_id == r.paper_id).first()`。改为一次性批量查询全部相关 `ExamPaper`，构建 `paper_id -> subject_id` 映射后内存查表。分班级聚合会使记录遍历次数成倍增长，此项必须同步修复。
4. **修复日期键碰撞**：现以 `%m-%d` 为字典键，当 `days > 30` 时跨月/跨年的同月同日数据会被静默合并。改为内部使用完整可排序日期键（`%Y-%m-%d`）进行分组与排序，仅在输出时格式化为 `%m-%d`。

#### 3.1.4 兼容性约束

- `score_trend` 字段保持不变，新增字段均为可选默认值，旧前端不会因字段缺失而报错。
- 响应体积增长与班级数成正比；`days` 上限 365、`class_id` 可选，均有界。
- 班级数无显式上限，`trendColors` 采用 `li % trendColors.length` 取色（模板既有逻辑），班级多于调色板长度时颜色循环复用。

### 3.2 前端：真实缺陷修复

| 文件 | 改动 | 消除错误 |
| --- | --- | ---: |
| `src/vtj/vue/score_analysis.vue` | **删除**（孤立、重复、含断裂 `./navbar.vue`） | −37 |
| `.vtj/vue/teacher_analytics.vue` | `loadData` 加入 `setup()` return；实现 8 个趋势图计算属性；`trendData` 来自 `overview.class_trend` | −22 |
| `.vtj/vue/tablet_forum.vue` | `Tag` → `PriceTag`（同步导入、模板 `:icon`、导航配置、`setup()` return） | 解除 build 阻断 |
| `src/utils/questionRender.d.ts` | **新增**无类型 JS 模块的声明 | −3 |
| `src/router/index.ts` | 为 `@/views/exercise.vue`、`solution.vue` 补声明 | −2 |
| `.vtj/vue/teacher_profile.vue` | `$refs.avatarInput` 改为显式类型模板引用 | −1 |
| `.vtj/vue/TeacherNavHeader.vue` | `$refs.profileAvatarInput` 改为显式类型模板引用 | −1 |
| `src/views/help.vue`、`mobile_answer.vue`、`mobile_news.vue` | 路由参数 `string \| number` 收窄为 `number` | −6 |
| `index.html` | CSP 补 `font-src 'self' data:;` 与 `worker-src 'self' blob:;` | — |

#### 3.2.1 趋势图计算属性契约

必须实现并从 `setup()` return（`computed`）：

| 绑定 | 类型 | 语义 |
| --- | --- | --- |
| `trendSvgWidth` | `number` | SVG `viewBox` 宽度 |
| `trendSvgHeight` | `number` | SVG `viewBox` 高度 |
| `trendYTicks` | `number[]` | Y 轴刻度值（兼作刻度文本） |
| `trendY` | `(tick: number) => number` | 刻度值 → 像素 Y 坐标 |
| `trendPoints` | `{ label: string }[]` | X 轴标签，源自各班级序列日期并集 |
| `trendX` | `(i: number) => number` | 索引 → 像素 X 坐标 |
| `trendLines` | `{ name: string; points: string; dots: { x: number; y: number }[] }[]` | 每班级一条折线 |
| `trendColors` | `string[]` | 调色板，模板以 `li % length` 取色 |

实现要点：

- Y 轴值域取所有班级序列分数的全局最小/最大值，并向上取整到 10 的倍数作为上界，下界取 0。
- `trendYTicks` 由值域线性等分生成，保证与 `trendY` 单调映射一致。
- `trendPoints.label` 取日期字符串（`%m-%d`）。
- 某班级在某日期无数据时，**跳过该点**而非补 0，避免折线虚假下跌。
- `trendData` 由 `overview.class_trend` 填充；同时保留从 `score_trend` 读取的兜底路径，当 `class_trend` 缺失时降级为单序列「平均分」，保证旧数据/空数据下图表不崩。

#### 3.2.2 CSP 变更

`index.html` 第 12 行调整为：

```html
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; connect-src 'self' ws: wss:; img-src 'self' data:; font-src 'self' data:; style-src 'self' 'unsafe-inline'; worker-src 'self' blob:;" />
```

`font-src 'self' data:` 解锁 VTJ 内嵌图标字体；`worker-src 'self' blob:` 为图表/Worker 场景预留，避免后续同类拦截。

### 3.3 统一守卫脚本 `scripts/verify-project-health.mjs`

接入 `package.json` 的 `prebuild`，四类检查分级如下。

#### 检查 1：图标导入合法性（**阻断**）

- 遍历 `.vtj/vue/**` 与 `src/**` 下全部 `.vue`。
- 用 `[^}]*` 精确匹配 `import { ... } from '@vtj/icons'`（**不可使用贪婪匹配**，否则会跨越多个 import 语句产生误报——此坑已实测踩过）。
- 与 `@vtj/icons` 运行时导出集比对。
- 存在未知图标时**立即失败**，并输出近义候选建议（按编辑距离/子串匹配候选，如 `Tag` → `PriceTag`、`CollectionTag`、`IconTag`）。

#### 检查 2：typecheck 错误基线（**阻断**）

- 执行 `vue-tsc --noEmit -p tsconfig.json`，解析 `file(line,col): error TSxxxx: message`。
- 与 `.typecheck-baseline.json` 比对，**仅在出现新错误或新文件受影响时失败**，并打印新增/消失的错误 diff。
- 归一化规则：忽略列号与消息文本中的具体数值，仅以 `文件 + 错误码 + 行号` 为键，避免无关改动引发误报。
- 基线为空且当前有错误时，按「首次建立基线」处理并提示复核。

#### 检查 3：孤立文件扫描（**警告**）

- 扫描 `src/**`、`.vtj/vue/**` 下 `.vue`，若既未被 `src/router/index.ts` 也未被 `.vtj/router.js` 引用则警告。
- **不得硬失败**：VTJ 的 `Provider` 可注册动态 `/page/:id` 路由，静态引用扫描必然存在漏报。

#### 检查 4：VTJ 版本漂移（**警告**）

- 对含 `useProvider({ ... version: 'N' })` 的 `.vtj/vue/*.vue`，取 `N` 与同名 `.vtj/files/<name>.json` 的 `__VERSION__` 比对。
- 不一致即警告，含义为「该文件已被手工修改，下次在设计器保存会被覆盖」。

---

## 四、关键设计决策与被否决的替代方案

### 决策 1：全修而非仅修构建阻断

- **选择**：删除死文件 + 真实实现趋势图 + 修复全部真实类型错误。
- **否决**：仅修 `Tag` 与 CSP、保留 78 项错误。理由：`teacher_analytics` 的筛选框失效与趋势图损坏是真实功能缺陷，页面虽不报错但对用户不可用；`vue-tsc` 已具备诊断价值，长期放任会掩盖新缺陷。

### 决策 2：错误基线机制（而非配置隔离）——**关键决策**

- **原设想**：用 `vueCompilerOptions.strictTemplates: false` 隔离模板推断噪音。
- **实测结论**：该方案**完全无效**。以临时探针 tsconfig 实测，78 项错误在开关前后**数量与内容完全一致**。
- **失效原因**：这些错误来自 Volar 的模板属性访问检查（`__VLS_ctx.x` 路径解析），该检查独立于 `strictTemplates` 开关运行；`strictTemplates` 仅影响「未知属性是否报错」这一层，管不到运算符与实参类型检查。
- **最终选择**：将 8 项不可消除的 codegen 噪音写入 `.typecheck-baseline.json`，由守卫脚本做「零新增」判定。
- **否决的其他方案**：
  - 关闭 `strict`——无法消除 TS2339/TS2365/TS2345/TS2307，且会削弱脚本层类型安全。
  - `@ts-nocheck` 整文件屏蔽——会连带屏蔽该文件未来的真实错误。
  - 直接改 `teacher_papers.vue` 加类型标注——下次设计器保存即被覆盖，`typecheck` 会重新变红，维护成本隐性存在。
  - 将页面转为 VTJ raw 手写页——会失去设计器可视化编辑能力，且需在设计器中人工操作。

### 决策 3：统一守卫脚本（覆盖四类）

- **选择**：单个 `scripts/verify-project-health.mjs` 覆盖图标导入、typecheck 基线、孤立文件、版本漂移，接入 `prebuild`。
- **理由**：四类问题同属「长期稳定性」，分散实现会导致 `prebuild` 链条膨胀、难以统一维护与统一回滚。
- **否决**：只做图标校验 + typecheck 基线（覆盖面不足，孤立文件与版本漂移正是本轮暴露的隐患模式）；容错插件把未知图标降级为占位符（会把问题静默化，长期更危险）。

### 决策 4：扩展后端实现真实分班级趋势

- **选择**：扩展 `/analytics/overview` 返回 `class_trend`，前端渲染多班级折线。
- **否决**：前端按现有 `score_trend` 渲染单序列「平均分」线——不修改 `.vue` 之外的文件即可完成，但与模板既有设计「每条折线（每个班级一条）」不符，功能不完整；不实现趋势图只留空状态提示——回避了真实需求。
- **附带收益**：分班级聚合会放大后端遍历成本，顺带修复 N+1 查询与日期键碰撞，对长期运行有实质收益。

---

## 五、`.typecheck-baseline.json` 结构

```json
{
  "generatedAt": "2026-09-26T00:00:00.000Z",
  "command": "vue-tsc --noEmit -p tsconfig.json",
  "totalErrors": 8,
  "entries": [
    {
      "file": ".vtj/vue/teacher_papers.vue",
      "line": 113,
      "code": "TS2365"
    },
    {
      "file": ".vtj/vue/teacher_papers.vue",
      "line": 116,
      "code": "TS2345"
    }
  ]
}
```

设计要点：

- 键为 `文件 + 错误码 + 行号`，**不含列号与消息正文**，避免无关改动造成基线抖动。
- 同一文件同一行可能有多条错误，允许多条 entry。
- `totalErrors` 仅供人读，判定以 `entries` 集合为准。
- 基线文件**纳入版本控制**，使基线变化本身可被 review 看见。

---

## 六、验证策略

| # | 命令 / 手段 | 通过标准 |
| --- | --- | --- |
| 1 | `npm run verify:health` | 四类检查全绿（检查 3、4 允许警告），退出码 0 |
| 2 | `npm run typecheck:guarded` | 零新增错误（相对基线），退出码 0 |
| 2b | `npm run typecheck` | **原始全量视图**：仍会报出 8 项基线噪音并以退出码 2 结束，属预期行为，不作为门禁 |
| 3 | `npm run build` | 端到端完成（内部串联 `prebuild` 守卫 + 基线校验 + `vite build`） |
| 4 | `npm run test:vite-resilience` | 仍输出 `PASS`，代理/端口工作无回归 |
| 5 | Playwright 移动视口 390×844 访问 `http://localhost:9527/` | 教师分析页筛选可用、趋势图渲染多班级折线、`/tablet/forum` 正常加载、控制台零 CSP 违规 |

**关于标准 2 的重要说明**：`npm run typecheck` 是未经门禁包装的原始 `vue-tsc`，它会如实报告
`.vtj/vue/teacher_papers.vue` 的 8 项 codegen 模板推断噪音并返回退出码 2。**这不代表回归**。
真正用于 CI 与构建的判定命令是 `npm run typecheck:guarded`（等价于 `node scripts/verify-typecheck-baseline.mjs`），
它在出现**新增**错误时才失败。`npm run build:prod` 已从裸 `vue-tsc` 改为调用 `typecheck:guarded`，
因此 `npm run build` 不会被这 8 项已知噪音阻断。

补充：后端改动需验证 `/api/teacher/analytics/overview` 在 `class_id` 有值与无值两种情形下均返回结构合法的 `class_trend`，且 `score_trend` 保持原样。

---

## 七、风险与回滚

| 改动 | 风险 | 回滚方式 |
| --- | --- | --- |
| 删除 `src/vtj/vue/score_analysis.vue` | 极低。无任何引用，git 可完整恢复 | `git checkout <commit> -- src/vtj/vue/score_analysis.vue` |
| 后端 `class_trend` | 低。新增可选字段，旧消费方不受影响 | 回滚 `teacher.py` 与 `schemas/teacher.py` 两个提交 |
| N+1 与日期键修正 | 中。改变了 `subject_comparison` 与 `score_trend` 的内部计算路径 | 与 `class_trend` 同一提交回滚；需回归验证 `subject_comparison` 与 `score_trend` |
| `teacher_analytics` 趋势计算属性 | 中。SVG 坐标计算错误会导致图表显示异常 | 独立提交，可单独回滚；回滚后趋势图回到「不渲染」而非「报错」 |
| `loadData` 加入 return | 低。恢复既有绑定 | 同上提交回滚 |
| `Tag` → `PriceTag` | 极低。仅字形替换 | 独立提交回滚 |
| 类型声明 `.d.ts` | 低。纯声明文件 | 独立提交回滚 |
| `$refs` 类型改造 | 中。需保持运行时行为一致 | 独立提交回滚 |
| 路由参数收窄 | 低。纯类型层 | 独立提交回滚 |
| CSP 增量指令 | 低。仅放宽 `font-src`/`worker-src` | 独立提交回滚 |
| 守卫脚本 + 基线 | 低。独立于上述全部修复 | 删除脚本、移除 `prebuild` 钩子、删除基线文件即可 |

回滚总则：守卫脚本与错误基线**独立于**所有修复，任一修复回滚不影响守卫继续运行；所有修复按文件分组提交，禁止跨组混合提交。

---

## 八、实施顺序建议

依赖关系：前端趋势计算属性依赖后端 `class_trend` 字段，故后端必须先行。

| 阶段 | 内容 | 依赖 |
| --- | --- | --- |
| 1 | 删除 `src/vtj/vue/score_analysis.vue` | 无。立即消除 37 项错误，风险最低，先行建立信心 |
| 2 | 后端：`ClassTrendPoint`/`ClassTrendSeries` schema + `class_trend` 输出 + N+1 修正 + 日期键修正 | 无 |
| 3 | 前端：`teacher_analytics` 趋势图完整实现（含 `loadData` return） | **依赖阶段 2** |
| 4 | `tablet_forum.vue` 的 `Tag` → `PriceTag`（解除 build 阻断） | 无，可与 1–3 并行 |
| 5 | 类型声明与 `$refs`、路由参数收窄（14 项 TS7016/TS18046/TS2365） | 依赖阶段 1（否则基线数字不准） |
| 6 | CSP 补 `font-src` / `worker-src` | 无 |
| 7 | 建立 `.typecheck-baseline.json`（此时应仅剩 `teacher_papers.vue` 8 项） | **依赖阶段 1、5** |
| 8 | 实现 `scripts/verify-project-health.mjs` 四类检查，接入 `prebuild` | **依赖阶段 7** |
| 9 | 全量验证：五项验证标准 + 文档更新 | 依赖全部 |

阶段 1 与阶段 2 无相互依赖，可并行推进以缩短总时长。
