"""
每日新闻爬虫（Playwright增强版）
来源1: epaper.cpd.com.cn - 人民公安报当日所有新闻（Playwright自动化跟随JS重定向）
来源2: people.com.cn - 理论与党史栏目前10条（HTTP + 正文回抓）
反爬策略: Playwright Stealth伪装 + UA轮换 + 延迟随机化 + 重试机制
多浏览器: 支持Chromium/Firefox/Edge，通过 .env 中 NEWS_BROWSER 配置
"""
import logging
import os
import re
import random
import time
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session
from ..core.database import SessionLocal
from ..models.models import NewsArticle, NewsImage
from .scraper_utils import safe_request, get_random_ua

logger = logging.getLogger(__name__)

# 噪音过滤正则模式
NOISE_PATTERNS = [
    # 通用UI噪音
    r'登录.*?注册', r'记住密码', r'忘记密码', r'扫码.*?关注',
    r'用户登录', r'会员中心', r'我的收藏', r'退出登录',
    r'推荐阅读.*', r'上一篇.*', r'下一篇.*',
    # 人民网页脚/导航噪音（非正文）
    r'人民日报社概况.*?联系我们', r'关于人民网.*?招聘英才',
    r'广告服务.*?合作加盟', r'供稿服务.*?数据服务',
    r'网站声明.*?网站律师', r'信息保护.*?联系我们',
    r'举报电话[：:]\s*\d[\d-]*', r'举报邮箱[：:]\s*\S+@\S+',
    r'服务邮箱[：:]\s*\S+@\S+',
    r'互联网新闻信息服务许可证\d+', r'增值电信业务经营许可证[^\n]*',
    r'广播电视节目制作经营许可证[^\n]*', r'信息网络传播视听节目许可证\d+',
    r'网络文化经营许可证[^\n]*', r'网络出版服务许可证[^\n]*',
    r'京ICP证\d+号', r'京公网安备\d+号',
    r'人\s*民\s*网\s*版\s*权\s*所\s*有[^\n]*',
    r'Copyright\s*[©©]\s*\d{4}[-–]\d{4}\s*by\s*\S+\.com[^\n]*',
    r'all rights reserved[^\n]*',
    # 人民网导航栏
    r'工会新闻网\s*\|.*?(?=\n)', r'毛主席纪念堂\s*\|.*?(?=\n)',
    r'不忘初心.*?官网\s*\|.*?(?=\n)', r'中共中央党史和文献研究院\s*\|.*?(?=\n)',
    r'中国共产党历史和文献网\s*\|.*?(?=\n)', r'全国社科工作办\s*\|.*?(?=\n)',
    r'中国人事考试网\s*\|.*?(?=\n)', r'学习贯彻.*?主题教育.*?\|.*?(?=\n)',
    r'党史学习教育.*?\|.*?(?=\n)', r'整治形式主义.*?\|.*?(?=\n)',
    # 侧边栏/页脚链接
    r'首页\s+要闻\s+党建\s+理论\s+党史\s+数据', r'登录\s*\|\s*注册',
    r'中国共产党新闻网\s*>>\s*党建', r'分享\s*\d*',
    r'相关专题\s*[·•]\s*专题报道', r'微信[“"][扫一扫][”"][^。]*添加[^。]*',
    r'学习路上\s*时习之', r'系列重要讲话数据库',
    r'学习宣传贯彻\s*党的二十大精神', r'跟着总书记学党史\s*数据库',
    r'中央和国家机关\s*建设模范机关', r'言之有理\s*学习文选',
    # 页脚
    r'人民日报违法和不良信息举报.*?(?=\n)',
    r'人民网服务邮箱.*?(?=\n)', r'互联网新闻信息服务许可证.*?(?=\n)',
]


