# 砺安题库 · Obsidian 自生长知识库（Vault）

> 模块 7 的知识库工作区：用 Obsidian 打开本目录，即可用双链、图谱、Markdown 自由维护备考知识。
> 内容通过系统「知识库」接口提交 → 审批 → 入库，Agent 对话时可引用，人工维护成本降到最低。

## 目录结构

| 分类目录 | 用途 | 对应系统分类 key |
| :--- | :--- | :--- |
| `law/` | 法条库：治安管理处罚法 / 人民警察法 / 刑法等核心条款与适用要点 | `law` |
| `recruit/` | 报考信息库：联考公告要点 / 岗位类型 / 报考条件 / 时间线 | `recruit` |
| `exam_point/` | 考点库：行测 / 申论 / 公专高频考点与解题方法 | `exam_point` |
| `wrong/` | 错题经验库：典型错题、踩坑记录与复盘笔记 | `wrong` |

## 使用流程（自生长闭环）

1. **打开 Vault**：Obsidian → Open folder as vault → 选择本目录 `docs/knowledge-vault/`。
2. **写笔记**：在对应分类下新建 `.md` 文件，首行 `# 标题`，正文用 Markdown（可用 `[[双链]]` 关联其他笔记，Obsidian 会画出图谱）。
3. **提交入库**：通过系统「知识库」接口把笔记标题 + 分类 + 内容提交，生成 `pending` 待审节点。
4. **审批通过**：管理员/本人审批通过后节点进入 `approved`，Agent 对话与检索即可引用。
5. **持续生长**：公告、新法条、新考点随时用同一流程增量补充，无需人工整理成结构化数据。

## 内容规范

- 法条类：只写要点与适用情景，具体条文以**现行有效法条**为准，注明"以现行有效法条为准"。
- 报考类：以**当年官方招录公告**为准，注明查看渠道（公安部/各省人事考试网）。
- 考点类：给结论 + 方法 + 一个例题/口诀，避免长篇复制教材。
- 错题类：按模板写「题干摘要 → 错误答案 → 正确思路 → 易错点」。

## 与系统对接的接口

- `GET  /api/knowledge/categories` 分类
- `GET  /api/knowledge/nodes?category=&status=` 节点列表（含内容）
- `POST /api/knowledge/nodes` 提交节点（pending）
- `POST /api/knowledge/nodes/{id}/approve` 审批入库
- `POST /api/knowledge/nodes/{id}/reject` 驳回
- `GET  /api/knowledge/graph` 知识图谱（节点 + 关系）
