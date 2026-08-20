# Obsidian 金句集成修复 - 规格说明

> 版本: v1.0 | 分支: obsidian-quote-fix | 日期: 2026-08-20

---

## 1. 功能名称

Obsidian 金句知识库完整集成修复

## 2. 问题陈述

### 2.1 核心问题

"每日金句"模块无法正常显示 Obsidian 知识库中的金句内容，原因是：

1. **路径不匹配**：代码硬编码 `01-金句库\2026`，实际目录是 `01-金句素材库\{01-政治类...08-古典名言类}`
2. **素材库为空**：所有分类目录只有 `.gitkeep`，无任何金句 `.md` 文件
3. **脚本路径过期**：14 个自动化脚本引用旧目录名，全部失效
4. **无金句生成机制**：没有定时任务或脚本负责生成金句

### 2.2 影响范围

- 首页"每日金句"始终显示数据库回退金句，而非 Obsidian 金句
- 收藏功能无法正常工作
- 自生长机制完全失效

---

## 3. 解决方案

### 3.1 修复范围

| 模块 | 内容 | 文件 |
|------|------|------|
| Obsidian 知识库 | 修正 14 个脚本路径 | `04-系统配置/scripts/*.ps1` |
| 数据迁移 | 迁移 279 条归档金句 | `99-归档/.../01-政治类/*.md` → `01-金句素材库/01-政治类/` |
| 后端 | 修正 Obsidian 路径 + 递归扫描 | `backend/app/api/v1/quotes.py` |
| 前端 | 验证金句展示和收藏功能 | `.vtj/vue/quote_banner.vue` |

### 3.2 路径修正对照表

| 组件 | 旧路径 | 新路径 |
|------|--------|--------|
| quotes.py | `01-金句库/2026` | `01-金句素材库` |
| daily-push.ps1 | `02-每日金句` | `05-推送记录` |
| daily-push.ps1 | `05-系统配置/prompts/03-daily-push.md` | `04-系统配置/prompts/03-daily-push.md` |
| verify-setup.ps1 | `01-金句库`, `02-主题分类`, `04-模板`, `05-系统配置`, `06-推送记录` | 全部更新 |
| opencode.json | `05-系统配置/prompts/` | `04-系统配置/prompts/` |

### 3.3 数据迁移策略

**源**：`99-归档/99-Archive/01-金句素材库-归档/01-政治类/{党建引领,治理体系,制度建设}/*.md`
**目标**：`01-金句素材库/01-政治类/{党建引领,治理体系,制度建设}/*.md`

**格式转换**：旧格式 frontmatter → 新格式

```yaml
# 旧格式
---
id: 20260815-153000-0001
created: 2026-08-15
source: 权威官方文件
quality_rating: 5
status: 已审核
tags: [金句, 申论, 制度建设]
category: 01-政治类/制度建设
---

# 新格式
---
type: 金句
date: 2026-08-15
source: 权威官方文件
quote: "金句正文"
applicable_topics: ["制度建设"]
keywords: []
sentiment: 积极
complexity: 中等
status: 已审核
---
```

### 3.4 后端路径修正

**文件**：`backend/app/api/v1/quotes.py`

**变更**：
1. 修改 `OBSIDIAN_QUOTE_DIR` 为 `01-金句素材库`
2. 新增递归扫描子目录逻辑
3. 支持 `01-政治类/`、`02-法治类/` 等 8 个分类目录

**验证**：`GET /api/quotes/quote/daily` 返回 `source_type: "obsidian"`

---

## 4. 文件变更清单

### 4.1 Obsidian 知识库文件