def _filter_noise(text: str) -> str:
    """过滤新闻正文中的噪音内容（使用 DOTALL 匹配跨行模式）"""
    original_text = text  # 保存原文，过滤过激时回退
    for pat in NOISE_PATTERNS:
        text = re.sub(pat, '', text, flags=re.DOTALL | re.IGNORECASE)

    # 删除导航风格的行（含|分隔符的短行、纯链接文字行）
    lines = text.split('\n')
    filtered_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            filtered_lines.append('')
            continue
        # 跳过纯导航行：含多个|分隔且平均每段<15字符
        if '|' in stripped:
            parts = [p.strip() for p in stripped.split('|') if p.strip()]
            if len(parts) >= 2:
                avg_len = sum(len(p) for p in parts) / len(parts)
                if avg_len < 15:
                    continue  # 跳过导航行
        # 跳过极短的非完整句子行（< 8字符且不以中文句号/问号/感叹号结尾）
        if len(stripped) < 8 and not re.search(r'[。！？]$', stripped):
            continue
        # 跳过已知导航关键词开头的行
        nav_starts = ['首页', '上一页', '下一页', '返回', '关于', '联系', '版权', 'ICP', '导航', '网站地图']
        if any(stripped.startswith(ns) for ns in nav_starts):
            continue
        filtered_lines.append(stripped)

    text = '\n'.join(filtered_lines)
    # 合并多余空行
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip()

    # 如果过滤后内容太短（< 100字符），保留过滤前的原文
    if len(text) < 100:
        return original_text[:8000]

    return text


def _download_images(soup, page_url: str, news_id: int, db: Session, label: str = "") -> int:
    """
    从 BeautifulSoup 解析的页面中提取 img 标签，下载图片并保存路径到 news_image 表。

    Returns:
        下载成功的图片数量
    """
    img_count = 0
    img_tags = soup.find_all("img")
    if not img_tags:
        return 0

    upload_dir = os.path.join(os.path.dirname(__file__), "..", "..", "uploads", "news", str(news_id))
    os.makedirs(upload_dir, exist_ok=True)

    for idx, img_tag in enumerate(img_tags):
        src = img_tag.get("src", "").strip()
        if not src:
            src = img_tag.get("data-src", "").strip()
        if not src:
            continue

        # CRITICAL FIX: 截断URL到有效图片扩展名，去除HTML标签残留
        # 修复公安报图片URL包含 %3C/a%3E%3Cp%20style= 等HTML实体的问题
        import re as _re_url
        clean_match = _re_url.match(r'^(.*?\.(?:jpg|jpeg|png|gif|webp|bmp))', src, _re_url.IGNORECASE)
        if clean_match:
            src = clean_match.group(1)
        else:
            # URL不以有效图片扩展名结尾，跳过
            continue

        # 安全检测: URL中不应包含HTML编码字符
        if '%3C' in src or '%3E' in src or '<' in src or '>' in src:
            logger.warning(f"[{label}] 图片URL包含HTML实体，已跳过: {src[:80]}")
            continue

        # 补全 URL
        if not src.startswith("http"):
            if src.startswith("//"):
                src = "https:" + src
            elif src.startswith("/"):
                parsed = urlparse(page_url)
                src = f"{parsed.scheme}://{parsed.netloc}{src}"
            else:
                src = urljoin(page_url, src)

        # 过滤太小的图片（可能是图标）
        width = img_tag.get("width", "")
        height = img_tag.get("height", "")
        try:
            w = int(width) if width else 0
            h = int(height) if height else 0
            if 0 < w < 50 or 0 < h < 50:
                continue
        except ValueError:
            pass

        try:
            img_resp = safe_request(src, timeout=15, label=f"{label}/img/{idx}")
            if img_resp is None:
                continue

            content_type = img_resp.headers.get("Content-Type", "")
            ext = ".jpg"
            if "png" in content_type:
                ext = ".png"
            elif "gif" in content_type:
                ext = ".gif"
            elif "webp" in content_type:
                ext = ".webp"

            filename = f"img_{idx}{ext}"
            filepath = os.path.join(upload_dir, filename)
            with open(filepath, "wb") as f:
                f.write(img_resp.content)

            # 保存相对路径到数据库
            relative_path = f"uploads/news/{news_id}/{filename}"
            db.add(NewsImage(
                news_id=news_id,
                image_path=relative_path,
                image_order=idx
            ))
            img_count += 1
            logger.debug(f"[{label}] 图片已下载: {relative_path}")

        except Exception as e:
            logger.warning(f"[{label}] 图片下载失败 {src}: {e}")
            continue

    if img_count > 0:
        try:
            db.commit()
        except Exception as e:
            logger.warning(f"[{label}] 图片记录提交失败: {e}")
            db.rollback()

    return img_count

