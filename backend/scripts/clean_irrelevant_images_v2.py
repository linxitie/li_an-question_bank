#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
clean_irrelevant_images_v2.py — 存量无关图片清理（问题2-R1）

功能：
  1. 扫描全部活跃题目的 question_content / options 中的 <img src="/static/questions/...">
  2. 用共享模块 image_filters.is_irrelevant_image 判定（与导入管线同一标准）
  3. 命中 qr_code / promo_banner（实锤）：
     - 从内容中移除对应 <img> 标签
     - 图片文件"移动"至 data/backups/removed_images_{ts}/（可恢复，不直接删除）
  4. 命中 qr_likely（疑似）：仅输出人工复核清单，不动数据
  5. 清理空目录（图片移走后无文件的 static/questions/{qid}/）
  6. --dry-run 默认：输出待删清单；--apply 执行（自动备份 DB）

用法:
  python scripts/clean_irrelevant_images_v2.py            # dry-run
  python scripts/clean_irrelevant_images_v2.py --apply    # 执行
  python scripts/clean_irrelevant_images_v2.py --apply --delete-files
      # （默认即移动文件；此参数保留兼容语义）
  python scripts/clean_irrelevant_images_v2.py --restore <audit.jsonl>
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

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

from app.services.image_filters import is_irrelevant_image  # noqa: E402

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DB_PATH = os.path.join(_BACKEND_DIR, 'data', 'question_bank.db')
_IMG_ROOT = os.path.join(_BACKEND_DIR, 'app', 'static', 'questions')

IMG_TAG_RE = re.compile(r'<img\s+[^>]*src=["\']([^"\']+)["\'][^>]*>', re.IGNORECASE)
# 实锤级（可自动清理）：人工确认的 md5 黑名单 + QR 解码成功 + 尺寸启发式
HARD_LEVELS = ('qr_code', 'promo_banner', 'tiny', 'extreme_ratio', 'blank')
# 疑似级（只标记进人工复核清单，绝不自动删）：qr_likely / promo_likely
SOFT_LEVELS = ('qr_likely', 'promo_likely')


def _img_url_to_path(src: str):
    """/static/questions/{qid}/{file} → 磁盘绝对路径；非本站图片返回 None"""
    m = re.match(r'^/static/questions/([^/]+)/([^/]+)$', src)
    if not m:
        return None
    return os.path.join(_IMG_ROOT, m.group(1), m.group(2))


