"""
招考信息爬虫（增强版）
来源: rszk.net - 事业单位/国考省考/教师招聘/国企招聘/医疗卫生/三支一扶
反爬策略: UA轮换池 + 请求延迟随机化 + 指数退避重试 + 健壮错误处理
详情抓取: Playwright (channel-main 精确提取) + BeautifulSoup 回退
"""
import logging
import re
import random
import time
from datetime import datetime
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session
from ..core.database import SessionLocal
from ..models.models import RecruitmentInfo
from .scraper_utils import safe_request, get_random_ua

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

logger = logging.getLogger(__name__)


def _extract_field(text: str, patterns: list) -> str:
    """正则提取字段：匹配标签后跟随的内容"""
    for pattern in patterns:
        m = re.search(f"{pattern}[：:\\s]*([^\\n]{{1,200}})", text)
        if m:
            return m.group(1).strip()
    return ""


def _detect_tag(text: str) -> dict:
    """自动检测标签和颜色（旧方法，保留兼容）"""
    tag_rules = [
        (["报名中", "正在报名", "开始报名"], "报名中", "#3b82f6"),
        (["即将报名", "即将开始"], "即将报名", "#f59e0b"),
        (["已截止", "报名截止", "结束"], "已截止", "#8a8faa"),
        (["笔试", "考试通知"], "笔试通知", "#c41e3a"),
        (["面试", "复审"], "面试/复审", "#10b981"),
        (["公示", "录用", "拟录用"], "公示", "#8b5cf6"),
        (["热门", "急招"], "热门", "#ef4444"),
    ]
    text_lower = text.lower()
    for keywords, tag, color in tag_rules:
        if any(kw in text_lower for kw in keywords):
            return {"tag": tag, "color": color}
    return {"tag": "最新", "color": "#10b981"}


def _detect_registration_status(start_str: str, end_str: str, full_text: str = "") -> dict:
    """
    智能检测报名状态，返回标签和颜色。
    优先级：日期比较 > 关键词检测 > 默认值

    状态颜色规范：
    - "正在报名": 绿色 #10b981
    - "即将报名": 藏蓝色 #1a2a6c
    - "报名结束": 中国红 #c41e3a
    """
    from datetime import datetime as dt

    def _parse_date(s: str):
        """尝试从字符串中解析日期"""
        import re
        patterns = [
            r"(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})[日]?",
            r"(\d{1,2})[-/月](\d{1,2})[日]?",
        ]
        for p in patterns:
            m = re.search(p, s)
            if m:
                groups = m.groups()
                if len(groups) == 3:
                    return dt(int(groups[0]), int(groups[1]), int(groups[2]))
                elif len(groups) == 2:
                    now = dt.now()
                    return dt(now.year, int(groups[0]), int(groups[1]))
        return None

    now = dt.now()
    start_dt = _parse_date(start_str) if start_str else None
    end_dt = _parse_date(end_str) if end_str else None

    # 日期比较
    if end_dt and end_dt < now:
        return {"tag": "报名结束", "color": "#c41e3a"}
    if start_dt and start_dt > now:
        return {"tag": "即将报名", "color": "#1a2a6c"}
    if start_dt and end_dt and start_dt <= now <= end_dt:
        return {"tag": "正在报名", "color": "#10b981"}

    # 关键词回退
    text_lower = full_text.lower()
    if any(kw in text_lower for kw in ["正在报名", "报名中", "进行中"]):
        return {"tag": "正在报名", "color": "#10b981"}
    if any(kw in text_lower for kw in ["即将报名", "即将开始", "预告"]):
        return {"tag": "即将报名", "color": "#1a2a6c"}
    if any(kw in text_lower for kw in ["已截止", "报名截止", "已结束", "结束"]):
        return {"tag": "报名结束", "color": "#c41e3a"}
    if any(kw in text_lower for kw in ["笔试", "考试通知"]):
        return {"tag": "笔试通知", "color": "#c41e3a"}
    if any(kw in text_lower for kw in ["面试", "复审"]):
        return {"tag": "面试/复审", "color": "#10b981"}
    if any(kw in text_lower for kw in ["公示", "录用", "拟录用"]):
        return {"tag": "公示", "color": "#8b5cf6"}

    return {"tag": "正在报名", "color": "#10b981"}


