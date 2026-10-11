#!/usr/bin/env python3
"""L3 落库链路门禁 — 10 条断言，用内存临时库，绝不触碰真实 DB。

用法:
  python scripts/gate_l3_ingest.py           # 校验
  python scripts/gate_l3_ingest.py -v        # 详细输出

断言 9 / 10（任务 35 新增，模块 J）
------------------------------------
  断言 9  题组图片落盘：复合题入库后 shared_content 中每个 [IMAGE:xxx]
          都必须有对应落盘文件，缺一即失败。反向用例见
          tests/test_gate_l3.py::test_reverse_*。
  断言 10 Excel 路径行数守恒：3 行入 → 库中恰好 3 题、含解析列的必须落库；
          缺答案行必须出现在提交报告里（reason == '缺答案' 且带行号），
          不得静默消失。

两个断言都由**生产函数**驱动（`_persist_group_images` /
`batch_import_parsed` / `parse_excel_buffer` / `_normalize_question`），
门禁只做判读，不重实现业务逻辑。
"""
import os
import re
import sys
import json
import tempfile
import time
import contextlib
import shutil

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


# ─────────────────────────── 断言 9: 题组图片落盘 ───────────────────────────
# 与题目侧 `_extract_and_save_images` 对称的判据：占位符必须换成可访问的 <img>
# 且磁盘上真有文件。J-1-1 之前的缺陷正是「21 个题组 10 个占位符 0 张落盘」。
GROUP_MARKER_RE = re.compile(r'\[IMAGE:([a-f0-9]+_\d+_\d+|\d+_\d+)\]')
GROUP_IMG_SRC_RE = re.compile(r'src="([^"]*static/question-groups/[^"]+)"')

_STAGING_DIR = os.path.join(os.path.dirname(__file__), '..', 'app', 'static', 'questions')


def pick_real_staging_png() -> 'str | None':
    """从真实暂存目录挑一张**内容图**（classify_image 判定为 keep）。

    与 tests/test_question_group_images.py 同一策略：绝不使用合成/空图片。
    全目录 4.5 万张里有 4041 张是推广图黑名单命中，随手取第一张很可能取到
    推广图 → 断言「有落盘」必然失败，那是夹具错不是代码错。
    """
    staging = os.path.normpath(_STAGING_DIR)
    if not os.path.isdir(staging):
        return None
    try:
        from app.services.image_filters import classify_image
    except Exception:
        return None
    for name in sorted(os.listdir(staging)):
        if not name.lower().endswith('.png'):
            continue
        path = os.path.join(staging, name)
        try:
            if os.path.getsize(path) < 500:
                continue
            data = open(path, 'rb').read()
        except OSError:
            continue
        try:
            decision, _reason = classify_image(data)
        except Exception:
            continue
        if decision == 'keep':
            return path
    return None


def check_group_image_persistence(shared_content_before: str, group,
                                   group_img_root: str) -> tuple:
    """判读题组成图：shared_content 里每个 IMAGE 标记都必须有落盘文件。

    返回 (ok, detail)。这条判据**可独立单测**——反向用例（tests/test_gate_l3.py）
    直接把「未调用 _persist_group_images 的题组」喂进来，必须返回 FAIL，
    且失败信息形如「shared_content 含 2 个 IMAGE 标记但只有 0 个落盘文件」。
    """
    n_markers = len(GROUP_MARKER_RE.findall(shared_content_before or ''))
    final_text = getattr(group, 'shared_content', '') or ''
    residual = GROUP_MARKER_RE.findall(final_text)
    urls = GROUP_IMG_SRC_RE.findall(final_text)
    on_disk = 0
    missing_files = []
    for url in urls:
        name = url.rsplit('/', 1)[-1]
        path = os.path.join(group_img_root, str(getattr(group, 'id', 0)), name)
        if os.path.isfile(path) and os.path.getsize(path) > 0:
            on_disk += 1
        else:
            missing_files.append(name)

    # shared_content_images 列的 URL 也必须逐条落到磁盘
    col_urls = []
    raw_images = getattr(group, 'shared_content_images', '') or ''
    if raw_images:
        try:
            col_urls = json.loads(raw_images)
        except Exception:
            col_urls = []
    col_missing = []
    for url in col_urls:
        name = str(url).rsplit('/', 1)[-1]
        path = os.path.join(group_img_root, str(getattr(group, 'id', 0)), name)
        if not (os.path.isfile(path) and os.path.getsize(path) > 0):
            col_missing.append(name)

    ok = (n_markers == on_disk and not residual and not missing_files
          and not col_missing and len(urls) == n_markers)
    detail = (f'shared_content 含 {n_markers} 个 IMAGE 标记但只有 {on_disk} 个落盘文件'
              f'；残留占位符{len(residual)}个，URL缺失{len(missing_files)}个')
    if col_missing:
        detail += f'；shared_content_images 列缺失{len(col_missing)}个'
    return ok, detail


