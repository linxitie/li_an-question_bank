# Obsidian 内容库目录规范 v1

> 日期：2026-11-14  
> 状态：待确认，尚未执行迁移  
> 范围：每日金句、每日新闻、招考信息

## 1. 设计目标

当前 Vault 里同时存在：

- 原始素材；
- AI 待审核卡片；
- 人工审核清单；
- 已发布成品；
- 已拒绝内容；
- 历史归档。

问题是目录按“时间/文件来源”堆叠，业务模块和生命周期混在一起。

新结构采用：

```text
业务模块（金句 / 新闻 / 招考）
    ×
生命周期（收件箱 / 待审核 / 已发布 / 已拒绝 / 归档）
```

每个模块、每个状态目录都有 `index.md`，根目录有 `Dashboard.md`。

## 2. 目录树

```text
content_hub_vault/
├── 00-Dashboard/
│   ├── Dashboard.md
│   ├── 金句总览.md
│   ├── 新闻总览.md
│   └── 招考总览.md
│
├── 01-每日金句/
│   ├── index.md
│   ├── 00-收件箱/
│   │   └── index.md
│   ├── 01-待审核/
│   │   └── index.md
│   ├── 02-已发布/
│   │   └── index.md
│   ├── 03-已拒绝/
│   │   └── index.md
│   └── 04-归档/
│       └── index.md
│
├── 02-每日新闻/
│   ├── index.md
│   ├── 00-收件箱/
│   │   └── index.md
│   ├── 01-待审核/
│   │   └── index.md
│   ├── 02-已发布/
│   │   └── index.md
│   ├── 03-已拒绝/
│   │   └── index.md
│   └── 04-归档/
│       └── index.md
│
├── 03-招考信息/
│   ├── index.md
│   ├── 00-收件箱/
│   │   └── index.md
│   ├── 01-待审核/
│   │   └── index.md
│   ├── 02-已发布/
│   │   └── index.md
│   ├── 03-已拒绝/
│   │   └── index.md
│   └── 04-归档/
│       └── index.md
│
├── 04-主题地图/
├── 99-系统/
│   ├── index.md
│   └── 迁移日志/
│
├── .obsidian/
└── uploads/
```

## 3. 状态映射

| frontmatter `status` | 新目录 |
|---|---|
| `inbox` / `draft` / 空 | `00-收件箱` |
| `pending` / `review` / `待审核` | `01-待审核` |
| `approved` / `published` / `已发布` | `02-已发布` |
| `rejected` / `已拒绝` | `03-已拒绝` |
| `archived` / `归档` | `04-归档` |

## 4. 类型映射

| frontmatter `type` | 新模块目录 |
|---|---|
| `quote` / `quotes` / `金句` | `01-每日金句` |
| `news` / `新闻` | `02-每日新闻` |
| `recruitment` / `招考` / `招聘` | `03-招考信息` |

没有 `type` 或无法识别的文件不移动，脚本会在报告中列出，交人工判断。

## 5. 迁移脚本

文件：

```text
backend/scripts/obsidian_organizer.py
```

默认只 dry-run：

```powershell
cd D:\砺安题库\li_an-question_bank\backend
python -m scripts.obsidian_organizer --vault content_hub_vault --dry-run
```

确认后真实移动：

```powershell
python -m scripts.obsidian_organizer --vault content_hub_vault --apply
```

脚本行为：

1. 扫描 `*.md`；
2. 跳过 `index.md`、`Dashboard.md`、`.obsidian`、`uploads`；
3. 读取 YAML frontmatter；
4. 按 `type + status` 计算目标目录；
5. 目标同名文件存在时不覆盖，自动加序号；
6. dry-run 只打印移动计划；
7. apply 才真正移动，并写迁移日志。

## 6. 未来导出路径

待脚本确认后，后端导出逻辑统一改成：

```text
金句待审：
01-每日金句/01-待审核/

金句已发布：
01-每日金句/02-已发布/

新闻待审：
02-每日新闻/01-待审核/

新闻已发布：
02-每日新闻/02-已发布/

新闻已拒绝：
02-每日新闻/03-已拒绝/

招考相关：
03-招考信息/<状态>/
```

不再写：

```text
00-收件箱/金句
00-收件箱/新闻
07-归档/新闻审核
```

## 7. 安全约束

- 第一次只运行 `--dry-run`；
- 不覆盖已有文件；
- 不移动 `index.md` / `Dashboard.md`；
- 不移动 `.obsidian`、`uploads`；
- 迁移日志写入 `99-系统/迁移日志/`；
- 建议迁移前对整个 Vault 做一次文件系统备份。
