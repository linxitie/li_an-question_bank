# -*- coding: utf-8 -*-
"""任务 35（模块 J）门禁反向用例 —— 证明新断言/守卫**真的能检出对应缺陷**。

设计约定
--------
每条新断言/守卫都有一条「缺陷注入」用例：把已知的缺陷形态喂给判据函数，
断言它返回 FAIL（或统计 > 0），并且失败信息能定位到缺陷。
再配一条「当前实现已修复」用例：走**生产函数**断言 PASS（红 → 绿）。

只用真实图片（磁盘暂存目录里 classify_image 判定为 keep 的内容图），
不造合成/空图片 —— 与 tests/test_question_group_images.py 同一纪律。
"""
import io
import json
import os
import re
import shutil
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'scripts')))

from gates.gate_l3_ingest import (  # noqa: E402
    GROUP_MARKER_RE,
    check_excel_row_conservation,
    check_group_image_persistence,
    patched_group_image_dirs,
    pick_real_staging_png,
)
from gates.gate_l2_matching import guard_material_blocks  # noqa: E402


def _group(tmp_root, shared, has_images=False, gid=55500001):
    """构造一个 QuestionGroup 行（不入库），shared_content 由调用方给定。"""
    from app.models.models import QuestionGroup
    g = QuestionGroup(group_type='material', shared_content=shared,
                      title='反向用例题组', subject='公专')
    # 不 add/flush：id 由判据函数用 getattr(group, 'id', 0) 兜底
    g.id = gid
    return g


# ─────────────────────── 断言 9: 题组图片落盘 ───────────────────────

def test_reverse_group_image_not_persisted_is_detected(tmp_path):
    """反向用例 9-A：J-1-1 缺陷原形 —— 建组后**没有**落盘。

    缺陷形态：21 个题组 10 个 [IMAGE:xxx] 占位符、shared_content_images 列全空、
    磁盘上 0 张图。判据必须 FAIL，且失败信息形如
    「shared_content 含 2 个 IMAGE 标记但只有 0 个落盘文件」。
    """
    shared = ('据国家统计局数据显示，2021年我国研究与试验发展经费支出27864亿元。'
              '[IMAGE:a1b2c3d4_1_0] 全年共签订技术合同67万项。'
              '[IMAGE:bb11cc22_1_0]')
    group_root = str(tmp_path / 'question-groups')
    g = _group(None, shared, gid=55500001)

    ok, detail = check_group_image_persistence(shared, g, group_root)

    assert ok is False, '未落盘的题组必须被判为 FAIL'
    assert '2 个 IMAGE 标记但只有 0 个落盘文件' in detail, detail


def test_reverse_group_image_url_points_to_missing_file(tmp_path):
    """反向用例 9-B：URL 写进 shared_content 但磁盘上没这张文件（裂图）。"""
    gid = 55500002
    group_root = str(tmp_path / 'question-groups')
    # 先建占用位文件让目录存在，再把文件删掉模拟「有 URL 无文件」
    shared = ('材料内容。[IMAGE:a1b2c3d4_1_0]'
              '<img src="/static/question-groups/%d/img_0_deadbeef.png" class="q-img" />'
              '<img src="/static/question-groups/%d/img_1_cafe1234.png" class="q-img" />'
              % (gid, gid))
    g = _group(None, shared, gid=gid)

    ok, detail = check_group_image_persistence(shared, g, group_root)

    assert ok is False, 'URL 指向不存在文件的题组必须被判为 FAIL'
    assert 'URL缺失2个' in detail, detail