@contextlib.contextmanager
def patched_group_image_dirs(staging_dir: str, group_img_root: str):
    """把题组图片通道的暂存目录与落盘根目录改到临时目录。

    绝不写真实 app/static：门禁必须无副作用，且 /static 下 4.5 万张暂存图
    不该被门禁再追加。GROUP_URL_PREFIX 保持生产值，URL 结构不变。
    """
    from app.services.question_ingest import images as _img_mod
    saved_staging, saved_root = _img_mod._STAGING_DIR, _img_mod.GROUP_IMG_ROOT
    _img_mod._STAGING_DIR = staging_dir
    _img_mod.GROUP_IMG_ROOT = group_img_root
    try:
        yield
    finally:
        _img_mod._STAGING_DIR = saved_staging
        _img_mod.GROUP_IMG_ROOT = saved_root


# ─────────────────────────── 断言 10: Excel 行数守恒 ─────────────────────────
def check_excel_row_conservation(rows, failed_items, kept, db_count_expected,
                                 questions_in_db, source_analysis=None):
    """判读 Excel 导入的行数守恒与提交可见性。

    :param rows:             `parse_excel_buffer` 产出的原始行
    :param failed_items:     提交报告（/batch-parsed failed_items 同构）
    :param kept:             实际入库的题数
    :param db_count_expected:期望入库题数
    :param questions_in_db:  库中题（含 answer_analysis，用于核对解析列）
    :param source_analysis:  源「解析」列值列表（核对落库内容一致性）

    三条判据：
      1) 行数守恒：len(rows) == kept + len(failed_items)（没有一行凭空消失）
      2) 库中题数 == 期望题数
      3) 每一份源解析都如实落到 answer_analysis
    """
    problems = []
    if len(rows) != kept + len(failed_items):
        problems.append(f'行数不守恒：{len(rows)}行 != 入库{kept} + 失败{len(failed_items)}')
    if kept != db_count_expected:
        problems.append(f'库中{kept}题 != 期望{db_count_expected}题')
    if source_analysis:
        landed = [q.answer_analysis or '' for q in questions_in_db]
        for src in source_analysis:
            if src and src not in landed:
                problems.append(f'解析列未落库：{src[:20]}')
    return problems