def _scrape_article_detail_playwright(page, url: str) -> dict:
    """使用Playwright抓取招考详情页，精确提取channel-main内容"""
    result = {
        "content": "", "content_html": "", "organization": "",
        "requirements": "", "registration_start": "", "registration_end": "",
        "deadline": "", "region": "", "tag": "", "tag_color": "",
        "images": [], "exam_format": "", "contact_info": "",
    }
    try:
        page.goto(url, wait_until='networkidle', timeout=30000)
        time.sleep(0.5)

        # 精确选择器: div.channel-main.clearfix
        main = page.query_selector('div.channel-main.clearfix')
        if not main:
            main = page.query_selector('div.channel-main')
        if not main:
            main = page.query_selector('div.article-content')

        if main:
            # 排除噪音div
            exclude_selectors = [
                'div.channel-article', 'div.channel-prompt', 'div.leftread',
                '.recommend', '.ad', '.sidebar',
            ]
            for sel in exclude_selectors:
                for el in main.query_selector_all(sel):
                    try:
                        el.evaluate('el => el.remove()')
                    except Exception:
                        pass

            result["content_html"] = main.inner_html()[:10000]
            result["content"] = main.inner_text()[:5000]

            # 提取图片
            for img in main.query_selector_all('img[src]'):
                src = img.get_attribute('src') or ''
                if src and not src.startswith('data:') and len(src) > 10:
                    alt = img.get_attribute('alt') or ''
                    full = urljoin(url, src) if not src.startswith('http') else src
                    result["images"].append({"url": full, "alt": alt})

        full_text = page.inner_text('body')

        # 提取报名时间
        time_pat = re.compile(r'报名时间[：:]?\s*(.+?)(?=\n\s*(?:考试|笔试|面试|联系|咨询|附件|\Z))', re.DOTALL)
        m = time_pat.search(full_text)
        if m:
            time_str = m.group(1).strip()[:200]
            parts = re.split(r'[-～~至]', time_str)
            if len(parts) == 2:
                result['registration_start'] = parts[0].strip()
                result['registration_end'] = parts[1].strip()
                result['deadline'] = parts[1].strip()

        # 提取考试方式
        if '笔试' in full_text and '面试' in full_text:
            result['exam_format'] = '笔试+面试'
        elif '笔试' in full_text:
            result['exam_format'] = '笔试'
        elif '面试' in full_text:
            result['exam_format'] = '面试'

        # 提取联系方式
        contact_pat = re.compile(r'(?:联系|咨询|电话)[：:]\s*(\S{5,30})')
        m = contact_pat.search(full_text)
        if m:
            result['contact_info'] = m.group(1)

        # 提取单位
        org_pat = re.compile(r'(?:发布单位|招聘单位|单位名称)[：:]\s*(\S{2,50})')
        m = org_pat.search(full_text)
        if m:
            result['organization'] = m.group(1)

        # 提取地区
        region_pat = re.compile(r'(?:工作地点|地区|省份)[：:]\s*(\S{2,20})')
        m = region_pat.search(full_text)
        if m:
            result['region'] = m.group(1)

        # 智能标签检测
        tag_info = _detect_registration_status(
            result["registration_start"], result["registration_end"], full_text
        )
        result["tag"] = tag_info["tag"]
        result["tag_color"] = tag_info["color"]

    except Exception as e:
        logger.warning(f"[recruitment/playwright] 详情抓取失败 {url}: {e}")
    return result