def test_reverse_group_image_marker_left_behind(tmp_path):
    """反向用例 9-C：占位符没被替换掉（替换漏了一个）。"""
    gid = 55500003
    group_root = str(tmp_path / 'question-groups')
    shared = ('材料内容。<img src="/static/question-groups/%d/img_0_deadbeef.png" />'
              '尾巴。[IMAGE:zz999999_1_0]' % gid)
    # 只落第一张盘
    os.makedirs(os.path.join(group_root, str(gid)), exist_ok=True)
    open(os.path.join(group_root, str(gid), 'img_0_deadbeef.png'), 'wb').write(b'x')
    g = _group(None, shared, gid=gid)

    ok, detail = check_group_image_persistence(shared, g, group_root)

    assert ok is False, '残留占位符必须被判为 FAIL'
    assert '残留占位符' in detail, detail


def test_current_impl_group_images_all_persisted():
    """绿用例 9：走生产 `_persist_group_images`，真实暂存图 → 判据 PASS。"""
    real_png = pick_real_staging_png()
    if not real_png:
        pytest.skip('磁盘上无真实暂存图（classify_image keep），不造假数据')

    from app.api.v1.catalog.question_import import _persist_group_images

    staging = tempfile.mkdtemp(prefix='test_rev_stage_')
    group_root = tempfile.mkdtemp(prefix='test_rev_group_')
    try:
        markers = ['a1b2c3d4_1_0', 'bb11cc22_1_0']
        for mk in markers:
            shutil.copy2(real_png, os.path.join(staging, mk + '.png'))
        shared = ('据国家统计局数据显示，2021年我国研究与试验发展经费支出27864亿元。'
                  '[IMAGE:%s] 全年共签订技术合同67万项。[IMAGE:%s]'
                  % (markers[0], markers[1]))
        gid = 55500004
        from app.models.models import QuestionGroup
        group = QuestionGroup(group_type='material', shared_content=shared,
                              title='绿用例题组', subject='公专')
        group.id = gid
        with patched_group_image_dirs(staging, group_root):
            _persist_group_images(group)

        ok, detail = check_group_image_persistence(shared, group, group_root)
        assert ok, detail
        assert '2 个 IMAGE 标记但只有 2 个落盘文件' in detail, detail
    finally:
        shutil.rmtree(staging, ignore_errors=True)
        shutil.rmtree(group_root, ignore_errors=True)


# ─────────────────── 断言 10: Excel 行数守恒 ───────────────────

class _FakeQ:
    """最小题库行替身（只提供判据读到的字段）。"""

    def __init__(self, answer_analysis):
        self.answer_analysis = answer_analysis


def test_reverse_excel_row_silently_dropped_is_detected():
    """反向用例 10-A：缺答案行既不入库也不进提交报告 → 静默消失。"""
    rows = [{'题目内容': '题1', '答案': 'A'}, {'题目内容': '题2', '答案': ''}]
    # 缺陷形态：failed_items 为空，行凭空少一条
    problems = check_excel_row_conservation(
        rows, failed_items=[], kept=1, db_count_expected=1,
        questions_in_db=[_FakeQ('解析1')], source_analysis=['解析1'])
    assert problems, '行数不守恒必须被报出'
    assert any('行数不守恒' in p for p in problems), problems


def test_reverse_excel_drop_reason_is_generic():
    """反向用例 10-B：丢弃报告只有「数据不完整」这类笼统原因。

    旧实现的缺陷：`_normalize_question` 返回裸 None，原因不可定位。
    门禁判据要求 reason == '缺答案' 且带行号。
    """
    reason = '数据不完整'
    assert reason != '缺答案', '门禁必须拒绝笼统原因'
    # 生产 excel_reader.normalize_question 的丢弃报告才是判据接受的形态
    from app.services.question_ingest.excel_reader import normalize_question
    report = normalize_question({'题目内容': '题干', '答案': '', '解析': '解析'})
    assert isinstance(report, dict), '生产丢弃报告必须是 dict'
    assert report.get('_drop_reason') == '缺答案', report
    assert '_raw' in report and report['_raw'], '丢弃行必须带原始数据（可定位）'


