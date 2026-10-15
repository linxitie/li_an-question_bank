# VTJ MCP Server — 开发工作流

本文档描述使用 VTJ MCP Server 进行低代码开发的典型工作流。

---

## 工作流 1：给现有页面添加业务逻辑

**场景**：用户需要为题库页的快速练习按钮添加真实数据加载逻辑。

```
1. 用户: "给题库页的快速练习按钮加上真实数据加载"

2. Claude 读取页面当前代码:
   → vtj_read_vue_file(id="mjvdqdu1", section="script")

3. Claude 查看 DSL 状态定义:
   → vtj_read_dsl_file(id="mjvdqdu1", section="state")

4. Claude 修改业务逻辑:
   → vtj_write_vue_script(id="mjvdqdu1", mode="methods", content="...")

5. Claude 同步到 DSL:
   → vtj_sync_vue_to_dsl(id="mjvdqdu1")

6. Claude 提醒用户: "已完成。请清理 Vite 缓存并刷新页面。"
```

---

## 工作流 2：新增页面

**场景**：用户需要创建一个成绩排行榜页面。

```
1. 用户: "创建一个成绩排行榜页面"

2. Claude 创建脚手架:
   → vtj_create_page_scaffold(
       id="score_ranking",
       name="ScoreRanking",
       title="成绩排行榜",
       addRoute=true,
       routePath="/score-ranking"
     )

3. Claude 查看可用组件:
   → vtj_get_material_catalog(category="data")

4. 用户在 VTJ 设计器中拖拽 UI

5. Claude 补充业务逻辑:
   → vtj_write_vue_script(id="score_ranking", content="...")
   → vtj_sync_vue_to_dsl(id="score_ranking")
```

---

## 工作流 3：了解项目全貌

**场景**：用户需要了解项目的整体结构。

```
1. 用户: "这个项目有哪些页面和组件？"

2. Claude 获取项目信息:
   → vtj_get_project_info()

3. Claude 查看路由:
   → vtj_get_routing_info()

4. Claude 查看可用组件库:
   → vtj_get_material_catalog()
```

---

## 工作流 4：检查页面一致性

**场景**：用户修改了 Vue 文件但不确定 DSL 是否同步。

```
1. 用户: "检查一下题库页的 Vue 和 DSL 是否一致"

2. Claude 检查一致性:
   → vtj_check_consistency(id="mjvdqdu1")

3. 如果不一致:
   → vtj_sync_vue_to_dsl(id="mjvdqdu1")
```

---

## 工作流 5：查看页面结构

**场景**：用户需要了解页面的组件树结构。

```
1. 用户: "给我看看题库页的结构"

2. Claude 获取结构:
   → vtj_get_page_structure(id="mjvdqdu1", depth=3)
```

---

## 工作流 6：添加静态路由

**场景**：用户需要为现有页面添加新的路由路径。

```
1. 用户: "给排行榜页面添加 /rank 路由"

2. Claude 添加路由:
   → vtj_add_route(path="/rank", name="ScoreRanking")
```

---

## 工作流 7：修改页面模板

**场景**：用户需要修改页面的模板结构。

```
1. 用户: "修改题库页的标题"

2. Claude 读取当前模板:
   → vtj_read_vue_file(id="mjvdqdu1", section="template")

3. Claude 修改模板:
   → vtj_write_vue_template(id="mjvdqdu1", content="...")
```

---

## 重要原则

1. **Claude Code 只修改 `<script>` 逻辑**：UI 结构变更通过 VTJ 设计器
2. **修改后必须同步**：`.vue` 修改 → `vtj_sync_vue_to_dsl` → 更新 `.vtj/files/*.json`
3. **raw: true 页面受保护**：VTJ 设计器不会覆盖这些页面的 Vue 文件
4. **自动备份**：所有写操作都会创建 `.bak` 备份文件
5. **dryRun 预览**：所有写操作支持 `dryRun` 参数预览变更
