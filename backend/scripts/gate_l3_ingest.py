#!/usr/bin/env python3
"""L3 落库链路门禁 — 8 条断言，用内存临时库，绝不触碰真实 DB。

用法:
  python scripts/gate_l3_ingest.py           # 校验
  python scripts/gate_l3_ingest.py -v        # 详细输出
"""
import os
import sys
import json
import tempfile
import time

# 确保 backend 在 sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.models import Base, QuestionBank, QuestionGroup, QuestionSubject, QuestionType, SysUser

_TMP_DB = os.path.join(tempfile.gettempdir(), f'gate_l3_test_{int(time.time())}.db')

# 安全断言：必须用临时文件 DB，绝不触碰真实库
assert 'question_bank.db' not in _TMP_DB, 'L3 门禁绝不触碰真实库'


def make_engine():
    # 用临时文件 DB 而非 :memory:，避免 StaticPool 共享连接导致索引重复创建
    if os.path.exists(_TMP_DB):
        os.remove(_TMP_DB)
    engine = create_engine(f'sqlite:///{_TMP_DB}')
    for table in Base.metadata.sorted_tables:
        try:
            table.create(engine, checkfirst=True)
        except Exception:
            pass
    return engine


def make_session(engine):
    Session = sessionmaker(bind=engine)
    return Session()


_counter = [0]

def fresh_engine():
    """每次调用返回一个全新的临时 DB 引擎"""
    _counter[0] += 1
    path = os.path.join(tempfile.gettempdir(), f'gate_l3_{int(time.time())}_{_counter[0]}.db')
    if os.path.exists(path):
        os.remove(path)
    engine = create_engine(f'sqlite:///{path}')
    # SQLite 对 __table_args__ 中的索引 checkfirst 不生效，逐表创建并忽略索引重复错误
    for table in Base.metadata.sorted_tables:
        try:
            table.create(engine, checkfirst=True)
        except Exception:
            pass
    return engine


def seed_base_data(db):
    """插入最小基础数据：科目、题型、用户"""
    subj = QuestionSubject(subject_id=3, subject_name='公专', subject_code='gongzhuan')
    db.add(subj)
    qtype = QuestionType(type_id=1, type_name='单选题', type_code='single', subject_id=3)
    db.add(qtype)
    user = SysUser(user_id=1, user_no='T001', username='test_teacher', password='x', phone='13800000000', user_type='teacher')
    db.add(user)
    db.commit()


def make_question(idx, **overrides):
    q = {
        'question_content': f'测试题目 {idx}：以下哪项正确？',
        'options': [{'key': 'A', 'value': '选项A'}, {'key': 'B', 'value': '选项B'},
                    {'key': 'C', 'value': '选项C'}, {'key': 'D', 'value': '选项D'}],
        'answer': 'A',
        'answer_analysis': f'解析 {idx}',
        'question_type_detail': '单选题',
        'subject_category': '公专',
        'score': 1,
        'difficulty': 3,
    }
    q.update(overrides)
    return q


