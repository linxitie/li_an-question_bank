---
name: li-an-workflow
description: Use for every coding task in the 砺安题库 repository. Enforces AGENTS.md red lines, plan-first approval, feature branch topology, VTJ raw-page safety, role/device checks, test evidence, and document archiving.
---

# 砺安题库工作流

本技能是项目 `AGENTS.md` 的可执行摘要。开工前必须同时读取：

1. 仓库根 `AGENTS.md`（强制规则与 R1-R12 红线）
2. `docs/plans/` 与 `docs/superpowers/{specs,plans}/` 中与本任务相关的方案
3. 当前分支说明与 `git status --short`
4. 涉及页面的路由、角色与设备归属

发生冲突时按以下优先级执行：

```text
用户本轮明确指令
  > AGENTS.md 红线与安全规则
  > 本技能
  > 通用最佳实践
```

## 1. 方案先行，审批后执行

非平凡改动（多文件、跨端、改接口、改路由、改 VTJ 页面、工具链安装）必须先方案后实现。

方案至少包含：

- 现状证据：文件路径 + 行号 + 实测命令
- 根因或目标差距
- 改动范围与不做什么
- 分支拓扑与提交拆分
- 验证方式与验收标准
- 风险、回滚与未决问题

方案展示给用户的同时必须落盘归档，不能只在对话里展示。用户明确批准前，不开始实施。

## 2. 分支拓扑

默认结构：

```text
main
├── feature/<模块>
│   └── feature/<模块>-<子任务>
└── feature/dev-tooling
    └── feature/dev-tooling-ai
```

规则：

- 不在 `main` 上直接开发；从对应父分支切子分支。
- Git 不允许 `feature/forum` 与 `feature/forum/xxx` 同时作为 ref。子分支使用连字符：`feature/forum-comment-avatar`。
- 一个子分支只承载一个可独立回滚的目标。
- 子分支完成后先合并回父分支；是否合并 `main` 由用户决定。
- 提交前逐项检查 `git diff` 与 `git status`，只 stage 本任务文件。
- 不把 `package-lock.json`、VTJ 运行时文件、既有未跟踪文档等无关改动混入提交。
- 不删除、不重置历史分支。

## 3. 文档归档

| 类型 | 权威位置 | 归档副本 |
|---|---|---|
| 设计/方案 | `docs/superpowers/specs/` | `solve_problems_files/<主题>_v<版本>.md` |
| 实施计划 | `docs/superpowers/plans/` | `solve_problems_files/<主题>_v<版本>_实施计划.md` |
| 运维手册 | `docs/ops/` | `solve_problems_files/<主题>_v<版本>_运维手册.md` |
| 排查/验收报告 | `docs/superpowers/specs/` | `solve_problems_files/<主题>_报告.md` |

归档后：

1. 更新对应 `README.md` 索引
2. 提交信息写明归档主题与版本
3. 向用户报告存档路径与摘要

`solve_problems_files/` 迁移完成后，改为写入 `docs/{design,plans,ops,archive}/`。

## 4. 不可违反的红线

- **R1** `.vtj/` 禁止移动、改名、删除。路由有 92 处按 page id 硬绑定。
- **R2** `raw: true` 页面禁止 `vtj_sync_vue_to_dsl`。
- **R3** `.vtj/` 页面的 `<template>` 禁止 AI 直接改；只有用户明确授权时才可改，且必须先 `dryRun: true` 并备份。AI 默认只改 `<script>`。
- **R4** `src/utils/device.ts` 与 `resolveDevicePath()` 原样保留。
- **R5** `mobile_*`、`tablet_*` 文件名前缀不重命名。
- **R6** `题库/` 禁止删除或移动。
- **R7** `backend/app/static/` 禁止删除。
- **R8** `backend/data/*.bak*` 禁止清理。
- **R9** `backend/data/audit/` 与 `待推断题目清单_*.csv` 不是垃圾。
- **R10** 数据库备份禁用 `shutil.copy2`，必须用 `sqlite3.backup()`。
- **R11** API 路径 `/api/v1/...` 冻结；变更必须比对 `backend/data/refactor_baseline/api_surface.json`。
- **R12** 不为平板复制手机页；优先复用 `mobile_*.vue` 并用 `meta.platform` 区分。

## 5. VTJ 页面工作法

1. 先确认页面是否 `raw: true`，并查路由与 page id。
2. 读取文件用 `read` 或 `vtj_read_vue_file`。
3. 只改 `<script>` 时优先用 `vtj_write_vue_script`，先 `dryRun: true`。
4. 需要改 `<template>` 时，必须已有用户明确授权；先备份，再 `dryRun`，确认 diff 后写入。
5. 永不执行 `vtj_sync_vue_to_dsl`，除非用户明确要求且页面不是 `raw: true`。
6. 修改后运行对应端页面，检查 PC/平板/手机的角色与设备映射。
7. 不把 VTJ 设计器运行时文件当作业务改动提交。

## 6. 实现检查表

### 后端

- 响应字段是否向后兼容，老客户端是否仍可解析
- 鉴权、角色、所有权判断是否覆盖
- 空值、超长、非法格式、XSS、敏感词是否处理
- 错误码与 HTTP 状态是否与既有约定一致
- 是否触碰 `/api/v1` 冻结路径

### 前端

- 角色（student/teacher/admin）× 设备（pc/tablet/mobile）是否正确
- PC、平板、手机是否复用同一数据契约
- 空状态、加载态、404、网络失败是否有回退
- 图片是否有 `alt` 与加载失败回退
- 响应式布局与可点击区域是否可用
- 是否引入重复页面而不是复用现有页面

### 数据与安全

- 不把真实密钥写入源码、文档、提交信息
- `.env` 类文件保持忽略
- 不记录用户隐私数据到日志
- 数据库变更必须有备份与回滚说明

## 7. 测试与验收

按改动范围选择最小但可信的证据：

- 后端：相关 `pytest` 文件；涉及契约时再跑更宽范围
- 前端：相关 `vitest` 文件；涉及类型时跑 `npm run typecheck` 并过滤本任务文件
- UI：用 Playwright 验证真实页面、真实接口、真实头像/图片加载
- 构建：涉及路由、依赖或发布配置时跑对应 build
- 手工验收：记录 URL、角色、设备、操作步骤、预期与实际

验收报告必须写明：

- 执行了哪些命令，结果如何
- 哪些没有验证，为什么
- 是否存在既有失败、环境限制或未覆盖风险

不要把“测试通过”写成没有证据的结论。全量测试有既有失败时，明确区分“本任务相关通过”与“仓库既有失败”。

## 8. 委派规则

- 代码侦察、外部文档、架构评审、边界明确的实现可以委派。
- 子代理不可用时如实说明，不假装已委派。
- 不把需要设计判断的 UI 工作交给纯执行代理。
- 多个写代理不得同时改同一文件；先划分所有权。
- 委派结果必须由主代理复核、整合并验证。

## 9. 交付格式

完成后向用户简要报告：

```text
分支：
提交：
改动文件：
验证：
未验证/风险：
下一步：
```

文档任务额外报告：权威路径 + 归档路径 + README 索引是否更新。
