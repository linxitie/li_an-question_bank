# -*- coding: utf-8 -*-
"""T11 QA场景1：经 Vite 代理（9527）实请求新端点（G8 强制，禁止只测直连 8000）。"""
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import pymupdf

BASE = 'http://localhost:9527'
URL = BASE + '/api/questions/import/separate-match-xingce'
PDF_ROOT = 'D:/砺安题库/砺安题库/题库/行测/安徽行测'
STEM = '2023年安徽省公务员录用考试《行测》题（网友回忆版）'

fails = []


def check(name, cond, detail=''):
    print('  [%s] %s%s' % ('PASS' if cond else 'FAIL', name,
                           ('  -> ' + str(detail)) if detail else ''))
    if not cond:
        fails.append(name)


def pdf_text(p):
    d = pymupdf.open(p)
    s = '\n'.join(d[i].get_text('text') for i in range(len(d)))
    d.close()
    return s


print('=== 前置：Vite 9527 与后端 8000 均在跑 ===')
r = requests.get(BASE + '/', timeout=10)
check('9527 首页 200（证明前端真在运行）', r.status_code == 200, r.status_code)
r8 = requests.get('http://localhost:8000/docs', timeout=10)
check('8000 /docs 200', r8.status_code == 200, r8.status_code)

from app.core.database import SessionLocal
from app.core.security import create_access_token
from app.models.models import SysUser
s = SessionLocal()
try:
    uid = s.query(SysUser.user_id).first()[0]
finally:
    s.close()
token = create_access_token({'user_id': uid})
H = {'Authorization': 'Bearer %s' % token}

print()
print('=== 经 9527 代理实请求（成功路径）===')
payload = {
    'questions_text': pdf_text(os.path.join(PDF_ROOT, STEM + '题本.pdf')),
    'answers_text': pdf_text(os.path.join(PDF_ROOT, STEM + '答案解析.pdf')),
    'paper_name': '安徽2023行测',
}
resp = requests.post(URL, json=payload, headers=H, timeout=300)
print('  HTTP %s  耗时 %.1fs  响应 %d 字节'
      % (resp.status_code, resp.elapsed.total_seconds(),
         len(resp.content)))
check('经 9527 代理返回 200', resp.status_code == 200, resp.status_code)

if resp.status_code == 200:
    d = resp.json()
    ks = set(d)
    print('  顶层字段(%d): %s' % (len(ks), sorted(ks)))
    check('字段数 >= 12', len(ks) >= 12, len(ks))
    check('含既有 12 字段',
          {'status', 'match_rate', 'matched_count', 'total_questions',
           'questions', 'unmatched_question_numbers', 'extra_answer_numbers',
           'analysis_count', 'strategy_used', 'auto_detected_subject',
           'details', 'message'}.issubset(ks),
          sorted(ks))
    check('match_rate >= 99', d['match_rate'] >= 99.0, d['match_rate'])
    check('total_questions = 110', d['total_questions'] == 110,
          d['total_questions'])
    check('含 xingce_report', 'xingce_report' in ks)

    xr = d.get('xingce_report', {})
    check('xingce_report 含分节区间表',
          bool(xr.get('section_intervals_q')), len(xr.get('section_intervals_q') or []))
    print('  分节区间:')
    for it in (xr.get('section_intervals_q') or []):
        print('    %-14s %s-%s (%s题)' % (it['name'], it['min'], it['max'], it['count']))
    print('  材料组数 = %s  preview_confirmable = %s'
          % (len(xr.get('material_groups') or []), xr.get('preview_confirmable')))
    check('材料组数 = 3', len(xr.get('material_groups') or []) == 3)

    # 保存一份真实响应，供证据留档
    os.makedirs('tmp', exist_ok=True)
    with io.open('tmp/task11_vite_response.json', 'w', encoding='utf-8') as f:
        json.dump({'http_status': resp.status_code,
                   'top_level_keys': sorted(ks),
                   'match_rate': d['match_rate'],
                   'total_questions': d['total_questions'],
                   'matched_count': d['matched_count'],
                   'blocked_count': xr.get('blocked_count'),
                   'preview_confirmable': xr.get('preview_confirmable'),
                   'section_intervals_q': xr.get('section_intervals_q'),
                   'material_group_count': len(xr.get('material_groups') or []),
                   'import_id': xr.get('import_id')},
                  f, ensure_ascii=False, indent=2)
    print('  已留档: tmp/task11_vite_response.json')

print()
print('=== 经 9527 的鉴权（代理不得绕过鉴权）===')
r2 = requests.post(URL, json={'questions_text': 'x', 'answers_text': 'y'}, timeout=60)
check('经代理无 token 仍被拒 401/403', r2.status_code in (401, 403), r2.status_code)

print()
print('RESULT = %s   失败 %d 项 %s'
      % ('PASS' if not fails else 'FAIL', len(fails), fails or ''))
sys.exit(0 if not fails else 1)