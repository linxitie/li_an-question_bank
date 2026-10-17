"""图片健康巡检：定期扫描自动修复断裂图片引用"""
import os
import sys
import re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..','..',  '..'))

from app.core.database import SessionLocal
from app.models.models import QuestionBank, QuestionImage
from app.services.image_service import (
    STATIC_DIR, verify_image_exists, sanitize_content_images,
    reextract_image_from_source
)


def health_check():
    """巡检所有含图片的题目，自动修复断裂引用"""
    db = SessionLocal()
    try:
        questions = db.query(QuestionBank).filter(
            QuestionBank.question_content.like('%<img%')
        ).all()

        print(f'[巡检] 扫描 {len(questions)} 条含图片题目')
        broken_count = 0
        fixed_count = 0

        for q in questions:
            content = q.question_content or ''
            img_pattern = re.compile(r'<img\s+src="([^"]+)"')
            imgs = img_pattern.findall(content)

            has_broken = False
            for src in imgs:
                if not verify_image_exists(src):
                    has_broken = True
                    broken_count += 1
                    break

            if not has_broken:
                continue

            before = content
            after = sanitize_content_images(content, q.question_id, db)

            if '<!-- img-missing' in after:
                recovered = reextract_image_from_source(q.question_id, db)
                if recovered:
                    after = sanitize_content_images(after, q.question_id, db)

            if after != before:
                q.question_content = after
                db.commit()
                fixed_count += 1

        print(f'[巡检] 发现断裂 {broken_count} 处，修复 {fixed_count} 条题目')

        total_imgs = 0
        missing_imgs = 0
        for q in questions:
            imgs = re.findall(r'<img\s+src="([^"]+)"', q.question_content or '')
            total_imgs += len(imgs)
            for src in imgs:
                if not verify_image_exists(src):
                    missing_imgs += 1

        rate = ((total_imgs - missing_imgs) / total_imgs * 100) if total_imgs else 100
        print(f'[巡检] 图片显示率: {rate:.2f}% ({total_imgs - missing_imgs}/{total_imgs})')

    finally:
        db.close()


if __name__ == '__main__':
    health_check()
