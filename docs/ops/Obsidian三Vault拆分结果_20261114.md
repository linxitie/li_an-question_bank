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
