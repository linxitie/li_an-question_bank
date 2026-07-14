# 每日新闻爬虫修复实施日志

## 日期：2026-06-28

## 实施概要

### 1. Playwright 环境安装 ✅
- `pip install playwright==1.60.0 playwright-stealth==2.0.3` — 成功
- `playwright install chromium` — 成功（Chromium 148.0.7778.96）
- `playwright install firefox` — 成功（后台完成）
- 已验证：Playwright 可正常启动 Chromium 并访问人民公安报页面

### 2. 后端爬虫增强 ✅
**文件**: `backend/app/services/news_scraper.py`

主要修改：
- **多浏览器支持**: `_create_browser()` 函数支持 chromium/firefox/msedge 三种浏览器
  - 使用 `os.getenv("NEWS_BROWSER", "chromium")` 读取配置
  - msedge 使用 `p.chromium.launch(channel="msedge")` 调用系统 Edge
  - 启动失败时自动回退到内置 Chromium
- **Stealth API 更新**: 适配 playwright-stealth v2.x API
  - 旧: `from playwright_stealth import stealth_sync` + `stealth_sync(page)`
  - 新: `from playwright_stealth import Stealth` + `Stealth().apply_stealth_sync(page)`
- **选择器增强**: 新增 `_find_news_links()` 函数，三级回退策略
  1. `<area>` 标签解析（人民公安报电子报图像映射）
  2. 通用新闻选择器（`.news-list a`, `.article-list a` 等）
  3. 最宽泛 `<a>` 标签抓取
- **重试机制**: 新增 `_goto_with_retry()` 函数，页面加载失败自动重试 3 次
- **内容提取增强**: 增加 `.TRS_Editor`（人民公安报 CMS 常用编辑器）等选择器
- **调试支持**: DEBUG 模式下自动保存页面截图到 `logs/screenshots/`

### 3. 环境配置 ✅
**文件**: `backend/.env` — 新增 `NEWS_BROWSER=chromium`
**文件**: `backend/app/core/config.py` — 新增 `NEWS_BROWSER` 字段

### 4. 前端新闻页面 ✅
**新建文件**:
- `.vtj/files/dailyNews.json` — VTJ DSL 定义
- `.vtj/vue/dailyNews.vue` — Vue 组件

**页面功能**:
- 新闻来源筛选（全部 / 人民公安报 / 人民网）
- 分类筛选（全部 / 公安报 / 理论 / 党史）
- 新闻列表（序号、标题、来源、分类、日期）
- 分页浏览（每页 20 条）
- 点击展开详情弹窗（标题、来源、日期、正文、查看原文链接）
- 加载状态和空数据状态
- 响应式设计，统一 UI 风格

**路由注册**: `.vtj/router.js` — 新增 `/daily-news` 路由

### 5. 首页 QuoteBanner 更新 ✅
**文件**: `.vtj/vue/11jve6eq7.vue`
- 在新闻区域底部添加"查看更多新闻 →"链接，指向 `/daily-news`
- 添加 `.news-more` 和 `.news-more-link` 样式

### 6. 验证结果 ✅
- Playwright 导入: OK
- Stealth 导入: OK
- 人民公安报页面可访问: OK
- 爬虫模块导入: OK
- FastAPI 应用加载: OK
- API 路由注册: `/api/news`, `/api/news/today`
- 数据库现有新闻: 39 条（来自人民网 HTTP 爬取）
- DSL-Vue 一致性: 已同步

## 已知问题

1. 数据库中旧新闻标题存在编码问题（乱码），可能是人民网页面编码处理导致
2. playwright-stealth 从 v1.x 升级到 v2.x，API 不兼容，已适配
3. Edge 浏览器需要系统已安装 Microsoft Edge 才能使用 `channel="msedge"`

## 后续建议

1. 启动后端服务后，等待 30 秒触发首次全量爬取，或手动调用爬取
2. 若人民公安报爬取仍失败，检查页面 HTML 结构是否有变化，调整选择器
3. 可增加新闻封面图提取功能（人民公安报电子报为图片版）