| 文件 | 变更 |
|------|------|
| `04-系统配置/scripts/daily-push.ps1` | 修正 `02-每日金句` → `05-推送记录`，`05-系统配置` → `04-系统配置` |
| `04-系统配置/scripts/verify-setup.ps1` | 修正所有旧路径引用 |
| `04-系统配置/scripts/fetch-rss.ps1` | 修正 `05-系统配置` → `04-系统配置` |
| `04-系统配置/scripts/clean-inbox.ps1` | 修正 `05-系统配置` → `04-系统配置` |
| `04-系统配置/scripts/quality-review.ps1` | 修正 `05-系统配置` → `04-系统配置` |
| `04-系统配置/scripts/quality-control.ps1` | 修正 `05-系统配置` → `04-系统配置` |
| `04-系统配置/scripts/smart-match.ps1` | 修正 `05-系统配置` → `04-系统配置` |
| `04-系统配置/scripts/batch-generate.ps1` | 修正 `05-系统配置` → `04-系统配置` |
| `04-系统配置/scripts/seed-generate.ps1` | 修正 `05-系统配置` → `04-系统配置` |
| `04-系统配置/scripts/create-jinju-entries.ps1` | 修正 `05-系统配置` → `04-系统配置` |
| `04-系统配置/scripts/cleanup-corrupted.ps1` | 修正 `05-系统配置` → `04-系统配置` |
| `04-系统配置/scripts/register-tasks.py` | 修正 `05-系统配置` → `04-系统配置` |
| `04-系统配置/scripts/test-quotes.py` | 修正 `05-系统配置` → `04-系统配置` |
| `opencode.json` | 修正 `05-系统配置/prompts/` → `04-系统配置/prompts/` |

### 4.2 数据迁移文件

| 操作 | 源 | 目标 |
|------|-----|------|
| 迁移 | `99-归档/99-Archive/01-金句素材库-归档/01-政治类/党建引领/*.md` | `01-金句素材库/01-政治类/党建引领/` |
| 迁移 | `99-归档/99-Archive/01-金句素材库-归档/01-政治类/治理体系/*.md` | `01-金句素材库/01-政治类/治理体系/` |
| 迁移 | `99-归档/99-Archive/01-金句素材库-归档/01-政治类/制度建设/*.md` | `01-金句素材库/01-政治类/制度建设/` |

### 4.3 后端文件

| 文件 | 变更 |
|------|------|
| `backend/app/api/v1/quotes.py` | 修改 `OBSIDIAN_QUOTE_DIR` + 新增递归扫描 |

---

## 5. 验证标准

### 5.1 后端验证

```bash
# 1. 每日金句返回 Obsidian 金句
curl http://localhost:8000/api/quotes/quote/daily
# 预期: source_type: "obsidian", content 非空

# 2. 收藏功能正常
curl -X POST http://localhost:8000/api/quotes/obsidian/{source}/favorite \
  -H "Authorization: Bearer {token}"
# 预期: favorited: true

# 3. 收藏列表正常
curl http://localhost:8000/api/collection/news-favorites?type=quote \
  -H "Authorization: Bearer {token}"
# 预期: 包含 Obsidian 金句收藏
```

### 5.2 前端验证

1. 首页"每日金句"显示 Obsidian 金句内容
2. 点击收藏按钮，收藏状态更新
3. 收藏页显示已收藏的 Obsidian 金句
4. "换一句"按钮正常工作

### 5.3 Obsidian 知识库验证

```powershell
# 运行全量校验
.\04-系统配置\scripts\verify-setup.ps1
# 预期: 全部通过
```

---

## 6. 风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 数据迁移格式转换失败 | 金句无法正确解析 | 编写迁移脚本，逐条验证 |
| 脚本路径修正遗漏 | 部分脚本仍失效 | 使用 grep 全量搜索旧路径 |
| 后端递归扫描性能 | 每次请求扫描所有子目录 | 添加缓存机制 |

---

## 7. 回滚计划

1. 恢复 `quotes.py` 中的 `OBSIDIAN_QUOTE_DIR` 为原值
2. 恢复 14 个脚本的旧路径引用
3. 删除迁移的金句文件（保留归档区原始数据）

---

> 本文档基于实际代码和 Obsidian 知识库结构编写，确保可落地、可验证。
