# -*- coding: utf-8 -*-
"""
新闻重复图片 / 重复段落历史数据清洗（幂等）

背景
----
news_scraper 的三条图片下载路径均无内容去重，同一张图被重复下载成
img_0.jpg / img_1.jpg / img_2.jpg —— 路径不同但内容完全相同（MD5 一致），
正文里同一段话也被重复 3 次。实测 546/2125 篇受影响，可删除冗余图片文件 1212 个。

为什么必须用 MD5 而不是路径比对：
    重复图片的 image_path 不同（img_0 / img_1 / img_2），按路径或字符串比对
    完全发现不了；只有内容哈希才能定位。这是初版方案误判「数据层无重复」的原因。

用法
----
    python scripts/repair_news_duplicates.py --dry-run   # 预览，不写库不删文件
    python scripts/repair_news_dedupe_alias.py --apply   # （不存在，见下）
    python scripts/repair_news_duplicates.py --apply     # 执行，可重复运行

设计要点
--------
1. 复用 app.services.news_scraper 的 _strip_dropped_image_markers，
   与采集端、前端 newsRender.js 三处口径完全一致，不引入第三份实现。
2. 幂等：同一篇文章第二次运行时已无重复图片，直接跳过。
3. 只处理「确实存在重复图片」的文章，不触碰其它文章的 content。
4. --apply 前自动用 SQLite 备份 API 生成快照（WAL 模式下不能用 shutil.copy）。
"""
import argparse
import hashlib
import os
import sqlite3
import sys
from datetime import datetime

# 与 migrate_study_goal_fields.py 保持一致：相对 backend/ 定位 SQLite 文件
DB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "data", "question_bank.db"
)
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# 图片物理目录：app/services/news_scraper.py 里 upload_dir 解析后就是这个位置
UPLOAD_ROOT = os.path.join(BACKEND_DIR, "uploads", "news")
SNAPSHOT_DIR = os.path.join(BACKEND_DIR, "data", "snapshots")

# 复用采集端的正文清理逻辑（先合并重复段落，再移除被判重丢弃的图片标记）
sys.path.insert(0, BACKEND_DIR)
from app.services.news_scraper import _strip_dropped_image_markers  # noqa: E402


def md5_of(path: str):
    """文件 MD5；文件不存在或读失败返回 None（不参与判重，留给人工确认）。"""
    try:
        h = hashlib.md5()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 256), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def physical_path(image_path: str) -> str:
    """image_path（uploads/news/{id}/img_0.jpg）-> 磁盘绝对路径。"""
    rel = (image_path or "").strip().lstrip("/")
    return os.path.normpath(os.path.join(BACKEND_DIR, rel))


def backup_db(conn: sqlite3.Connection) -> str:
    """WAL 模式下必须用 sqlite3 备份 API，shutil.copy 会丢失未 checkpoint 的数据。"""
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst_path = os.path.join(SNAPSHOT_DIR, "question_bank_pre_news_dedupe_%s.db" % ts)
    dst = sqlite3.connect(dst_path)
    try:
        with dst:
            conn.backup(dst)
    finally:
        dst.close()
    return dst_path


def scan(conn: sqlite3.Connection, limit_news: int = 0):
    """扫描重复图片。返回 (report, plan) —— report 供打印，plan 供执行。"""
    cur = conn.execute(
        "SELECT a.news_id, a.content FROM news_article a "
        "WHERE EXISTS (SELECT 1 FROM news_image i WHERE i.news_id = a.news_id) "
        "ORDER BY a.news_id"
    )
    articles = cur.fetchall()
    if limit_news:
        articles = articles[:limit_news]

    report = []
    plan = []

    for news_id, content in articles:
        rows = conn.execute(
            "SELECT image_id, image_path, image_order FROM news_image "
            "WHERE news_id = ? ORDER BY image_order",
            (news_id,),
        ).fetchall()
        if len(rows) < 2:
            continue

        # 按内容哈希分组
        groups = {}
        for image_id, image_path, image_order in rows:
            fp = physical_path(image_path)
            digest = md5_of(fp)
            if digest is None:
                continue
            groups.setdefault(digest, []).append(
                {
                    "image_id": image_id,
                    "image_path": image_path,
                    "image_order": image_order,
                    "file": fp,
                }
            )

        dropped = []
        for digest, members in groups.items():
            if len(members) < 2:
                continue
            # 保留 image_order 最小的一张
            members.sort(key=lambda m: (m["image_order"] if m["image_order"] is not None else 0))
            for extra in members[1:]:
                dropped.append(extra)

        if not dropped:
            continue

        dropped_orders = set(
            d["image_order"] for d in dropped if d["image_order"] is not None
        )
        new_content = _strip_dropped_image_markers(content or "", dropped_orders)

        report.append(
            {
                "news_id": news_id,
                "images_total": len(rows),
                "images_dropped": len(dropped),
                "content_changed": new_content != (content or ""),
                "orders": sorted(dropped_orders),
            }
        )
        plan.append(
            {
                "news_id": news_id,
                "dropped": dropped,
                "new_content": new_content,
            }
        )

    return report, plan