# 浏览器类型配置（从环境变量读取，默认 chromium）
NEWS_BROWSER = os.getenv("NEWS_BROWSER", "chromium").lower()
# 是否开启调试截图（DEBUG=true 时自动开启）
DEBUG_MODE = os.getenv("DEBUG", "false").lower() == "true"


def _create_browser(browser_type: str = None):
    """
    创建 Playwright 浏览器（含 stealth 反检测伪装）

    支持浏览器类型:
    - chromium: Chromium 无头浏览器（默认，Playwright 内置）
    - firefox:  Firefox 无头浏览器
    - msedge:   Microsoft Edge（使用系统安装的 Edge）

    Returns:
        (playwright_instance, browser, page)
    """
    from playwright.sync_api import sync_playwright
    from playwright_stealth import Stealth

    bt = (browser_type or NEWS_BROWSER).lower()
    logger.info(f"[browser] 启动浏览器类型: {bt}")

    p = sync_playwright().start()

    # 通用浏览器启动参数
    common_args = [
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
        "--disable-dev-shm-usage",
    ]

    try:
        if bt == "firefox":
            browser = p.firefox.launch(headless=True)
        elif bt == "msedge":
            # Edge 使用 Chromium 引擎 + channel="msedge"
            browser = p.chromium.launch(
                headless=True,
                channel="msedge",
                args=common_args + ["--disable-gpu"],
            )
        else:
            # 默认 Chromium
            browser = p.chromium.launch(
                headless=True,
                args=common_args + ["--disable-gpu"],
            )
    except Exception as e:
        logger.error(f"[browser] 启动失败 ({bt}): {e}")
        # 回退到默认 Chromium
        if bt != "chromium":
            logger.warning("[browser] 回退到内置 Chromium")
            browser = p.chromium.launch(
                headless=True,
                args=common_args + ["--disable-gpu"],
            )
        else:
            raise

    context = browser.new_context(
        user_agent=get_random_ua(),
        viewport={"width": 1920, "height": 1080},
        locale="zh-CN",
    )
    page = context.new_page()

    # 应用 stealth 反检测伪装（playwright-stealth v2.x API）
    stealth = Stealth(
        navigator_webdriver=True,
        navigator_languages=True,
        navigator_platform=True,
        navigator_vendor=True,
        webgl_vendor=True,
        chrome_app=True,
        chrome_csi=True,
        chrome_load_times=True,
        hairline=True,
        iframe_content_window=True,
        media_codecs=True,
    )
    stealth.apply_stealth_sync(page)
    logger.info("[browser] Stealth 反检测伪装已应用")

    return p, browser, page


def _download_news_images(news_id: int, image_urls: list, db: Session) -> list:
    """
    从图片URL列表下载图片到 uploads/news/{news_id}/ 目录，
    并将路径保存到 news_image 表。

    Returns:
        saved: 已保存的图片相对路径列表
    """
    import os as _os
    upload_dir = _os.path.join(_os.path.dirname(__file__), "..", "..", "uploads", "news", str(news_id))
    _os.makedirs(upload_dir, exist_ok=True)
    saved = []
    for idx, url in enumerate(image_urls[:10]):  # 最多10张图
        try:
            r = safe_request(url, timeout=15, label=f"news/img/{idx}")
            if r is None or not hasattr(r, 'content'):
                continue
            if len(r.content) < 100 or len(r.content) > 5 * 1024 * 1024:
                continue
            ext = url.rsplit('.', 1)[-1].split('?')[0] or 'jpg'
            if ext not in ('jpg', 'jpeg', 'png', 'gif', 'webp'):
                ext = 'jpg'
            fname = f'img_{idx}.{ext}'
            fpath = _os.path.join(upload_dir, fname)
            with open(fpath, 'wb') as f:
                f.write(r.content)
            relative_path = f'uploads/news/{news_id}/{fname}'
            db.add(NewsImage(
                news_id=news_id,
                image_path=relative_path,
                image_order=idx
            ))
            saved.append(relative_path)
            logger.debug(f"[news/img] 图片已下载: {relative_path}")
        except Exception:
            continue
    if saved:
        try:
            db.commit()
        except Exception as e:
            logger.warning(f"[news/img] 图片记录提交失败: {e}")
            db.rollback()
    return saved


