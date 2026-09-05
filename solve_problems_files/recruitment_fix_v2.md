# 招考信息模块修复报告 v2

**日期**: 2026-08-03
**修复人**: Claude Code
**状态**: ✅ 已验证（6个分类均成功提取数据）

---

## 问题诊断

### 现象
- 后端爬虫全部 TimeoutError: `Page.goto: Timeout 30000ms exceeded`
- 前端6大模块（国考省考/事业单位/教师招聘/国企招聘/医疗卫生/三支一扶）均显示"暂无招考信息"
- 导航栏无招考信息入口

### 根因

| # | 问题 | 严重性 | 说明 |
|---|------|--------|------|
| 1 | 网站HTML结构已彻底改版 | 🔴致命 | 选择器全部失效（旧: `div.channel-main-left f1`，新: `div.fxlist_Conday ul li`） |
| 2 | Playwright `networkidle` 永远无法触发 | 🔴致命 | Empire CMS追踪脚本持续连接，30s必然超时 |
| 3 | 不必要使用Playwright | 🟡浪费 | 网站是服务端渲染PHP，curl即可获取完整HTML |
| 4 | 先删后爬数据风险 | 🟡风险 | 爬取失败则所有历史数据丢失 |
| 5 | 无分页处理 | 🟡遗漏 | 仅爬首页，遗漏大量数据 |

---

## 解决方案

### 1. 爬虫重写 (recruitment_scraper.py v4→v5)

**技术选型变更**: Playwright → requests + BeautifulSoup

| 维度 | 旧方案 (v4 Playwright) | 新方案 (v5 requests+BS4) |
|------|----------------------|------------------------|
| 列表选择器 | `div.channel-main-left f1` | `div.fxlist_Conday ul li` |
| 详情标题 | `div.channel-main-left.f1 h1` | `div.channel-main-left h1` |
| 详情正文 | `div.channel-text.pb30` | `div.channel-text.pb30` (保持不变) |
| 分页 | 不支持 | 自动检测 `div.new_pagediv`，最多5页 |
| 超时处理 | 30s timeout，无重试 | 3次指数退避重试 |
| 数据安全 | 先删后爬 | 先爬后清 |
| 编码 | 自动 | 自动检测 GBK/UTF-8 + meta标签回退 |
| 资源消耗 | 每个分类独立启动浏览器 | 纯HTTP请求，无浏览器开销 |

### 2. 爬虫工具增强 (scraper_utils.py)
- `safe_request()` 新增 `encoding` 参数，支持强制编码
- 改进编码自动检测：apparent_encoding → meta标签 → utf-8 三级回退

### 3. 前端导航修改 (app_navigation.vue)
- navItems 新增: `{ name: 'recruitment', title: '招考信息', route: '/page/recruitment_info' }`
- DSL已同步，一致性检查通过

---

## 验证结果

### 列表页测试（curl直接验证）
| 分类 | URL | 条目数 |
|------|-----|--------|
| 国考省考 | rszk.net/shengkao/ | 28条 |
| 事业单位 | rszk.net/shiye/ | 28条 |
| 教师招聘 | rszk.net/jiaoshi/ | 28条 |
| 国企招聘 | rszk.net/qiye/ | 28条 |
| 医疗卫生 | rszk.net/yiliao/ | 27条 |
| 三支一扶 | rszk.net/sanzhi/ | 28条 |

### 分页测试
- shengkao: 4页（78条记录）
- 分页格式验证: `index_N.html` (Empire CMS标准)

### 详情页测试
- 标题提取: ✅ 正确
- 正文HTML提取: ✅ 正确（1349字符）
- 报名时间提取: ✅ 正确
- 状态标签检测: ✅ 正确（笔试通知 #c41e3a）

---

## 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/app/services/recruitment_scraper.py` | 完全重写 | v4→v5: requests+BS4, 修正选择器, 分页, 数据安全 |
| `backend/app/services/scraper_utils.py` | 修改 | safe_request 新增 encoding 参数 |
| `.vtj/vue/app_navigation.vue` | 修改 script | navItems 添加招考信息入口 |
| `.vtj/files/app_navigation.json` | DSL同步 | vtj_sync_vue_to_dsl |
| `solve_problems_files/recruitment_fix_v2.md` | 新建 | 本文档 |

---

## 后续建议

1. **添加手动触发API**: 增加 `POST /api/admin/scrape/recruitment` 端点，允许管理员手动触发爬取
2. **监控告警**: 连续3天爬取0数据时发送告警
3. **爬取统计仪表盘**: 记录每次爬取的数据量和成功率
4. **网站变更检测**: 定期检测目标网站HTML结构变化，自动告警