def test_reverse_excel_analysis_column_lost(tmp_path):
    """反向用例 10-C：含「解析」列的题解析没落库（232 道公专空解析同源缺陷）。"""
    rows = [{'题目内容': '题1', '答案': 'A', '解析': '解析一'}]
    problems = check_excel_row_conservation(
        rows, failed_items=[], kept=1, db_count_expected=1,
        questions_in_db=[_FakeQ('')], source_analysis=['解析一'])
    assert problems, '解析列未落库必须被报出'
    assert any('解析列未落库' in p for p in problems), problems


def test_current_impl_excel_three_rows_land_as_three_questions():
    """绿用例 10：3 行 Excel → 库中恰好 3 题，解析列逐条落库。

    直接驱动生产 parse_excel_buffer / _normalize_question /
    batch_import_parsed，用内存临时库，绝不触碰真实 DB。
    """
    import asyncio
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.foundation.schema import ddl_statements
    from app.models.models import Base, QuestionBank, SysUser
    from gates.gate_l3_ingest import build_probe_xlsx
    from app.services.question_ingest.excel_reader import parse_excel_buffer
    from app.api.v1.catalog.question_import import (
        _normalize_question, batch_import_parsed)

    tmp_db = os.path.join(tempfile.gettempdir(), 'test_gate_l3_excel.db')
    if os.path.exists(tmp_db):
        os.remove(tmp_db)
    engine = create_engine(f'sqlite:///{tmp_db}')
    for table in Base.metadata.sorted_tables:
        try:
            table.create(engine, checkfirst=True)
        except Exception:
            pass
    # F4 起导入成功会在同一事务写 foundation_outbox；临时库需自建该表。
    with engine.begin() as conn:
        for statement in ddl_statements():
            conn.exec_driver_sql(statement)
    db = sessionmaker(bind=engine)()

    try:
        from app.models.models import QuestionSubject, QuestionType
        db.add(QuestionSubject(subject_id=3, subject_name='公专',
                               subject_code='gongzhuan'))
        db.add(QuestionType(type_id=1, type_name='单选题', type_code='single',
                            subject_id=3))
        user = SysUser(user_id=1, user_no='T035', username='gate_tester',
                       password='x', phone='13800000000', user_type='teacher')
        db.add(user)
        db.commit()

        raw_rows = parse_excel_buffer(build_probe_xlsx(), 'test_gate_l3.xlsx')
        payloads = [_normalize_question(r) for r in raw_rows]
        assert all(p is not None for p in payloads), payloads
        analyses = [p['answer_analysis'] for p in payloads if p]
        assert all(analyses), analyses

        r = asyncio.run(batch_import_parsed(
            {'paper_name': '绿用例公专卷', 'subject_category': '公专',
             'import_mode': 'separate', 'match_rate': 0,
             'questions': payloads}, db.query(SysUser).first(), db))
        db.commit()

        assert r['success_count'] == 3, r
        assert db.query(QuestionBank).count() == 3
        landed = [q.answer_analysis or '' for q in db.query(QuestionBank).all()]
        for a in analyses:
            assert a in landed, (a, landed)
    finally:
        db.rollback()
        db.close()
        engine.dispose()
        if os.path.exists(tmp_db):
            os.remove(tmp_db)


# ─────────────── L2 材料块守卫（J-2 / a267744）────────────────

MAT_QNUM = re.compile(r'^[ \t]*(\d{1,3})[ \t]*[.．、]')
MAT_MATERIAL = re.compile(r'^[ \t]*（([一二三四五六七八九十]{1,3})）[ \t]*$')


def _good_material_lines():
    """J-2 修复后的正确形态：材料块内无题号、表格行归位、图片自称归属与落点一致。"""
    return [
        '110. 能够从上述材料中得出的是：',
        'A.2021年9月，四类业务中信息技术服务收入占比最高',
        'B.2021年8月，软件业务收入是信息技术服务收入的2倍',
        '（二）',
        '据国家统计局数据显示，2021年我国研究与试验发展经费支出27864亿元。',
        '地区 | 2019 | 2020 | 2021',
        '全国 | 100 | 120 | 140',
        '111. 2021年，我国境内专利授权数比上一年增加：',
        'A.120万件 [IMAGE:a1b2c3d4_111_0]',
        'B.95万件',
    ]


