"""
考试日历爬虫（结构化重写版）
来源: shiyebian.com — .rb_news-list > .rb_news-item > .rb_news-content
提取: 标题 / 链接 / 招聘人数 / 报名时间 / 考试形式
"""
import logging
import re
from datetime import datetime, timedelta
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session
from ..core.database import SessionLocal
from ..models.models import ExamCalendar
from .scraper_utils import safe_request

logger = logging.getLogger(__name__)

# 省份关键词（用于从标题中提取地区）
PROVINCES = [
    "北京", "天津", "上海", "重庆", "河北", "山西", "辽宁", "吉林",
    "黑龙江", "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南",
    "湖北", "湖南", "广东", "广西", "海南", "四川", "贵州", "云南",
    "西藏", "陕西", "甘肃", "青海", "宁夏", "新疆", "内蒙古", "全国", "中央",
]


def _extract_province(title: str) -> str:
    """从标题中提取省份"""
    for p in PROVINCES:
        if p in title:
            return p
    return ""


def _extract_date_from_meta(text: str) -> tuple:
    """
    从报名时间文本中提取月/日。
    例: "报名: 6月22日至7月2日" → (6, 22)
    例: "报名: 2026年6月22日至7月2日" → (6, 22)
    """
    patterns = [
        r"(\d{1,2})月(\d{1,2})日",       # 6月22日
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            return int(m.group(1)), int(m.group(2))
    return None, None


def _detect_exam_format(meta_divs) -> str:
    """
    从 .rb_news-meta 的 div 中提取完整考试形式文本。
    例: "笔试:《职业能力倾向测验》《综合应用能力》"
    """
    formats = []
    for div in meta_divs:
        div_html = str(div)
        div_text = div.get_text(strip=True)
        # 图标检测 + 关键词检测
        if "fa-bishi" in div_html or "笔试" in div_text:
            if div_text not in formats:
                formats.append(div_text)
        elif "fa-mianshi" in div_html or "面试" in div_text:
            if div_text not in formats:
                formats.append(div_text)
    return "；".join(formats)


def _parse_registration_time(meta_divs) -> str:
    """从 .rb_news-meta 中提取报名时间文本"""
    for div in meta_divs:
        div_html = str(div)
        div_text = div.get_text(strip=True)
        # 图标检测 或 关键词检测
        if "fa-baoming" in div_html or "报名" in div_text:
            # 去掉 "报名:" 前缀
            text = re.sub(r"^报名[：:\s]*", "", div_text)
            return text
    return ""


def _scrape_exam_detail(url: str) -> dict:
    """进入考试详情页，抓取完整信息（requests 回退方案）"""
    result = {'registration_start': '', 'registration_end': '', 'exam_format': '',
              'description': '', 'images': []}
    try:
        resp = safe_request(url, timeout=15, label="exam/detail")
        if resp is None:
            return result
        resp.encoding = resp.apparent_encoding or 'utf-8'
        soup = BeautifulSoup(resp.text, 'lxml')

        # 提取正文
        for selector in ['div.article-content', 'div.content', 'div.article', 'article', 'div.main']:
            elem = soup.select_one(selector)
            if elem:
                for bad in elem.select('script, style, nav, footer, .ad'):
                    bad.decompose()
                result['description'] = str(elem)[:10000]
                break

        full_text = soup.get_text()

        # 提取报名时间
        time_pat = re.compile(r'报名时间[：:]\s*(.+?)(?:\n|$)')
        m = time_pat.search(full_text)
        if m:
            time_str = m.group(1).strip()
            parts = re.split(r'[-～~至]', time_str)
            if len(parts) == 2:
                result['registration_start'] = parts[0].strip()
                result['registration_end'] = parts[1].strip()

        # 提取考试方式
        if '笔试' in full_text and '面试' in full_text:
            result['exam_format'] = '笔试+面试'
        elif '笔试' in full_text:
            result['exam_format'] = '笔试'
        elif '面试' in full_text:
            result['exam_format'] = '面试'

        # 提取图片
        for img in soup.select('img[src]'):
            src = img.get('src', '')
            if src and not src.startswith('data:'):
                result['images'].append(urljoin(url, src) if not src.startswith('http') else src)
    except Exception as e:
        logger.warning(f"[exam/detail] 详情抓取失败 {url}: {e}")
    return result


def _scrape_exam_detail_playwright(page, url):
    """使用Playwright抓取考试详情页完整内容"""
    result = {'registration_start': '', 'registration_end': '', 'exam_format': '',
              'description': '', 'content_html': '', 'recruitment_count': ''}
    try:
        page.goto(url, wait_until='networkidle', timeout=30000)
        import time; time.sleep(1)

        # 精确选择器: div.ws-content.ws-card
        content_elem = page.query_selector('div.ws-content.ws-card')
        if not content_elem:
            content_elem = page.query_selector('div.ws-content')
        if not content_elem:
            content_elem = page.query_selector('div.article-content')

        if content_elem:
            result['content_html'] = content_elem.inner_html()[:10000]
            result['description'] = content_elem.inner_text()[:5000]

        full_text = page.inner_text('body')

        # 提取报名时间 (多行版)
        time_pat = re.compile(r'报名时间[：:]?\s*(.+?)(?=\n\s*(?:考试|笔试|面试|联系|咨询|附件|\Z))', re.DOTALL)
        m = time_pat.search(full_text)
        if m:
            time_str = m.group(1).strip()[:200]
            parts = re.split(r'[-～~至]', time_str)
            if len(parts) == 2:
                result['registration_start'] = parts[0].strip()
                result['registration_end'] = parts[1].strip()

        # 提取考试方式
        if '笔试' in full_text and '面试' in full_text:
            result['exam_format'] = '笔试+面试'
        elif '笔试' in full_text:
            result['exam_format'] = '笔试'
        elif '面试' in full_text:
            result['exam_format'] = '面试'

        # 提取招聘人数
        count_pat = re.compile(r'(?:招聘|招录|拟招聘|拟招录)\s*(\d+)\s*(?:名|人|个)')
        m = count_pat.search(full_text)
        if m:
            result['recruitment_count'] = m.group(1)

    except Exception as e:
        logger.warning(f"[exam/playwright] 详情抓取失败: {e}")
    return result


def _parse_date_str(date_str: str, default_year: int = None) -> datetime:
    """
    解析日期字符串为 datetime 对象。
    支持: "2026年6月22日", "6月22日", "2026-06-22"
    """
    if not date_str:
        return None
    if default_year is None:
        default_year = datetime.now().year

    # 匹配 "YYYY年M月D日" 或 "M月D日"
    m = re.search(r'(?:(\d{4})年)?(\d{1,2})月(\d{1,2})日', date_str)
    if m:
        year = int(m.group(1)) if m.group(1) else default_year
        month = int(m.group(2))
        day = int(m.group(3))
        return datetime(year, month, day)

    # 匹配 "YYYY-MM-DD"
    m = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', date_str)
    if m:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    return None


def scrape_exams_from_shiyebian(db: Session) -> int:
    """爬取 shiyebian.com 的结构化考试信息（Playwright 详情抓取），返回新增数量"""
    count = 0
    p = browser = page = None
    try:
        url = "https://www.shiyebian.com/"
        logger.info("[exam] 开始爬取 shiyebian.com 考试日历...")
        resp = safe_request(url, label="exam")
        if resp is None:
            logger.error("[exam] 无法获取 shiyebian.com 页面")
            return 0

        soup = BeautifulSoup(resp.text, "lxml")

        # === Step 1: 定位 .rb_news-list > .rb_news-item ===
        items = soup.select(".rb_news-list .rb_news-item")
        if not items:
            # 备用：直接查找 .rb_news-item
            items = soup.select(".rb_news-item")
        if not items:
            # 备用2：查找 .rb_card-body 下的所有链接
            logger.warning("[exam] 未找到 .rb_news-item，尝试备用解析...")
            items = soup.select(".rb_card-body a.rb_news-title")

        logger.info(f"[exam] 找到 {len(items)} 个招考条目")

        seen_titles = set()
        exam_items = []

        for item in items:
            try:
                # 如果是 a 标签（备用模式）
                if item.name == "a":
                    title_a = item
                    content = item.find_parent("div")
                    if content is None:
                        content = item.parent
                else:
                    # 标准模式：li.rb_news-item
                    content = item.select_one(".rb_news-content")
                    if content is None:
                        continue
                    title_a = content.select_one("a.rb_news-title")

                if title_a is None:
                    continue

                # === Step 2: 提取标题和链接 ===
                # 去掉 count-badge 获取纯标题
                count_badge = title_a.select_one(".count-badge")
                if count_badge:
                    count_badge.decompose()  # 移除 badge
                title = title_a.get_text(strip=True)

                href = title_a.get("href", "")
                if not title or len(title) < 4:
                    continue

                # 补全 URL
                if href and not href.startswith("http"):
                    if href.startswith("/"):
                        href = "https://www.shiyebian.com" + href
                    else:
                        href = "https://www.shiyebian.com/" + href

                # 去重
                if title in seen_titles:
                    continue
                seen_titles.add(title)

                # === Step 3: 解析 .rb_news-meta ===
                meta_divs = []
                if content and content.name != "a":
                    meta_divs = content.select(".rb_news-meta > div")
                registration_time = _parse_registration_time(meta_divs)
                exam_format = _detect_exam_format(meta_divs)

                # === Step 4: 日期提取 ===
                month, day = _extract_date_from_meta(registration_time)
                if month is None:
                    # 回退：从标题提取
                    month, day = _extract_date_from_meta(title)
                if month is None:
                    month = datetime.now().month
                    day = datetime.now().day

                # === Step 5: 省份提取 ===
                province = _extract_province(title)

                exam_items.append({
                    "title": title,
                    "url": href,
                    "month": month,
                    "day": day,
                    "province": province,
                    "registration_time": registration_time,
                    "exam_format": exam_format,
                })

                if len(exam_items) >= 20:
                    break

            except Exception as parse_err:
                logger.warning(f"[exam] 解析条目失败: {parse_err}")
                continue

        # === 启动 Playwright 浏览器（用于详情页抓取） ===
        try:
            from playwright.sync_api import sync_playwright
            p = sync_playwright().start()
            browser = p.chromium.launch(headless=True, args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ])
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                locale="zh-CN",
            )
            page = context.new_page()
            logger.info("[exam] Playwright 浏览器已启动（chromium headless）")
        except Exception as pw_err:
            logger.warning(f"[exam] Playwright 启动失败，将使用 requests 回退: {pw_err}")
            # 回退方案：使用原有的 requests 详情抓取
            now_year_fallback = datetime.now().year
            for item in exam_items:
                try:
                    exists = db.query(ExamCalendar).filter(
                        ExamCalendar.title == item["title"]
                    ).first()
                    if exists:
                        continue
                    detail = _scrape_exam_detail(item["url"])
                    m = int(item["month"])
                    d = int(item["day"])
                    exam_date = datetime(now_year_fallback, m, d)
                    reg_start = None; reg_end = None
                    if detail.get('registration_start'):
                        try: reg_start = _parse_date_str(detail['registration_start'], now_year_fallback)
                        except Exception: pass
                    if detail.get('registration_end'):
                        try: reg_end = _parse_date_str(detail['registration_end'], now_year_fallback)
                        except Exception: pass
                    exam_format = detail.get('exam_format') or item.get('exam_format', '')
                    description = detail.get('description') or item.get('registration_time', '')
                    exam = ExamCalendar(
                        title=item["title"], exam_date=exam_date,
                        month=str(m), day=str(d),
                        province=item["province"], exam_format=exam_format,
                        url=item["url"], description=description[:10000] if description else '',
                        content_html='', recruitment_count='',
                        registration_start=reg_start, registration_end=reg_end, status=1,
                    )
                    db.add(exam)
                    count += 1
                except Exception as insert_err:
                    logger.warning(f"[exam] 插入失败 '{item['title'][:30]}': {insert_err}")
            db.commit()
            return count

        # === 写入数据库（使用 Playwright 抓取详情） ===
        now_year = datetime.now().year
        for item in exam_items:
            try:
                exists = db.query(ExamCalendar).filter(
                    ExamCalendar.title == item["title"]
                ).first()
                if exists:
                    continue

                # 使用 Playwright 进入详情页抓取完整信息
                detail = _scrape_exam_detail_playwright(page, item["url"])

                # 构造 exam_date
                m = int(item["month"])
                d = int(item["day"])
                exam_date = datetime(now_year, m, d)

                # 解析报名时间
                reg_start = None
                reg_end = None
                if detail.get('registration_start'):
                    try:
                        reg_start = _parse_date_str(detail['registration_start'], now_year)
                    except Exception:
                        pass
                if detail.get('registration_end'):
                    try:
                        reg_end = _parse_date_str(detail['registration_end'], now_year)
                    except Exception:
                        pass

                # 优先使用详情页的 exam_format
                exam_format = detail.get('exam_format') or item.get('exam_format', '')

                # 构建描述
                description = detail.get('description') or item.get('registration_time', '')

                exam = ExamCalendar(
                    title=item["title"],
                    exam_date=exam_date,
                    month=str(m),
                    day=str(d),
                    province=item["province"],
                    exam_format=exam_format,
                    url=item["url"],
                    description=description[:10000] if description else '',
                    content_html=detail.get('content_html', '')[:10000] if detail.get('content_html') else '',
                    recruitment_count=detail.get('recruitment_count', '') or '',
                    registration_start=reg_start,
                    registration_end=reg_end,
                    status=1,
                )
                db.add(exam)
                count += 1
            except Exception as insert_err:
                logger.warning(f"[exam] 插入失败 '{item['title'][:30]}': {insert_err}")
                continue

        if count > 0:
            db.commit()
            logger.info(f"[exam] 成功: 新增 {count} 条考试信息 (共解析 {len(exam_items)} 条)")
        else:
            logger.info(f"[exam] 完成: 无新数据 (共解析 {len(exam_items)} 条)")

    except Exception as e:
        db.rollback()
        logger.error(f"[exam] 爬取异常: {type(e).__name__}: {e}", exc_info=True)
    finally:
        # 关闭 Playwright 浏览器
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


