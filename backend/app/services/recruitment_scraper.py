"""
招考信息爬虫 v5（requests + BeautifulSoup + 分页 + 数据安全）
来源: rszk.net — Empire CMS 服务端渲染，6个分类各自独立URL
策略:
  - 纯 HTTP 请求（不需要 Playwright），消除超时问题
  - BeautifulSoup 解析列表页 div.fxlist_Conday > ul > li
  - 自动检测 Empire CMS 分页（div.new_pagediv），逐页爬取
  - 先爬后清：全部爬取成功后一次性替换旧数据，失败保留历史数据
  - safe_request 带 UA 轮换 + 随机延迟 + 指数退避重试
选择器基于 2026-08-03 curl 验证的网站实际 HTML 结构
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
from .scraper_utils import safe_request, get_random_ua, REQUEST_DELAY_MIN, REQUEST_DELAY_MAX

logger = logging.getLogger(__name__)

# ============================================================
# 6 个分类的独立爬取配置
# ============================================================
CATEGORY_CONFIG = {
    # 国考省考 = 国家公务员考试(guokao) + 地方公务员考试(shengkao)
    "国考省考": {"urls": [
        "https://www.rszk.net/guokao/",
        "https://www.rszk.net/shengkao/",
    ]},
    "事业单位": {"urls": ["https://www.rszk.net/shiye/"]},
    "教师招聘": {"urls": ["https://www.rszk.net/jiaoshi/"]},
    "国企招聘": {"urls": ["https://www.rszk.net/qiye/"]},
    "医疗卫生": {"urls": ["https://www.rszk.net/yiliao/"]},
    "三支一扶": {"urls": ["https://www.rszk.net/sanzhi/"]},
}

# ============================================================
# CSS 选择器（基于 2026-08-03 网站实际结构验证）
# ============================================================
# 列表页
LIST_CONTAINER = 'div.fxlist_Conday'
LIST_ITEMS = 'div.fxlist_Conday ul li'
RECOM_ITEMS = 'div.fxlist_recom ul li a[href]'  # 推荐条目
PAGINATION = 'div.new_pagediv'
# 详情页
DETAIL_TITLE = 'div.channel-main.clearfix h1'
DETAIL_BODY = 'div.channel-text.pb30'
DETAIL_DATE = 'div.channel-laiyuan p.fl span'
DETAIL_SOURCE = 'div.channel-laiyuan p.fl a'

# 每分类最多爬取页数
MAX_PAGES_PER_CATEGORY = 5

# 操作类通知标题黑名单（作答须知/打印准考证/报考指南等噪音，全局过滤）
NOISE_TITLE_KEYWORDS = [
    "须知", "准考证", "报考指南", "考试大纲", "参考目录",
    "咨询电话", "温馨提示", "成绩查询", "分数线", "缴费",
]

# 附件文件扩展名（正文内下载链接识别）
ATTACHMENT_EXTENSIONS = (
    ".xls", ".xlsx", ".doc", ".docx", ".pdf", ".zip", ".rar", ".et", ".wps",
)
# 附件链接锚文本关键词
ATTACHMENT_ANCHOR_KEYWORDS = ("附件", "下载", "职位表", "附表", "表格")

# 报名时间正则（支持多种格式）
TIME_PATTERNS = [
    # 报名时间：2026年7月15日 至 2026年7月25日
    r'报名时间[：:\s]*(\d{4}年\d{1,2}月\d{1,2}日)\s*[至\-～~]\s*(\d{4}年\d{1,2}月\d{1,2}日)',
    # 报名时间：2026-07-15 至 2026-07-25
    r'报名时间[：:\s]*(\d{4}-\d{1,2}-\d{1,2})\s*[至\-～~]\s*(\d{4}-\d{1,2}-\d{1,2})',
    # 报名时间：7月15日—7月25日（不跨年）
    r'报名时间[：:\s]*(\d{1,2}月\d{1,2}日)\s*[至\-～~]\s*(\d{1,2}月\d{1,2}日)',
    # 报名时间：2026年7月15日～7月25日（省去年）
    r'报名时间[：:\s]*(\d{4}年\d{1,2}月\d{1,2}日)\s*[至\-～~]\s*(\d{1,2}月\d{1,2}日)',
]


def _safe_get_html(url: str, label: str = "") -> str:
    """
    安全获取页面 HTML，使用 safe_request 带重试机制。
    返回 HTML 字符串，失败返回空字符串。
    """
    prefix = f"[{label}] " if label else ""

    for attempt in range(3):
        try:
            delay = random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX)
            time.sleep(delay)

            import requests as req
            resp = req.get(
                url,
                headers={
                    "User-Agent": get_random_ua(),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                    "Accept-Encoding": "gzip, deflate",
                    "Connection": "keep-alive",
                    "Cache-Control": "max-age=0",
                },
                timeout=30,
            )
            resp.raise_for_status()
            # 自动检测编码
            if resp.apparent_encoding:
                resp.encoding = resp.apparent_encoding
            elif not resp.encoding or resp.encoding.lower() == 'iso-8859-1':
                # 尝试从 meta 标签检测
                m = re.search(rb'<meta[^>]+charset=["\']?([a-zA-Z0-9\-]+)', resp.content[:2048])
                if m:
                    resp.encoding = m.group(1).decode('ascii')
                else:
                    resp.encoding = 'utf-8'
            return resp.text

        except req.exceptions.Timeout:
            logger.warning(f"{prefix}请求超时 (尝试 {attempt+1}/3): {url}")
        except req.exceptions.ConnectionError as e:
            logger.warning(f"{prefix}连接错误 (尝试 {attempt+1}/3): {e}")
        except req.exceptions.HTTPError as e:
            logger.warning(f"{prefix}HTTP {e.response.status_code} (尝试 {attempt+1}/3): {url}")
        except Exception as e:
            logger.warning(f"{prefix}请求异常 (尝试 {attempt+1}/3): {type(e).__name__}: {e}")

        if attempt < 2:
            backoff = (attempt + 1) * 2
            time.sleep(backoff)

    logger.error(f"{prefix}请求最终失败: {url}")
    return ""


def _extract_time_range(text: str) -> dict:
    """从正文中提取报名起止时间"""
    for pattern in TIME_PATTERNS:
        m = re.search(pattern, text)
        if m:
            start_str = m.group(1).strip()
            end_str = m.group(2).strip()
            return {"registration_start": start_str, "registration_end": end_str}
    return {"registration_start": "", "registration_end": ""}


def _detect_tag(start_str: str, end_str: str, full_text: str) -> dict:
    """
    智能检测报名状态标签。
    优先级：日期比较 > 正文关键词 > 默认
    状态颜色：正在报名=#10b981(绿) 即将报名=#1a2a6c(藏蓝) 报名结束=#c41e3a(红)
    """
    def _parse(s: str):
        """尝试解析中/英文日期"""
        m = re.search(r'(\d{4})年?(\d{1,2})月(\d{1,2})日', s)
        if m:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        m = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', s)
        if m:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        m = re.search(r'(\d{1,2})月(\d{1,2})日', s)
        if m:
            now = datetime.now()
            return datetime(now.year, int(m.group(1)), int(m.group(2)))
        return None

    now = datetime.now()
    start_dt = _parse(start_str) if start_str else None
    end_dt = _parse(end_str) if end_str else None

    # 日期比较优先
    if end_dt and end_dt < now:
        return {"tag": "报名结束", "color": "#c41e3a"}
    if start_dt and start_dt > now:
        return {"tag": "即将报名", "color": "#1a2a6c"}
    if start_dt and end_dt and start_dt <= now <= end_dt:
        return {"tag": "正在报名", "color": "#10b981"}

    # 关键词回退
    t = full_text.lower()
    if any(kw in t for kw in ["正在报名", "报名中", "进行中"]):
        return {"tag": "正在报名", "color": "#10b981"}
    if any(kw in t for kw in ["即将报名", "即将开始", "预告"]):
        return {"tag": "即将报名", "color": "#1a2a6c"}
    if any(kw in t for kw in ["已截止", "报名截止", "已结束"]):
        return {"tag": "报名结束", "color": "#c41e3a"}
    if any(kw in t for kw in ["笔试", "考试通知"]):
        return {"tag": "笔试通知", "color": "#c41e3a"}
    if any(kw in t for kw in ["面试", "复审"]):
        return {"tag": "面试/复审", "color": "#10b981"}
    if any(kw in t for kw in ["公示", "录用", "拟录用"]):
        return {"tag": "公示", "color": "#8b5cf6"}

    return {"tag": "正在报名", "color": "#10b981"}


def _process_content_links(target, page_url: str):
    """
    增强正文中的链接：
      - 附件链接（扩展名命中或锚文本含 附件/下载/职位表/附表/表格）→ 绝对地址 + target=_blank
      - 非附件内联链接（如「点击进入」）→ unwrap 保留文字、去链接
    """
    for a in target.find_all('a', href=True):
        href = (a.get('href') or '').strip()
        if not href:
            a.unwrap()
            continue
        anchor = a.get_text(strip=True)
        is_attachment = href.lower().endswith(ATTACHMENT_EXTENSIONS) or \
            any(k in anchor for k in ATTACHMENT_ANCHOR_KEYWORDS)
        if is_attachment:
            full_url = urljoin(page_url, href) if not href.startswith('http') else href
            a['href'] = full_url
            a['target'] = '_blank'
            a['rel'] = 'noopener'
        else:
            a.unwrap()


def _is_noise_title(title: str) -> bool:
    """操作类通知标题过滤（作答须知/打印准考证/报考指南等）"""
    return any(k in title for k in NOISE_TITLE_KEYWORDS)


def _parse_detail_page(html: str, url: str) -> dict:
    """
    解析详情页 HTML，提取标题/正文/图片/报名时间/考试方式/联系方式等。
    返回 dict，所有字段有默认值。
    """
    result = {
        "title": "", "content": "", "content_html": "", "organization": "",
        "registration_start": "", "registration_end": "",
        "deadline": "", "region": "", "tag": "", "tag_color": "",
        "images": [], "exam_format": "", "contact_info": "", "publish_date": "",
    }
    try:
        soup = BeautifulSoup(html, 'lxml')

        # ---- 标题 ----
        for h in soup.select(DETAIL_TITLE):
            t = h.get_text(strip=True)
            if t:
                result["title"] = t
                break

        # ---- 发布时间 ----
        date_span = soup.select_one(DETAIL_DATE)
        if date_span:
            result["publish_date"] = date_span.get_text(strip=True)

        # ---- 正文 HTML ----
        body_div = soup.select_one(DETAIL_BODY)
        if body_div:
            # 优先取 gb_article_body 内的内容
            article_body = body_div.select_one('#gb_article_body')
            target = article_body if article_body else body_div

            # 提取图片
            for img in target.find_all('img', src=True):
                src = img.get('src', '')
                if src and not src.startswith('data:') and len(src) > 10:
                    alt = img.get('alt', '')
                    full_url = urljoin(url, src) if not src.startswith('http') else src
                    result["images"].append({"url": full_url, "alt": alt})

            # 附件链接增强 + 非附件内联链接清洗（「点击进入」→纯文本）
            _process_content_links(target, url)

            result["content_html"] = str(target)
            result["content"] = target.get_text(separator='\n', strip=True)

        # ---- 从正文提取各字段 ----
        full_text = result["content"] or soup.get_text()

        # 报名时间
        time_info = _extract_time_range(full_text)
        result["registration_start"] = time_info["registration_start"]
        result["registration_end"] = time_info["registration_end"]
        result["deadline"] = time_info["registration_end"]

        # 考试方式
        if '笔试' in full_text and '面试' in full_text:
            result['exam_format'] = '笔试+面试'
        elif '笔试' in full_text:
            result['exam_format'] = '笔试'
        elif '面试' in full_text:
            result['exam_format'] = '面试'

        # 联系方式
        contact_pat = re.compile(r'(?:联系电话|联系方式|咨询电话|联系人|电话)[：:]\s*(\S{5,30})')
        m = contact_pat.search(full_text)
        if m:
            result['contact_info'] = m.group(1)

        # 发布单位
        org_pat = re.compile(r'(?:发布单位|招聘单位|单位名称|用人单位|工作单位)[：:]\s*(\S{2,50})')
        m = org_pat.search(full_text)
        if m:
            result['organization'] = m.group(1)

        # 地区
        region_pat = re.compile(r'(?:工作地点|地区|省份)[：:]\s*(\S{2,20})')
        m = region_pat.search(full_text)
        if m:
            result['region'] = m.group(1)

        # 状态标签
        tag_info = _detect_tag(result["registration_start"], result["registration_end"], full_text)
        result["tag"] = tag_info["tag"]
        result["tag_color"] = tag_info["color"]

    except Exception as e:
        logger.warning(f"[recruitment/detail] 详情解析失败 {url}: {type(e).__name__}: {e}")

    return result


def _extract_list_items(html: str, base_url: str) -> list:
    """
    从分类列表页 HTML 提取所有招考条目链接。
    主选择器: div.fxlist_Conday ul li
    备用选择器: div.fxlist_recom ul li a
    返回 [{title, url, date}, ...]
    """
    soup = BeautifulSoup(html, 'lxml')
    items = []
    seen_titles = set()

    def _add_link(title: str, href: str, date_str: str = ""):
        if not title or len(title) < 5:
            return
        if _is_noise_title(title):
            return
        if title in seen_titles:
            return
        if title in ['首页', '上一页', '下一页', '末页', '返回列表']:
            return
        seen_titles.add(title)
        full_url = urljoin(base_url, href) if not href.startswith('http') else href
        items.append({"title": title, "url": full_url, "date": date_str})

    # 方式1: fxlist_Conday 列表（主要）
    for li in soup.select(LIST_ITEMS):
        try:
            links = li.find_all('a', href=True)
            if not links:
                continue
            # 最后一个 <a> 是文章标题链接
            article_link = links[-1]
            title = article_link.get_text(strip=True)
            href = article_link.get('href', '')
            if not href:
                continue
            time_tag = li.find('time')
            date_str = time_tag.get_text(strip=True) if time_tag else ""
            _add_link(title, href, date_str)
        except Exception:
            continue

    # 方式2: fxlist_recom 推荐条目（备用）
    for a in soup.select(RECOM_ITEMS):
        try:
            title = a.get_text(strip=True)
            href = a.get('href', '')
            if href:
                _add_link(title, href)
        except Exception:
            continue

    # 方式3: 通用备用 — 任何包含 .html 的文章链接
    if not items:
        logger.warning("[recruitment/list] 主选择器无结果，尝试通用提取...")
        all_links = soup.find_all('a', href=re.compile(r'\.html$'))
        for a in all_links:
            try:
                title = a.get_text(strip=True)
                href = a.get('href', '')
                _add_link(title, href)
            except Exception:
                continue

    logger.info(f"[recruitment/list] 共提取 {len(items)} 条有效条目")
    return items


def _extract_pages(html: str, base_url: str) -> list:
    """
    从分页区域提取所有页码 URL。
    Empire CMS 格式: index_2.html, index_3.html ...
    返回 [page1_url, page2_url, ...]，最多 MAX_PAGES_PER_CATEGORY 页
    """
    soup = BeautifulSoup(html, 'lxml')
    pages = [base_url]

    pagediv = soup.select_one(PAGINATION)
    if not pagediv:
        return pages

    for a in pagediv.find_all('a', href=True):
        href = a['href']
        if 'index_' in href:
            full = urljoin(base_url, href)
            if full not in pages:
                pages.append(full)
                if len(pages) >= MAX_PAGES_PER_CATEGORY:
                    break

    # 按页码排序（index_2 < index_3 < ...）
    def _page_num(u):
        m = re.search(r'index_(\d+)', u)
        return int(m.group(1)) if m else 1

    pages.sort(key=_page_num)
    return pages


def scrape_category(category: str, config: dict) -> list:
    """
    爬取指定分类的招考信息，返回招募信息 dict 列表（不写入DB）。
    流程：
      1. 获取列表页第一页
      2. 检测分页，构建完整URL列表
      3. 逐页解析条目链接
      4. 逐个获取详情页并解析
      5. 返回所有 RecruitmentInfo 构造参数字典列表

    失败时返回空列表，由上层 scrape_all_recruitment 汇总。
    """
    records = []
    seen_titles = set()

    # 一个分类可对应多个 URL（如 国考省考 = guokao + shengkao），逐个爬取后合并
    for base_url in config["urls"]:
        try:
            logger.info(f"[recruitment/{category}] 开始爬取 ({base_url})")

            # ---- 第1步: 获取首页 ----
            html = _safe_get_html(base_url, f"recruitment/{category}")
            if not html:
                logger.error(f"[recruitment/{category}] 首页获取失败 {base_url}")
                continue

            # ---- 第2步: 获取所有分页 ----
            page_urls = _extract_pages(html, base_url)
            logger.info(f"[recruitment/{category}] 检测到 {len(page_urls)} 页")

            # ---- 第3步: 逐页提取条目 ----
            all_items = []
            for page_url in page_urls:
                if page_url != base_url:
                    page_html = _safe_get_html(page_url, f"recruitment/{category}")
                    if not page_html:
                        continue
                    page_items = _extract_list_items(page_html, page_url)
                else:
                    page_items = _extract_list_items(html, page_url)

                all_items.extend(page_items)
                logger.info(f"[recruitment/{category}] 第 {page_urls.index(page_url)+1}/{len(page_urls)} 页: {len(page_items)} 条")

                # 页间延迟（反爬）
                if len(page_urls) > 1:
                    time.sleep(random.uniform(1.5, 3.0))

            if not all_items:
                logger.warning(f"[recruitment/{category}] {base_url} 列表页未提取到任何条目")
                continue

            # ---- 第4步: 逐个获取详情并构建记录 ----
            for item in all_items:
                try:
                    title = item["title"]
                    # 同分类内去重
                    if title in seen_titles:
                        continue
                    seen_titles.add(title)

                    # 获取详情页
                    detail_html = _safe_get_html(item["url"], f"recruitment/{category}/detail")
                    if not detail_html:
                        # 详情页获取失败，用列表页信息创建基础记录
                        records.append({
                            "title": title,
                            "url": item["url"],
                            "category": category,
                            "content": "",
                            "content_html": "",
                            "tag": "正在报名",
                            "tag_color": "#10b981",
                        })
                        continue

                    # 解析详情
                    detail = _parse_detail_page(detail_html, item["url"])

                    # 优先用详情页标题
                    final_title = detail["title"] or title

                    records.append({
                        "title": final_title,
                        "url": item["url"],
                        "category": category,
                        "organization": detail["organization"],
                        "region": detail["region"],
                        "content": detail["content"],
                        "content_html": detail.get("content_html", ""),
                        "registration_start": detail["registration_start"],
                        "registration_end": detail["registration_end"],
                        "deadline": detail["deadline"],
                        "tag": detail["tag"],
                        "tag_color": detail["tag_color"],
                        "images": detail.get("images", []),
                        "exam_format": detail.get("exam_format", ""),
                        "contact_info": detail.get("contact_info", ""),
                        # 源站发布日期：详情页优先，列表页日期兜底
                        "publish_date": detail.get("publish_date", "") or item.get("date", "") or "",
                    })

                    # 条间延迟（反爬）
                    time.sleep(random.uniform(0.5, 1.5))

                except Exception as e:
                    logger.warning(f"[recruitment/{category}] 处理失败 '{item['title'][:40]}': {type(e).__name__}: {e}")
                    continue

        except Exception as e:
            logger.error(f"[recruitment/{category}] 爬取异常 {base_url}: {type(e).__name__}: {e}", exc_info=True)

    logger.info(f"[recruitment/{category}] ✓ 成功: {len(records)} 条")
    return records


def _replace_category(db: Session, category: str, records: list) -> int:
    """分类独立更新：删除该分类旧数据并插入新数据（单事务）"""
    deleted = db.query(RecruitmentInfo).filter(
        RecruitmentInfo.category == category
    ).delete(synchronize_session=False)
    for rec_data in records:
        rec = RecruitmentInfo(
            title=rec_data["title"],
            url=rec_data.get("url", ""),
            category=category,
            organization=rec_data.get("organization", ""),
            region=rec_data.get("region", ""),
            content=rec_data.get("content", ""),
            content_html=rec_data.get("content_html", ""),
            requirements=rec_data.get("requirements", ""),
            registration_start=rec_data.get("registration_start", ""),
            registration_end=rec_data.get("registration_end", ""),
            deadline=rec_data.get("deadline", ""),
            tag=rec_data.get("tag", "正在报名"),
            tag_color=rec_data.get("tag_color", "#10b981"),
            images=rec_data.get("images", []),
            exam_format=rec_data.get("exam_format", ""),
            contact_info=rec_data.get("contact_info", ""),
            publish_date=rec_data.get("publish_date", "") or "",
            status=1,
        )
        db.add(rec)
    db.commit()
    return deleted


def scrape_all_recruitment():
    """
    全量爬取入口（由调度器 scheduler.py 调用）。

    数据安全策略（v6 — 分类独立更新）:
      每个分类爬取成功后，立即替换该分类的数据（DELETE 该分类 → INSERT 新数据 → COMMIT）。
      某分类失败 → 仅该分类保留旧数据，其他分类正常更新。
      彻底解决 v5"全部分类成功才替换"导致的"一个分类拖垮全局、数据长期不更新"问题。
    """
    logger.info("=" * 60)
    logger.info("招考信息爬取任务开始 (v6 — 分类独立更新)")
    db = SessionLocal()
    total = 0
    failed_cats = []
    try:
        for category, config in CATEGORY_CONFIG.items():
            try:
                records = scrape_category(category, config)
                if records:
                    deleted = _replace_category(db, category, records)
                    total += len(records)
                    logger.info(
                        f"[recruitment/{category}] 独立更新完成: "
                        f"删除 {deleted} 条旧数据, 插入 {len(records)} 条新数据"
                    )
                else:
                    logger.warning(f"[recruitment/{category}] 未获取到数据，保留该分类旧数据")
                # 分类间间隔（反爬）
                if category != list(CATEGORY_CONFIG.keys())[-1]:
                    time.sleep(random.uniform(2.0, 4.0))
            except Exception as e:
                failed_cats.append(category)
                db.rollback()
                logger.error(
                    f"[recruitment/{category}] 分类爬取失败（保留该分类旧数据）: "
                    f"{type(e).__name__}: {e}"
                )

        logger.info(f"招考信息爬取完成: 更新 {total} 条")
        if failed_cats:
            logger.warning(f"失败分类（保留旧数据）: {', '.join(failed_cats)}")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"招考信息爬取全局异常: {type(e).__name__}: {e}", exc_info=True)
    finally:
        db.close()