def _scrape_article_detail(url: str) -> dict:
    """
    抓取招考详情页，提取：
    - content（正文）、organization（发布单位）
    - requirements（招聘条件）、registration_start/end（报名时间）
    - region（地区）、tag（标签）
    """
    result = {
        "content": "", "organization": "", "requirements": "",
        "registration_start": "", "registration_end": "",
        "deadline": "", "region": "", "tag": "", "tag_color": "",
        "content_html": "", "images": [], "exam_format": "",
        "contact_info": "",
    }
    try:
        time.sleep(random.uniform(0.5, 1.5))
        resp = safe_request(url, timeout=10, label="recruitment/detail")
        if resp is None:
            return result
        resp.encoding = resp.apparent_encoding or 'utf-8'
        soup = BeautifulSoup(resp.text, "lxml")

        # 提取正文（纯文本 + 过滤HTML）
        content_selectors = [
            "div.article-content", "div.content", "div.article",
            "div.news-content", "article", "div.text", "div.main",
            "div.detail", "div.info-content",
        ]
        for selector in content_selectors:
            elem = soup.select_one(selector)
            if elem:
                # Remove noise elements
                for bad in elem.select('script, style, nav, footer, .ad, .sidebar, .recommend'):
                    bad.decompose()
                result["content_html"] = str(elem)[:10000]
                result["content"] = elem.get_text(separator="\n", strip=True)[:5000]
                # 提取正文中的图片
                for img in elem.select('img[src]'):
                    src = img.get('src', '')
                    if src and not src.startswith('data:'):
                        full = urljoin(url, src) if not src.startswith('http') else src
                        w = img.get('width', '0')
                        if not (w.isdigit() and int(w) < 50):
                            result["images"].append({"url": full, "alt": img.get('alt', '')})
                break

        full_text = soup.get_text()

        # 提取各字段
        result["organization"] = _extract_field(full_text,
            ["发布单位", "招聘单位", "单位名称", "用人单位", "工作单位"])
        result["requirements"] = _extract_field(full_text,
            ["招聘条件", "资格条件", "报考条件", "基本条件", "岗位要求", "任职要求"])
        result["registration_start"] = _extract_field(full_text,
            ["报名开始", "开始报名", "报名起始", "报名时间", "报名日期", "起止时间"])
        result["registration_end"] = _extract_field(full_text,
            ["报名截止", "截止日期", "截止时间", "报名结束", "结束日期", "结束时间"])
        result["deadline"] = result["registration_end"]  # 兼容旧字段
        result["region"] = _extract_field(full_text,
            ["工作地点", "地区", "省份", "城市", "地点"])

        # 检测考试方式（笔试/面试）
        if '笔试' in full_text and '面试' in full_text:
            result["exam_format"] = '笔试+面试'
        elif '笔试' in full_text:
            result["exam_format"] = '笔试'
        elif '面试' in full_text:
            result["exam_format"] = '面试'

        # 提取联系方式
        result["contact_info"] = _extract_field(full_text,
            ["联系电话", "联系方式", "咨询电话", "联系人", "电话"])

        # 智能标签检测：优先根据报名时间判断状态
        tag_info = _detect_registration_status(result["registration_start"], result["registration_end"], full_text)
        result["tag"] = tag_info["tag"]
        result["tag_color"] = tag_info["color"]

        return result
    except Exception as e:
        logger.warning(f"[recruitment/detail] 详情抓取失败 {url}: {e}")
        return result

# 6 个分类的爬取配置
CATEGORY_CONFIG = {
    "事业单位": {"url": "https://www.rszk.net/index.html", "kw": ["事业", "单位"]},
    "国考省考": {"url": "https://www.rszk.net/index.html", "kw": ["国考", "省考", "公务员"]},
    "教师招聘": {"url": "https://www.rszk.net/index.html", "kw": ["教师", "招聘", "教资"]},
    "国企招聘": {"url": "https://www.rszk.net/index.html", "kw": ["国企", "央企", "国家电网"]},
    "医疗卫生": {"url": "https://www.rszk.net/index.html", "kw": ["医疗", "医院", "卫生", "护理"]},
    "三支一扶": {"url": "https://www.rszk.net/index.html", "kw": ["三支一扶", "支教", "支农", "支医"]},
}