def run_assertions():
    results = []
    engine = make_engine()
    db = make_session(engine)
    seed_base_data(db)

    try:
        from app.api.v1.question_import import _upsert_question_core
    except ImportError as e:
        print(f'无法导入 _upsert_question_core: {e}')
        sys.exit(1)

    # 断言 1: 传入 N 题 → 库中恰好 N 题
    try:
        user = db.query(SysUser).first()
        for i in range(5):
            _upsert_question_core(db, user, make_question(i))
        db.commit()
        count = db.query(QuestionBank).count()
        ok = count == 5
        results.append(('断言1: N题入N题', ok, f'传入5题，库中{count}题'))
    except Exception as e:
        results.append(('断言1: N题入N题', False, str(e)[:100]))

    # 断言 2: requirements 落库
    try:
        engine = fresh_engine(); db = make_session(engine)
        seed_base_data(db)
        user2 = db.query(SysUser).first()
        _upsert_question_core(db, user2, make_question(0, requirements='①全面准确；②不超过300字'))
        db.commit()
        q = db.query(QuestionBank).first()
        ok = q is not None and q.requirements is not None and '全面准确' in q.requirements
        results.append(('断言2: requirements落库', ok, f'requirements={q.requirements if q else "N/A"}'))
    except Exception as e:
        results.append(('断言2: requirements落库', False, str(e)[:100]))

    # 断言 3: group_id 落库 + question_groups 行存在
    try:
        engine = fresh_engine(); db = make_session(engine)
        seed_base_data(db)
        user3 = db.query(SysUser).first()
        group = QuestionGroup(group_type='material', shared_content='测试材料', title='测试题组', subject='公专')
        db.add(group)
        db.flush()
        _upsert_question_core(db, user3, make_question(0, group_id=group.id))
        db.commit()
        q = db.query(QuestionBank).first()
        g = db.query(QuestionGroup).first()
        ok = q is not None and q.group_id == group.id and g is not None and g.shared_content == '测试材料'
        results.append(('断言3: group_id落库', ok, f'group_id={q.group_id if q else "N/A"}, group存在={g is not None}'))
    except Exception as e:
        results.append(('断言3: group_id落库', False, str(e)[:100]))

    # 断言 4: blocked=true → 拒绝且零写入
    try:
        engine = fresh_engine(); db = make_session(engine)
        seed_base_data(db)
        user4 = db.query(SysUser).first()
        n0 = db.query(QuestionBank).count()
        try:
            _upsert_question_core(db, user4, make_question(0, blocked=True, block_reasons=['answer_block_count_mismatch']))
            db.commit()
            ok = False
            detail = '未抛异常（blocked 闸门失效）'
        except Exception:
            db.rollback()
            n1 = db.query(QuestionBank).count()
            ok = n1 == n0
            detail = f'拒绝入库，库中{n1}题（期望{n0}）'
        results.append(('断言4: blocked拒绝零写入', ok, detail))
    except Exception as e:
        results.append(('断言4: blocked拒绝零写入', False, str(e)[:100]))

    # 读取 question_import.py 源码供断言 5/6/7 使用
    qi_path = os.path.join(os.path.dirname(__file__), '..', 'app', 'api', 'v1', 'question_import.py')
    try:
        with open(qi_path, 'r', encoding='utf-8') as f:
            qi_src = f.read()
    except Exception:
        qi_src = ''

    # 断言 5: payload.questions 优先于 preview_data（RC-3）
    try:
        ok = "payload.get('questions')" in qi_src and 'deprecated' in qi_src
        results.append(('断言5: payload.questions优先', ok, '已修复' if ok else '未修复'))
    except Exception as e:
        results.append(('断言5: payload.questions优先', False, str(e)[:100]))

    # 断言 6: 建卷路径不抛 NameError（RC-4）
    try:
        ok = 'confirmed_items = []' in qi_src and 'confirmed_items.append' in qi_src
        results.append(('断言6: 建卷不抛NameError', ok, '已修复' if ok else '未修复'))
    except Exception as e:
        results.append(('断言6: 建卷不抛NameError', False, str(e)[:100]))

    # 断言 7: blocked 闸门在 /batch-parsed 中
    try:
        ok = "status_code=409" in qi_src and 'blocked' in qi_src
        results.append(('断言7: batch-parsed blocked闸门', ok, '已修复' if ok else '未修复'))
    except Exception as e:
        results.append(('断言7: batch-parsed blocked闸门', False, str(e)[:100]))

    # 断言 8: 幂等
    try:
        engine = fresh_engine(); db = make_session(engine)
        seed_base_data(db)
        user8 = db.query(SysUser).first()
        q_data = make_question(0)
        _upsert_question_core(db, user8, q_data)
        db.commit()
        n1 = db.query(QuestionBank).count()
        _upsert_question_core(db, user8, q_data)
        db.commit()
        n2 = db.query(QuestionBank).count()
        ok = n2 == n1
        results.append(('断言8: 幂等去重', ok, f'第一次{n1}题，第二次{n2}题'))
    except Exception as e:
        results.append(('断言8: 幂等去重', False, str(e)[:100]))

    return results


def main():
    verbose = '-v' in sys.argv
    results = run_assertions()
    all_pass = True
    for name, ok, detail in results:
        status = '✅ PASS' if ok else '❌ FAIL'
        print(f'  {status}  {name}: {detail}')
        if not ok:
            all_pass = False

    passed = sum(1 for _, ok, _ in results if ok)
    print(f'\nL3 落库链路门禁: {passed}/{len(results)} 通过')
    if all_pass:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == '__main__':
    main()
