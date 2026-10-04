# -*- coding: utf-8 -*-
"""
清理孤立新闻图片文件（news_image 行已删、磁盘文件残留）

背景
----
repair_news_duplicates.py 清洗历史重复图片时删除了 1246 条 news_image 行，
但当时使用了 --no-delete-files（因为文件本身无备份，删除不可逆），
因此磁盘上留下 1246 个已无任何记录引用的孤立文件。

本脚本负责把这批残留文件收尾：
  1. 全盘扫描 uploads/news/ 下的图片文件
  2. 与 news_image 表中仍被引用的路径做差集 -> 孤立文件
  3. --apply 时**先打包成 zip**（可完整还原），再删除原文件

安全性设计
----------
  - 打包在删除之前，zip 内含完整相对路径与原始字节，可原样还原
  - 全程事务化思路：先打包成功并校验条目数一致，才开始删除
  - 幂等：可重复运行，已清理过的不会被重复处理
  - 默认 dry-run，必须显式 --apply 才动文件

用法
----
    python scripts/cleanup_orphan_news_images.py --dry-run
    python scripts/cleanup_orphan_news_images.py --apply
    python scripts/cleanup_orphan_news_images.py --apply --no-zip    # 不打包直接删（不建议）
"""
import argparse
import os
import sqlite3
import sys
import zipfile
from datetime import datetime

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BACKEND_DIR, "data", "question_bank.db")
UPLOAD_ROOT = os.path.join(BACKEND_DIR, "uploads", "news")
SNAPSHOT_DIR = os.path.join(BACKEND_DIR, "data", "snapshots")

IMG_EXT = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg")


def referenced_paths(conn) -> set:
    """news_image 表中仍被引用的相对路径集合。"""
    rows = conn.execute("SELECT image_path FROM news_image").fetchall()
    out = set()
    for (p,) in rows:
        if p:
            out.add(str(p).strip().lstrip("/").replace("\\", "/"))
    return out


def scan_orphans(conn):
    """返回 [(绝对路径, 相对路径), ...]"""
    if not os.path.isdir(UPLOAD_ROOT):
        return []
    referenced = referenced_paths(conn)
    orphans = []
    for news_id in sorted(os.listdir(UPLOAD_ROOT)):
        news_dir = os.path.join(UPLOAD_ROOT, news_id)
        if not os.path.isdir(news_dir):
            continue
        for fname in sorted(os.listdir(news_dir)):
            fp = os.path.join(news_dir, fname)
            if not os.path.isfile(fp):
                continue
            if not fname.lower().endswith(IMG_EXT):
                continue
            rel = "uploads/news/%s/%s" % (news_id, fname)
            if rel not in referenced:
                orphans.append((fp, rel))
    return orphans


def make_zip(orphans) -> str:
    """把孤立文件打包，返回 zip 路径。打包失败抛异常，绝不进入删除阶段。"""
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    zpath = os.path.join(SNAPSHOT_DIR, "orphan_news_images_%s.zip" % ts)
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as zf:
        for fp, rel in orphans:
            zf.write(fp, arcname=rel)
    return zpath


def verify_zip(zpath: str, expect: int) -> None:
    """校验 zip 条目数与源文件数一致，且至少能读出每个条目的字节数。"""
    with zipfile.ZipFile(zpath) as zf:
        names = [n for n in zf.namelist() if not n.endswith("/")]
        if len(names) != expect:
            raise RuntimeError(
                "zip 条目数 %d 与待删文件数 %d 不一致，已中止删除" % (len(names), expect)
            )
        for n in names:
            if zf.getinfo(n).file_size <= 0:
                raise RuntimeError("zip 条目 %s 大小异常，已中止删除" % n)


def main() -> int:
    ap = argparse.ArgumentParser(description="清理孤立新闻图片（默认 dry-run）")
    ap.add_argument("--dry-run", action="store_true", help="只预览（默认行为）")
    ap.add_argument("--apply", action="store_true", help="实际执行")
    ap.add_argument("--no-zip", action="store_true", help="不打包直接删除（不建议）")
    args = ap.parse_args()

    do_apply = args.apply and not args.dry_run

    if not os.path.exists(DB_PATH):
        print("找不到数据库: %s" % DB_PATH)
        return 2

    conn = sqlite3.connect(DB_PATH)
    try:
        orphans = scan_orphans(conn)
    finally:
        conn.close()

    total_bytes = sum(os.path.getsize(fp) for fp, _ in orphans)
    news_ids = sorted({rel.split("/")[2] for _, rel in orphans})

    print("=" * 62)
    print("扫描结果：孤立图片文件 %d 个" % len(orphans))
    print("  涉及新闻 %d 篇" % len(news_ids))
    print("  合计大小 %.2f MB" % (total_bytes / 1024.0 / 1024.0))
    print("=" * 62)
    if orphans:
        print("  示例（最多 8 个）：")
        for _, rel in orphans[:8]:
            print("    " + rel)
        if len(orphans) > 8:
            print("    ... 其余 %d 个省略" % (len(orphans) - 8))

    if not do_apply:
        print("")
        if not orphans:
            print("没有孤立文件（幂等：可能已清理过）。")
        else:
            print("预览模式，未删除任何文件。确认后加 --apply 执行。")
        return 0

    if not orphans:
        print("")
        print("无需处理。")
        return 0

    zpath = None
    if not args.no_zip:
        print("")
        print("正在打包 %d 个文件（删除前的可还原备份）..." % len(orphans))
        zpath = make_zip(orphans)
        verify_zip(zpath, len(orphans))
        size_mb = os.path.getsize(zpath) / 1024.0 / 1024.0
        print("打包完成并校验通过: %s (%.2f MB)" % (zpath, size_mb))
        print("  ↑ 该 zip 可完整还原这些文件，如需恢复直接解压回 backend/ 目录")

    deleted = 0
    failed = []
    for fp, _ in orphans:
        try:
            os.remove(fp)
            deleted += 1
        except OSError as e:
            failed.append((fp, str(e)))

    print("")
    print("删除完成: %d / %d" % (deleted, len(orphans)))
    if failed:
        print("失败 %d 个:" % len(failed))
        for fp, err in failed[:10]:
            print("  %s -> %s" % (fp, err))
    if zpath:
        print("原始文件备份: %s" % zpath)
    return 0


if __name__ == "__main__":
    sys.exit(main())