def scrape_category(db: Session, category: str, config: dict) -> int:
    """爬取指定分类的招考信息，返回新增数量。使用Playwright抓取详情页（channel-main精确提取）"""
    count = 0
    browser = None
    pw_instance = None
    try:
        logger.info(f"[recruitment/{category}] 开始爬取...")
        resp = safe_request(config["url"], label=f"recruitment/{category}")
        if resp is None:
            logger.error(f"[recruitment/{category}] 无法获取页面")
            return 0

        soup = BeautifulSoup(resp.text, "lxml")

        # 查找所有链接
        links = soup.select("a[href]")
        if not links:
            logger.warning(f"[recruitment/{category}] 页面无链接，尝试备用解析...")
            links = soup.find_all("a")

        seen_titles = set()
        category_items = []

        for link in links:
            title = link.get_text(strip=True)
            href = link.get("href", "")
            if not title or len(title) < 3:
                continue

            # 关键词匹配分类
            matched = any(kw in title for kw in config["kw"])
            if not matched:
                continue

            if title in seen_titles:
                continue
            seen_titles.add(title)

            # 补全链接
            if href and not href.startswith("http"):
                if href.startswith("/"):
                    href = "https://www.rszk.net" + href
                else:
                    href = "https://www.rszk.net/" + href

            category_items.append({"title": title, "url": href})
            if len(category_items) >= 10:
                break

        if not category_items:
            logger.warning(f"[recruitment/{category}] 未匹配到任何条目 (共扫描 {len(links)} 个链接)")

        # 启动 Playwright 浏览器（用于详情页抓取）
        if HAS_PLAYWRIGHT:
            try:
                pw_instance = sync_playwright().start()
                browser = pw_instance.chromium.launch(headless=True)
                logger.info(f"[recruitment/{category}] Playwright 浏览器已启动")
            except Exception as pw_err:
                logger.warning(f"[recruitment/{category}] Playwright 启动失败，回退到 requests: {pw_err}")
                browser = None

        # 创建共享 page 用于浏览详情页
        page = None
        if browser:
            try:
                page = browser.new_page()
            except Exception:
                page = None

        # 写入数据库（去重）
        for item in category_items:
            try:
                exists = db.query(RecruitmentInfo).filter(
                    RecruitmentInfo.title == item["title"],
                    RecruitmentInfo.category == category
                ).first()
                if exists:
                    continue

                # 抓取详情页：优先 Playwright，回退 requests
                if page:
                    detail = _scrape_article_detail_playwright(page, item["url"])
                else:
                    detail = _scrape_article_detail(item["url"])

                rec = RecruitmentInfo(
                    title=item["title"],
                    url=item["url"],
                    category=category,
                    organization=detail["organization"],
                    region=detail["region"],
                    content=detail["content"],
                    requirements=detail["requirements"],
                    registration_start=detail["registration_start"],
                    registration_end=detail["registration_end"],
                    deadline=detail["deadline"],
                    tag=detail["tag"],
                    tag_color=detail["tag_color"],
                    content_html=detail.get("content_html", ""),
                    images=detail.get("images", []),
                    exam_format=detail.get("exam_format", ""),
                    contact_info=detail.get("contact_info", ""),
                    status=1
                )
                db.add(rec)
                count += 1
            except Exception as insert_err:
                logger.warning(f"[recruitment/{category}] 插入失败 '{item['title'][:30]}': {insert_err}")
                continue

        if count > 0:
            db.commit()
            logger.info(f"[recruitment/{category}] 成功: 新增 {count} 条")
        else:
            logger.info(f"[recruitment/{category}] 完成: 无新数据")

    except Exception as e:
        db.rollback()
        logger.error(f"[recruitment/{category}] 爬取异常: {type(e).__name__}: {e}", exc_info=True)

    finally:
        # 关闭 Playwright 浏览器
        if page:
            try:
                page.close()
            except Exception:
                pass
        if browser:
            try:
                browser.close()
            except Exception:
                pass
        if pw_instance:
            try:
                pw_instance.stop()
            except Exception:
                pass

    return count


def scrape_all_recruitment():
    """执行全部分类招考爬取（由调度器调用）"""
    logger.info("=" * 40)
    logger.info("招考信息爬取任务开始")
    db = SessionLocal()
    try:
        total = 0
        failed = 0
        for category, config in CATEGORY_CONFIG.items():
            try:
                added = scrape_category(db, category, config)
                total += added
            except Exception as cat_err:
                failed += 1
                logger.error(f"[recruitment/{category}] 分类爬取失败: {cat_err}")

        logger.info(f"招考信息爬取完成: 新增 {total} 条, 失败 {failed} 个分类")
        logger.info("=" * 40)
    finally:
        db.close()
