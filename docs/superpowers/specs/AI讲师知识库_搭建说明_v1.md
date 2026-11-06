# AI 讲师知识库（Obsidian）搭建说明

> 版本：v1　日期：2026-11-04　状态：已搭建，待评审，未接入业务代码
> 位置：`D:\\Obsidian仓库\\AI讲师知识库`（与另外 3 个库共享同一 Obsidian vault）
> 媒体源：`E:\\砺安题库相关资料\\名师讲解视频`（只读引用，未复制）

## 1. 一页纸结论

- 已完成：15 个目录骨架 + 76 集资源台账 + 7 个系列总览 + 4 张 Canvas + Dataview 实时表 + 库内铁律与使用指南。
- 未做（等决策）：删 `桐哥讲公专.zip`（14.8 GB）、删 4 个残片、媒体目录 junction 挂载、插件额外安装。
- 边界：本库是**教研生产面**；学生端运行时读题库数据库，不读本库 Markdown。
- 校验：73 个 Canvas 文件节点全部可解析，168 条双链 **0 断链**。

## 2. 目录结构

| 目录 | 职责 |
|---|---|
| `wiki/视听资源/` | 一集一笔记，四级：科目 → 讲师-系列 → 集 |
| `wiki/考点/` `法条/` `错因/` `讲义/` | 考点卡、法条卡、错因卡、逐页讲稿（视频脚本上游） |
| `raw/` + `raw/_inbox/` | 只读原始语料与收件箱 |
| `config/` | rules / templates / schema / tag-taxonomy |
| `atlas/` | Canvas 图谱 + Dataview 总览表 |
| `output/` | changesets / reports / manifests |
| `scripts/` | 可重跑的生成与校验脚本位置 |

## 3. 资源盘点（ffprobe 实测）

| 系列 | 讲师 | 科目 | 集数 | 时长(h) | 体积(GB) |
|---|---|---|---|---|---|
| 2022版八大主题讲座 | 白宁 | 公专 | 8 | 34.9 | 2.04 |
| 2025公专全程课 | 白宁 | 公专 | 2 | 10.4 | 0.61 |
| 2025八大讲座 | 白宁 | 公专 | 1 | 4.1 | 0.24 |
| 2027版八大讲座 | 白宁 | 公专 | 5 | 21.1 | 3.96 |
| 2027基础课 | 桐哥 | 公专 | 51 | 77.0 | 15.1 |
| 资料分析系统课 | 刘文超 | 行测 | 8 | 16.6 | 1.15 |
| 桐哥讲公专.zip | 桐哥 | 公专 | 1（归档） | — | 14.8 |

合计 **76 集 / 112.6 小时 / 37.1 GB**（含归档包 38.9 GB）；80 个原始文件，4 个重复/残片。

## 4. frontmatter 契约

- 必填：`id` / `type` / `title` / `status`；契约文件 `config/schema/frontmatter.schema.json`。
- `type` 枚举：`video_resource` `series` `exam_point` `law_article` `error_pattern` `lesson`。
- `status` 状态机：`available` → `transcribed` → `mapped` → `archived`；旁支 `incomplete` `duplicate`。
- 单集必含：`series_id` `episode` `teacher` `bvid` `duration_sec` `file_path`（E 盘绝对路径）。

## 5. 可视化

- `atlas/资源全景.canvas`：三科目分组 + 6 个系列入口 + 缺口清单。
- `atlas/白宁公专-2022八大主题.canvas`、`atlas/行测-资料分析.canvas`、`atlas/桐哥公专-目录.canvas`。
- `atlas/资源总览表.md`：3 组 Dataview 查询（按系列汇总 / 全部集 / 待处理），随笔记自动更新。
- 原生关系图谱：靠双链自动生成，无需额外配置。

## 6. 搭建与写入方式

- 通过 dsh-obsidian MCP 读写（obsidian_list / read / append 已实测）。
- 通过 Obsidian 已安装插件 **Local REST API v5.1.0** 写入（`PUT /vault/<path>` 返回 204）并 `POST /open/<path>` 在 GUI 中打开 Canvas。
- 已启用插件（共享 vault）：Dataview、Templater、Local REST API、Aurora Dashboard、Charts View、Calendar、Periodic Notes。
- 生成逻辑为一次性脚本（run_code + node:fs），未落盘为 `scripts/generate_vault.py`；后续需要重跑时应补写为正式脚本。

## 7. 校验结果

- Canvas 文件节点 73/73 可解析；Wikilink 168 条，断链 0。
- 76 集笔记标题已清洗（去 B 站后缀 `【2027新课】`、去重复集号前缀），正文 `#` 标题与 frontmatter `title` 一致。
- 4 个残片（3 个 `.part` + 1 个 `.temp.mp4`）与 1 个纯音轨已在系列总览「重复与残片」记账，未删除。

## 8. 待用户决策

1. 是否删除 `E:\\砺安题库相关资料\\名师讲解视频\\桐哥讲公专.zip`（14.8 GB，内容已全部解压）。
2. 是否删除 3 个 `.part` 与 1 个 `.temp.mp4`（约 0.9 GB）。
3. 是否把媒体目录 junction 到 `AI讲师知识库/wiki/视听资源/_media`（可在 Obsidian 内直接播放，但会让 vault 索引 37 GB 媒体，且有误删风险）。
4. 是否额外安装插件（如 Media Extended）以支持库内播放。

## 9. 后续（本模块下一阶段）

- 首批 20 张考点卡（公专执法程序 10 + 行测判断推理 10），与题库系统 `knowledge_point` 对齐。
- 桐哥 2027 基础课逐集 ASR 转写 → 时间轴切分 → 考点映射。
- 法条卡：治安管理处罚法、人民警察法、刑事诉讼法高频条文。
- 编译链路打通：本库 → `output/changesets/*.json` → 系统审核 → GraphStore / 文档库。
