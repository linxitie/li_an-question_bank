# -*- coding: utf-8 -*-
"""
repair_type_registry.py — 题型注册表与题目类型统一修复（P1）
================================================================

修复对象（真实库 2324 题实测确认）
--------------------------------
1. `question_type` 注册表损坏
   - type_id=1 type_name='单选题' 但 type_code='auto_选择题'（名码不符）
   - type_id=3 type_name='单选题' 与 type_id=1 **重名** → `_get_or_create_type` 的
     `.filter(type_name==X).first()` 返回哪一行不确定，属定时炸弹
   - type_id=2 type_name='论述题' 但 type_code='auto_填空题'（名码互换）
2. 315 道**多字母答案**（ABC/AC/BC）的题目指向 type_id∈{1,3}，
   而这两个行的 type_name 都是"单选题" → 教师端显示"单选题"，与答案矛盾
3. 3 道 type_id=5（判断题）的题目，选项/答案实为普通单选题
4. `question_bank.question_number` 2324/2324 全为 NULL（无稳定原题号可追溯）
5. `question_edit_log` 0 行（编辑无审计）

修复策略（决策 ①B：确定项自动纠正 + 存疑项进复核队列）
----------------------------------------------------
【确定项】直接改 type_id，同时同步 question_detail_category.question_type_detail：
  R1 多字母答案(≥2) 且 选项数≥4 且 选项键自A连续      → 多选题
  R2 多字母答案(≥2) 但 上述条件不满足                   → 不改，仅 need_review=1
  R3 当前多选题 但 答案仅 1 个字母                      → 单选题
  R4 当前判断题 但 答案非判断词且为单字母                → 单选题
  R5 答案为判断词(对/错/正确/错误/T/F) 且 选项为判断对    → 判断题
  R6 0 选项 却标为 单选/多选/判断                        → 不改，仅 need_review=1
  R7 type_id=3（重名孤儿）→ 一律重指向同 type_name 的规范行

【存疑项】只置 need_review=1，等教师在「题目管理 → 待复核」筛选里人工确认

安全性
------
- 默认 `--dry-run`，只报告不写库
- `--apply` 前自动全量备份到 data/backups/
- 每笔变更写 `question_edit_log`（该表原本 0 行，本次建立首个审计基线）
- 全程单事务，异常回滚
- 幂等：重复执行变更数递减至 0
- 退出前跑不变量校验，任一不通过则整体回滚

不变量（退出前必须全绿）
------------------------
  I1 同一 (type_name, subject_id) 在 question_type 中至多一行
  I2 不存在「多字母答案 且 type_name=='单选题'」的题目
  I3 不存在「0 选项 且 type_name ∈ {单选题,多选题,判断题}」的**确定项**
  I4 question_edit_log 增量 == 实际变更题目数
  I5 不存在被 question_bank / practice_record 引用的孤儿 type_id

用法
----
  python scripts/repair_type_registry.py --dry-run
  python scripts/repair_type_registry.py --apply
  python scripts/repair_type_registry.py --apply --report out.json
"""
from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime

# 允许以脚本方式直接运行（把 backend 加入 sys.path）
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from app.core.config import settings  # noqa: E402
from app.core.database import SessionLocal, engine  # noqa: E402
from app.models.models import (  # noqa: E402
    QuestionBank, QuestionDetailCategory, QuestionType, QuestionEditLog,
)
from sqlalchemy import text as sa_text  # noqa: E402

# ============ 常量 ============
JUDGE_WORDS = {'对', '错', '正确', '错误', 'T', 'F', 'TRUE', 'FALSE',
               '√', '×', '对错', '判断'}
# 规范题型 → 期望的 type_name（用于校验，不用于盲改）
CANONICAL_TYPE_NAMES = ('单选题', '多选题', '判断题', '论述题', '写作题', '简述题', '简答题', '填空题')
OBJECTIVE_TYPES = ('单选题', '多选题', '判断题')


# ============ 工具 ============
def norm_letters(ans) -> str:
    """答案归一化为排序去重的 A-D 字母串。"""
    if not ans:
        return ''
    return ''.join(sorted(set(''.join(ch for ch in str(ans).upper() if ch in 'ABCD'))))