def cleanup_expired_exams(db: Session = None) -> int:
    """硬删除注册已截止且超过1天的记录（优先使用 registration_end）"""
    from datetime import datetime as dt, timedelta
    own_db = db is None
    if own_db:
        db = SessionLocal()
    try:
        cutoff = dt.now() - timedelta(days=1)
        deleted = db.query(ExamCalendar).filter(
            (ExamCalendar.registration_end < cutoff) |
            ((ExamCalendar.registration_end == None) & (ExamCalendar.exam_date < cutoff))
        ).delete(synchronize_session=False)
        db.commit()
        if deleted > 0:
            logger.info(f"[exam] 清理过期数据: {deleted} 条 (registration_end/exam_date < {cutoff.strftime('%Y-%m-%d')})")
        return deleted
    except Exception as e:
        db.rollback()
        logger.error(f"[exam] 清理过期数据失败: {e}")
        return 0
    finally:
        if own_db:
            db.close()


def clear_all_exams():
    """清空全部考试日历数据（一次性操作）"""
    db = SessionLocal()
    try:
        count = db.query(ExamCalendar).delete(synchronize_session=False)
        db.commit()
        logger.info(f"[exam] 清空全部数据: {count} 条")
        return count
    finally:
        db.close()


def scrape_all_exams():
    """执行全部考试日历爬取 — 先清理过期，再爬取最新"""
    db = SessionLocal()
    try:
        cleanup_expired_exams(db)  # 先清理过期
        total = scrape_exams_from_shiyebian(db)  # 再爬取最新
        logger.info(f"考试日历爬取完成，共新增 {total} 条")
    finally:
        db.close()
