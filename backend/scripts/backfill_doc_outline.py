# -*- coding: utf-8 -*-
"""C1 回填：给已有讲义（有 docx 原件的）抽一次大纲，写进 `study_material.doc_meta`。

用法（在 backend 目录下）：
    python scripts/backfill_doc_outline.py            # 只看计划
    python scripts/backfill_doc_outline.py --apply    # 真写

幂等：已有 `doc_meta` 的资料默认跳过；`--force` 强制重算。
只处理「有原件且是 docx」的资料——PDF 没有样式信息，硬抽目录误报率高。
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal  # noqa: E402
from app.models.models import MaterialFile, StudyMaterial  # noqa: E402
from app.services import doc_outline, material_files  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="真写库（默认 dry-run）")
    ap.add_argument("--force", action="store_true", help="已有 doc_meta 也重算")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        rows = (db.query(StudyMaterial)
                .filter(StudyMaterial.status >= 0)
                .order_by(StudyMaterial.material_id.asc()).all())
        planned, skipped, failed = 0, 0, 0
        for m in rows:
            file = (db.query(MaterialFile)
                    .filter(MaterialFile.material_id == m.material_id)
                    .order_by(MaterialFile.file_id.asc()).first())
            if not file or (file.file_ext or "").lower() != "docx":
                continue
            if m.doc_meta and not args.force:
                skipped += 1
                continue
            try:
                path = material_files.resolve_abs_path(file)
            except FileNotFoundError:
                failed += 1
                print(f"  [缺失] #{m.material_id} {file.file_name}（磁盘上没有）")
                continue
            meta = doc_outline.extract_docx_outline(path)
            if meta is None:
                failed += 1
                print(f"  [解析失败] #{m.material_id} {file.file_name}")
                continue
            planned += 1
            label = f"{meta['chapter_count']} 章 · {doc_outline.human_word_count(meta['word_count'])}"
            print(f"  #{m.material_id} {m.title[:28]:<28} → {label}")
            if args.apply:
                m.doc_meta = doc_outline.dumps(meta)
        if args.apply:
            db.commit()
        print(f"\n{'已写入' if args.apply else '计划写入'} {planned} 条；跳过（已有）{skipped}；失败 {failed}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