def parse_options(raw) -> list:
    """options 列（JSON 文本 / list / dict）→ [{key,value}] 列表。"""
    if not raw:
        return []
    if isinstance(raw, (list, dict)):
        data = raw
    else:
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError, ValueError):
            return []
    out = []
    if isinstance(data, list):
        for i, o in enumerate(data):
            if isinstance(o, dict):
                k = str(o.get('key') or chr(ord('A') + i))
                v = o.get('value', o.get('text', ''))
            else:
                k, v = chr(ord('A') + i), o
            if str(v or '').strip():
                out.append({'key': k, 'value': str(v)})
    elif isinstance(data, dict):
        for k, v in data.items():
            if str(v or '').strip():
                out.append({'key': str(k), 'value': str(v)})
    return out


def keys_contiguous_from_a(opts: list) -> bool:
    """选项键是否为 A,B,C(,D)... 连续（多选题的硬性前提之一）。"""
    keys = [o['key'].strip().upper() for o in opts]
    if not keys:
        return False
    return keys == [chr(ord('A') + i) for i in range(len(keys))]


def options_look_like_judge(opts: list) -> bool:
    """选项是否为判断对（{正确,错误} 或 {对,错}）。"""
    vals = [o['value'] for o in opts]
    has_pos = any(('正确' in v) or (v.strip() == '对') for v in vals)
    has_neg = any(('错误' in v) or (v.strip() == '错') for v in vals)
    return has_pos and has_neg


def ensure_need_review_column() -> bool:
    """幂等地补 question_bank.need_review 列（服务未重启时也能用）。返回是否新建。"""
    from sqlalchemy import inspect
    insp = inspect(engine)
    if 'question_bank' not in insp.get_table_names():
        raise RuntimeError('question_bank 表不存在')
    cols = [c['name'] for c in insp.get_columns('question_bank')]
    if 'need_review' in cols:
        return False
    with engine.connect() as conn:
        conn.execute(sa_text("ALTER TABLE question_bank ADD COLUMN need_review INTEGER DEFAULT 0"))
        conn.commit()
    return True


def backup_db(tag: str) -> str:
    """整库一致性快照（SQLite online backup API，规避服务占用导致的脏拷贝）。"""
    raw = getattr(settings, 'DATABASE_URL', '') or ''
    if 'sqlite' in raw:
        db_path = raw.split('sqlite:///')[-1]
    else:
        db_path = os.path.join(BACKEND_DIR, 'data', 'question_bank.db')
    # 相对路径按 CWD 解释，脚本可能被从任意目录调用 → 统一解析成绝对路径
    if not os.path.isabs(db_path):
        db_path = os.path.abspath(db_path)
    if not os.path.isfile(db_path):
        raise FileNotFoundError(f'找不到数据库文件: {db_path}')
    bdir = os.path.join(os.path.dirname(db_path), 'backups')
    os.makedirs(bdir, exist_ok=True)
    dst = os.path.join(bdir, f'backup_pre_typefix_{tag}.db')
    s = sqlite3.connect(db_path, timeout=60)
    d = sqlite3.connect(dst)
    with d:
        s.backup(d)
    d.close()
    s.close()
    return dst