def _fetch_article_detail(url: str) -> tuple:
    """
    从文章详情页抓取完整正文和图片URL列表。
    用于人民网等需要二次请求获取全文的新闻源。

    Returns:
        (content: str, images: list[str])
    """
    try:
        resp = safe_request(url, timeout=15, label="news/detail")
        if resp is None:
            return '', []
        resp.encoding = resp.apparent_encoding or 'utf-8'
        soup = BeautifulSoup(resp.text, 'lxml')
        content = _extract_article_content(soup)
        content = _filter_noise(content)

        # 提取图片URL
        images = []
        for img in soup.select('img[src]'):
            src = img.get('src', '')
            if src and not src.startswith('data:'):
                w = img.get('width', '0')
                if w.isdigit() and int(w) < 50:
                    continue
                from urllib.parse import urljoin as _urljoin
                full_url = _urljoin(url, src) if not src.startswith('http') else src
                images.append(full_url)
        return content, images
    except Exception:
        return '', []


def _fetch_people_detail_playwright(page, url):
    """使用Playwright抓取人民网新闻详情页，精确提取div.p2j_con3内容"""
    content = ''
    images = []
    try:
        page.goto(url, wait_until='networkidle', timeout=30000)
        time.sleep(0.5)

        # 精确选择器（用户指定）
        selectors = [
            'div.p2j_con3.clearfix.g-w1200',
            'div.p2j_con3',
            'div.text-con',
            'div.article-content',
            'article',
        ]
        content_elem = None
        for sel in selectors:
            content_elem = page.query_selector(sel)
            if content_elem:
                break

        if content_elem:
            # 激进移除噪音子元素（导航、侧栏、页头、分享、分页等）
            noise_selectors = [
                '.nav', '.navbar', '.navigation', '.menu',
                '.sidebar', '.ad', '.advertisement',
                '.login', '.register', '.user',
                '.recommend', '.related', '.hot',
                '.footer', '.header', '.top-bar',
                '.share', '.share-box', '.toolbar',
                '.pagination', '.page-nav', '.breadcrumb', '.position',
                '.crumb', '.path', '.channel-nav',
                '.search', '.logo', '.qrcode',
                'script', 'style', 'iframe',
            ]
            for ns in noise_selectors:
                for el in content_elem.query_selector_all(ns):
                    try:
                        el.evaluate('el => el.remove()')
                    except:
                        pass
            content = content_elem.inner_text()[:8000]

            # 提取图片
            for img in content_elem.query_selector_all('img[src]'):
                src = img.get_attribute('src') or ''
                if src and not src.startswith('data:') and len(src) > 10:
                    w = img.get_attribute('width') or '0'
                    if w.isdigit() and int(w) < 50:
                        continue
                    images.append(src)

        # 如果没有内容，回退
        if not content:
            content = page.inner_text('body')[:5000]
    except Exception as e:
        logger.warning(f"[people/playwright] 详情抓取失败: {e}")
    return content, images


def _random_delay(min_s=0.5, max_s=2.0):
    """模拟人类行为的随机延迟"""
    time.sleep(random.uniform(min_s, max_s))


def _extract_article_content(soup):
    """
    从 BeautifulSoup 对象中提取文章正文（多选择器 fallback）
    覆盖人民公安报 CMS（TRS_Editor）和常见新闻模板
    """
    content_selectors = [
        # 人民网专用选择器
        "div.p2j_con3.clearfix.g-w1200",
        "div.p2j_con3",
        "div.text-con",
        # 人民公安报 CMS (TRS 编辑器)
        "div.TRS_Editor",
        "div.TRS_PreAppend",
        "div.TRS_Editor div",
        # 通用文章内容
        "div.article-content",
        "div#article-content",
        "div.content",
        "div.article",
        "div.article-body",
        "div.detail-content",
        "div#detail-content",
        "div.news-content",
        "div#news-content",
        "div.news-detail",
        "div.main-text",
        "article",
        "div.text",
        "div.entry-content",
        "div.post-content",
    ]
    for selector in content_selectors:
        elem = soup.select_one(selector)
        if elem:
            # 移除内部脚本和样式
            for bad in elem.select("script, style"):
                bad.decompose()
            text = elem.get_text(separator="\n", strip=True)
            if len(text) > 50:
                return text[:8000]  # 增加上限到8000字符

    # Fallback: body text with noise removal
    for bad in soup.select("script, style, nav, footer, header, .nav, .footer, .sidebar, .header, .menu"):
        bad.decompose()
    body = soup.find("body")
    if body:
        text = body.get_text(separator="\n", strip=True)
        return text[:8000]
    return ""


