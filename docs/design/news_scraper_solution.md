# 每日新闻爬虫修复方案

## 问题诊断

### 问题1: Playwright模块未安装
**错误信息:**
```
ModuleNotFoundError: No module named 'playwright'
```
**根因:** `requirements.txt` 中已声明 `playwright>=1.48.0` 和 `playwright-stealth>=1.0.6`，但实际 Python 环境中未安装这两个包，且未下载浏览器二进制文件。

### 问题2: 人民公安报页面爬取失败
**根因:** 人民公安报 (epaper.cpd.com.cn) 使用 JavaScript 重定向链加载内容，普通 HTTP 请求无法获取实际页面内容。必须使用浏览器自动化工具（Playwright）执行 JS 后才能获取 DOM。

### 问题3: 前端新闻展示不完善
**现状:** 新闻仅嵌入在首页 QuoteBanner 组件中，展示5条，无独立页面、无分页、无分类筛选。

---

## 解决方案

### 第一步: 安装Playwright环境
```bash
# 1. 安装Python包
pip install playwright>=1.48.0 playwright-stealth>=1.0.6

# 2. 安装浏览器二进制（Chromium + Firefox + Edge）
playwright install chromium
playwright install firefox

# 3. 验证
python -c "from playwright.sync_api import sync_playwright; print('OK')"
```

### 第二步: 增强爬虫脚本 (backend/app/services/news_scraper.py)

#### 多浏览器支持
在 `.env` 中添加配置项 `NEWS_BROWSER`，支持:
- `chromium` — Chromium 无头浏览器（默认）
- `firefox` — Firefox 无头浏览器
- `msedge` — Microsoft Edge（使用系统已安装的Edge）

修改 `_create_browser()` 函数根据配置选择浏览器类型。

#### 选择器增强
当前仅解析 `<area>` 标签，增加回退选择器:
- `a[href]` — 通用链接
- `.news-list a` — 新闻列表链接
- `.article-title a` — 文章标题链接

#### 内容提取增强
增加人民公安报特定选择器:
- `.TRS_Editor` — 人民公安报CMS常用编辑器
- `.article-content`, `#article-content`

#### 重试机制
页面加载失败自动重试3次（每次间隔递增）。

### 第三步: 创建前端独立新闻页面（VTJ MCP）

使用VTJ设计器创建:
- **页面ID:** `dailyNews`
- **路由:** `/daily-news`
- **功能:** 来源筛选、分类筛选、分页列表、详情弹窗

### 第四步: 更新首页新闻区块
在 QuoteBanner (11jve6eq7) 中添加"查看更多"链接指向 `/daily-news`。

---

## 涉及文件

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/requirements.txt` | 不变 | 已包含 playwright 依赖 |
| `backend/.env` | 修改 | 新增 NEWS_BROWSER 配置 |
| `backend/app/services/news_scraper.py` | 修改 | 多浏览器+选择器增强+重试 |
| `.vtj/vue/dailyNews.vue` | 新建 | 每日新闻独立页面 |
| `.vtj/files/dailyNews.json` | 新建 | DSL 定义 |
| `.vtj/router.js` | 修改 | 注册新路由 |
| `.vtj/vue/11jve6eq7.vue` | 修改 | 添加"查看更多"链接 |
| `.vtj/files/11jve6eq7.json` | 同步 | DSL 一致性同步 |
