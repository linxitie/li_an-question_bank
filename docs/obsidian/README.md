# docs/obsidian —— 知识图谱自生长知识库（生成物目录）

## 这是什么

学生端「知识图谱」的数据投影成 Obsidian 笔记库，由
`backend/app/services/kg_vault_export.py`（CLI 壳：`scripts/kg_vault/export_kg_vault.py`）
从运行中的 SQLite（`backend/.env` 的 SQLITE_PATH，只读）生成。

默认输出：`docs/obsidian/知识图谱自生长/`（已在 .gitignore 中忽略，属生成物）。

## 目录与命名

```
用户/<学号>/                    ← 一个学生一个独立 Obsidian vault
  ├── .obsidian/app.json        ← 该用户的 vault 配置
  ├── README.md / 弱项看板.md
  ├── 节点/<考点>.md             ← 关联双链 + 最近行为
  ├── 科目/<科目>.md
  ├── 历史/YYYY-MM-DD.md         ← 每日快照
  └── 图谱.canvas
知识图谱索引.md                  ← 全部学生清单（纯路径，不属于任何 vault）
```

- 目录名用**学号**（`user_no`），不用昵称：学号唯一、稳定，昵称可改/可空/可能重名；
- 没有任何图谱节点的新学生也会建目录（弱项看板显示「还没有学习数据」空态）。

## 什么时候会自动生成

1. **注册即建库**：`POST /api/auth/register` 成功后调用导出器，立即创建 `用户/<学号>/`；
2. **每日 07:10**：后端 APScheduler 任务「知识图谱 Obsidian 每日刷新 07:10」重写全部学生；
3. 手动刷新：

```powershell
cd D:\AAA项目文件\砺安题库\li_an-question_bank
python scripts/kg_vault/export_kg_vault.py                # 全部学生
python scripts/kg_vault/export_kg_vault.py --user 202516001  # 单个学号
python scripts/kg_vault/export_kg_vault.py --check        # 只统计，不写文件
```

> 注意：注册钩子与每日任务都需要**重启后端**才生效（当前进程若是旧代码，需要重启一次）。

## 多用户隔离模型

- 每个 `用户/<学号>/` 都是独立 Obsidian vault，双链命名空间互不影响；
- 在 Obsidian 里「打开文件夹作为仓库」时，选自己的 `用户/<学号>/`，不要打开外层目录；
- 原因：Obsidian 的双链（`[[考点名]]`）在同一 vault 内全局解析，多用户同名考点会串数据。

## 每日自动刷新（可选，双保险）

调度器已内置 07:10 任务；如果后端不常开，可以再挂系统计划任务：

```powershell
schtasks /Create /TN "砺安-知识图谱每日刷新" /TR "powershell -NoProfile -ExecutionPolicy Bypass -File \"D:\AAA项目文件\砺安题库\li_an-question_bank\scripts\kg_vault\每日刷新.ps1\"" /SC DAILY /ST 07:00 /F
```

日志：`%TEMP%\kg_vault_last_run.log`；删除：`schtasks /Delete /TN "砺安-知识图谱每日刷新" /F`。
