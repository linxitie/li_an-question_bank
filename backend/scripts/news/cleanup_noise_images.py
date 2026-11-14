#!/usr/bin/env python3
"""清理历史新闻图片中的二维码、Logo、Icon 和小尺寸占位图。

默认只扫描待审新闻；默认 dry-run，不删除任何数据。
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from PIL import Image

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.models import NewsArticle, NewsImage

BACKEND_DIR = Path(__file__).resolve().parents[2]
DEFAULT_VAULT = Path(settings.VAULT_PATH_NEWS)
ARCHIVE_DIR = BACKEND_DIR / "data" / "archive" / "news_noise_images"
_CARD_ROOT = ("01-待审核",)


def inspect_image(path: Path) -> tuple[str, str]:
    """返回 (是否噪声, 原因)。"""
    if not path.is_file():
        return True, "file_missing"
    try:
        with Image.open(path) as image:
            width, height = image.size
    except Exception:
        return True, "unreadable"
    if width < 100 or height < 100:
        return True, "too_small"
    long_side, short_side = max(width, height), min(width, height)
    if short_side / long_side >= 0.85 and width * height <= 90000:
        return True, "square_icon"
    try:
        import cv2
        import numpy as np

        matrix = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)
        if matrix is not None:
            decoded, points, _ = cv2.QRCodeDetector().detectAndDecode(matrix)
            if decoded or points is not None:
                return True, "qrcode_detected"
    except Exception:
        pass
    return False, "kept"


def clean_card_text(text: str, removed_paths: set[str]) -> tuple[str, bool]:
    lines = text.splitlines()
    kept = []
    for line in lines:
        if any(path in line for path in removed_paths):
            continue
        kept.append(line)
    cleaned = "\n".join(kept)
    # 图片全部被移除后，删除空的“## 图片”章节。
    sections = cleaned.split("\n## ")
    rebuilt = [sections[0]]
    for section in sections[1:]:
        heading, _, rest = section.partition("\n")
        if heading.strip() == "图片" and not rest.strip():
            continue
        rebuilt.append(section)
    result = "\n## ".join(rebuilt).rstrip() + "\n"
    return result, result != text


def main() -> int:
    parser = argparse.ArgumentParser(description="清理新闻图片噪声")
    parser.add_argument("--apply", action="store_true", help="真正删除数据库记录并移动文件")
    parser.add_argument("--include-published", action="store_true", help="同时清理已发布新闻图片")
    parser.add_argument("--vault", default=str(DEFAULT_VAULT))
    args = parser.parse_args()

    db = SessionLocal()
    rows = (
        db.query(NewsImage, NewsArticle)
        .join(NewsArticle, NewsImage.news_id == NewsArticle.news_id)
        .all()
    )
    if not args.include_published:
        rows = [
            (image, news)
            for image, news in rows
            if (news.review_status or "pending") in {"pending", "high_risk"}
        ]
    removed: list[tuple[NewsImage, str]] = []
    kept = 0
    for image, _news in rows:
        relative = Path(str(image.image_path or "").lstrip("/\\"))
        noise, reason = inspect_image(BACKEND_DIR / relative)
        if noise:
            removed.append((image, reason))
        else:
            kept += 1

    removed_paths = {
        str(image.image_path or "").lstrip("/\\") for image, _reason in removed if image.image_path
    }
    cards_touched = 0
    vault = Path(args.vault).expanduser()
    card_root = vault.joinpath(*_CARD_ROOT)
    if card_root.is_dir():
        for card in card_root.rglob("*.md"):
            text = card.read_text(encoding="utf-8")
            cleaned, changed = clean_card_text(text, removed_paths)
            if changed and not args.apply:
                cards_touched += 1
            elif changed:
                card.write_text(cleaned, encoding="utf-8")
                cards_touched += 1

    if args.apply:
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        for image, _reason in removed:
            relative = Path(str(image.image_path or "").lstrip("/\\"))
            source = BACKEND_DIR / relative
            if source.is_file():
                target = ARCHIVE_DIR / source.name
                if target.exists():
                    target = ARCHIVE_DIR / f"{image.image_id}_{source.name}"
                try:
                    shutil.move(str(source), str(target))
                except OSError:
                    pass
            vault_image = vault / relative
            if vault_image.is_file():
                vault_archive = ARCHIVE_DIR / "vault" / vault_image.name
                vault_archive.parent.mkdir(parents=True, exist_ok=True)
                if vault_archive.exists():
                    vault_archive = vault_archive.with_name(
                        f"{vault_image.stem}_{vault_image.suffix}"
                    )
                try:
                    shutil.move(str(vault_image), str(vault_archive))
                except OSError:
                    pass
            db.delete(image)
        db.commit()
    db.close()

    summary = {
        "apply": args.apply,
        "scope": "all" if args.include_published else "pending",
        "scanned": len(rows),
        "removed": len(removed),
        "kept": kept,
        "cards_touched": cards_touched,
        "reasons": {},
        "archive": str(ARCHIVE_DIR) if args.apply else None,
    }
    for _image, reason in removed:
        summary["reasons"][reason] = summary["reasons"].get(reason, 0) + 1
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
