# -*- coding: utf-8 -*-
"""T12 验证 2：exam_paper / exam_paper_tag 幂等 + 公专既有数据零影响。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.models.models import ExamPaper, ExamPaperTag, SysUser
from app.api.v1.catalog.question_import import (
    _upsert_xingce_paper, _resolve_xingce_paper_metadata,
)

fails = []


def check(name, cond, detail=''):
    print('  [%s] %s%s' % ('PASS' if cond else 'FAIL', name,
                           ('  -> ' + str(detail)) if detail else ''))
    if not cond:
        fails.append(name)


db = SessionLocal()
try:
    # ── 基线快照 ──────────────────────────────────────────────────
    papers_before = {p.paper_id: (p.paper_name, p.paper_type, p.subject_id,
                                  p.paper_code)
                     for p in db.query(ExamPaper).all()}
    # 全量快照（含行测 tag）。此前只快照 subject_category != '行测' 的子集，
    # 却与「排除我的试卷后的全部 tag」比对，口径错配导致 12 行假「新增」。
    tags_before = [
        (t.paper_id, t.exam_year, t.exam_province, t.exam_type,
         t.subject_category, t.is_complete)
        for t in db.query(ExamPaperTag).all()]
    n_paper0 = db.query(ExamPaper).count()
    n_tag0 = db.query(ExamPaperTag).count()
    gx_papers = {k: v for k, v in papers_before.items() if v[2] != 1}
    n_gx_tag = sum(1 for t in tags_before if t[4] != '行测')
    print('基线 exam_paper=%d  exam_paper_tag=%d' % (n_paper0, n_tag0))
    print('  其中非行测 paper=%d  非行测 tag=%d  行测 tag=%d'
          % (len(gx_papers), n_gx_tag, n_tag0 - n_gx_tag))

    user = db.query(SysUser).first()
    meta = _resolve_xingce_paper_metadata(
        '甘肃行测', '2023年甘肃公务员录用考试《行测》题（网友回忆版）题本.pdf', '', '')
    print('元数据: %s' % {k: meta.get(k) for k in
                        ('exam_year', 'exam_province', 'exam_type',
                         'subject_category', 'paper_variant')})

    PNAME = '__T12_幂等验证用试卷__'
    # ── 1. 首次创建 ──────────────────────────────────────────────
    db.query(ExamPaper).filter(ExamPaper.paper_name == PNAME).delete()
    db.commit()
    # 行测配对成功即完整卷：显式覆盖，不依赖 _detect_complete_paper 的文本启发
    p1, c1 = _upsert_xingce_paper(db, user, meta, PNAME, 120, is_complete=True)
    db.flush()
    check('首次创建 created=True', c1 is True, c1)
    check('试卷 subject_id=1（行测）', p1.subject_id == 1, p1.subject_id)
    check("composition_method='IMPORT'", p1.composition_method == 'IMPORT',
          p1.composition_method)
    check("paper_type='DRAFT'", p1.paper_type == 'DRAFT', p1.paper_type)
    tag1 = db.query(ExamPaperTag).filter(ExamPaperTag.paper_id == p1.paper_id).first()
    check('标签已创建', tag1 is not None)
    check("标签 subject_category='行测'", tag1.subject_category == '行测',
          tag1.subject_category)
    check('标签 is_complete=1', tag1.is_complete == 1, tag1.is_complete)
    check('标签 exam_province=甘肃', tag1.exam_province == '甘肃',
          tag1.exam_province)
    check('标签 exam_year=2023', tag1.exam_year == 2023, tag1.exam_year)
    check('标签 exam_type=省考', tag1.exam_type == '省考', tag1.exam_type)
    pid1 = p1.paper_id

    # ── 2. 幂等：重复导入 ─────────────────────────────────────────
    p2, c2 = _upsert_xingce_paper(db, user, meta, PNAME, 120)
    db.flush()
    check('重复导入 created=False', c2 is False, c2)
    check('重复导入复用同一 paper_id', p2.paper_id == pid1,
          (p2.paper_id, pid1))
    n_tag_same = db.query(ExamPaperTag).filter(
        ExamPaperTag.paper_id == pid1).count()
    check('标签未重复堆积（仍为 1 行）', n_tag_same == 1, n_tag_same)
    n_by_name = db.query(ExamPaper).filter(
        ExamPaper.paper_name == PNAME).count()
    check('同名试卷仍为 1 行', n_by_name == 1, n_by_name)

    # ── 3. ENDED → DRAFT 复活 ────────────────────────────────────
    p2.paper_type = 'ENDED'
    db.flush()
    p3, c3 = _upsert_xingce_paper(db, user, meta, PNAME, 120)
    db.flush()
    check('ENDED 被复活为 DRAFT', p3.paper_type == 'DRAFT', p3.paper_type)
    check('复活仍复用同一 paper_id', p3.paper_id == pid1, p3.paper_id)

    # ── 4. 低于阈值不建卷 ────────────────────────────────────────
    p4, c4 = _upsert_xingce_paper(db, user, meta, PNAME, 3)
    check('题目数 < 5 不创建试卷', p4 is None and c4 is False, (p4, c4))

    # ── 5. 公专既有数据零影响 ────────────────────────────────────
    papers_after = {p.paper_id: (p.paper_name, p.paper_type, p.subject_id,
                                 p.paper_code)
                    for p in db.query(ExamPaper).all() if p.paper_id != pid1}
    tags_after = [(t.paper_id, t.exam_year, t.exam_province, t.exam_type,
                   t.subject_category, t.is_complete)
                  for t in db.query(ExamPaperTag).all()
                  if t.paper_id != pid1]
    unchanged_p = all(papers_after.get(k) == v for k, v in papers_before.items())
    check('既有 %d 个 exam_paper 逐字段未变' % len(papers_before), unchanged_p,
          [k for k, v in papers_before.items() if papers_after.get(k) != v][:5])
    # tag 元组内含 None（exam_year/exam_province 可为空），直接 sorted 会
    # 抛 TypeError: '<' not supported between NoneType and str
    def _k(t):
        return tuple('' if v is None else str(v) for v in t)

    check('既有 %d 行 exam_paper_tag 逐字段未变' % len(tags_before),
          sorted(tags_before, key=_k) == sorted(tags_after, key=_k),
          '新增=%d 丢失=%d 被改=%d' % (
              len(set(map(_k, tags_after)) - set(map(_k, tags_before))),
              len(set(map(_k, tags_before)) - set(map(_k, tags_after))),
              len([1 for a, b in zip(sorted(tags_before, key=_k),
                                     sorted(tags_after, key=_k)) if a != b])))
    check('行测 tag 未被本次误改',
          db.query(ExamPaperTag).filter(
              ExamPaperTag.paper_id == pid1).count() == 1)

    # ── 清理测试数据 ─────────────────────────────────────────────
    db.query(ExamPaperTag).filter(ExamPaperTag.paper_id == pid1).delete()
    db.query(ExamPaper).filter(ExamPaper.paper_id == pid1).delete()
    db.commit()
    print('已清理测试试卷 paper_id=%d' % pid1)
    print('清理后 exam_paper=%d（基线 %d）  exam_paper_tag=%d（基线 %d）'
          % (db.query(ExamPaper).count(), n_paper0,
             db.query(ExamPaperTag).count(), n_tag0))
    check('清理后回到基线行数',
          db.query(ExamPaper).count() == n_paper0
          and db.query(ExamPaperTag).count() == n_tag0)

    db.rollback()
finally:
    db.close()

print()
print('RESULT = %s   失败 %d 项 %s'
      % ('PASS' if not fails else 'FAIL', len(fails), fails or ''))
sys.exit(0 if not fails else 1)