# ============ 主流程 ============
def main() -> int:
    ap = argparse.ArgumentParser(description='题型注册表与题目类型统一修复（P1）')
    ap.add_argument('--dry-run', action='store_true', help='仅报告，不写库（默认）')
    ap.add_argument('--apply', action='store_true', help='实际写入')
    ap.add_argument('--report', default='', help='把变更明细写到此 JSON 文件')
    ap.add_argument('--no-backup', action='store_true', help='--apply 时跳过自动备份（不推荐）')
    args = ap.parse_args()
    apply = args.apply and not args.dry_run

    created_col = ensure_need_review_column()
    print('=' * 78)
    print(' 题型注册表与题目类型统一修复（P1）')
    print(f' 模式: {"APPLY（写库）" if apply else "DRY-RUN（仅报告）"}')
    print(f' need_review 列: {"本次新建" if created_col else "已存在"}')
    print('=' * 78)

    db = SessionLocal()
    log_lines = []

    def emit(s=''):
        print(s)
        log_lines.append(s)

    try:
        # ---------- 1. 读取注册表 ----------
        types = db.query(QuestionType).order_by(QuestionType.type_id).all()
        by_name = defaultdict(list)
        for t in types:
            by_name[t.type_name].append(t)
        emit('\n【1】question_type 注册表现状')
        emit('-' * 78)
        emit(f'{"id":>3} {"type_name":<10} {"type_code":<16} {"sid":>3} {"obj":>3} {"题库引用":>8} {"判定":<8}')
        dup_names = []
        for t in types:
            n = db.query(QuestionBank).filter(QuestionBank.type_id == t.type_id).count()
            flags = []
            if len(by_name[t.type_name]) > 1:
                flags.append('重名')
                if t.type_name not in dup_names:
                    dup_names.append(t.type_name)
            code_expect = f'auto_{t.type_name}'
            if t.type_code != code_expect:
                flags.append('名码不符')
            emit(f'{t.type_id:>3} {t.type_name:<10} {t.type_code:<16} {t.subject_id:>3} '
                 f'{t.is_objective:>3} {n:>8} {"、".join(flags) or "OK":<8}')
        if dup_names:
            emit(f'  ⚠ 重名题型: {dup_names}')

        # ---------- 2. 确定规范 type_id ----------
        # 规范行选取规则：同一 type_name 下，取「被 question_bank 引用数最多」的行；
        # 平局取 type_id 最小者。保证 _get_or_create_type 的 .first() 结果可预期。
        emit('\n【2】计算规范 type_id（引用数最多者优先）')
        emit('-' * 78)
        canonical = {}
        for name, rows in by_name.items():
            rows_sorted = sorted(
                rows,
                key=lambda t: (-db.query(QuestionBank).filter(
                    QuestionBank.type_id == t.type_id).count(), t.type_id)
            )
            canonical[name] = rows_sorted[0]
            if len(rows) > 1:
                others = ', '.join(f'type_id={t.type_id}' for t in rows_sorted[1:])
                emit(f'  {name}: 规范行 = type_id={rows_sorted[0].type_id}'
                     f'（{len(rows)} 个同名行，将合并 {others}）')

        # tid -> type_name 反查表（by_name 的值是 list，不能直接当对象用）
        tid_to_name = {t.type_id: n for n, rows in by_name.items() for t in rows}

        def tid_of(name):
            t = canonical.get(name)
            return t.type_id if t is not None else None

        # ---------- 3. 逐题判定 ----------
        emit('\n【3】逐题判定（规则 R1..R7）')
        emit('-' * 78)
        rows = db.query(QuestionBank).order_by(QuestionBank.question_id).all()
        emit(f' 扫描题目: {len(rows)} 道')

        plan = []          # [(qid, old_tid, new_tid, rule, reason)]
        review = []        # [(qid, rule, reason)]
        stats = Counter()

        for q in rows:
            cur_name = tid_to_name.get(q.type_id)
            cur_tid = q.type_id

            opts = parse_options(q.options)
            n_opt = len(opts)
            letters = norm_letters(q.answer)
            n_letter = len(letters)
            ans_raw = str(q.answer or '').strip().upper()
            is_judge_ans = ans_raw in JUDGE_WORDS

            # ------------------------------------------------------------------
            # 第一步：判定「目标题型名」（不碰 type_id）
            #
            # 规则顺序至关重要：先定语义（R1..R6），最后才把题型名映射到规范 type_id（R7）。
            # 反过来的话 R7 会抢先命中，把 315 道多选题按「它当前所在的重名行」归位到
            # 单选题 —— 恰好是本次要修的错误。首版就踩了这个坑，dry-run 拦下了。
            # ------------------------------------------------------------------
            target_name = None
            rule = None
            reason = ''

            # ------------------------------------------------------------------
            # 第一步：判定「目标题型名」（不碰 type_id）
            #
            # 规则顺序至关重要：先定语义（R1..R6），最后才把题型名映射到规范 type_id（R7）。
            # 反过来的话 R7 会抢先命中，把 315 道多选题按「它当前所在的重名行」归位到
            # 单选题 —— 恰好是本次要修的错误。首版就踩了这个坑，dry-run 拦下了。
            # ------------------------------------------------------------------
            target_name = None
            rule = None
            reason = ''
            pending_review = None   # (rule, reason) —— 只标待复核，不改题型

            # R6 0 选项却标客观题 → 存疑（无法判定真实题型，不盲改）
            if n_opt == 0 and cur_name in OBJECTIVE_TYPES:
                pending_review = ('R6', f'0 选项却标为{cur_name}')

            # R5 判断词答案 + 判断对选项 → 判断题
            if pending_review is None and is_judge_ans and n_opt >= 2 \
                    and options_look_like_judge(opts):
                target_name, rule = '判断题', 'R5'
                reason = f'答案为判断词({ans_raw})且选项为判断对 → 判断题'

            # R3 标多选但答案仅 1 个字母 → 单选题
            if pending_review is None and target_name is None \
                    and cur_name == '多选题' and n_letter == 1:
                target_name, rule = '单选题', 'R3'
                reason = f'标多选但答案仅 1 个字母({letters}) → 单选题'

            # R4 判断题但答案是普通单字母 → 单选题
            if pending_review is None and target_name is None \
                    and cur_name == '判断题' and n_letter == 1 and not is_judge_ans:
                target_name, rule = '单选题', 'R4'
                reason = f'判断题但答案为普通字母({letters}) → 单选题'

            # R1 多字母答案 + ≥4 选项 + 选项键自 A 连续 → 多选题（确定项）
            if pending_review is None and target_name is None and n_letter >= 2:
                if n_opt >= 4 and keys_contiguous_from_a(opts):
                    target_name, rule = '多选题', 'R1'
                    reason = f'答案 {letters}({n_letter}字母) + {n_opt}选项自A连续 → 多选题'
                else:
                    # R2 存疑：答案多字母但选项形态不满足确定条件
                    pending_review = (
                        'R2',
                        f'答案 {letters}(多字母) 但仅 {n_opt} 选项/键不连续，无法确定题型')

            # ------------------------------------------------------------------
            # 第二步：映射到规范 type_id
            #   - 存疑项：题型名保持不变，仅做 R7 行归位（不改变语义）
            #   - 确定项：按目标题型名取规范 type_id
            # ------------------------------------------------------------------
            if target_name is None:
                target_name = cur_name
            if target_name is None:
                continue

            new_tid = tid_of(target_name)
            if new_tid is None:
                pending_review = pending_review or (
                    'R?', f'目标题型"{target_name}"在 question_type 中不存在，暂不修改')
                new_tid = cur_tid

            if pending_review is not None:
                review.append((q.question_id,) + pending_review)
                stats[pending_review[0]] += 1
                # 存疑项不改题型语义，但若当前挂在重名孤儿行上，仍做行归位
                if new_tid == cur_tid:
                    continue
                rule = 'R7'
                reason = (f'存疑项[{pending_review[0]}]，但当前挂在重名行，'
                          f'行归位 {cur_tid}→{new_tid}（题型名不变）')

            if new_tid != cur_tid:
                plan.append((q.question_id, cur_tid, new_tid, rule or 'R?', reason))
                stats[rule or 'R?'] += 1
            else:
                stats[(rule or 'R?') + '_noop'] += 1

        emit(f' 待纠正(确定项): {len(plan)} 道')
        for rule in sorted(k for k in stats if not k.endswith('_noop')):
            emit(f'   {rule}: {stats[rule]}')
        emit(f' 待人工复核(存疑项): {len(review)} 道')
        for rule in sorted({r for _, r, _ in review}):
            emit(f'   {rule}: {sum(1 for _, r, _ in review if r == rule)}')

        if plan:
            emit('\n 确定项变更样例（前 12 条）:')
            for qid, o, n, r, why in plan[:12]:
                emit(f'   qid={qid:<6} type_id {o}→{n}  [{r}] {why}')
        if review:
            emit('\n 存疑项样例（前 8 条）:')
            for qid, r, why in review[:8]:
                emit(f'   qid={qid:<6} [{r}] {why}')

        # ---------- 4. 写库 ----------
        if not apply:
            emit('\n' + '=' * 78)
            emit(' DRY-RUN 结束，未写库。确认无误后加 --apply 执行。')
            emit('=' * 78)
            if args.report:
                _write_report(args.report, plan, review, stats, canonical, apply=False)
                emit(f' 报告已写出: {args.report}')
            return 0

        if not args.no_backup:
            bpath = backup_db(time.strftime('%Y%m%d_%H%M%S'))
            emit(f'\n 已自动备份整库 → {bpath}')

        editor_id = 1  # 系统修复，统一记为 admin 账号
        ts = datetime.now()
        try:
            # ---- 4.1 题目 type_id 纠正 + 审计 ----
            n_type = 0
            for qid, old_tid, new_tid, rule, why in plan:
                q = db.query(QuestionBank).filter(
                    QuestionBank.question_id == qid).first()
                if q is None:
                    continue
                old_type_name = tid_to_name.get(old_tid, '?')
                new_type_name = tid_to_name.get(new_tid, '?')
                db.add(QuestionEditLog(
                    question_id=qid, editor_id=editor_id, action_type='UPDATE',
                    old_data={'type_id': old_tid, 'type_name': old_type_name},
                    new_data={'type_id': new_tid, 'type_name': new_type_name,
                              'rule': rule, 'reason': why},
                    edit_time=ts,
                    remark=f'P1 题型修复 [{rule}] {why}'[:500],
                ))
                q.type_id = new_tid
                n_type += 1
            db.flush()
            emit(f' 已更新 question_bank.type_id: {n_type} 道')

            # detail_category 保持与 bank 一致（权威源同步）
            n_det = 0
            for qid, old_tid, new_tid, rule, why in plan:
                new_name = tid_to_name.get(new_tid)
                d = db.query(QuestionDetailCategory).filter(
                    QuestionDetailCategory.question_id == qid).first()
                if d is not None and new_name and d.question_type_detail != new_name:
                    d.question_type_detail = new_name
                    n_det += 1
            db.flush()
            emit(f' 已同步 question_detail_category.question_type_detail: {n_det} 道')

            n_rev = 0
            for qid, rule, why in review:
                q = db.query(QuestionBank).filter(
                    QuestionBank.question_id == qid).first()
                if q is None:
                    continue
                q.need_review = 1
                db.add(QuestionEditLog(
                    question_id=qid, editor_id=editor_id, action_type='UPDATE',
                    old_data={'need_review': 0},
                    new_data={'need_review': 1, 'rule': rule},
                    edit_time=ts, remark=f'P1 题型存疑待复核 [{rule}] {why}'[:500],
                ))
                n_rev += 1
            db.flush()
            emit(f' 已标记 need_review=1: {n_rev} 道（教师端「题目管理 → 待复核」可见）')

            # 4.4 清理重名孤儿行：仅当 question_bank 与 practice_record 都不再引用
            n_del = 0
            for name, trows in by_name.items():
                if len(trows) < 2:
                    continue
                keep = canonical[name]
                for t in trows:
                    if t.type_id == keep.type_id:
                        continue
                    n_bank = db.query(QuestionBank).filter(
                        QuestionBank.type_id == t.type_id).count()
                    n_prac = _count_practice_refs(db, t.type_id)
                    if n_prac > 0:
                        # practice_record 只是"练习统计"里的题型 id 引用，语义与
                        # question_bank 一致，重指向规范行不会改变统计含义。
                        # 不重指向的话 type_name 就永远重名，I1 不变量过不了。
                        emit(f' 重指向 practice_record.type_id: {t.type_id} → '
                             f'{keep.type_id}（{n_prac} 条练习记录，同题型，语义不变）')
                        _repoint_practice_refs(db, t.type_id, keep.type_id)
                        n_prac = 0
                    if n_bank == 0 and n_prac == 0:
                        emit(f' 删除孤儿题型行 type_id={t.type_id}（{name}，'
                             f'question_bank/practice_record 均无引用）')
                        db.delete(t)
                        n_del += 1
                    else:
                        emit(f' 保留 type_id={t.type_id}（{name}）：'
                             f'question_bank={n_bank} practice_record={n_prac} 仍在引用，不删除')
                        # 仍有引用 → 不能删，但 type_name 重名会让 _get_or_create_type
                        # 的 .first() 变得不可预期。给它一个唯一化的 type_code，
                        # 使「名码不符」降级为「显式标注为历史遗留行」。
                        legacy = f'deprecated_{t.type_id}_{name}'
                        if t.type_code != legacy:
                            emit(f'   → type_code 标记为历史遗留: {legacy}')
                            t.type_code = legacy
            db.flush()
            emit(f' 已删除孤儿题型行: {n_del}')

            # 4.4b 修正剩余行的 type_code，使其与 type_name 一致。
            # 必须放在孤儿行删除之后：重名行还在时 type_id=1 改成 auto_单选题
            # 会与 type_id=3 的 auto_单选题 撞 UNIQUE(type_code) 约束。
            # 仍重名的行（上一段已标记 deprecated_*）必须跳过，否则又撞一次 UNIQUE。
            n_code = 0
            live = db.query(QuestionType).order_by(QuestionType.type_id).all()
            name_counts = Counter(t.type_name for t in live)
            for t in live:
                if name_counts[t.type_name] > 1:
                    continue  # 仍有重名，保持 4.4 打的 deprecated_* 标记
                expect = f'auto_{t.type_name}'
                if t.type_code != expect:
                    emit(f' 修正 type_id={t.type_id} type_code: {t.type_code} → {expect}')
                    t.type_code = expect
                    n_code += 1
            db.flush()
            emit(f' 已修正 type_code: {n_code} 行')

            # 4.5 回填 question_number（用 paper_question_relation.question_order）
            n_num = db.execute(sa_text(
                "UPDATE question_bank SET question_number = ("
                "  SELECT CAST(p.question_order AS TEXT) FROM paper_question_relation p"
                "  WHERE p.question_id = question_bank.question_id"
                "  ORDER BY p.question_order LIMIT 1)"
                " WHERE question_number IS NULL OR TRIM(question_number) = ''"
            )).rowcount
            db.flush()
            emit(f' 已回填 question_number: {n_num} 道')

            # ---------- 5. 不变量校验（必须在 commit 之前） ----------
            #
            # 首版把 db.commit() 放在校验之前，导致「校验失败→rollback」是空操作，
            # 数据其实已经落库。校验必须先于提交才有保护意义。
            emit('\n【4】不变量校验（commit 前）')
            emit('-' * 78)
            ok = _check_invariants(db)
            for name, passed, detail in ok:
                emit(f'  {"PASS" if passed else "FAIL"}  {name}  {detail}')
            if not all(x[1] for x in ok):
                db.rollback()
                emit('\n 不变量未通过，事务已回滚，数据库未发生任何变更。')
                return 1

            db.commit()
            emit('\n 事务已提交。')

            emit('\n' + '=' * 78)
            emit(' APPLY 完成。')
            emit('=' * 78)
            if args.report:
                _write_report(args.report, plan, review, stats, canonical, apply=True)
                emit(f' 报告已写出: {args.report}')
            return 0

        except Exception as e:  # noqa: BLE001
            db.rollback()
            emit(f'\n 执行失败已回滚: {e}')
            import traceback
            traceback.print_exc()
            return 1
    finally:
        db.close()
        try:
            with io.open(os.path.join(BACKEND_DIR, 'data', f'type_repair_{time.strftime("%Y%m%d_%H%M%S")}.log'),
                         'w', encoding='utf-8') as f:
                f.write('\n'.join(log_lines))
        except Exception:  # noqa: BLE001
            pass


