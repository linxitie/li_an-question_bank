"""
历史题目题型/答案统一修复脚本
================================
修复三类历史数据问题（幂等，可重复运行）：

1. question_bank.type_id 错位：122 道选择题的 type_id 指向"论述题"、25 道多选指向"单选"，
   导致教师端列表（读 q.type.type_name）显示错误题型。
2. 多选题被标为单选：真实多选（答案含≥2个A-D字母）在 question_detail_category 层被标为"单选题"。
3. 选择题答案未归一化："A、B、C" / "A B" / "对" / "错" 等未统一为 "ABC" / "A" / "B"。

修复策略（单一事实来源）：
- 统一复用 text_parser 的 _detect_question_type（分层分类器）+ canonical_answer（答案归一化）。
- 同时修正 question_bank.type_id 与 question_detail_category.question_type_detail，使二者一致。

用法:
    python scripts/repair_question_types.py --dry-run   # 仅报告（默认）
    python scripts/repair_question_types.py --apply     # 实际写入（先自动备份+JSONL审计）

审计与回滚:
    --apply 执行前自动备份整库至 data/backups/backup_pre_typerepair_{ts}.sqlite，
    每笔变更写入 data/audit/type_repair_{ts}.jsonl（含整行快照），支持人工回滚。
"""
import sys
import os
import json
import shutil
import sqlite3
import argparse
import logging
from collections import Counter
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import and_
from app.core.database import SessionLocal
from app.models.models import QuestionBank, QuestionDetailCategory, QuestionType
from app.services.text_parser import _detect_question_type, canonical_answer, normalize_type_name

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def _get_or_create_type(db, type_name: str, subject_id: int) -> QuestionType:
    """按 (type_name, subject_id) 解析题型行；不存在则创建（不 commit，由调用方统一提交）。"""
    qtype = db.query(QuestionType).filter(and_(
        QuestionType.type_name == type_name,
        QuestionType.subject_id == subject_id
    )).first()
    if qtype:
        return qtype

    # 兼容旧 type_code 格式
    legacy = db.query(QuestionType).filter(
        QuestionType.type_code == f"auto_{type_name}"
    ).first()
    if legacy and legacy.subject_id == subject_id:
        return legacy

    qtype = QuestionType(
        type_name=type_name,
        type_code=f"auto_{subject_id}_{type_name}",
        subject_id=subject_id,
        is_objective=1 if type_name in ('单选题', '多选题') else 0,
    )
    db.add(qtype)
    db.flush()
    return qtype


def _detected_type(q: QuestionBank):
    """对单题做关键词工程重检测，返回 (detected_type, normalized_answer)。

    注意：_detect_question_type 返回 (type_name, confidence) 元组，必须解包，
    否则 detected 为元组导致后续所有比较恒为"已变化"（历史 bug，会污染全表）。
    """
    content = q.question_content or ''
    options = q.options
    detected, _conf = _detect_question_type(content, options, q.answer or '')
    # 客观选择题：答案归一化（A、B → AB；对/错 → A/B）；论述/写作保留原文
    if detected in ('单选题', '多选题'):
        norm = canonical_answer(q.answer or '')
        new_answer = norm if norm else (q.answer or '')
    else:
        new_answer = q.answer or ''
    return detected, new_answer


