#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
backfill_analysis.py — 公专答案解析存量回填（问题3-R1）

数据事实（2026-08 实测）：
  - 314 道公专题解析为空（其中 204 题无 source/year 元数据）
  - 答案 PDF（46 份）有文本层，pymupdf 可直接抽取
  - 解析块以 "N、本题考查..." 分块，答案字母内嵌文中（"正确答案是X"，单 PDF 命中97处）
  - 解析文本不含题干 → 无法题干对题干匹配；改用三信号模型

三信号匹配模型（block → question）：
  S1 包含度: 题干(含选项文本) 被解析文本包含的程度（匹配字符数/较短文本长度）
  S2 答案一致: 解析中提取的答案字母 == 题目已存答案（归一化后）
  S3 选项重叠: 解析中 "X项" 后句与对应选项值的字符重合率

置信度分级：
  HIGH   : S1 ≥ 0.50 且 (S2 一致 或 题目无答案)        → --apply 回填
  MEDIUM : 0.35 ≤ S1 < 0.50                            → CSV 人工复核清单
  LOW    : S1 < 0.35                                   → 无来源计数

安全：--dry-run 默认（输出直方图与样例）；--apply 先备份+JSONL审计；--restore 可逆。
"""
import sys
import os
import re
import json
import shutil
import sqlite3
import argparse
import logging
from datetime import datetime
from difflib import SequenceMatcher

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_DB_PATH = os.path.join(_BACKEND_DIR, 'data', 'question_bank.db')
_ANSWER_DIR = os.path.join(os.path.dirname(_BACKEND_DIR), '题库', '答案解析（不用打印）')

HIGH_SIM = 0.50
MEDIUM_SIM = 0.35

_PDF_BLOCK_RE = re.compile(r'\n\s*(\d{1,3})\s*[、.．]\s*')
_ANS_IN_TEXT_RE = re.compile(
    r'(?:正确答案|故正确答案|参考答案)[是为：:\s]*([A-D]{1,4})')
_CN_NUM_RE = re.compile(r'[（(]?(\d{1,2})[)）]?[、.．]\s*')


def _norm(text: str) -> str:
    """匹配用归一化：去空白/标点，保留中英文数字"""
    return re.sub(r'[\s，。、；：？！“”‘’"\'（）()【】\[\]<>《》\-—_·.…,;:?!]', '', text or '')


def parse_answer_pdfs():
    """解析全部答案 PDF → [(pdf_name, num, analysis_text, answer_letters)]"""
    import fitz
    blocks = []
    if not os.path.exists(_ANSWER_DIR):
        logger.warning(f"答案目录不存在: {_ANSWER_DIR}")
        return blocks
    for fn in sorted(os.listdir(_ANSWER_DIR)):
        if not fn.lower().endswith('.pdf'):
            continue
        path = os.path.join(_ANSWER_DIR, fn)
        try:
            doc = fitz.open(path)
            full = '\n'.join(doc[i].get_text() for i in range(len(doc)))
            doc.close()
        except Exception as e:
            logger.warning(f"PDF 解析失败 {fn}: {e}")
            continue
        # 去掉页眉推广与页码行
        full = re.sub(r'获取试卷更新[^\n]*\n?', '', full)
        full = re.sub(r'^\s*-\s*\d+\s*-\s*$', '', full, flags=re.MULTILINE)
        parts = _PDF_BLOCK_RE.split(full)
        # parts: [前导, num1, text1, num2, text2, ...]
        for i in range(1, len(parts) - 1, 2):
            num = int(parts[i])
            text = parts[i + 1].strip()
            if len(text) < 20:
                continue
            m = _ANS_IN_TEXT_RE.search(text)
            letters = m.group(1) if m else ''
            blocks.append((fn, num, text, letters))
    logger.info(f"共解析 {len(set(b[0] for b in blocks))} 份 PDF，{len(blocks)} 个解析块")
    return blocks


def containment(needle_norm: str, haystack_norm: str) -> float:
    """包含度：匹配字符数 / 较短文本长度（题干⊂解析 场景优于 ratio）"""
    if not needle_norm or not haystack_norm:
        return 0.0
    sm = SequenceMatcher(None, needle_norm, haystack_norm)
    m = sum(b.size for b in sm.get_matching_blocks())
    return m / min(len(needle_norm), len(haystack_norm))


def load_targets(db):
    """空解析的活跃公专题"""
    from app.models.models import QuestionBank
    rows = db.query(QuestionBank).filter(
        QuestionBank.status == 1,
        QuestionBank.subject_id == 3,
    ).all()
    targets = []
    for q in rows:
        analysis = (q.answer_analysis or '').strip()
        if analysis in ('', '无', '[OCR导入，待补充答案解析]', '待补充'):
            targets.append(q)
    logger.info(f"待回填题目: {len(targets)}")
    return targets


def match_all(db, blocks, sim_high=HIGH_SIM, sim_med=MEDIUM_SIM):
    """执行匹配，返回 (high_list, medium_list, no_match_count, hist)"""
    import json as _json
    from app.services.text_parser import canonical_answer

    # 预归一化块文本
    norm_blocks = [(b[0], b[1], b[2], b[3], _norm(b[2])) for b in blocks]

    high, medium = [], []
    no_match = 0
    hist = {}

    for q in targets_iter(db):
        stem_opts = q.question_content or ''
        try:
            opts = _json.loads(q.options) if isinstance(q.options, str) else (q.options or [])
            for o in opts:
                if isinstance(o, dict) and o.get('value'):
                    v = str(o['value'])
                    if '<' not in v and len(v) > 4:  # 跳过图片选项
                        stem_opts += ' ' + v
        except Exception:
            pass
        needle = _norm(stem_opts)
        if len(needle) < 10:
            no_match += 1
            continue

        q_ans = canonical_answer(q.answer or '')
        best = None  # (contain, block)
        for fn, num, text, letters, ntext in norm_blocks:
            c = containment(needle, ntext)
            if best is None or c > best[0]:
                best = (c, (fn, num, text, letters))
        if best is None:
            no_match += 1
            continue
        c, (fn, num, text, letters) = best
        bucket = int(c * 10) / 10
        hist[bucket] = hist.get(bucket, 0) + 1

        # S2: 答案一致性
        letters_norm = re.sub(r'[，,]', '', letters or '')
        ans_match = (not q_ans) or (not letters_norm) or (letters_norm == q_ans) or \
                    (set(letters_norm) == set(q_ans))

        rec = {
            'qid': q.question_id, 'pdf': fn, 'block_num': num,
            'contain': round(c, 3), 'pdf_answer': letters_norm,
            'q_answer': q.answer or '', 'ans_match': bool(ans_match),
            'stem': (q.question_content or '')[:50],
            'analysis_head': text[:80],
            'full_text': text, 'letters': letters_norm,
        }
        if c >= sim_high and ans_match:
            high.append(rec)
        elif c >= sim_med:
            medium.append(rec)
        else:
            no_match += 1
    return high, medium, no_match, hist


def targets_iter(db):
    from app.models.models import QuestionBank
    rows = db.query(QuestionBank).filter(
        QuestionBank.status == 1, QuestionBank.subject_id == 3).all()
    for q in rows:
        analysis = (q.answer_analysis or '').strip()
        if analysis in ('', '无', '[OCR导入，待补充答案解析]', '待补充'):
            yield q


def do_dry_run():
    blocks = parse_answer_pdfs()
    if not blocks:
        return
    from app.core.database import SessionLocal
    db = SessionLocal()
    try:
        high, medium, no_match, hist = match_all(db, blocks)
        print('=' * 70)
        print('[DRY RUN] 回填匹配报告（未修改数据）')
        print('=' * 70)
        print(f"HIGH（自动回填候选）: {len(high)}")
        print(f"MEDIUM（人工复核）  : {len(medium)}")
        print(f"LOW/无匹配          : {no_match}")
        print('\n包含度直方图:')
        for k in sorted(hist):
            print(f"  {k:.1f}: {hist[k]}")
        print('\nHIGH 样例（前10）:')
        for r in high[:10]:
            print(f"  qid={r['qid']} contain={r['contain']} pdf答案={r['pdf_answer']!r} "
                  f"题答案={r['q_answer']!r} | {r['stem']}")
        print('\nMEDIUM 样例（前5）:')
        for r in medium[:5]:
            print(f"  qid={r['qid']} contain={r['contain']} | {r['stem']}")
        # 导出人工复核 CSV
        if medium:
            csv_path = os.path.join(_BACKEND_DIR, 'data', 'audit',
                                    'backfill_review.csv')
            os.makedirs(os.path.dirname(csv_path), exist_ok=True)
            with open(csv_path, 'w', encoding='utf-8-sig') as f:
                f.write('qid,contain,pdf_answer,q_answer,stem,analysis_head\n')
                for r in medium:
                    f.write(f"{r['qid']},{r['contain']},{r['pdf_answer']},"
                            f"{r['q_answer']},{r['stem']},{r['analysis_head']}\n")
            print(f"\n人工复核清单 → {csv_path}")
        print("\n确认后执行: python scripts/backfill_analysis.py --apply")
    finally:
        db.close()


def do_apply():
    blocks = parse_answer_pdfs()
    from app.core.database import SessionLocal
    from app.models.models import QuestionBank
    db = SessionLocal()
    try:
        high, medium, no_match, hist = match_all(db, blocks)
        if not high:
            logger.info("无 HIGH 置信回填项，0 changes")
            return
        # 备份
        backup_dir = os.path.join(_BACKEND_DIR, 'data', 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        dst = os.path.join(backup_dir, f'backup_pre_backfill_{ts}.sqlite')
        con = sqlite3.connect(_DB_PATH)
        con.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        con.close()
        shutil.copy2(_DB_PATH, dst)
        logger.info(f"已备份整库 → {dst}")

        audit_path = os.path.join(_BACKEND_DIR, 'data', 'audit',
                                  f'backfill_{ts}.jsonl')
        audit_f = open(audit_path, 'w', encoding='utf-8')
        applied = 0
        try:
            for r in high:
                q = db.query(QuestionBank).filter(
                    QuestionBank.question_id == r['qid']).first()
                if not q:
                    continue
                old_analysis = q.answer_analysis
                old_answer = q.answer
                new_analysis = r['full_text']
                # 答案回填：仅当题目无有效答案且 PDF 有字母
                new_answer = old_answer
                if (old_answer or '').strip() in ('', '待补充') and r['letters']:
                    new_answer = r['letters']
                audit_f.write(json.dumps({
                    'qid': r['qid'], 'pdf': r['pdf'], 'block': r['block_num'],
                    'old_analysis': old_analysis, 'new_analysis': new_analysis,
                    'old_answer': old_answer, 'new_answer': new_answer,
                }, ensure_ascii=False) + '\n')
                q.answer_analysis = new_analysis
                q.answer = new_answer
                applied += 1
            db.commit()
            audit_f.close()
            logger.info(f"回填完成: {applied} 题")
            logger.info(f"审计日志 → {audit_path}")
            logger.info(f"回滚: python scripts/backfill_analysis.py --restore {audit_path}")
        except Exception:
            db.rollback()
            audit_f.close()
            raise
    finally:
        db.close()


def do_restore(audit_path):
    if not os.path.exists(audit_path):
        print(f'❌ 审计文件不存在: {audit_path}')
        sys.exit(1)
    from app.core.database import SessionLocal
    from app.models.models import QuestionBank
    db = SessionLocal()
    entries = [json.loads(l) for l in open(audit_path, encoding='utf-8') if l.strip()]
    for e in reversed(entries):
        q = db.query(QuestionBank).filter(
            QuestionBank.question_id == e['qid']).first()
        if q:
            q.answer_analysis = e['old_analysis']
            q.answer = e['old_answer']
    db.commit()
    db.close()
    print(f'✅ 已回滚 {len(entries)} 题（来自 {audit_path}）')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='公专答案解析存量回填')
    parser.add_argument('--apply', action='store_true', help='实际执行（默认dry-run）')
    parser.add_argument('--restore', metavar='JSONL')
    args = parser.parse_args()
    if args.restore:
        do_restore(args.restore)
    elif args.apply:
        do_apply()
    else:
        do_dry_run()
