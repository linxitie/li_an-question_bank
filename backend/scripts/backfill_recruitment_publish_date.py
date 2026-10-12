"""
招考信息「源站发布日期」回填脚本
=================================
背景：
    爬虫早已抓到详情页发布日期（recruitment_scraper.DETAIL_DATE），但历史上从未落库——
    recruitment_info 表没有该列。结果接口只能按 create_time 排序，而 create_time 是
    「爬取插入时刻」（同一批 178 条跨度仅 98 微秒），叠加爬虫按页码 1→5 插入，
    最终把**最旧**内容排在最前，即用户看到的"内容永远不更新"。

本脚本：
    复用既有 safe_request（UA 轮换 + 随机延迟 + 指数退避）与 DETAIL_DATE 选择器，
    逐条重取已存 url 的详情页，补齐 publish_date（YYYY-MM-DD）。

特性：
    - 幂等：仅处理 publish_date 为空的行，重复运行安全
    - 默认 dry-run：不加 --apply 一律零写入
    - 抗错：单条失败不中断整轮，计入 failed 并继续
    - 限速：safe_request 内建 1.0~2.5s 随机间隔，叠加本脚本的分类级间隔

用法：
    python scripts/backfill_recruitment_publish_date.py --dry-run                    # 预览（默认）
    python scripts/backfill_recruitment_publish_date.py --dry-run --limit 20         # 小批预览
    python scripts/backfill_recruitment_publish_date.py --apply --category 国考省考   # 只回填一个分类
    python scripts/backfill_recruitment_publish_date.py --apply                      # 全量（耗时较长）

注意：
    全量约 800 条、每条含随机间隔，预计 40~60 分钟。建议夜间低峰执行。
"""
import sys
import os
import re
import time
import random
import argparse
import logging
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import or_
from bs4 import BeautifulSoup
from app.core.database import SessionLocal
from app.models.models import RecruitmentInfo
from app.services.scraper_utils import safe_request
from app.services.recruitment_scraper import DETAIL_DATE

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def normalize_date(raw: str) -> str:
    """把源站各种日期写法归一为 YYYY-MM-DD；无法识别返回空串。

    覆盖：'2026-05-25' / '2026/05/25' / '2026年5月25日' / '05-25'（补当年）
    """
    if not raw:
        return ""
    text = raw.strip()

    m = re.search(r"(20\d{2})\s*[-/年]\s*(\d{1,2})\s*[-/月]\s*(\d{1,2})", text)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            return f"{y:04d}-{mo:02d}-{d:02d}"

    # 仅有月日（如 '05-25'）→ 视为当年
    m = re.search(r"(?<!\d)(\d{1,2})\s*[-/月]\s*(\d{1,2})(?!\d)", text)
    if m:
        mo, d = int(m.group(1)), int(m.group(2))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            return f"{datetime.now().year:04d}-{mo:02d}-{d:02d}"

    return ""


def extract_publish_date(html: str) -> str:
    """复用爬虫的 DETAIL_DATE 选择器抽取发布日期并归一化。"""
    try:
        soup = BeautifulSoup(html, 'lxml')
        node = soup.select_one(DETAIL_DATE)
        if node:
            return normalize_date(node.get_text(strip=True))
    except Exception as e:
        logger.debug(f"[backfill] 日期解析异常: {type(e).__name__}: {e}")
    return ""


def fetch_publish_date(url: str) -> str:
    """抓取单个详情页的发布日期；失败返回空串（不抛异常）。"""
    resp = safe_request(url, label="backfill")
    if resp is None or resp.status_code != 200:
        return ""
    try:
        resp.encoding = resp.apparent_encoding or 'utf-8'
    except Exception:
        pass
    return extract_publish_date(resp.text)


def main():
    parser = argparse.ArgumentParser(description="招考信息源站发布日期回填")
    parser.add_argument("--dry-run", action="store_true",
                        help="仅报告不写库（默认行为，显式声明以对齐项目脚本惯例）")
    parser.add_argument("--apply", action="store_true",
                        help="实际写入数据库（默认 dry-run，不写库）")
    parser.add_argument("--limit", type=int, default=0,
                        help="最多处理多少条（0 = 不限）")
    parser.add_argument("--category", default="",
                        help="只处理指定分类，留空则全部")
    parser.add_argument("--delay", type=float, default=2.0,
                        help="每条之间的额外附加间隔秒数（默认 2.0）")
    args = parser.parse_args()

    mode = "APPLY（写库）" if args.apply else "DRY-RUN（只读，不写库）"

    db = SessionLocal()
    scanned = filled = skipped = failed = 0
    try:
        q = db.query(RecruitmentInfo).filter(
            RecruitmentInfo.status == 1,
            or_(RecruitmentInfo.publish_date.is_(None), RecruitmentInfo.publish_date == ""),
        )
        if args.category:
            q = q.filter(RecruitmentInfo.category == args.category)
        # 有 url 的优先，否则无法回填
        rows = q.filter(RecruitmentInfo.url.isnot(None), RecruitmentInfo.url != "").all()

        if args.limit and args.limit > 0:
            rows = rows[:args.limit]

        logger.info("=" * 60)
        logger.info(f"招考信息发布日期回填 — 模式: {mode}")
        logger.info(f"待回填行数: {len(rows)}"
                    f"{f' | 分类: {args.category}' if args.category else ' | 全部分类'}"
                    f"{f' | 上限: {args.limit}' if args.limit > 0 else ''}")
        logger.info("=" * 60)

        if not rows:
            logger.info("没有需要回填的数据，结束。")
            return

        for i, rec in enumerate(rows, 1):
            scanned += 1
            url = rec.url or ""
            pd = fetch_publish_date(url)
            if not pd:
                failed += 1
                logger.warning(f"[{i}/{len(rows)}] 未取到日期 (fail={failed}) {rec.title[:32]}")
            else:
                if args.apply:
                    rec.publish_date = pd
                    db.commit()
                filled += 1
                logger.info(f"[{i}/{len(rows)}] {pd}  {rec.title[:38]}")
            # 附加间隔，避免与 safe_request 内建间隔叠加过载源站
            time.sleep(args.delay + random.uniform(0, 1.0))

        logger.info("=" * 60)
        logger.info(f"回填完成 — 扫描 {scanned} | 成功 {filled} | 跳过 {skipped} | 失败 {failed}")
        if not args.apply and filled:
            logger.info("（本次为 DRY-RUN，未写入数据库；加 --apply 才会真正落库）")
        logger.info("=" * 60)

    except KeyboardInterrupt:
        logger.warning("用户中断（已处理部分若为 --apply 模式已逐条提交）")
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"回填过程异常终止: {type(e).__name__}: {e}", exc_info=True)
    finally:
        db.close()


if __name__ == "__main__":
    main()