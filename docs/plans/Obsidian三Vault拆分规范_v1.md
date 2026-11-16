# Obsidian 三 Vault 拆分规范 v1

> 日期：2026-11-14  
> 状态：待审批；尚未执行真实迁移  
> 替代：`Obsidian内容库目录规范_v1.md`（单 Vault 三模块方案，已废弃）

## 1. 原则

每日金句、每日新闻、招考信息必须是三个**完全独立**的 Obsidian Vault，各自有独立根目录、独立 `.obsidian` 配置和独立索引。

禁止：

- 三个模块写入同一个根目录；
- 金句文件写到新闻 Vault；
- 通过一个 `OBSIDIAN_VAULT_PATH` 复用同一个库。

## 2. 三个独立 Vault

```text
D:\砺安题库\li_an-question_bank\
├── 每日金句知识库\              # VAULT_PATH_QUOTE
│   ├── .obsidian\
│   ├── 00-Dashboard\
│   │   └── Dashboard.md
│   ├── 00-收件箱\
│   ├── 01-待审核\
│   ├── 02-已发布\
│   ├── 03-已拒绝\
│   ├── 04-归档\
│   └── 99-系统\
│
├── backend\content_hub_vault\   # VAULT_PATH_NEWS
│   ├── .obsidian\
│   ├── 00-Dashboard\
│   │   └── Dashboard.md
│   ├── 00-收件箱\
│   ├── 01-待审核\
│   ├── 02-已发布\
│   ├── 03-已拒绝\
│   ├── 04-归档\
│   └── 99-系统\
│
└── 招考信息知识库\              # VAULT_PATH_JOB
    ├── .obsidian\
    ├── 00-Dashboard\
    │   └── Dashboard.md
    ├── 00-收件箱\
    ├── 01-待审核\
    ├── 02-已发布\
    ├── 03-已拒绝\
    ├── 04-归档\
    └── 99-系统\
```

## 3. 环境变量

```env
VAULT_PATH_QUOTE="D:/砺安题库/li_an-question_bank/每日金句知识库"
VAULT_PATH_NEWS="D:/砺安题库/li_an-question_bank/backend/content_hub_vault"
VAULT_PATH_JOB="D:/砺安题库/li_an-question_bank/招考信息知识库"
```

旧的 `OBSIDIAN_VAULT_PATH` 不再使用。

## 4. 代码路由

| 模块 | 配置 | 导出目标 |
|---|---|---|
| 金句 | `settings.VAULT_PATH_QUOTE` | 每日金句知识库 |
| 新闻 | `settings.VAULT_PATH_NEWS` | backend/content_hub_vault |
| 招考 | `settings.VAULT_PATH_JOB` | 招考信息知识库 |

所有导出函数只接收各自 Vault 路径，不接收“通用内容库路径”。

## 5. 迁移脚本

脚本：

```text
backend/scripts/split_obsidian_vaults.py
```

Dry-run：

```powershell
cd D:\砺安题库\li_an-question_bank\backend
.\.venv\Scripts\python.exe -m scripts.split_obsidian_vaults --dry-run
```

真实移动：

```powershell
.\.venv\Scripts\python.exe -m scripts.split_obsidian_vaults --apply
```

迁移规则：

```text
type: quote   → VAULT_PATH_QUOTE
type: news    → VAULT_PATH_NEWS
type: job / recruitment / 招考 → VAULT_PATH_JOB
```

生命周期目录：

```text
00-收件箱
01-待审核
02-已发布
03-已拒绝
04-归档
```

脚本默认 dry-run；不覆盖同名文件；迁移日志写入新闻 Vault 的 `99-系统/迁移日志/`。

## 6. 本地 Obsidian 打开方式

1. 打开 Obsidian。
2. 点击左下角「打开其他库」。
3. 选择「打开文件夹作为库」。
4. 分别选择：
   - `D:\砺安题库\li_an-question_bank\每日金句知识库`
   - `D:\砺安题库\li_an-question_bank\backend\content_hub_vault`
   - `D:\砺安题库\li_an-question_bank\招考信息知识库`
5. 三个库会分别出现在 Obsidian 的库切换器中，互不混写。
