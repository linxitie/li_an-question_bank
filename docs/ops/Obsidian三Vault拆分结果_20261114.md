# Obsidian 三 Vault 拆分执行结果

> 日期：2026-11-14  
> 状态：已执行

## 迁移结果

```text
计划移动：4367
实际移动：4367
跳过：59
未知文件：59
```

迁移日志：

```text
backend/content_hub_vault/99-系统/迁移日志/拆分迁移_20261114_224537.json
```

## 当前三库边界

```text
每日金句知识库
  quote 类型：6469
  news 类型：0

backend/content_hub_vault
  news 类型：81
  quote 类型：0

招考信息知识库
  当前为空，已建立
```

## 迁移后检查

```text
拆分脚本再次 dry-run：planned=0
重复执行不会继续移动
```

新闻归档文件已在 `content_hub_vault/04-归档`，不会回流到 `01-待审核`。

## 环境变量

```env
VAULT_PATH_QUOTE="D:/砺安题库/li_an-question_bank/每日金句知识库"
VAULT_PATH_NEWS="D:/砺安题库/li_an-question_bank/backend/content_hub_vault"
VAULT_PATH_JOB="D:/砺安题库/li_an-question_bank/招考信息知识库"
```

## 注意事项

- `.env` 不纳入 Git；
- `招考信息知识库` 已建立基础目录；
- 建议在 Obsidian 中分别打开三个根目录作为三个库；
- 旧的单 Vault 目录规范已废弃，以《Obsidian三Vault拆分规范_v1.md》为准。


## 新闻 Vault 二次清理（2026-11-15）

清理脚本：

```text
backend/scripts/clean_news_vault.py
```

已将新闻 Vault 中残留的金句主题地图、旧审核看板、旧金句清单和招考索引移出：

```text
移动：60
新闻类型：81
新闻库剩余非新闻 Markdown：
- 00-系统总览看板.md（看板）
- 02-新闻/index.md（新闻索引）
- 00-收件箱/新闻/时效性看板.md（新闻审核看板）
```

现在 `backend/content_hub_vault` 顶层只保留：

```text
00-收件箱
02-新闻
04-归档
99-系统
.obsidian
uploads
```
