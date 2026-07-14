# 砺安题库 — Playwright 迁移 & VTJ MCP 验证方案

> 生成日期：2026-06-27 | 状态：待审批

---

## 一、背景

上一轮实施（每日新闻 & 招考信息修复）已完成 **10/11 文件**：
- ✅ 数据库 content 字段 + auto-migration
- ✅ 新闻 API content 返回
- ✅ QuoteBanner 新闻详情弹窗（点击标题→弹窗展示正文）
- ✅ 招考爬虫详情页抓取（正文/发布单位/截止日期等）
- ✅ 招考 API 完整字段返回
- ✅ HomePage 2x3 模块卡片重设计 + 详情弹窗
- ✅ DSL JSON 同步

**待完成：**
1. 新闻爬虫仍使用 **Selenium** — 用户要求改用 **Playwright**（反检测能力更强）
2. 确认 VTJ MCP 工具已正确用于前端修改

---

## 二、Playwright vs Selenium 对比

| 特性 | Selenium | Playwright |
|------|----------|------------|
| 反检测能力 | 弱（navigator.webdriver=true 易被检测） | 强（stealth 插件，真实浏览器指纹） |
| JS 重定向跟随 | 需要 WebDriverWait | 自动跟随，更稳定 |
| 浏览器管理 | 需要 webdriver-manager 手动匹配 | 内置 `playwright install chromium` |
| 异步支持 | 同步 | 原生 async/await |
| 资源消耗 | headless Chrome ~300MB | headless Chromium ~250MB |

---

## 三、实施方案（3步）

### Step 1: 依赖替换

```diff
# backend/requirements.txt
- selenium>=4.27.0
- webdriver-manager>=4.0.0
+ playwright>=1.48.0
+ playwright-stealth>=1.0.6
```

### Step 2: 重写 news_scraper.py

核心变化：
- `_create_driver()` → `_create_browser()` + `sync_playwright()`
- `driver.get()` → `page.goto()`（自动跟随 JS 重定向）
- `driver.page_source` → `page.content()`
- `driver.quit()` → `browser.close()`

**反爬核心代码：**
```python
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync

def _create_browser():
    p = sync_playwright().start()
    browser = p.chromium.launch(headless=True, args=[
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox"
    ])
    context = browser.new_context(
        user_agent=get_random_ua(),
        viewport={"width": 1920, "height": 1080},
        locale="zh-CN"
    )
    page = context.new_page()
    stealth_sync(page)  # 注入反检测
    return p, browser, page

def scrape_cpd_news(db):
    p, browser, page = _create_browser()
    try:
        page.goto("https://epaper.cpd.com.cn/.../rmga/")
        page.wait_for_load_state("networkidle")
        # ... 解析逻辑不变
    finally:
        browser.close()
        p.stop()
```

### Step 3: 验证

```bash
# 1. 安装
pip install playwright playwright-stealth
playwright install chromium

# 2. 测试爬虫
cd backend
python -c "from app.services.news_scraper import scrape_all_news; scrape_all_news()"

# 3. 检查日志: [cpd] 新增 N 条公安报新闻

# 4. 清理前端缓存
rm -rf node_modules/.vite/
npm run dev
```

---

## 四、VTJ MCP 验证清单

使用 VTJ MCP 工具验证前端修改：

| MCP 工具 | 参数 | 预期结果 |
|----------|------|----------|
| `vtj_read_vue_file` | id="jjvdntly" | 模板含 `recruit-modal-overlay` |
| `vtj_read_vue_file` | id="11jve6eq7" | 模板含 `news-modal-overlay` |
| `vtj_check_consistency` | id="jjvdntly" | status: consistent |
| `vtj_check_consistency` | id="11jve6eq7" | status: consistent |

## 五、修改文件清单

| 文件 | 修改类型 | 说明 |
|------|----------|------|
| `backend/requirements.txt` | 替换 | selenium→playwright+stealth |
| `backend/app/services/news_scraper.py` | 重写 | Selenium→Playwright |

## 六、验证方案
1. 安装 Playwright + Chromium → `playwright install chromium` 成功
2. 后端启动 → 无 import 错误
3. 手动触发爬虫 → `[cpd] 新增 N 条` 日志
4. 前端首页 → 新闻点击 → 弹窗正文展示
5. 前端首页 → 招考 2x3 卡片 → 点击标题 → 详情弹窗
6. VTJ MCP `vtj_check_consistency` → 全部 consistent