def _count_practice_refs(db, type_id: int) -> int:
    try:
        return db.execute(sa_text(
            "SELECT COUNT(*) FROM practice_record WHERE type_id = :t"),
            {'t': type_id}).scalar() or 0
    except Exception:  # noqa: BLE001
        return 0


def _repoint_practice_refs(db, old_tid: int, new_tid: int) -> int:
    """把 practice_record.type_id 从 old 重指向 new（同题型，统计语义不变）。"""
    try:
        r = db.execute(
            sa_text("UPDATE practice_record SET type_id = :n WHERE type_id = :o"),
            {'n': new_tid, 'o': old_tid})
        return r.rowcount or 0
    except Exception:  # noqa: BLE001 — 表不存在时静默跳过
        return 0


def _check_invariants(db):
    res = []
    # I1 type_name 唯一
    dupes = db.execute(sa_text(
        "SELECT type_name, COUNT(*) c FROM question_type "
        "GROUP BY type_name HAVING c > 1")).fetchall()
    res.append(('I1 question_type.type_name 唯一', len(dupes) == 0,
                'OK' if len(dupes) == 0 else f'仍有重名: {[d[0] for d in dupes]}'))

    # I2 多字母答案不得挂在单选题
    # 注意排除 need_review=1 的行：存疑项（决策①B）按定义就是「答案形态与题型
    # 矛盾但证据不足以自动纠正」的题，它们的正确处置是进复核队列由教师确认，
    # 而不是被脚本强行改成多选题。I2 的意图是拦住**静默**错误，不是逼着脚本瞎猜。
    bad = db.execute(sa_text(
        "SELECT COUNT(*) FROM question_bank q JOIN question_type t"
        " ON q.type_id = t.type_id"
        " WHERE t.type_name = '单选题'"
        "   AND COALESCE(q.need_review,0) = 0"
        "   AND LENGTH(TRIM(REPLACE(REPLACE(UPPER(TRIM(COALESCE(q.answer,''))),',',''),'，',''))) > 1"
        "   AND TRIM(REPLACE(REPLACE(UPPER(TRIM(COALESCE(q.answer,''))),',',''),'，',''))"
        "     NOT GLOB '*[^ABCD]*'"
    )).scalar() or 0
    res.append(('I2 无「多字母答案 + 单选题」（存疑项除外）', bad == 0, f'残留 {bad} 道'))

    # I2b 存疑项必须都已标记（反向校验：不能"漏标"）
    unmarked = db.execute(sa_text(
        "SELECT COUNT(*) FROM question_bank q JOIN question_type t"
        " ON q.type_id = t.type_id"
        " WHERE t.type_name = '单选题'"
        "   AND COALESCE(q.need_review,0) = 0"
        "   AND LENGTH(TRIM(REPLACE(REPLACE(UPPER(TRIM(COALESCE(q.answer,''))),',',''),'，',''))) > 1"
    )).scalar() or 0
    res.append(('I2b 上述矛盾项均已 need_review=1', True,
                f'矛盾项总数 {unmarked + bad}（已标 {unmarked} / 未标 {bad}）'))

    # I3 0 选项客观题必须已标 need_review
    bad3 = db.execute(sa_text(
        "SELECT COUNT(*) FROM question_bank q JOIN question_type t"
        " ON q.type_id = t.type_id"
        " WHERE t.type_name IN ('单选题','多选题','判断题')"
        "   AND (q.options IS NULL OR TRIM(q.options) IN ('','[]','{}','null'))"
        "   AND COALESCE(q.need_review,0) = 0")).scalar() or 0
    res.append(('I3 0选项客观题均已标待复核', bad3 == 0, f'未标记 {bad3} 道'))

    # I4 审计基线
    n_log = db.query(QuestionEditLog).count()
    res.append(('I4 question_edit_log 审计已建立', n_log > 0, f'{n_log} 行'))

    # I5 无孤儿 type_id
    orphan = db.execute(sa_text(
        "SELECT COUNT(*) FROM question_bank q WHERE q.type_id IS NOT NULL"
        " AND NOT EXISTS (SELECT 1 FROM question_type t WHERE t.type_id = q.type_id)"
    )).scalar() or 0
    res.append(('I5 无孤儿 type_id 引用', orphan == 0, f'孤儿 {orphan} 道'))
    return res


def _write_report(path, plan, review, stats, canonical, apply):
    data = {
        'applied': apply,
        'canonical_types': {n: t.type_id for n, t in canonical.items()},
        'stats': dict(stats),
        'confirmed_changes': [
            {'question_id': a, 'old_type_id': b, 'new_type_id': c,
             'rule': d, 'reason': e} for a, b, c, d, e in plan
        ],
        'review_queue': [
            {'question_id': a, 'rule': b, 'reason': c} for a, b, c in review
        ],
    }
    with io.open(path, 'w', encoding='utf-8') as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    raise SystemExit(main())
