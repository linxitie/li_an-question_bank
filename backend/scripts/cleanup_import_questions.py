"""题目导入脏数据清理工具（T9 步骤 D/E/F）

背景
----
计划任务 T9 要求「删除这 10 份 PDF 导入的题目，用户重新导入」。
dry-run 调查结论（见 .omo/evidence/task-9-dryrun.txt）：

  * ``question_bank`` 与 ``question_import_record`` 之间**没有任何外键**，
    ``question_bank`` 也没有 ``import_id`` 列，无法按导入记录反查。
  * 10 份 PDF 中仅 1 份有导入记录（import_id=1349），状态为 ``PREVIEW``，
    即解析完成但从未确认入库；其余 9 份**从未上传过**。
  * 内容指纹法命中 55 条，但其 ``source`` 全为「北京考试」、id 不连续，
    属跨资料同题造成的**假阳性**。

因此「甲：仅删除这 10 份 PDF 的题目」在当前数据下**无法可靠执行**。

本脚本把删除动作做成**显式选择 + 默认只演���**的形式，
在你明确指定范围之前不会删除任何数据。

用法
----
    # 默认 dry-run：只报告将要删除什么，不落刀
    python scripts/cleanup_import_questions.py --scope 甲

    # 确认后真正执行（会自动再备份一次）
    python scripts/cleanup_import_questions.py --scope 甲 --execute

可选范围
--------
甲  仅「这 10 份 PDF 导入的题目」
      口径：内容指纹（重新解析 10 份 PDF 的题干，归一化后与库精确匹配）
      ⚠ 实测目标数为 0（9 份从未导入，1 份从未确认入库）
      ⚠ 指纹法在当前库中会命中 55 条「北京考试」假阳性，已默认排除

乙  清空 question_bank 全部题目
      影响：2,484 道题，含真题/北京联考/江苏真题/天津真题等 20+ 个来源，
      以及手工录入内容。此范围远超本任务边界，务必确认。

丙  乙 + 连带清理关联表
      paper_question_relation / question_edit_log / question_image

安全措施
--------
1. 默认 dry-run，必须显式 ``--execute`` 才写库
2. 执行前自动备份并校验 integrity_check
3. 单事务执行，任一步失败整体回滚
4. 记录删除前行数，执行后断言差值精确等于清单数
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import sqlite3
import sys
from datetime import datetime
from typing import Optional

# 这 10 份真题 PDF 的判定：文件名以 4 位年份开头（知识点资料不以此开头）
PDF_DIR = r"C:\Users\21499\OneDrive\Desktop\公安题目（打印）"
BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BACKEND, "data", "question_bank.db")

# 直接以 `python scripts/cleanup_import_questions.py` 运行时，Python 只把脚本所在
# 目录（backend/scripts）加入 sys.path，导入 app.* 会失败；此处补上 backend 根。
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

# Windows 控制台默认 GBK，无法输出 ⚠ 等符号，会抛 UnicodeEncodeError
def _force_utf8(stream) -> None:
    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # 极老版本或不支持的流，忽略即可
            pass


_force_utf8(sys.stdout)
_force_utf8(sys.stderr)

# 关联表：清空题目时需一并清理的表（存在才处理）
RELATED_TABLES = ["paper_question_relation", "question_edit_log", "question_image"]


def backup(db_path: str) -> str:
    """备份并校验；校验不过直接抛错，绝不带着坏备份继续。"""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak_dir = os.path.join(os.path.dirname(db_path), "backups", f"pre_cleanup_{stamp}")
    os.makedirs(bak_dir, exist_ok=True)
    bak = os.path.join(bak_dir, os.path.basename(db_path))
    shutil.copy2(db_path, bak)
    con = sqlite3.connect(bak)
    try:
        state = con.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        con.close()
    if state != "ok":
        raise RuntimeError(f"备份完整性校验失败: {state}")
    digest = hashlib.sha256(open(bak, "rb").read()).hexdigest()
    print(f"[备份] {bak}\n       SHA256 = {digest}")
    return bak


def _normalize(s: Optional[str]) -> str:
    """题干归一化：去占位符、去 HTML 标签、去全部空白。"""
    s = re.sub(r"\[IMAGE:[^\]]*\]", "", s or "")
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\s+", "", s)


def targets_scope_jia(con) -> tuple:
    """甲：仅这 10 份 PDF 导入的题目（内容指纹口径）。"""
    import glob
    from app.api.v1.catalog.question_import import _extract_text_from_pdf
    from app.services.text_parser import ContentCleaner, extract_question_blocks

    pdfs = [p for p in sorted(glob.glob(os.path.join(PDF_DIR, "*.pdf")))
            if re.match(r"^20\d\d", os.path.basename(p))]
    print(f"[甲] 目标 PDF: {len(pdfs)} 份")
    fingerprints = set()
    for p in pdfs:
        clean = ContentCleaner.clean_text(_extract_text_from_pdf(open(p, "rb").read()))
        for b in extract_question_blocks(clean):
            k = _normalize(b.get("content"))
            if len(k) >= 8:            # 过短题干不具备指纹唯一性
                fingerprints.add(k)
    print(f"[甲] 可用唯一指纹: {len(fingerprints)} 条")

    rows = con.execute(
        "SELECT question_id, question_content, source FROM question_bank").fetchall()
    hits = [(qid, src) for qid, content, src in rows
            if _normalize(content) in fingerprints]
    print(f"[甲] 指纹命中: {len(hits)} 条")

    # 排除已知假阳性：命中项 source 与目标 PDF 所属考试不符
    # （实测这 55 条 source 均为「北京考试」，来自另一份资料）
    real = [(qid, src) for qid, src in hits if (src or "") != "北京考试"]
    print(f"[甲] 排除「北京考试」假阳性 {len(hits) - len(real)} 条后，真实目标: {len(real)} 条")
    if hits and not real:
        print("[甲] ⚠ 全部命中均为跨资料同题造成的假阳性，真实目标为 0。")
    return [q for q, _ in real], hits


def targets_scope_yi(con) -> tuple:
    """乙：question_bank 全部题目。"""
    rows = con.execute("SELECT question_id, source FROM question_bank").fetchall()
    from collections import Counter
    dist = Counter((s or "(空)") for _, s in rows)
    print(f"[乙] 目标: question_bank 全部 {len(rows)} 条")
    print(f"[乙] 来源分布(前8): {dict(dist.most_common(8))}")
    return [q for q, _ in rows], rows


def main() -> int:
    ap = argparse.ArgumentParser(description="题目导入脏数据清理（T9）")
    ap.add_argument("--scope", required=True, choices=["甲", "乙", "丙"],
                    help="甲=仅这10份PDF导入的题目(实测目标0) 乙=清空全部 丙=乙+关联表")
    ap.add_argument("--db", default=DB_PATH)
    ap.add_argument("--execute", action="store_true",
                    help="真正执行删除；不加此参数则为 dry-run")
    args = ap.parse_args()

    con = sqlite3.connect(args.db)
    try:
        before = con.execute("SELECT COUNT(*) FROM question_bank").fetchone()[0]
        print(f"当前题库行数: {before}\n")
        if args.scope == "甲":
            ids, _raw = targets_scope_jia(con)
        else:
            ids, _raw = targets_scope_yi(con)

        n = len(ids)
        print("\n" + "=" * 60)
        print(f"范围 {args.scope}：将影响 {n} 道题")
        for qid in ids[:5]:
            row = con.execute(
                "SELECT substr(question_content,1,50) FROM question_bank WHERE question_id=?",
                (qid,)).fetchone()
            print(f"   id={qid}  {row[0] if row else ''}")
        if n > 5:
            print(f"   ... 另有 {n - 5} 道")
        print("=" * 60)

        if not args.execute:
            print("\n*** DRY-RUN：未删除任何数据。确认无误后加 --execute ***")
            return 0

        if n == 0:
            print("\n目标数为 0，无需执行。")
            return 0

        print("\n[执行] 开始备份...")
        backup(args.db)

        ph = ",".join("?" * len(ids))
        con.execute("BEGIN")
        try:
            cur = con.execute(f"DELETE FROM question_bank WHERE question_id IN ({ph})", ids)
            deleted = cur.rowcount
            if args.scope == "丙":
                for t in RELATED_TABLES:
                    exists = con.execute(
                        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (t,)
                    ).fetchone()
                    if exists:
                        con.execute(f"DELETE FROM {t}")
                        print(f"[执行] 已清空关联表 {t}")
            con.commit()
        except Exception:
            con.rollback()
            print("[执行] 失败已整体回滚，未删除任何数据。")
            raise

        after = con.execute("SELECT COUNT(*) FROM question_bank").fetchone()[0]
        state = con.execute("PRAGMA integrity_check").fetchone()[0]
        print(f"\n[结果] 删除 {deleted} 条 | 行数 {before} -> {after} "
              f"({'一致 PASS' if before - deleted == after else '不一致 FAIL'})")
        print(f"[结果] integrity_check = {state}")
        ok = (deleted == n) and (before - deleted == after) and state == "ok"
        print("结果:", "PASS" if ok else "FAIL")
        return 0 if ok else 1
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())