def _goto_with_retry(page, url, wait_until="networkidle", timeout=30000, max_retries=3, label=""):
    """
    带重试机制的页面导航
    自动重试失败的页面加载，最多 max_retries 次
    """
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"[{label}] 导航至: {url} (第{attempt}次)")
            page.goto(url, wait_until=wait_until, timeout=timeout)
            _random_delay(0.5, 1.5)
            return True
        except Exception as e:
            last_error = e
            logger.warning(f"[{label}] 第{attempt}次导航失败: {type(e).__name__}: {e}")
            if attempt < max_retries:
                wait = attempt * 2  # 递增等待: 2s, 4s
                logger.info(f"[{label}] {wait}秒后重试...")
                time.sleep(wait)
    logger.error(f"[{label}] 导航最终失败（{max_retries}次尝试）: {last_error}")
    return False


def _find_news_links(soup, page_url):
    """
    从页面解析新闻链接（多选择器回退）
    返回: [(title, url), ...]
    """
    links = []

    # 方法1: <area> 标签（人民公安报电子报图像映射）
    areas = soup.find_all("area")
    if areas:
        logger.info("[cpd] 发现 area 标签，按图像映射方式解析")
    for area in areas:
        title = area.get("title", "").strip()
        href = area.get("href", "").strip()
        if title and len(title) >= 3 and href:
            links.append((title, href))

    # 方法2: 如果 area 标签没找到，回退到通用链接选择器
    if not links:
        logger.info("[cpd] 未发现 area 标签，使用通用选择器回退")
        link_selectors = [
            "a[title]",
            ".news-list a",
            ".newslist a",
            ".article-list a",
            ".list a[href]",
            "a[href*='content']",
            "a[href*='html']",
            "a[href*='article']",
            "a[href*='news']",
        ]
        for selector in link_selectors:
            elements = soup.select(selector)
            for elem in elements:
                title = elem.get("title", "").strip() or elem.get_text(strip=True)
                href = elem.get("href", "").strip()
                if title and len(title) >= 5 and href:
                    links.append((title, href))
            if links:
                break

    # 方法3: 最宽泛的链接抓取
    if not links:
        logger.info("[cpd] 使用最宽泛链接抓取")
        for a in soup.find_all("a", href=True):
            title = a.get_text(strip=True)
            href = a["href"].strip()
            if title and len(title) >= 5 and href:
                links.append((title, href))

    # URL 补全
    result = []
    base = page_url.rsplit("/", 1)[0] + "/"
    for title, href in links:
        if not href.startswith("http"):
            if href.startswith("//"):
                href = "https:" + href
            elif href.startswith("/"):
                # 提取域名
                from urllib.parse import urlparse
                parsed = urlparse(page_url)
                href = f"{parsed.scheme}://{parsed.netloc}{href}"
            else:
                href = base + href.lstrip("./")
        result.append((title, href))

    return result


# ════════════════════════════════════════════════════════════
#  来源1: 人民公安报 (epaper.cpd.com.cn)
# ════════════════════════════════════════════════════════════

