#!/usr/bin/env python3
"""
fix_irrelevant_images.py — 扫描数据库中的题目图片，检测并清理无关图片
运行方式：
  cd backend && python fix_irrelevant_images.py [--dry-run] [--delete-files]

功能：
  1. 扫描 question_bank 表的 question_content 字段中的 <img> 标签
  2. 检测图片是否为无关内容（logo/页眉页脚/扫描条）
  3. 从 question_content 中移除无关图片标签
  4. 可选删除磁盘上的图片文件
"""
import re
import sys
import os
import io

# 设置 backend 目录为工作路径，确保 app 模块可被导入
_backend_dir = os.path.dirname(os.path.abspath(__file__))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from app.core.database import SessionLocal

from sqlalchemy import text


# 图片标签匹配
IMG_TAG_PATTERN = re.compile(r'<img\s+[^>]*src=["\']([^"\']+)["\'][^>]*>', re.IGNORECASE)


def is_irrelevant_image(img_path: str) -> bool:
    """检测图片路径是否指向无关图片（基于尺寸分析）"""
    try:
        from PIL import Image

        # 构建完整路径
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if img_path.startswith('/static/'):
            full_path = os.path.join(backend_dir, img_path.lstrip('/'))
        elif img_path.startswith('http'):
            # 远程图片跳过检测（无法读取）
            return False
        else:
            full_path = os.path.join(backend_dir, 'static', img_path.lstrip('/'))

        if not os.path.exists(full_path):
            return False

        img = Image.open(full_path)
        w, h = img.size

        # 小于100x100的图片大概率是logo/图标
        if w < 100 and h < 100:
            return True

        # 宽高比极端的图片是页眉页脚/扫描条
        ratio = max(w, h) / max(min(w, h), 1)
        if ratio > 8 and min(w, h) < 60:
            return True

        # 检测近乎纯白/纯灰的图片（扫描仪空白页边距）
        if w > 200 and h > 50 and h < 100:
            img_small = img.resize((20, 20))
            pixels = list(img_small.getdata())
            if pixels:
                first = pixels[0]
                avg = sum(first[:3]) / 3 if isinstance(first, tuple) else first
                variance = sum(
                    ((p[:3][0] if isinstance(p, tuple) else p) - avg) ** 2
                    for p in pixels
                ) / len(pixels)
                if variance < 50:  # 几乎纯色
                    return True

    except ImportError:
        pass  # PIL未安装跳过检测
    except Exception:
        pass  # 检测失败不阻止

    return False


def main():
    dry_run = '--dry-run' in sys.argv
    delete_files = '--delete-files' in sys.argv

    db = SessionLocal()
    try:
        total = 0
        irrelevant_count = 0
        removed_tags = 0
        deleted_files = 0
        affected_questions = set()

        # 分页扫描
        offset = 0
        batch_size = 1000
        while True:
            rows = db.execute(
                text("SELECT question_id, question_content FROM question_bank "
                     "WHERE question_content LIKE '%<img%' "
                     "ORDER BY question_id LIMIT :limit OFFSET :offset"),
                {'limit': batch_size, 'offset': offset}
            ).fetchall()

            if not rows:
                break

            for row in rows:
                qid = row[0]
                content = row[1] or ''
                total += 1

                # 提取所有图片标签
                img_tags = IMG_TAG_PATTERN.findall(content)
                if not img_tags:
                    continue

                new_content = content
                for src in img_tags:
                    if is_irrelevant_image(src):
                        irrelevant_count += 1
                        affected_questions.add(qid)

                        # 从内容中移除整个 <img> 标签
                        tag_pattern = re.compile(
                            r'<img\s+[^>]*src=["\']' + re.escape(src) + r'["\'][^>]*>',
                            re.IGNORECASE
                        )
                        new_content = tag_pattern.sub('', new_content)
                        removed_tags += 1

                        # 可选删除文件
                        if delete_files and not dry_run:
                            backend_dir = os.path.dirname(
                                os.path.dirname(os.path.abspath(__file__))
                            )
                            if src.startswith('/static/'):
                                full_path = os.path.join(backend_dir, src.lstrip('/'))
                                if os.path.exists(full_path):
                                    os.remove(full_path)
                                    deleted_files += 1

                # 更新数据库
                if new_content != content and not dry_run:
                    db.execute(
                        text("UPDATE question_bank SET question_content = :val "
                             "WHERE question_id = :qid"),
                        {'val': new_content, 'qid': qid}
                    )

            offset += batch_size
            print(f"  已扫描 {total} 条含图片题目...")

        if not dry_run:
            db.commit()

        # 输出报告
        print(f"\n{'[DRY RUN] ' if dry_run else ''}无关图片清理报告:")
        print(f"  扫描题目总数: {total}")
        print(f"  检测到无关图片: {irrelevant_count}")
        print(f"  移除图片标签: {removed_tags}")
        print(f"  涉及题目数量: {len(affected_questions)}")
        if delete_files:
            print(f"  删除磁盘文件: {deleted_files}")

    finally:
        db.close()


if __name__ == '__main__':
    main()
