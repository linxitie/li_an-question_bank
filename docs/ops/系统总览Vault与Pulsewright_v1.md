# 系统总览 Vault 与 Pulsewright

> 日期：2026-11-15  
> 状态：已建立

## 位置

```text
D:\砺安题库\li_an-question_bank\系统总览知识库
```

## 目录

```text
系统总览知识库/
├── .obsidian/
│   ├── community-plugins.json      # 已启用 pulsewright
│   └── plugins/pulsewright/        # main.js / manifest.json / styles.css
├── 00-Dashboard/
│   └── Dashboard.md
├── 01-每日金句/
│   ├── index.md
│   ├── 00-收件箱/
│   ├── 01-待审核/
│   ├── 02-已发布/
│   ├── 03-已拒绝/
│   └── 04-归档/
├── 02-每日新闻/
│   └── ... 同样的生命周期目录
├── 03-招考信息/
│   └── ... 同样的生命周期目录
└── 99-系统/
```

## 数据来源

总览库是三个独立 Vault 的**只读镜像**，源库仍是唯一真源。

同步脚本：

```text
backend/scripts/sync_overview_vault.py
```

执行：

```powershell
cd D:\砺安题库\li_an-question_bank\backend
.\.venv\Scripts\python.exe -m scripts.sync_overview_vault --apply
```

当前镜像数量：

```text
金句：6475 篇（含导航）
新闻：87 篇（含导航）
招考：6 篇（含导航）
```

## Pulsewright

- 版本：1.0.3
- 插件 ID：`pulsewright`
- 已写入 `.obsidian/community-plugins.json`
- 打开 Obsidian 后，从左侧 Ribbon 图标或命令面板打开

## 注意

Pulsewright 只扫描当前 Vault，所以总览库必须保留镜像文件；源库更新后需要重新运行同步脚本。

三个源 Vault 仍保持独立，不互相写入。