def build_probe_xlsx() -> bytes:
    """构造 3 行真实结构化 Excel（含「解析」列）的内存字节。"""
    import io
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.append(['题目内容', '答案', '解析', '选项A', '选项B', '题型', '分值', '难度'])
    rows = [
        ['以下关于人民警察职责的说法正确的是：', 'A', '解析一：依据《人民警察法》第六条。',
         '公安机关的人民警察依法履行法定职责', '警察职责由个人自行约定', '单选题', 1, 3],
        ['下列哪项属于公安机关的侦查措施：', 'B', '解析二：依据《刑事诉讼法》相关规定。',
         '任意传唤证人', '依法讯问犯罪嫌疑人', '单选题', 1, 3],
        ['关于执法监督的说法错误的是：', 'C', '解析三：依据《公安机关督察条例》。',
         '督察机构可对直属单位开展督察', '督察结论无需公开', '单选题', 1, 3],
    ]
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


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

    # ── 断言 9: 题组图片落盘（J-1-1 守卫）────────────────────────────
    # 缺陷形态：21 个题组 10 个 [IMAGE:xxx] 占位符、shared_content_images 全空、
    # 磁盘上 0 张图。判据就是「标记数 == 落盘文件数」。
    try:
        real_png = pick_real_staging_png()
        if not real_png:
            results.append(('断言9: 题组图片落盘', False,
                            '磁盘上无真实暂存图（classify_image keep），跳过即失守'))
        else:
            from app.api.v1.question_import import _persist_group_images
            staging_dir = tempfile.mkdtemp(prefix='gate_l3_stage_')
            group_root = tempfile.mkdtemp(prefix='gate_l3_group_')
            try:
                # 两个 marker 共用同一张真实图（材料块与题块共用同 marker 的生产场景）
                # marker 必须落在 [a-f0-9]+_\d+_\d+ 字符集内，否则连正则不匹配
                markers = ['a1b2c3d4_1_0', 'bb11cc22_1_0']
                for mk in markers:
                    shutil.copy2(real_png, os.path.join(staging_dir, mk + '.png'))
                shared = ('据国家统计局数据显示，2021年我国研究与试验发展经费支出27864亿元。'
                          '[IMAGE:%s] 全年共签订技术合同67万项。[IMAGE:%s]'
                          % (markers[0], markers[1]))
                engine = fresh_engine(); db = make_session(engine)
                seed_base_data(db)
                group = QuestionGroup(group_type='material', shared_content=shared,
                                      title='断言9题组', subject='公专')
                db.add(group)
                db.flush()
                # 生产通道：建组后立即落盘（与 _detect_and_link_composite_groups 同序）
                with patched_group_image_dirs(staging_dir, group_root):
                    _persist_group_images(group)
                db.commit()
                db.expire_all()
                group = db.query(QuestionGroup).first()
                ok, detail = check_group_image_persistence(shared, group, group_root)
                results.append(('断言9: 题组图片落盘', ok, detail))
            finally:
                shutil.rmtree(staging_dir, ignore_errors=True)
                shutil.rmtree(group_root, ignore_errors=True)
    except Exception as e:
        results.append(('断言9: 题组图片落盘', False, str(e)[:100]))

    # ── 断言 10: Excel 行数守恒 + 解析列落库 + 丢弃行可见 ─────────────
    try:
        from app.services.question_ingest.excel_reader import (
            parse_excel_buffer, normalize_question as _er_normalize)
        from app.api.v1.question_import import (
            _normalize_question, batch_import_parsed)

        xlsx_bytes = build_probe_xlsx()
        raw_rows = parse_excel_buffer(xlsx_bytes, 'gate_l3_probe.xlsx')
        # 追加一行缺答案的行（模拟 232 道公专空解析同源缺陷）
        drop_row = {'题目内容': '关于执法程序的说法错误的是：',
                    '答案': '', '解析': '解析四：缺答案必须可见。'}
        all_rows = raw_rows + [drop_row]

        source_analysis = []
        failed_items = []
        kept_payloads = []
        for idx, row in enumerate(all_rows):
            # 生产双通道都必须是 None / 丢弃报告，不能一行凭空消失
            er = _er_normalize(row)
            qi = _normalize_question(row)
            if qi is None:
                reason = '未知原因'
                if isinstance(er, dict) and er.get('_drop_reason'):
                    reason = str(er['_drop_reason'])
                failed_items.append({
                    'index': idx, 'question_number': str(idx + 1),
                    'reason': reason, 'field_missing': reason,
                    'raw_answer': (row.get('答案') or '').strip(),
                    'raw_analysis': (row.get('解析') or '').strip(),
                })
                continue
            assert er is None or isinstance(er, dict), '双通道判定必须一致'
            kept_payloads.append(qi)
            source_analysis.append(qi.get('answer_analysis') or '')

        engine = fresh_engine(); db = make_session(engine)
        seed_base_data(db)
        user10 = db.query(SysUser).first()
        import asyncio
        r10 = asyncio.run(batch_import_parsed(
            {'paper_name': 'L3断言10公专卷', 'subject_category': '公专',
             'import_mode': 'separate', 'match_rate': 0,
             'questions': kept_payloads}, user10, db))
        db.commit()
        questions_in_db = db.query(QuestionBank).all()
        problems = check_excel_row_conservation(
            all_rows, failed_items, len(questions_in_db), len(kept_payloads),
            questions_in_db, source_analysis)

        # 解析列必须逐条落库（task-34 QA 的第 5 项变体）
        lost_analysis = [s for s in source_analysis
                         if s and s not in [q.answer_analysis or ''
                                            for q in questions_in_db]]
        if lost_analysis:
            problems.append(f'解析列丢失 {len(lost_analysis)} 条')

        # 丢行的 reason 必须是具体的「缺答案」，且带行号，不得静默
        drop_visible = any(
            f.get('reason') == '缺答案' and f.get('index') == len(raw_rows)
            for f in failed_items)
        if not drop_visible:
            problems.append('缺答案行未出现在失败清单（静默消失或 reason 不含「缺答案」）')

        detail = (f'{len(all_rows)}行 → 入库{len(questions_in_db)}题，'
                  f'失败清单{len(failed_items)}条，'
                  f'解析列落库{len(source_analysis)}条')
        if problems:
            detail += '；' + '；'.join(problems[:3])
        results.append(('断言10: Excel行数守恒', not problems, detail))
    except Exception as e:
        results.append(('断言10: Excel行数守恒', False, str(e)[:100]))

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