def _backup_db():
    backup_dir = os.path.join(_BACKEND_DIR, 'data', 'backups')
    os.makedirs(backup_dir, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    dst = os.path.join(backup_dir, f'backup_pre_imgclean_{ts}.sqlite')
    con = sqlite3.connect(_DB_PATH)
    con.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    con.close()
    shutil.copy2(_DB_PATH, dst)
    return dst


def scan_and_clean(dry_run: bool = True):
    con = sqlite3.connect(_DB_PATH)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT question_id, question_content, options FROM question_bank "
        "WHERE status=1 AND (question_content LIKE '%<img%' OR options LIKE '%<img%')"
    ).fetchall()
    logger.info(f"含 <img> 的活跃题目: {len(rows)}")

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    removed_dir = os.path.join(_BACKEND_DIR, 'data', 'backups', f'removed_images_{ts}')
    audit_dir = os.path.join(_BACKEND_DIR, 'data', 'audit')
    os.makedirs(audit_dir, exist_ok=True)
    audit_path = os.path.join(audit_dir, f'img_clean_{ts}.jsonl')

    plan = []          # (qid, field, old_value, new_value, [(src, path, level, reason)])
    review = []        # 疑似清单
    stats = {'scanned': len(rows), 'hard_hits': 0, 'soft_hits': 0,
             'content_updated': 0, 'options_updated': 0, 'files_moved': 0,
             'empty_dirs_removed': 0}

    for r in rows:
        qid = r['question_id']
        hits_here = []
        new_content = r['question_content'] or ''
        new_options_raw = r['options']

        def _check_text(text, field):
            hits = []
            def _sub(m):
                src = m.group(1)
                path = _img_url_to_path(src)
                if not path or not os.path.exists(path):
                    return m.group(0)
                with open(path, 'rb') as f:
                    data = f.read()
                level, reason = is_irrelevant_image(data)
                if level in HARD_LEVELS:
                    hits.append((src, path, level, reason))
                    return ''  # 移除标签
                elif level in SOFT_LEVELS:
                    review.append((qid, field, src, reason))
                return m.group(0)
            return IMG_TAG_RE.sub(_sub, text), hits

        new_content, h1 = _check_text(new_content, 'content')
        hits_here.extend(h1)

        new_options_raw2 = new_options_raw
        if new_options_raw:
            try:
                opts = json.loads(new_options_raw)
                changed = False
                for o in opts:
                    if isinstance(o, dict) and o.get('value'):
                        nv, h2 = _check_text(str(o['value']), f"option:{o.get('key')}")
                        hits_here.extend(h2)
                        if nv != o['value']:
                            o['value'] = nv
                            changed = True
                if changed:
                    new_options_raw2 = json.dumps(opts, ensure_ascii=False)
            except Exception:
                new_options_raw2 = new_options_raw

        if hits_here:
            stats['hard_hits'] += len(hits_here)
            plan.append((qid, new_content, new_options_raw2, hits_here,
                         r['question_content'], new_options_raw))

    # ===== 输出清单 =====
    print('=' * 70)
    print(f'[{"DRY RUN" if dry_run else "APPLY"}] 实锤无关图片命中 {stats["hard_hits"]} 处，'
          f'涉及 {len(plan)} 题；疑似待人工复核 {len(review)} 处')
    print('=' * 70)
    for qid, nc, no, hits, oc, oo in plan[:40]:
        for src, path, level, reason in hits:
            print(f"  qid={qid} [{level}] {reason[:40]} ← {os.path.basename(src)}")

    if not plan:
        logger.info("无需清理（幂等：可能已处理），0 changes")
        con.close()
        return

    if dry_run:
        print(f"\n确认后执行: python scripts/clean_irrelevant_images_v2.py --apply")
        con.close()
        return

    # ===== APPLY =====
    backup_path = _backup_db()
    logger.info(f"已备份整库 → {backup_path}")
    os.makedirs(removed_dir, exist_ok=True)
    audit_f = open(audit_path, 'w', encoding='utf-8')

    try:
        for qid, nc, no, hits, oc, oo in plan:
            audit_f.write(json.dumps({
                'action': 'update_content', 'qid': qid,
                'old_content': oc, 'new_content': nc,
                'old_options': oo, 'new_options': no,
                'hits': [{'src': s, 'level': lv, 'reason': rs} for s, _, lv, rs in hits],
            }, ensure_ascii=False) + '\n')
            con.execute('UPDATE question_bank SET question_content=?, options=? '
                        'WHERE question_id=?', (nc, no, qid))
            stats['content_updated'] += 1
            for src, path, level, reason in hits:
                dst = os.path.join(removed_dir, f'{qid}_{os.path.basename(path)}')
                try:
                    shutil.move(path, dst)
                    stats['files_moved'] += 1
                    audit_f.write(json.dumps({
                        'action': 'move_file', 'qid': qid,
                        'from': path, 'to': dst, 'level': level,
                    }, ensure_ascii=False) + '\n')
                except Exception as e:
                    logger.warning(f"移动失败 {path}: {e}")
        con.commit()

        # 清理空目录
        if os.path.exists(_IMG_ROOT):
            for d in os.listdir(_IMG_ROOT):
                dp = os.path.join(_IMG_ROOT, d)
                if os.path.isdir(dp) and not os.listdir(dp):
                    os.rmdir(dp)
                    stats['empty_dirs_removed'] += 1

        audit_f.close()
        logger.info(f"完成: 内容更新 {stats['content_updated']} 题, "
                    f"图片移动 {stats['files_moved']} 张, 空目录清理 {stats['empty_dirs_removed']} 个")
        logger.info(f"被移图片暂存 → {removed_dir}")
        logger.info(f"审计日志 → {audit_path}")
        logger.info(f"疑似待人工复核 {len(review)} 处（未动数据）:")
        for qid, field, src, reason in review[:20]:
            logger.info(f"  qid={qid} [{field}] {os.path.basename(src)} — {reason}")
    except Exception:
        con.rollback()
        audit_f.close()
        raise
    finally:
        con.close()


def do_restore(audit_path):
    if not os.path.exists(audit_path):
        print(f'❌ 审计文件不存在: {audit_path}')
        sys.exit(1)
    con = sqlite3.connect(_DB_PATH)
    entries = [json.loads(l) for l in open(audit_path, encoding='utf-8') if l.strip()]
    for e in reversed(entries):
        if e['action'] == 'update_content':
            con.execute('UPDATE question_bank SET question_content=?, options=? '
                        'WHERE question_id=?',
                        (e['old_content'], e['old_options'], e['qid']))
        elif e['action'] == 'move_file':
            if os.path.exists(e['to']):
                shutil.move(e['to'], e['from'])
    con.commit()
    con.close()
    print(f'✅ 已回滚（来自 {audit_path}）')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='存量无关图片清理 v2（QR解码+横幅特征）')
    parser.add_argument('--apply', action='store_true', help='实际执行（默认dry-run）')
    parser.add_argument('--delete-files', action='store_true', help='兼容参数（默认即移动文件）')
    parser.add_argument('--restore', metavar='JSONL', help='从审计日志回滚')
    args = parser.parse_args()
    if args.restore:
        do_restore(args.restore)
    else:
        scan_and_clean(dry_run=not args.apply)