def _backup_db() -> str:
    """整库备份（--apply 前调用），返回备份路径。"""
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(backend_dir, 'data', 'question_bank.db')
    backup_dir = os.path.join(backend_dir, 'data', 'backups')
    os.makedirs(backup_dir, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    dst = os.path.join(backup_dir, f'backup_pre_typerepair_{ts}.sqlite')
    con = sqlite3.connect(db_path)
    con.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    con.close()
    shutil.copy2(db_path, dst)
    return dst


def _write_audit(change_rows: list) -> str:
    """变更明细写入 JSONL 审计日志，返回路径。"""
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    audit_dir = os.path.join(backend_dir, 'data', 'audit')
    os.makedirs(audit_dir, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    path = os.path.join(audit_dir, f'type_repair_{ts}.jsonl')
    with open(path, 'w', encoding='utf-8') as f:
        for r in change_rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    return path


def repair(dry_run: bool = True):
    db = SessionLocal()
    try:
        questions = db.query(QuestionBank).filter(QuestionBank.status == 1).all()
        total = len(questions)
        logger.info(f"共 {total} 道题目待检查（dry_run={dry_run}）")

        stats = {
            'total': total,
            'type_id_changed': 0,
            'detail_changed': 0,
            'answer_changed': 0,
            'placeholder_answer': 0,
        }
        before_counter = Counter()
        after_counter = Counter()
        change_rows = []

        for q in questions:
            old_bank_type = q.type.type_name if q.type else ''
            detail = db.query(QuestionDetailCategory).filter(
                QuestionDetailCategory.question_id == q.question_id
            ).first()
            old_detail_type = detail.question_type_detail if detail else ''

            detected, new_answer = _detected_type(q)

            # ★ 零证据保护：答案为空/待补充时不翻转题型（无答案支撑的重判不可靠，
            #   等解析回填拿到真实答案后再重跑本脚本即可补判）
            if (q.answer or '').strip() in ('', '待补充') and detected != old_bank_type:
                detected = old_bank_type or detected

            before_counter[old_bank_type or '(null)'] += 1
            after_counter[detected] += 1

            if q.answer == '待补充':
                stats['placeholder_answer'] += 1

            # 判定是否变化
            type_changed = detected != old_bank_type
            detail_changed = detected != old_detail_type
            answer_changed = new_answer != (q.answer or '')

            if type_changed:
                stats['type_id_changed'] += 1
            if detail_changed:
                stats['detail_changed'] += 1
            if answer_changed:
                stats['answer_changed'] += 1

            if type_changed or detail_changed or answer_changed:
                change_rows.append({
                    'question_id': q.question_id,
                    'old_bank': old_bank_type,
                    'old_detail': old_detail_type,
                    'new': detected,
                    'old_answer': q.answer or '',
                    'new_answer': new_answer,
                })
                logger.info(
                    f"Q{q.question_id}: bank[{old_bank_type}] detail[{old_detail_type}] "
                    f"→ {detected} | answer[{q.answer!r}] → [{new_answer!r}]"
                )

            if not dry_run:
                # 1) 修正 question_bank.type_id（若题型变化）
                if type_changed:
                    qtype = _get_or_create_type(db, detected, q.subject_id)
                    q.type_id = qtype.type_id
                # 2) 归一化选择题答案
                if answer_changed:
                    q.answer = new_answer
                # 3) 修正 question_detail_category（若题型变化）
                if detail_changed:
                    if detail:
                        detail.question_type_detail = detected
                    else:
                        db.add(QuestionDetailCategory(
                            question_id=q.question_id,
                            question_type_detail=detected,
                        ))

        if not dry_run:
            backup_path = _backup_db()
            logger.info(f"已备份整库 → {backup_path}")
            db.commit()
            logger.info("已提交全部修改")
            audit_path = _write_audit(change_rows)
            logger.info(f"审计日志 → {audit_path}（{len(change_rows)} 条变更）")

        # ===== 汇总报表 =====
        print("\n" + "=" * 60)
        print("修复汇总（dry_run=%s）" % dry_run)
        print("=" * 60)
        print(f"题目总数         : {stats['total']}")
        print(f"type_id 修正      : {stats['type_id_changed']}")
        print(f"detail 修正       : {stats['detail_changed']}")
        print(f"答案归一化        : {stats['answer_changed']}")
        print(f"待补充答案(人工)  : {stats['placeholder_answer']}")
        print("\n题型分布（修复前 → 修复后）:")
        for k in sorted(set(before_counter) | set(after_counter)):
            print(f"  {k:<12}: {before_counter.get(k, 0):>4} → {after_counter.get(k, 0):>4}")

        if change_rows:
            print("\n变更明细（前 %d 条）:" % min(len(change_rows), 200))
            for r in change_rows[:200]:
                print(f"  #{r['question_id']:<5} {r['old_bank']:<6}/{r['old_detail']:<6} → {r['new']:<6} "
                      f"ans[{r['old_answer']!r}→{r['new_answer']!r}]")
        return stats
    finally:
        db.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="历史题目题型/答案统一修复")
    parser.add_argument('--dry-run', dest='dry_run', action='store_true', default=True, help='仅报告不写入（默认）')
    parser.add_argument('--apply', dest='dry_run', action='store_false', help='实际写入数据库')
    args = parser.parse_args()
    repair(dry_run=args.dry_run)
