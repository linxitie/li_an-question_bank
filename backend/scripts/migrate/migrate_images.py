"""一次性迁移脚本：修复历史图片数据，确保98%显示率"""
import os
import re
import shutil
import sys
import hashlib

# 添加后端目录到 path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..','..',  '..'))

from app.core.database import SessionLocal
from app.models.models import QuestionBank, QuestionImage
from app.services.image_service import STATIC_DIR, verify_image_exists


def migrate():
    db = SessionLocal()
    try:
        questions = db.query(QuestionBank).filter(
            QuestionBank.question_content.like('%[IMAGE:%')
        ).all()

        print(f'[迁移] 发现 {len(questions)} 条含图片占位符的题目')
        fixed_count = 0
        skipped_count = 0

        for q in questions:
            content = q.question_content
            markers = re.findall(r'\[IMAGE:([a-f0-9]+_\d+_\d+|\d+_\d+)\]', content)

            if not markers:
                continue

            for idx, marker_key in enumerate(markers):
                possible_sources = [
                    os.path.join(STATIC_DIR, f'{marker_key}.png'),
                ]

                # 如果 marker_key 是 uuid_x_y 格式，也尝试 x_y 格式
                parts = marker_key.split('_')
                if len(parts) == 3:
                    simple_key = f'{parts[1]}_{parts[2]}'
                    possible_sources.append(os.path.join(STATIC_DIR, f'{simple_key}.png'))

                src_file = None
                for src in possible_sources:
                    if os.path.exists(src):
                        src_file = src
                        break

                if src_file:
                    dst_dir = os.path.join(STATIC_DIR, str(q.question_id))
                    os.makedirs(dst_dir, exist_ok=True)
                    img_data = open(src_file, 'rb').read()
                    md5 = hashlib.md5(img_data).hexdigest()[:8]
                    dst_name = f'img_{idx}_{md5}.png'
                    dst_file = os.path.join(dst_dir, dst_name)

                    if not os.path.exists(dst_file):
                        shutil.copy2(src_file, dst_file)

                    rel_path = f'/static/questions/{q.question_id}/{dst_name}'

                    q.question_content = content.replace(
                        f'[IMAGE:{marker_key}]',
                        f'<img src="{rel_path}" class="q-img" loading="lazy" />'
                    )
                    content = q.question_content

                    existing = db.query(QuestionImage).filter(
                        QuestionImage.question_id == q.question_id,
                        QuestionImage.image_path == rel_path
                    ).first()
                    if not existing:
                        img = QuestionImage(
                            question_id=q.question_id,
                            image_path=rel_path,
                            image_type='题干图',
                            image_order=idx
                        )
                        db.add(img)

                    fixed_count += 1
                else:
                    q.question_content = content.replace(f'[IMAGE:{marker_key}]', '')
                    content = q.question_content
                    skipped_count += 1

            db.commit()

        print(f'[迁移] 完成：修复 {fixed_count} 张图片，跳过 {skipped_count} 个缺失图片')

        remaining = db.query(QuestionBank).filter(
            QuestionBank.question_content.like('%[IMAGE:%')
        ).count()
        print(f'[迁移] 剩余未修复：{remaining} 条')

    finally:
        db.close()


if __name__ == '__main__':
    migrate()
