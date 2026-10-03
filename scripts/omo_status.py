#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""后台任务运行状态采集器 + 极简 HTTP 服务。

解决什么问题
------------
子代理/后台任务超时或模型不可用时，用户看不到后台到底卡在哪一步，只能干等
（实测本项目已连续14 次子代理失败）。本工具把 opencode 的会话状态实时暴露出来，
让"后台是否在有效运行"变成可验证的事实，而不是猜测。

数据源
------
``%USERPROFILE%/.local/share/opencode/opencode.db``（SQLite）

⚠️ **必须只读打开**。写坏这个库会毁掉用户所有会话历史，不可恢复。
用 ``file:...?mode=ro`` URI 强制只读，顺带避免与opencode 进程争锁。

状态分级（对应用户红线："超过7分钟没有任何响应就转主代理接管"）
--------------------------------------------------------------
=============== ==================== ====== ================================
状态age_s 判据  颜色  含义
=============== ==================== ====== ================================
RUNNING<= 120s      绿     正常在跑
SLOW         120~420s     黄     变慢，需留意
STALLED      > 420s        红     必须接管，takeover=true
=============== ==================== ====== ================================

next_action 字段（供编排器自动决策）
------------------------------------
``takeover`` 存在 STALLED → 应转主代理接管，附 takeover_targets
``advance``  全部子任务已结束 → 可推进下一步
``wait``     其余正常情况 → 继续等待

用法
----
    python scripts/omo_status.py--serve --port 9600
    python scripts/omo_status.py                # 打印一次状态JSON（调试用）

