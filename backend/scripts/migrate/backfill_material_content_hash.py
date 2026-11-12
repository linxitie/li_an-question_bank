# -*- coding: utf-8 -*-
"""回填 / 归一 `study_material.content_hash`（2026-11-12）。

背景：W2（2026-11-09）开始"同内容不重复建"，去重靠 `study_material.content_hash`
一列。但该列有两类问题（实测）：
  · **98 条为 NULL**（W2 之前入库）；
  · 另有若干条有值、但**与当前口径算出来的哈希不一致**（历史上有过不同的建卡/导入路径，
    例如按正文算 vs 按正反面算）。→ 同一份内容重传时，列比对仍然不命中。

本脚本做两件事（都可 dry-run）：
  1. **回填**：`content_hash IS NULL` 且能算出正文的，补上；
  2. `--recompute` **归一**：把"算得出来但与当前口径不一致"的行重算覆盖，
     让"同一份内容 → 同一个哈希"变成全局事实（哈希是派生字段，重算安全）。

口径（与 `api/v1/library/materials._material_content_hash` 一致）：
  · 卡片：正面 + 背面；
  · 其它类型：正文 `content`。
**正文与正反面都为空的行保持 NULL**（不拿标题兜底）——否则"无正文的试卷行"会按标题
算出可被误撞的哈希，反而制造假重复。

安全措施：
  · 默认 dry-run，只打印"会改哪些"，不写库；
  · `--apply` 写前用 `sqlite3.backup()` 做一致性备份（R10：WAL 下禁止 copy2）；
  · 写后 `PRAGMA integrity_check`，并报告"重算后重复哈希"条数（只报告，不删数据）。

用法：
  python backend/scripts/migrate/backfill_material_content_hash.py                  # dry-run（只看 NULL）
  python backend/scripts/migrate/backfill_material_content_hash.py --recompute      # dry-run（含归一）
  python backend/scripts/migrate/backfill_material_content_hash.py --recompute --apply
  python backend/scripts/migrate/backfill_material_content_hash.py --db <path> --apply

回滚：用 `--apply` 打印出的备份文件顶回（同时删 -wal/-shm）。
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DB = BACKEND_DIR / "data" / "question_bank.db"
BACKUP_DIR = BACKEND_DIR / "data" / "backups"

# 让脚本能直接用应用里的清洗/哈希实现（口径只写一次）
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def _cleaner():
    from app.services.material_sanitizer import content_cleaner
    return content_cleaner


def _raw_text(row) -> str:
    """与 `_material_content_hash` 同口径；正文为空时**不**退化成标题。"""
    if (row["type"] or "") == "card":
        return f"{row['card_front'] or ''}{row['card_back'] or ''}".strip()
    return (row["content"] or "").strip()


def _backup(db_path: Path) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = BACKUP_DIR / f"before_backfill_content_hash_{stamp}.db"
    src = sqlite3.connect(str(db_path))
    dst = sqlite3.connect(str(out))
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="回填/归一 study_material.content_hash（默认 dry-run）")
    ap.add_argument("--db", default=str(DEFAULT_DB), help="SQLite 路径")
    ap.add_argument("--apply", action="store_true", help="真正写库（默认只预览）")
    ap.add_argument("--recompute", action="store_true",
                    help="把「有值但与当前口径不一致」的行也重算（归一）")
    ap.add_argument("--limit", type=int, default=0, help="最多处理多少行（0=全部）")
    args = ap.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"[FAIL] 库不存在: {db_path}")
        return 2

    cleaner = _cleaner()
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(study_material)")]
        if "content_hash" not in cols:
            print("[FAIL] study_material 没有 content_hash 列")
            return 2

        sql = ("SELECT material_id, type, title, summary, content, card_front, card_back, "
               "content_hash FROM study_material ORDER BY material_id")
        if args.limit > 0:
            sql += f" LIMIT {int(args.limit)}"
        rows = conn.execute(sql).fetchall()

        plan, skipped, same = [], [], 0
        for row in rows:
            raw = _raw_text(row)
            if not raw:
                skipped.append(row["material_id"])
                continue
            new_hash = cleaner.calculate_content_hash(raw)
            old_hash = row["content_hash"]
            if not new_hash:
                skipped.append(row["material_id"])
            elif old_hash == new_hash:
                same += 1
            elif old_hash is None:
                plan.append((row["material_id"], row["type"] or "", new_hash, None))
            elif args.recompute:
                plan.append((row["material_id"], row["type"] or "", new_hash, old_hash))

        fill = sum(1 for p in plan if p[3] is None)
        fix = len(plan) - fill
        by_type = Counter(t for _, t, _, _ in plan)
        print(f"[i] 库: {db_path}")
        print(f"[i] 资料 {len(rows)} 条；正文为空保持 NULL {len(skipped)} 条；哈希已一致 {same} 条")
        print(f"[i] 计划写入 {len(plan)} 条（回填 {fill} + 归一 {fix}）")
        if by_type:
            print("[i] 按类型: " + ", ".join(f"{k or '(空)'}={v}" for k, v in sorted(by_type.items())))
        if skipped:
            print(f"[i] 保持 NULL 的 id（前 12 个）: {skipped[:12]}")
        for mid, t, h, old in plan[:10]:
            mark = "FILL" if old is None else "FIX "
            print(f"[{mark}] #{mid:<5} {t:<8} {h[:12]}…" + (f"  (原 {old[:12]}…)" if old else ""))

        if not args.apply:
            print("[i] dry-run：未写库。确认无误后加 --apply"
                  + ("（归一建议加 --recompute）" if not args.recompute else ""))
            return 0
        if not plan:
            print("[OK] 没有需要写入的行（幂等）")
            return 0

        backup = _backup(db_path)
        print(f"[OK] 已备份: {backup}")

        changed = 0
        for mid, _t, h, _old in plan:
            cur = conn.execute(
                "UPDATE study_material SET content_hash = ? WHERE material_id = ?", (h, mid))
            changed += cur.rowcount
        conn.commit()

        left = conn.execute(
            "SELECT COUNT(*) FROM study_material WHERE content_hash IS NULL").fetchone()[0]
        dup = conn.execute(
            "SELECT COUNT(*) FROM (SELECT content_hash FROM study_material "
            "WHERE content_hash IS NOT NULL GROUP BY content_hash HAVING COUNT(*) > 1)"
        ).fetchone()[0]
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        print(f"[OK] 已写入 {changed} 条；剩余 NULL {left} 条；"
              f"重算后重复哈希组 {dup} 组（只报告，不删数据）；integrity_check={integrity}")
        if integrity != "ok":
            print("[FAIL] 完整性检查未通过，请用备份回滚")
            return 1
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
