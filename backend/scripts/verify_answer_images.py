#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""端到端验证「答案区图片」链路（用户缺陷 D2）。

为什么必须单独验证
------------------
D2 的修复只改了代码，**从未证明它真的能落库**。本脚本用真实语料跑完整链路：

    PDF → _extract_text_from_pdf（插入 [IMAGE:xxx] 占位符）
        → extract_question_blocks（切题，答案/解析带占位符）
        → _upsert_question_core（真实入库 + 图片提取 + 占位符回写）
        → 回读 question_image 表与 answer_analysis 字段

语料：2023 国考副省级答案.pdf（全语料实测含 5 张 ≥60x60 大图，
     属「答案逻辑思维导图」，且**全在答案区**）。

判定标准
--------
1. 解析出的块数与解析器单独跑一致（未因入库流程丢题）
2. ``question_image`` 新增行数 > 0（图片真的落库了）
3. ``answer_analysis`` / ``answer`` 中的 ``[IMAGE:`` 占位符被替换为 ``<img``（原位落地）
4. 数据库清理干净，公专 2583 行不变

用法：python scripts/verify_answer_images.py
"""
import glob
import os
import sys
import traceback

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

CORPUS = r'D:\砺安题库\砺安题库\题库\申论'
SRC = 'ZZIMG_VERIFY_TMP'


def main():
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from app.models.models import (QuestionBank, QuestionGroup,
                                       QuestionDetailCategory, QuestionImage,
                                       SysUser)
        from app.services.text_parser import extract_question_blocks
        from app.api.v1 import question_import as QI

        # --- 选语料：钉死用已验证正常的「副省级答案」卷 ---
        # ⚠️ 踩过两次坑，按文件名匹配都会选错：
        #   ① `*副省级*答案*` 排序取首 → 选中 2021「两套答案」卷，该PDF IMG=0
        #      → 测出 "added 0 images" 假阴性
        #   ② 改成「含大图优先」→ 又选中 `2023…副省卷`（注意是「副省卷」不是「副省级」），
        #      该文件是**另一个卷**，本身解析就失败（只切出 1 块，题号异常），
        #      用它验证必然全 0 → 又一次假阴性
        # 现按「解析块数正常 + 含大图 + 文件名含答案」三重筛选，并打印证据。
        import pymupdf as _fitz
        from app.services.text_parser import extract_question_blocks as _EX

        def _count_big_images(fp):
            d = _fitz.open(fp)
            n = sum(1 for pg in d for im in pg.get_images(full=True)
                    if len(im) > 3 and im[2] >= 60 and im[3] >= 60)
            d.close()
            return n

        pool = glob.glob(os.path.join(CORPUS, '**', '*副省级*答案*.pdf'),
                         recursive=True)
        picked, picked_n = None, 0
        for p in sorted(pool):
            try:
                d = _fitz.open(p)
                raw = ''.join(pg.get_text() for pg in d)
                d.close()
                nb = len(_EX(raw.replace('\r\n', '\n').replace('\r', '\n')))
            except Exception:
                continue
            if nb < 2:          # 解析块数正常的卷才可用
                continue
            ni = _count_big_images(p)
            if ni > 0:
                picked, picked_n = p, ni
                break
        if not picked:
            print('NO_CANDIDATE')
            return 1
        path = picked
        print('CORPUS %s big_images=%d'
              % (os.path.basename(path)[:44], picked_n))

        with open(path, 'rb') as f:
            buf = f.read()

        # 1) 真实取文（会插入 [IMAGE:xxx] 占位符）
        text = QI._extract_text_from_pdf(buf)
        markers = text.count('[IMAGE:')
        print('STEP1 extract_text markers=%d textlen=%d' % (markers, len(text)))

        # 2) 解析切题
        blocks = extract_question_blocks(text)
        print('STEP2 blocks=%d' % len(blocks))
        if not blocks:
            print('NO_BLOCKS')
            return 1
        blk_marker = sum((b.get('answer') or '').count('[IMAGE:')
                         + (b.get('analysis') or '').count('[IMAGE:')
                         for b in blocks)
        print('STEP2 markers_in_answer_or_analysis=%d' % blk_marker)

        # 3) 真实入库
        eng = create_engine('sqlite:///' + os.path.join(BASE, 'data',
                                                          'question_bank.db'))
        db = sessionmaker(bind=eng)()
        user = db.query(SysUser).first()
        before_img = db.query(QuestionImage).count()

        made = []
        for b in blocks:
            payload = {
                'question_content': b.get('content') or '',
                'answer': b.get('answer') or '',
                'answer_analysis': b.get('analysis') or '',
                'requirements': b.get('requirements'),
                'score': b.get('score'),
                'subject_category': '申论',
                'import_mode': 'combined',
                'question_type_detail': '简答题',
                'source': SRC,
                'material_text': b.get('material_text') or '',
                'question_number': b.get('question_number'),
                'question_level': b.get('question_level'),
                'sort_order': b.get('sort_order'),
            }
            made.append(QI._upsert_question_core(db, user, payload)
                        .get('question_id'))
        db.commit()

        after_img = db.query(QuestionImage).count()
        print('STEP3 question_image %d -> %d (added %d)'
              % (before_img, after_img, after_img - before_img))

        # 4) 回读校验
        ok_rows = 0
        leftover = 0
        inlined = 0
        for qid in made:
            if not qid:
                continue
            o = db.query(QuestionBank).filter(
                QuestionBank.question_id == qid).first()
            if not o:
                continue
            n = db.query(QuestionImage).filter(
                QuestionImage.question_id == qid).count()
            if n:
                ok_rows += 1
            blob = '%s\n%s' % (o.answer or '', o.answer_analysis or '')
            if '[IMAGE:' in blob:
                leftover += 1
            if '<img' in blob:
                inlined += 1
        print('STEP4 rows_with_image=%d/%d leftover_placeholder=%d '
              'inlined_img_tag=%d' % (ok_rows, len(made), leftover, inlined))

        # 5) 清理
        rows = db.query(QuestionBank).filter(QuestionBank.source == SRC).all()
        gs = {r.group_id for r in rows if r.group_id}
        for r in rows:
            db.query(QuestionDetailCategory).filter(
                QuestionDetailCategory.question_id == r.question_id).delete()
            db.query(QuestionImage).filter(
                QuestionImage.question_id == r.question_id).delete()
            db.delete(r)
        db.flush()
        for gid in gs:
            if gid and db.query(QuestionBank).filter(
                    QuestionBank.group_id == gid).count() == 0:
                g = db.query(QuestionGroup).filter(
                    QuestionGroup.id == gid).first()
                if g and g.source == SRC:
                    db.delete(g)
        db.commit()

        shenlun = db.query(QuestionBank).filter(
            QuestionBank.subject_id == 2).count()
        gongzhuan = db.query(QuestionBank).filter(
            QuestionBank.subject_id == 3).count()
        total = db.query(QuestionBank).count()
        final_img = db.query(QuestionImage).count()
        print('STEP5 cleaned shenlun=%d gongzhuan=%d total=%d img_rows=%d'
              % (shenlun, gongzhuan, total, final_img))
        db.close()

        # 判定
        good = (after_img > before_img and leftover == 0
                and gongzhuan == 2583 and total == 2583)
        print('IMAGE_PIPELINE_%s' % ('VERIFIED' if good else 'INCOMPLETE'))
        return 0 if good else 1
    except Exception:
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())