"""批量导入端点直测 —— 双轨入库(题库+试卷)与幂等性。

直接调用 batch_import_parsed 协程（绕过HTTP层），使用真实 SQLite 会话，
验证《双轨入库》流程图的落地契约：
    T1 试卷入库到"试卷管理"（DRAFT）
    T2 题目拆分入库到"题库"
    T3 paper_question 映射关系建立
    幂等：重复导入同一批 → 全部走复用(DUPLICATE)，关联不膨胀，paper_id 不变
"""
import asyncio
import sys
import os
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

import pytest

from app.core.database import SessionLocal
from app.models.models import (
    SysUser, ExamPaper, QuestionBank,
    PaperQuestionRelation, QuestionImportRecord, QuestionDetailCategory,
)
from app.api.v1.catalog.question_import import batch_import_parsed


def _mk_user() -> SysUser:
    # 仅作为 creator_id 数值来源，不落库
    u = SysUser()
    u.user_id = 990001
    u.username = 'ut_batch_runner'
    u.real_name = '批处理直测'
    return u


def _mk_payload(run_marker: str):
    """5道题（满足分离导入≥5的建卷启发式），其中第5题无答案→待确认。

    ⚠️ 题目内容不得包含 UTB 标记或"测试要点"字样——batch_import_parsed
    已有测试模板防御闸门（test_pattern_detected），此类数据会被拒收。
    run_marker 仅用于 paper_name，保证试卷名与导入记录可定位。
    """
    tag = f"自测{run_marker}"
    qs = []
    for i in range(1, 6):
        qs.append({
            "question_content": f"第{i}题：人民警察职业素养情景题{i}的表述正确的是？",
            "options": [
                {"key": "A", "value": f"选项A内容{i}"},
                {"key": "B", "value": f"选项B内容{i}"},
                {"key": "C", "value": f"选项C内容{i}"},
                {"key": "D", "value": f"选项D内容{i}"},
            ],
            "answer": ["B", "D", "A", "C", ""][i - 1] if i < 5 else "",
            "answer_analysis": f"解析{i}：依据相关法律法规条文判断。",
            "question_type_detail": "多选题" if i == 4 else "单选题",
            "score": 2 if i == 4 else 1,
            "difficulty": 3,
        })
    return {
        "paper_name": f"{tag}_2016江西招警真题",
        "subject_category": "公专",
        "import_mode": "separate",
        "match_rate": 97.5,
        "questions": qs,
    }


def _relations_count(db, paper_id):
    return db.query(PaperQuestionRelation).filter(
        PaperQuestionRelation.paper_id == paper_id).count()


@pytest.fixture()
def db_session(tmp_path):
    """隔离临时库 fixture。

    ⚠️ 历史事故：本测试曾直连真实 SessionLocal（指向 data/question_bank.db），
    断言失败时清理代码不执行，导致 UTB 模板垃圾题污染生产库 10 题 + 2 试卷
    （2026-08 由 repair_utb_pollution.py 清除）。
    现改用 tmp_path 独立 SQLite + create_all，测试结束自动销毁。
    禁止改回真实 SessionLocal。
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.core.database import Base

    engine = create_engine(f'sqlite:///{tmp_path / "test_batch_import.db"}')
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestSession()
    yield db
    db.rollback()
    db.close()
    engine.dispose()


def test_dual_track_and_idempotent_rerun(db_session):
    run_marker = uuid.uuid4().hex[:8]
    user = _mk_user()

    # ================= 第一次导入 =================
    r1 = asyncio.run(batch_import_parsed(_mk_payload(run_marker), user, db_session))

    assert r1['success_count'] == 5, r1
    assert r1['duplicate_count'] == 0
    assert r1['failed_items'] == []
    assert r1['total'] == 5
    # 双轨：分离导入+匹配率>0+≥5题 → 必须建卷
    assert isinstance(r1['paper_id'], int), f"双轨未建卷: {r1}"
    assert r1['need_confirm_count'] == 1  # 仅第5题待补充
    # T3: 关联关系逐题建立
    db_session.expire_all()
    assert _relations_count(db_session, r1['paper_id']) == 5
    # 试卷主记录存在且为草稿态（T1）
    paper = db_session.query(ExamPaper).filter(
        ExamPaper.paper_id == r1['paper_id']).first()
    assert paper is not None
    assert paper.paper_type == 'DRAFT'
    assert paper.composition_method == 'IMPORT'

    new_ids_1 = list(r1['new_question_ids'])

    # ================= 第二次导入（同内容）=================
    r2 = asyncio.run(batch_import_parsed(_mk_payload(run_marker), user, db_session))

    assert r2['success_count'] == 0
    assert r2['duplicate_count'] == 5, r2
    assert r2['paper_id'] == r1['paper_id'], '同名同作者必须复用既有试卷'
    db_session.expire_all()
    assert _relations_count(db_session, r2['paper_id']) == 5, \
        '重复导入不得使关联关系膨胀'

    # 汇总导入记录已生成两条（每跑一次一条，含paper_id回填）
    recs = db_session.query(QuestionImportRecord).filter(
        QuestionImportRecord.original_filename.like(f"%{run_marker}%")).all()
    assert len(recs) == 2
    assert all(rec.paper_id == r1['paper_id'] for rec in recs)

    # ================= 清理测试数据 =================
    # 双保险：fixture 已用隔离临时库，此段在临时库上执行，正常情况为空操作
    db_session.query(PaperQuestionRelation).filter(
        PaperQuestionRelation.paper_id == r1['paper_id']).delete()
    db_session.query(ExamPaper).filter(
        ExamPaper.paper_id == r1['paper_id']).delete()
    db_session.query(QuestionDetailCategory).filter(
        QuestionDetailCategory.question_id.in_(new_ids_1)).delete(
        synchronize_session=False)
    db_session.query(QuestionBank).filter(
        QuestionBank.question_id.in_(new_ids_1)).delete(synchronize_session=False)
    db_session.query(QuestionImportRecord).filter(
        QuestionImportRecord.original_filename.like(f"%{run_marker}%")).delete(
        synchronize_session=False)
    db_session.commit()


def test_paper_question_count_tracks_linked_questions(db_session):
    run_marker = uuid.uuid4().hex[:8]
    r1 = asyncio.run(batch_import_parsed(_mk_payload(run_marker), _mk_user(), db_session))
    db_session.expire_all()
    paper = db_session.query(ExamPaper).filter(
        ExamPaper.paper_id == r1['paper_id']).first()

    assert paper.question_count == 5