仅用标准库，无第三方依赖。
"""

import argparse
import json
import os
import re
import sqlite3
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

# ---------------------------------------------------------------- 阈值
RUNNING_MAX_AGE = 120      # 2 分钟内更新 = 正常
SLOW_MAX_AGE = 420         # 7 分钟（用户红线）
STALE_EXIT_AGE = 1800      # 30 分钟后视为已结束（opencode 的超时上限）

# 主编排器 session：子代理的 parent_id 都指向它
ORCHESTRATOR_HINT = 'ses_f0b3e1f33ffedoQ6S5mf0ebHZP'


def find_db(explicit=None):
    """定位 opencode.db。找不到时返回 None 而不是抛异常——服务要能带着错误信息启动。"""
    cands = []
    if explicit:
        cands.append(explicit)
    home = os.path.expanduser('~')
    cands += [
        os.path.join(home, '.local', 'share', 'opencode', 'opencode.db'),
        os.path.join(home, 'AppData', 'Roaming', 'opencode', 'opencode.db'),
        os.path.join(home, '.opencode', 'opencode.db'),
    ]
    for c in cands:
        if c and os.path.exists(c):
            return os.path.normpath(c)
    return None


def _open_ro(db_path):
    """只读打开。mode=ro 保证写操作直接失败，而不是损坏库。"""
    uri = 'file:%s?mode=ro' % db_path.replace('\\', '/').replace('?', '%3f')
    return sqlite3.connect(uri, uri=True, timeout=3)


def _cols(cur, table):
    try:
        return {r[1] for r in cur.execute('PRAGMA table_info(%s)' % table)}
    except sqlite3.Error:
        return set()


def classify(age_s):
    if age_s is None:
        return 'UNKNOWN'
    if age_s <= RUNNING_MAX_AGE:
        return 'RUNNING'
    if age_s <= SLOW_MAX_AGE:
        return 'SLOW'
    return 'STALLED'


def collect(db_path=None):
    """采集一次状态。任何失败都返回结构完整的 dict，绝不抛异常中断服务。"""
    now_ms = int(time.time() * 1000)
    result = {
        'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'now_ms': now_ms,
        'db_path': None,
        'error': None,
        'orchestrator': None,
        'children': [],
        'summary': {'total': 0, 'running': 0, 'slow': 0, 'stalled': 0,
                    'finished': 0, 'takeover': False},
        'takeover_targets': [],
        'next_action': 'wait',
        'next_action_reason': '',
    }

    resolved = find_db(db_path)
    result['db_path'] = resolved
    if not resolved:
        result['error'] = '未找到 opencode.db（查找路径：%s）' % os.path.expanduser('~')
        result['next_action'] = 'wait'
        result['next_action_reason'] = '数据源缺失，无法判断后台状态'
        return result

    try:
        con = _open_ro(resolved)
        cur = con.cursor()

        if 'session' not in {r[0] for r in
                             cur.execute("SELECT name FROM sqlite_master WHERE type='table'")}:
            result['error'] = 'opencode.db 中没有 session 表（版本不兼容？）'
            con.close()
            return result

        has_children = 'parent_id' in _cols(cur, 'session')
        SELECT_COLS = (
            'SELECT id, title, agent, model, time_created, time_updated, '
            'time_archived, cost, tokens_input, tokens_output, tokens_reasoning '
            'FROM session')
        if has_children:
            # 子代理会话：有 parent_id，指向编排器
            cur.execute(SELECT_COLS + ' WHERE parent_id IS NOT NULL '
                        'ORDER BY time_updated DESC LIMIT 40')
        else:
            # 无 parent_id 列的旧版本：退化为排除编排器本身
            cur.execute(SELECT_COLS + ' WHERE id != ? '
                        'ORDER BY time_updated DESC LIMIT 40', (ORCHESTRATOR_HINT,))
        children = cur.fetchall()

        # 活跃度证据：消息数 / part 数 / 最近 part 时间
        existing_tables = {r[0] for r in
                           cur.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        # 活跃度证据：消息数 / part 数 / 最近 part 时间
        msg_counts, part_counts, last_part = {}, {}, {}
        if 'message' in existing_tables:
            try:
                for sid, n in cur.execute(
                        'SELECT session_id, COUNT(*) FROM message GROUP BY session_id'):
                    msg_counts[sid] = n
            except sqlite3.Error:
                pass
        if 'part' in existing_tables:
            try:
                for sid, n in cur.execute(
                        'SELECT session_id, COUNT(*) FROM part GROUP BY session_id'):
                    part_counts[sid] = n
            except sqlite3.Error:
                pass
            try:
                for sid, mx in cur.execute(
                        'SELECT session_id, MAX(time_updated) FROM part GROUP BY session_id'):
                    last_part[sid] = mx
            except sqlite3.Error:
                pass

        orch = None
        items = []
        for row in children:
            (sid, title, agent, model, t_create, t_update,
             t_arch, cost, tin, tout, treason) = row
            # 已归档 = 已结束
            if t_arch:
                status = 'FINISHED'
                age_s = None
            else:
                ref = last_part.get(sid) or t_update
                age_s = max(0, (now_ms - ref) // 1000)
                status = classify(age_s)
                if age_s > STALE_EXIT_AGE:
                    status = 'FINISHED'
            entry = {
                'session_id': sid,
                'title': (title or '')[:80],
                'agent': agent or '',
                'model': model or '',
                'status': status,
                'age_s': age_s,
                'messages': msg_counts.get(sid, 0),
                'parts': part_counts.get(sid, 0),
                'tokens_in': tin or 0,
                'tokens_out': tout or 0,
                'tokens_reasoning': treason or 0,
                'cost': cost or 0,
                'archived': bool(t_arch),
                'takeover': status == 'STALLED',
            }
            # 主编排器本身不算"待接管"
            if sid == ORCHESTRATOR_HINT:
                orch = entry
                continue
            items.append(entry)

        # 只展示最近 24 小时内有活动的，避免历史僵尸刷屏
        items = [i for i in items
                 if i['status'] != 'FINISHED' or (i['age_s'] or 0) < 86400]
        items.sort(key=lambda i: (i['age_s'] is None, i['age_s'] or 0))

        s = result['summary']
        for i in items:
            s['total'] += 1
            key = i['status'].lower()
            if key in s:
                s[key] += 1

        result['children'] = items
        result['orchestrator'] = orch

        stalled = [i['session_id'] for i in items if i['takeover']]
        if stalled:
            result['next_action'] = 'takeover'
            result['takeover_targets'] = stalled
            result['summary']['takeover'] = True
            result['next_action_reason'] = (
                '有 %d 个后台任务超过 %d 秒(%.0f分钟)无响应，触发用户红线，应转主代理接管'
                % (len(stalled), SLOW_MAX_AGE, SLOW_MAX_AGE / 60))
        elif s['total'] > 0 and s['running'] == 0 and s['slow'] == 0:
            result['next_action'] = 'advance'
            result['next_action_reason'] = '所有后台任务均已结束，可推进下一步'
        else:
            result['next_action'] = 'wait'
            result['next_action_reason'] = '后台任务仍在运行，继续等待'

        con.close()
    except Exception as exc:                                  # noqa: BLE001
        # 采集失败必须降级而不是崩掉，否则用户连"看不到"都做不到
        result['error'] = '%s: %s' % (type(exc).__name__, exc)
        result['next_action_reason'] = '采集失败，无法判断后台状态'
    return result


# ---------------------------------------------------------------- HTTP
DASHBOARD_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              'omo_dashboard.html')


class Handler(BaseHTTPRequestHandler):
    db_path = None

    def log_message(self, format, *args):     # noqa: A002 - 基类签名固定名 format
        pass                                    # 静音访问日志，避免刷屏

    def _send(self, code, body, ctype):
        raw = body.encode('utf-8') if isinstance(body, str) else body
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):                        # noqa: N802
        path = self.path.split('?')[0]
        if path == '/api/status':
            self._send(200, json.dumps(collect(self.db_path),
                                       ensure_ascii=False),
                       'application/json; charset=utf-8')
        elif path in ('/', '/index.html'):
            try:
                with open(DASHBOARD_PATH, 'r', encoding='utf-8') as f:
                    self._send(200, f.read(), 'text/html; charset=utf-8')
            except OSError as exc:
                self._send(500, 'dashboard 读取失败: %s' % exc,
                           'text/plain; charset=utf-8')
        elif path == '/healthz':
            self._send(200, 'ok', 'text/plain; charset=utf-8')
        else:
            self._send(404, 'not found', 'text/plain; charset=utf-8')


def main():
    ap = argparse.ArgumentParser(description='后台任务运行状态展示器')
    ap.add_argument('--serve', action='store_true', help='启动 HTTP 服务')
    ap.add_argument('--port', type=int, default=9600, help='端口（默认 9600）')
    ap.add_argument('--db', default=None, help='opencode.db 路径（默认自动查找）')
    args = ap.parse_args()

    if not args.serve:
        print(json.dumps(collect(args.db), ensure_ascii=False, indent=2))
        return 0

    Handler.db_path = args.db
    try:
        srv = HTTPServer(('127.0.0.1', args.port), Handler)
    except OSError as exc:
        print('[FATAL] 端口 %d 无法绑定：%s' % (args.port, exc), file=sys.stderr)
        print('        可能已被占用，换端口：--port 9601', file=sys.stderr)
        return 1

    db = find_db(args.db)
    print('=' * 64)
    print('  后台任务运行状态展示器')
    print('=' * 64)
    print('  面板   : http://127.0.0.1:%d' % args.port)
    print('  接口   : http://127.0.0.1:%d/api/status' % args.port)
    print('  数据库 : %s' % (db or '未找到（面板会显示错误）'))
    print('  红线   : 超过 %d 秒(%.0f分钟)无响应标记 STALLED 并建议接管'
          % (SLOW_MAX_AGE, SLOW_MAX_AGE / 60))
    print('  停止   : Ctrl+C')
    print('=' * 64)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print('\n已停止。')
        srv.server_close()
    return 0


if __name__ == '__main__':
    sys.exit(main())