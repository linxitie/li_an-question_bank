# -*- coding: utf-8 -*-
"""P3-9/P3-10/P3-12：复合题建组、申论文档级材料、重复题回填组字段。"""
import pytest

from app.api.v1.catalog.question_import import (
    _detect_and_link_composite_groups,
    _link_shenlun_material_groups,
)
from app.models.models import QuestionBank, QuestionGroup
from app.services.question_ingest.upsert import _upsert_question_core


@pytest.fixture(autouse=True)
def _clear_group_cache():
    """内存库每个用例重建，跨库残留的 group_id 缓存必须清空，否则挂到不存在的组。"""
    from app.api.v1.catalog.question_import import _SHENLUN_GROUP_CACHE

    _SHENLUN_GROUP_CACHE.clear()
    yield
    _SHENLUN_GROUP_CACHE.clear()


def _add_question(db, test_subject, test_user, test_question_type,
                  content, answer='参考答案'):
    q = QuestionBank(
        subject_id=test_subject.subject_id,
        type_id=test_question_type.type_id,
        question_content=content,
        answer=answer,
        audit_status=1,
        status=1,
        creator_id=test_user.user_id,
    )
    db.add(q)
    db.flush()
    return q


def test_shenlun_doc_material_links_all_essay_questions(
        db_session, test_user, test_subject, test_question_type):
    material = '给定资料1：某市推进基层治理现代化，通过网格化管理提升服务效能。'
    q1 = _add_question(db_session, test_subject, test_user, test_question_type,
                       '1. 根据给定资料1，概括该市基层治理的主要做法。')
    q2 = _add_question(db_session, test_subject, test_user, test_question_type,
                       '2. 根据给定资料1，分析网格化管理的作用。')
    q3 = _add_question(db_session, test_subject, test_user, test_question_type,
                       '3. 结合给定资料1，提出进一步优化的建议。')
    db_session.commit()

    items = [
        {'material_text': material, 'format': 'essay'},
        {'format': 'essay'},
        {'format': 'essay'},
    ]
    id_map = {0: q1.question_id, 1: q2.question_id, 2: q3.question_id}

    linked = _link_shenlun_material_groups(
        db_session, items, id_map, subject_name='申论', source_tag='test')
    db_session.commit()
    db_session.expire_all()

    assert linked == 3
    questions = [db_session.query(QuestionBank).filter(
        QuestionBank.question_id == qid).first() for qid in id_map.values()]
    group_ids = {q.group_id for q in questions}
    assert len(group_ids) == 1 and 0 not in group_ids, group_ids

    group = db_session.query(QuestionGroup).filter(
        QuestionGroup.id == group_ids.pop()).first()
    assert group is not None
    assert material in (group.shared_content or '')


def test_duplicate_upsert_backfills_group(db_session, test_user):
    data = {
        'question_content': '根据给定资料1，概括基层治理的主要做法。',
        'answer': '1.完善网格机制；2.加强队伍建设。',
        'subject_category': '申论',
        'question_type_detail': '简答题',
        'format': 'essay',
        'source': '重导测试',
    }
    first = _upsert_question_core(db_session, test_user, dict(data))
    db_session.commit()
    assert first['import_status'] == 'SUCCESS'

    material = '给定资料1：某市推进基层治理现代化，通过网格化管理提升服务效能。'
    second = _upsert_question_core(
        db_session, test_user, {**data, 'material_text': material})
    db_session.commit()

    assert second['import_status'] == 'DUPLICATE'
    assert second['question_id'] == first['question_id']
    assert 'group_id' in second['backfilled_fields']

    existing = db_session.query(QuestionBank).filter(
        QuestionBank.question_id == first['question_id']).first()
    assert existing.group_id > 0
    group = db_session.query(QuestionGroup).filter(
        QuestionGroup.id == existing.group_id).first()
    assert material in (group.shared_content or '')

    third = _upsert_question_core(
        db_session, test_user,
        {**data, 'material_text': '给定资料2：另一份完全不同的材料正文，不应覆盖。'})
    db_session.commit()
    db_session.refresh(existing)
    assert existing.group_id == group.id
    assert db_session.query(QuestionGroup).filter(
        QuestionGroup.group_type == 'material').count() == 1
    assert third['import_status'] == 'DUPLICATE'


def test_composite_groups_do_not_steal_claimed_heads(
        db_session, test_user, test_subject, test_question_type):
    """旧 claimed 混用下标与 qid：组头下标恰等于前组某成员 qid 时被误跳过。

    内存库 qid 从 1 递增，故 idx=2 的第二组头会撞上前组成员 qid=2。
    """
    contents = [
        '根据以下材料，回答1-2题。',
        '2. 关于基层治理的说法，正确的是？',
        '根据以下材料，回答3-4题。',
        '4. 关于网格化管理的说法，正确的是？',
    ]
    questions = [_add_question(db_session, test_subject, test_user,
                               test_question_type, c) for c in contents]
    db_session.commit()
    assert [q.question_id for q in questions] == [1, 2, 3, 4]

    id_map = {i: q.question_id for i, q in enumerate(questions)}
    items = [{'question_content': c} for c in contents]
    groups_created, members_linked = _detect_and_link_composite_groups(
        db_session, items, id_map, subject_name='公专', source_tag='test')
    db_session.commit()
    db_session.expire_all()

    assert groups_created == 2
    assert members_linked == 4

    rows = [db_session.query(QuestionBank).filter(
        QuestionBank.question_id == qid).first() for qid in id_map.values()]
    group_ids = [q.group_id for q in rows]
    assert group_ids == [group_ids[0]] * 2 + [group_ids[2]] * 2
    assert group_ids[0] != group_ids[2]
    assert 0 not in group_ids
    assert len({q.question_id for q in rows}) == len(rows)