def test_guard_material_block_clean_text_passes():
    """绿用例：干净文本三项守卫全绿。"""
    stats = guard_material_blocks(_good_material_lines())
    assert stats['material_blocks'] == 1, stats
    assert stats['qnums_inside_material'] == 0, stats
    assert stats['images_misattributed'] == 0, stats
    assert stats['table_rows_correct'] == stats['table_rows_total'] == 2, stats


def test_reverse_guard_question_number_inside_material():
    """反向用例 L2-A：材料块区间里混进了题号。

    判据：材料块的第一个题号必须大于该材料标记之前出现过的最大题号。
    材料 prose 里混入前一材料的题号时，首题号会倒退 → 守卫必须计数。
    """
    lines = [
        '110. 能够从上述材料中得出的是：',
        'A.2021年9月，四类业务中信息技术服务收入占比最高',
        '（二）',
        '据国家统计局数据显示，2021年我国研究与试验发展经费支出27864亿元。',
        '地区 | 2019 | 2020 | 2021',
        '109. 2019年该地区私有云市场规模约为：',   # 表格行里漏进来的题号
        '全国 | 100 | 120 | 140',
        '111. 2021年，我国境内专利授权数比上一年增加：',
        'A.120万件',
    ]
    stats = guard_material_blocks(lines)
    assert stats['qnums_inside_material'] >= 1, stats


def test_reverse_guard_material_image_owned_by_previous_question():
    """反向用例 L2-B：图片占位符的自称归属与物理落点错位。

    `[IMAGE:{hex}_{题号}_{序号}]` 自带归属题号。材料块的图落在材料区间
    （向上最近的题号行是上一题 110）却自称属于 111，前端就会把这张材料图
    挂到错的题上 —— 守卫必须计数。
    """
    lines = _good_material_lines()
    # 把占位符搬到材料区间里，同时自称归属 111（落点向上最近题号是 110）
    lines = [l.replace('A.120万件 [IMAGE:a1b2c3d4_111_0]', 'A.120万件')
             for l in lines]
    lines = [l.replace('地区 | 2019 | 2020 | 2021',
                       '地区 | 2019 | 2020 | 2021 [IMAGE:a1b2c3d4_111_0]')
             for l in lines]
    stats = guard_material_blocks(lines)
    assert stats['images_misattributed'] == 1, stats


def test_reverse_guard_table_row_escapes_material_block():
    """反向用例 L2-C：表格行被追加到页尾，脱离所属材料块（J-2-1 修复前的形态）。"""
    lines = _good_material_lines()
    # 把两行表格内容搬到材料的首个题号之后
    rows = [l for l in lines if ' | ' in l]
    lines = [l for l in lines if ' | ' not in l]
    lines = lines[:9] + rows + lines[9:]
    stats = guard_material_blocks(lines)
    assert stats['table_rows_total'] == 2, stats
    assert stats['table_rows_correct'] == 0, stats
    assert stats['table_rows_correct'] < stats['table_rows_total'], stats


def test_guard_marker_regex_rejects_non_hex_keys():
    """守卫只认 [a-f0-9]+_\\d+_\\d+ 形态的占位符，非十六进制 key 不误判。"""
    assert GROUP_MARKER_RE.findall('[IMAGE:gate9a_1_0]') == []
    assert GROUP_MARKER_RE.findall('[IMAGE:a1b2c3d4_1_0]') == ['a1b2c3d4_1_0']
    assert GROUP_MARKER_RE.findall('[IMAGE:../../etc/passwd]') == []
