# VTJ 页面模板备份 — RT-4/RT-5 富文本集成

- 备份时间：2026-10-25
- 分支：`feat/fix-bug`
- 基线提交：`247d9fe feat(rich-text): add shared viewer and editor`
- 用途：RT-4（answer_page 题干/选项改用 `renderQuestionContent`）+ RT-5（teacher/admin 题组材料改用 `RichTextEditor`）改动前的原样快照，用于回滚
- 备份内容为 **改动前** 的 HEAD 版本，已用 `git hash-object` 与 HEAD blob 逐一对齐（全部 MATCH）

## 文件清单

| 备份文件 | 源路径 | 说明 |
|---|---|---|
| `answer_page.vue` | `.vtj/vue/answer_page.vue` | 答题页（题干/选项 v-html 方案） |
| `teacher_questions.vue` | `.vtj/vue/teacher_questions.vue` | 教师端题目管理（题组材料编辑） |
| `admin_questions.vue` | `.vtj/vue/admin_questions.vue` | 管理端题目管理（题组材料编辑） |
| `answer_page.json` | `.vtj/files/answer_page.json` | 对应 DSL，仅备份不改动 |
| `teacher_questions.json` | `.vtj/files/teacher_questions.json` | 对应 DSL，仅备份不改动 |
| `admin_questions.json` | `.vtj/files/admin_questions.json` | 对应 DSL，仅备份不改动 |

## 回滚方法

```powershell
Copy-Item backend\data\audit\vtj_template_backup_20261025_rt\answer_page.vue .vtj\vue\answer_page.vue -Force
Copy-Item backend\data\audit\vtj_template_backup_20261025_rt\teacher_questions.vue .vtj\vue\teacher_questions.vue -Force
Copy-Item backend\data\audit\vtj_template_backup_20261025_rt\admin_questions.vue .vtj\vue\admin_questions.vue -Force
```

> 注意：本次改动**未**修改 `.vtj/files/*.json`，也未调用 `vtj_sync_vue_to_dsl`。