def scrape_cpd_news(db: Session) -> int:
    """
    爬取人民公安报当日新闻（Playwright 自动跟随 JS 重定向链）

    流程:
    1. 启动 Playwright 浏览器（chromium/firefox/msedge）
    2. 导航至人民公安报电子报首页
    3. 等待 JS 重定向完成（自动跳转到当日版面）
    4. 解析新闻标题和链接
    5. 逐条进入详情页抓取正文
    6. 存入数据库（去重）

    Returns:
        新增新闻数量
    """
    count = 0
    p = browser = None
    try:
        base_url = "https://epaper.cpd.com.cn/szb/wwwcpd_9/dzb_16465/rmga/"
        logger.info(f"[cpd] 启动浏览器（{NEWS_BROWSER}，headless + stealth）...")
        p, browser, page = _create_browser()

        # 导航至电子报首页，等待 JS 重定向
        if not _goto_with_retry(page, base_url, wait_until="networkidle", timeout=30000, label="cpd"):
            logger.error("[cpd] 页面加载失败，跳过")
            return 0

        final_url = page.url
        html = page.content()
        logger.info(f"[cpd] 最终页面: {final_url} ({len(html)} 字节)")

        # 调试截图（DEBUG 模式下）
        if DEBUG_MODE:
            try:
                screenshot_dir = os.path.join(os.path.dirname(__file__), "..", "..", "logs", "screenshots")
                os.makedirs(screenshot_dir, exist_ok=True)
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                page.screenshot(path=os.path.join(screenshot_dir, f"cpd_{ts}.png"), full_page=True)
                logger.info(f"[cpd] 调试截图已保存")
            except Exception as se:
                logger.warning(f"[cpd] 截图失败: {se}")

        soup = BeautifulSoup(html, "lxml")

        # 解析新闻链接（多选择器回退）
        news_links = _find_news_links(soup, final_url)
        logger.info(f"[cpd] 发现 {len(news_links)} 个潜在链接")

        # 去重 + 过滤
        seen_titles = set()
        unique_links = []
        for title, href in news_links:
            if title in seen_titles:
                continue
            if len(title) < 3:
                continue
            # 过滤掉非新闻链接（如导航、广告）
            skip_kw = ["首页", "上一页", "下一页", "返回", "关于", "版权", "广告", "更多"]
            if any(kw == title for kw in skip_kw):
                continue
            seen_titles.add(title)
            unique_links.append((title, href))

        logger.info(f"[cpd] 去重后 {len(unique_links)} 条候选新闻（最多30条）")

        for title, article_url in unique_links:
            if count >= 30:
                break

            # 数据库去重
            exists = db.query(NewsArticle).filter(
                NewsArticle.title == title,
                NewsArticle.source == "cpd"
            ).first()
            if exists:
                logger.debug(f"[cpd] 已存在，跳过: {title[:30]}")
                continue

            # 进入文章详情页抓取正文和图片
            content = ""
            try:
                if _goto_with_retry(page, article_url, wait_until="domcontentloaded", timeout=20000, label="cpd-article"):
                    article_html = page.content()
                    article_soup = BeautifulSoup(article_html, "lxml")
                    content = _extract_article_content(article_soup)
                    # 噪音过滤
                    content = _filter_noise(content)
                    if content:
                        logger.info(f"[cpd] 正文提取成功: {len(content)} 字符")
                    else:
                        logger.warning(f"[cpd] 未提取到正文: {article_url}")
                else:
                    logger.warning(f"[cpd] 文章页面加载失败: {article_url}")
            except Exception as e:
                logger.warning(f"[cpd] 文章正文抓取异常 {article_url}: {type(e).__name__}: {e}")

            # 解析发布日期（尝试从URL或内容推断）
            publish_date = _parse_cpd_date(final_url)

            article = NewsArticle(
                title=title,
                url=article_url,
                source="cpd",
                category="公安报",
                publish_date=publish_date,
                summary=content[:200] if content else "",
                content=content or ""
            )
            db.add(article)
            db.flush()  # 获取 news_id 用于图片关联

            # 提取图片
            try:
                if 'article_soup' in dir() and article_soup:
                    _download_images(article_soup, article_url, article.news_id, db, label="cpd")
            except Exception as e:
                logger.warning(f"[cpd] 图片提取异常: {e}")

            count += 1
            logger.info(f"[cpd] 第{count}条入库: {title[:40]}")

        if count > 0:
            db.commit()
            logger.info(f"[cpd] ✅ 新增 {count} 条公安报新闻")
        else:
            logger.info("[cpd] 无新增新闻（可能已全部存在或未解析到链接）")

    except Exception as e:
        db.rollback()
        logger.error(f"[cpd] ❌ 爬取失败: {type(e).__name__}: {e}", exc_info=True)
    finally:
        if browser:
            try:
                browser.close()
            except Exception:
                pass
        if p:
            try:
                p.stop()
            except Exception:
                pass

    return count


def _parse_cpd_date(url: str) -> datetime:
    """从人民公安报 URL 中解析日期"""
    import re
    # URL 格式示例: .../2025-01/15/...
    date_match = re.search(r'/(\d{4}-\d{2})/(\d{2})/', url)
    if date_match:
        date_str = f"{date_match.group(1)}-{date_match.group(2)}"
        try:
            return datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            pass
    return datetime.now()