def apply_plan(conn: sqlite3.Connection, plan, delete_files: bool = True) -> dict:
    stats = {"rows_deleted": 0, "files_deleted": 0, "files_missing": 0, "content_updated": 0}
    for item in plan:
        for d in item["dropped"]:
            conn.execute("DELETE FROM news_image WHERE image_id = ?", (d["image_id"],))
            stats["rows_deleted"] += 1
            if delete_files:
                try:
                    os.remove(d["file"])
                    stats["files_deleted"] += 1
                except FileNotFoundError:
                    stats["files_missing"] += 1
                except OSError as e:
                    print("  ! 删除文件失败 %s: %s" % (d["file"], e))
        if item["new_content"]:
            conn.execute(
                "UPDATE news_article SET content = ? WHERE news_id = ?",
                (item["new_content"], item["news_id"]),
            )
            stats["content_updated"] += 1
    return stats


def main() -> int:
    ap = argparse.ArgumentParser(description="新闻重复图片/段落清洗（幂等）")
    ap.add_argument("--dry-run", action="store_true", help="只预览，不写库不删文件（默认）")
    ap.add_argument("--apply", action="store_true", help="实际执行")
    ap.add_argument("--no-delete-files", action="store_true", help="只删数据库行，保留磁盘文件")
    ap.add_argument("--limit", type=int, default=0, help="只处理前 N 篇（调试用）")
    args = ap.parse_args()

    do_apply = args.apply and not args.dry_run
    if not os.path.exists(DB_PATH):
        print("找不到数据库: %s" % DB_PATH)
        return 2

    conn = sqlite3.connect(DB_PATH)
    try:
        report, plan = scan(conn, limit_news=args.limit)

        print("=" * 60)
        print("扫描结果：%d 篇文章存在内容重复的图片" % len(report))
        total_imgs = sum(r["images_dropped"] for r in report)
        total_changed = sum(1 for r in report if r["content_changed"])
        print("可删除冗余图片：%d 张" % total_imgs)
        print("正文需要同步清理：%d 篇" % total_changed)
        print("=" * 60)
        for r in report[:20]:
            print(
                "  news_id=%-6d 图片 %d->%d  丢弃 order=%s 正文变更=%s"
                % (
                    r["news_id"],
                    r["images_total"],
                    r["images_total"] - r["images_dropped"],
                    r["orders"],
                    "是" if r["content_changed"] else "否",
                )
            )
        if len(report) > 20:
            print("  ... 其余 %d 篇省略" % (len(report) - 20))

        if not do_apply:
            print("")
            print("预览模式，未做任何改动。确认无误后加 --apply 执行。")
            return 0

        if not plan:
            print("")
            print("没有需要清理的数据（幂等：可能已清理过）。")
            return 0

        print("")
        print("正在备份数据库 ...")
        bpath = backup_db(conn)
        print("备份完成: %s" % bpath)

        conn.execute("BEGIN")
        try:
            stats = apply_plan(
                conn, plan, delete_files=not args.no_delete_files
            )
            conn.commit()
        except Exception:
            conn.rollback()
            print("执行失败，已回滚。")
            raise

        print("")
        print("完成：删除图片行 %d，删除文件 %d，文件缺失跳过 %d，更新正文 %d 篇"
              % (
                  stats["rows_deleted"],
                  stats["files_deleted"],
                  stats["files_missing"],
                  stats["content_updated"],
              ))
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())