# ════════════════════════════════════════════════════════════
#  来源2: 人民网 (people.com.cn)
# ════════════════════════════════════════════════════════════

def scrape_people_news(db: Session) -> int:
    """爬取人民网理论/党建/党史新闻标题链接及正文（Playwright增强），返回新增数量"""
    count = 0
    p = browser = None
    try:
        resp = safe_request("https://www.people.com.cn/", label="news/people")
        if resp is None:
            logger.error("[people] 无法获取页面")
            return 0
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        all_links = soup.select("a[href]")
        seen = set()

        for link in all_links:
            title = link.get_text(strip=True)
            href = link.get("href", "")

            if not title or len(title) < 5:
                continue
            if not href.startswith("http"):
                if href.startswith("//"):
                    href = "https:" + href
                elif href.startswith("/"):
                    href = "https://www.people.com.cn" + href
                else:
                    continue

            # 只取包含 theory/history/dangshi 等关键词的链接
            theory_kw = ["theory", "lilun", "党史", "dangshi", "党建", "dangjian", "history"]
            is_theory = any(kw in href.lower() or kw in title for kw in theory_kw)
            if not is_theory:
                continue

            cat = "党史" if any(kw in title + href for kw in ["党史", "dangshi", "history"]) else "理论"

            dedup_key = (title, "people")
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            # 数据库去重
            exists = db.query(NewsArticle).filter(
                NewsArticle.title == title,
                NewsArticle.source == "people"
            ).first()
            if exists:
                continue

            # 使用Playwright抓取详情页（首次使用时创建浏览器）
            content = ""
            image_urls = []
            try:
                if browser is None:
                    logger.info(f"[people] 启动浏览器（{NEWS_BROWSER}）用于详情抓取...")
                    p, browser, page = _create_browser()

                if _goto_with_retry(page, href, wait_until="networkidle", timeout=30000, label="people-detail"):
                    content, image_urls = _fetch_people_detail_playwright(page, href)
                    content = _filter_noise(content)
                else:
                    # HTTP 回退
                    logger.warning(f"[people] Playwright详情加载失败，回退HTTP: {href}")
                    content, image_urls = _fetch_article_detail(href)
            except Exception as e:
                logger.warning(f"[people] Playwright异常，回退HTTP: {href}: {e}")
                content, image_urls = _fetch_article_detail(href)

            if content:
                logger.info(f"[people] 正文提取成功: {len(content)} 字符, {len(image_urls)} 图片")
            else:
                logger.warning(f"[people] 未提取到正文: {href}")

            article = NewsArticle(
                title=title,
                url=href,
                source="people",
                category=cat,
                publish_date=datetime.now(),
                summary=content[:200] if content else "",
                content=content or ""
            )
            db.add(article)
            db.flush()  # 获取 news_id 用于图片关联

            # 提取图片（从详情页 URL 列表下载）
            if image_urls:
                try:
                    _download_news_images(article.news_id, image_urls, db)
                except Exception as e:
                    logger.warning(f"[people] 图片提取异常: {e}")

            count += 1
            if count >= 10:
                break

        if count > 0:
            db.commit()
            logger.info(f"[people] ✅ 新增 {count} 条人民网新闻")
        else:
            logger.info("[people] 无新增新闻")
    except Exception as e:
        db.rollback()
        logger.error(f"[people] ❌ 爬取失败: {type(e).__name__}: {e}", exc_info=True)
    finally:
        if browser:
            try:
                browser.close()
            except Exception:
                pass
        if p:
            try:
                p.stop()
            except Exception:
                pass

    return count


# ════════════════════════════════════════════════════════════
#  调度入口
# ════════════════════════════════════════════════════════════

def scrape_all_news():
    """执行全部新闻爬取（调度器调用入口）"""
    db = SessionLocal()
    try:
        total = 0
        logger.info("=" * 50)
        logger.info(f"开始新闻爬取 (浏览器: {NEWS_BROWSER})")
        logger.info("=" * 50)
        total += scrape_cpd_news(db)
        total += scrape_people_news(db)
        logger.info(f"新闻爬取完成，共新增 {total} 条")
    except Exception as e:
        logger.error(f"新闻爬取全局异常: {type(e).__name__}: {e}", exc_info=True)
    finally:
        db.close()
