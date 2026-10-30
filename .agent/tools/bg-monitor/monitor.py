#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
后台任务实时展示器（开发辅助工具，不参与产品构建）

用途
----
解决「后台代理/subagent 看不到进度、只能干等」的问题：
实时列出当前项目下所有后台子代理会话，并按 **5 分钟规则** 高亮告警。

判定规则（与 CLAUDE.md/Opencode执行命令工作流.md 一致）
  空闲 < 2min   -> 正常（绿）
  空闲 2-5min   -> 关注（黄）即将到阈值
  空闲 >= 5min  -> 超时（红）主代理应立即接管或重启

关键指标 `idle` = now - session.time_updated（最后活动时间），
而非 `elapsed`（总时长）。任务可能总时长很长但一直在产出，
只有「空闲超过 5 分钟」才真正意味着卡死。

用法
----
  python tools/bg-monitor/monitor.py            # 启动看板 (默认 http://127.0.0.1:8799)
  python tools/bg-monitor/monitor.py --port 9000
  python tools/bg-monitor/monitor.py --once     # 仅打印一次状态后退出（CI/脚本用）

安全性
------
- 以 SQLite **只读模式**（mode=ro）打开 opencode.db，绝不写入；
  避免与正在运行的 OpenCode 进程产生锁冲突。
- 仅监听 127.0.0.1，不对外暴露。
"""
import argparse
import json
import os
import sqlite3
import sys
import threading
import time
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# 控制台按 UTF-8 输出，避免 Windows GBK 下的中文乱码。
# reconfigure 是 TextIOWrapper 专有方法，基类 TextIO 无此声明，
# 故用 getattr 探测而非直接调用，既兼容旧环境也避免静态检查误报。
_reconf = getattr(sys.stdout, "reconfigure", None)
if _reconf is not None:
    _reconf(encoding="utf-8", errors="replace")

DB_PATH = os.path.expandvars(r"%USERPROFILE%\.local\share\opencode\opencode.db")
PROJECT_KEY = "砺安题库"

IDLE_WARN = 120      # 2 分钟：关注
IDLE_STALL = 300     # 5 分钟：超时（与工作流规范一致）
ACTIVE_WINDOW = 1800  # 30 分钟：超过此时长视为历史会话，默认不再展示（避免历史噪音）


def _connect_ro():
    """只读连接，避免与 OpenCode 主进程抢锁"""
    uri = "file:" + DB_PATH.replace("\\", "/") + "?mode=ro"
    return sqlite3.connect(uri, uri=True, timeout=5)


def _norm_ts(v):
    """兼容秒/毫秒两种时间戳，统一为秒"""
    if not v:
        return 0
    return v / 1000.0 if v > 1e11 else float(v)


def collect(active_window=ACTIVE_WINDOW):
    """采集当前项目的主会话与后台子代理状态

    只统计 **当前主会话直接派生** 的子会话（parent_id == main.id），
    且默认仅保留 active_window 秒内有活动的会话，
    避免上千小时前的历史会话全部涌入造成噪音（历史会话本身不是"卡死"）。
    """
    now = time.time()
    result = {
        "now": now,
        "now_str": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now)),
        "threshold_stall": IDLE_STALL,
        "db_exists": os.path.exists(DB_PATH),
        "main": None,
        "children": [],
        "error": None,
    }
    if not result["db_exists"]:
        result["error"] = "未找到 opencode.db: %s" % DB_PATH
        return result

    try:
        c = _connect_ro()
    except Exception as e:  # noqa: BLE001
        result["error"] = "数据库打开失败: %s" % e
        return result

    try:
        rows = c.execute(
            "SELECT id, parent_id, title, agent, time_created, time_updated, "
            "tokens_input, tokens_output, cost "
            "FROM session WHERE directory LIKE ? "
            "ORDER BY time_updated DESC LIMIT 400",
            ("%" + PROJECT_KEY + "%",),
        ).fetchall()

        if not rows:
            result["error"] = "本项目暂无会话记录"
            return result

        by_id = {}
        for r in rows:
            by_id[r[0]] = {
                "id": r[0],
                "parent_id": r[1],
                "title": (r[2] or "")[:80],
                "agent": r[3] or "-",
                "created": _norm_ts(r[4]),
                "updated": _norm_ts(r[5]),
                "tokens_in": r[6] or 0,
                "tokens_out": r[7] or 0,
                "cost": r[8] or 0,
            }

        # 主会话 = 最近更新且无父会话者
        main = None
        for v in rows and [by_id[x[0]] for x in rows]:
            if not v["parent_id"]:
                main = v
                break
        result["main"] = main

        # 子代理 = 仅当前主会话直接派生的会话
        # 注意不能把「项目内所有 parent_id」都算进来，否则历史会话会被
        # 误判为当前后台任务；parent 必须精确等于主会话 id。
        kids = [v for v in by_id.values() if main and v["parent_id"] == main["id"]]
        # 默认仅保留活跃窗口内的会话（历史会话不算"卡死"）
        kids = [v for v in kids if (now - v["updated"]) <= active_window]

        # 取每个子会话最后一条 part 作为「最近活动」摘要
        for k in kids:
            try:
                last = c.execute(
                    "SELECT data FROM part WHERE session_id=? "
                    "ORDER BY time_created DESC LIMIT 6",
                    (k["id"],),
                ).fetchall()
                acts = []
                for (d,) in last:
                    try:
                        j = json.loads(d)
                    except Exception:
                        continue
                    t = j.get("type")
                    if t == "tool":
                        acts.append("[tool] %s" % (j.get("tool") or "?"))
                    elif t == "text" and j.get("text"):
                        acts.append(j["text"].strip().replace("\n", " ")[:90])
                k["last_activity"] = acts[0] if acts else "(无活动记录)"
                try:
                    cc = Counter()
                    for (d,) in c.execute(
                        "SELECT data FROM part WHERE session_id=? LIMIT 800", (k["id"],)
                    ):
                        try:
                            cc[json.loads(d).get("type")] += 1
                        except Exception:
                            pass
                    k["parts"] = dict(cc)
                except Exception:
                    k["parts"] = {}
            except Exception:
                k["last_activity"] = "(读取失败)"
                k["parts"] = {}

            k["elapsed"] = int(now - k["created"])
            k["idle"] = int(now - k["updated"])
            k["status"] = (
                "stall" if k["idle"] >= IDLE_STALL
                else ("warn" if k["idle"] >= IDLE_WARN else "ok")
            )

        kids.sort(key=lambda x: x["idle"], reverse=True)
        result["children"] = kids
        # 统计被活跃窗口过滤掉的历史子会话数量，让看板可提示"另有 N 个历史会话"
        if main:
            all_kids = [v for v in by_id.values() if v["parent_id"] == main["id"]]
            result["hidden_historical"] = max(0, len(all_kids) - len(kids))

        if main:
            main["elapsed"] = int(now - main["created"])
            main["idle"] = int(now - main["updated"])

    except Exception as e:  # noqa: BLE001
        result["error"] = "采集失败: %s" % e
    finally:
        c.close()
    return result


def _fmt(sec):
    sec = int(sec or 0)
    if sec < 60:
        return "%ds" % sec
    if sec < 3600:
        return "%dm%02ds" % (sec // 60, sec % 60)
    return "%dh%02dm" % (sec // 3600, (sec % 3600) // 60)


HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>后台任务展示器</title>
<style>
  * { box-sizing: border-box; }
  body { margin:0; font-family: "Segoe UI","Microsoft YaHei",sans-serif;
         background:#0f1419; color:#e6edf3; }
  header { padding:14px 20px; background:#161b22; border-bottom:1px solid #30363d;
           display:flex; align-items:center; gap:16px; flex-wrap:wrap; }
  h1 { font-size:16px; margin:0; font-weight:700; }
  .meta { font-size:12px; color:#8b949e; }
  .badge { padding:2px 9px; border-radius:11px; font-size:11px; font-weight:700; }
  .b-ok { background:#1f6f43; color:#7ee2a8; }
  .b-warn { background:#8a6116; color:#ffd479; }
  .b-stall { background:#8b2c2c; color:#ff9d9d; }
  .rule { margin-left:auto; font-size:12px; color:#ffd479;
          background:#2b2410; border:1px solid #6b5410; padding:5px 11px; border-radius:6px; }
  main { padding:16px 20px 40px; }
  table { width:100%; border-collapse:collapse; font-size:13px; }
  th,td { text-align:left; padding:9px 10px; border-bottom:1px solid #21262d; vertical-align:top; }
  th { color:#8b949e; font-weight:600; font-size:12px; position:sticky; top:0; background:#0f1419; }
  tr.stall { background:#2d1618; } tr.warn { background:#2a2312; }
  .sid { font-family:Consolas,monospace; font-size:11px; color:#79c0ff; }
  .act { color:#8b949e; font-size:12px; max-width:420px;
         overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .empty { padding:40px; text-align:center; color:#8b949e; }
  .dot { display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:6px; }
  .d-ok{background:#3fb950}.d-warn{background:#d29922}.d-stall{background:#f85149;animation:pulse 1s infinite}
  @keyframes pulse { 50% { opacity:.25 } }
  .num { font-family:Consolas,monospace; }
  #err { background:#3d1d1d; border:1px solid #8b2c2c; padding:10px; border-radius:6px;
         margin-bottom:14px; font-size:13px; }
</style>
</head>
<body>
<header>
  <h1>后台任务展示器</h1>
  <span class="meta" id="clock">--</span>
  <span class="meta" id="cnt"></span>
  <span class="meta" id="refresh"></span>
  <div class="rule">规则：空闲 ≥ 5 分钟（红色）→ 主代理必须立即接管或重启，禁止干等</div>
</header>
<main>
  <div id="err" style="display:none"></div>
  <div id="maininfo" class="meta" style="margin-bottom:12px"></div>
  <div id="body"></div>
</main>
<script>
let tick = 0;
function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
function fmt(sec){sec=sec|0;if(sec<60)return sec+'s';if(sec<3600)return Math.floor(sec/60)+'m'+(sec%60)+'s';
  return Math.floor(sec/3600)+'h'+String(Math.floor((sec%3600)/60)).padStart(2,'0')+'m';}
const LBL={ok:'正常',warn:'关注',stall:'超时'};

async function load(){
  try{
    const r = await fetch('/api/status?t=' + Date.now(), {cache:'no-store'});
    const d = await r.json();
    document.getElementById('clock').textContent = d.now_str;
    const e = document.getElementById('err');
    if(d.error){ e.style.display='block'; e.textContent='⚠ '+d.error; }
    else e.style.display='none';

    const m = d.main;
    document.getElementById('maininfo').innerHTML = m
      ? '主会话：<span class="sid">'+esc(m.id)+'</span> · '+esc(m.agent)
        + ' · 已运行 '+fmt(m.elapsed)+' · 空闲 '+fmt(m.idle)
      : '未找到主会话';

    const cs = d.children||[];
    document.getElementById('cnt').textContent = '子代理 '+cs.length+' 个';
    document.getElementById('refresh').textContent = tick ? ('· '+tick+'s 后刷新') : '';

    if(!cs.length){ document.getElementById('body').innerHTML =
      '<div class="empty">当前没有后台子代理会话</div>'; return; }

    let h = '<table><thead><tr><th>状态</th><th>Agent</th><th>会话 ID</th>'
          + '<th>空闲</th><th>总时长</th><th>Tokens</th><th>最近活动</th></tr></thead><tbody>';
    cs.forEach(c=>{
      h += '<tr class="'+c.status+'">'
        + '<td><span class="dot d-'+c.status+'"></span><span class="badge b-'+c.status+'">'+LBL[c.status]+'</span></td>'
        + '<td>'+esc(c.agent)+'</td>'
        + '<td class="sid" title="'+esc(c.title)+'">'+esc(String(c.id).slice(0,22))+'</td>'
        + '<td class="num">'+fmt(c.idle)+'</td>'
        + '<td class="num">'+fmt(c.elapsed)+'</td>'
        + '<td class="num">'+((c.tokens_out||0))+'</td>'
        + '<td class="act" title="'+esc(c.last_activity)+'">'+esc(c.last_activity)+'</td>'
        + '</tr>';
    });
    document.getElementById('body').innerHTML = h + '</tbody></table>';
  }catch(err){ document.getElementById('err').style.display='block';
    document.getElementById('err').textContent='请求失败: '+err.message; }
}
tick = 3;
setInterval(()=>{ tick--; if(tick<=0){ tick=3; load(); }
  document.getElementById('refresh').textContent = tick+'s 后刷新'; }, 1000);
load();
</script>
</body>
</html>
"""


# 活跃窗口由命令行决定，Handler 通过闭包式模块级变量读取
ACTIVE_WINDOW_CURRENT = ACTIVE_WINDOW


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):  # noqa: A002 — 签名须与基类兼容
        """静默访问日志（避免每 3 秒轮询刷屏）"""
        pass

    def _send(self, body, ctype):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        if self.path.startswith("/api/status"):
            self._send(json.dumps(collect(ACTIVE_WINDOW_CURRENT), ensure_ascii=False).encode("utf-8"),
                       "application/json; charset=utf-8")
        else:
            self._send(HTML.encode("utf-8"), "text/html; charset=utf-8")


def print_once(active_window=ACTIVE_WINDOW):
    d = collect(active_window)
    print("=" * 66)
    print("后台任务展示器 · %s" % d["now_str"])
    print("=" * 66)
    if d.get("error"):
        print("错误:", d["error"])
    m = d.get("main")
    if m:
        print("主会话 %s | %s | 运行 %s | 空闲 %s" %
              (m["id"], m["agent"], _fmt(m["elapsed"]), _fmt(m["idle"])))
    cs = d.get("children") or []
    print("-" * 66)
    if not cs:
        print("当前无活跃后台子代理（活跃窗口 %d 秒内）" % active_window)
    for k in cs:
        print("[%-5s] %-20s 空闲 %-7s 总 %-7s out=%-6s %s" % (
            k["status"], k["agent"], _fmt(k["idle"]), _fmt(k["elapsed"]),
            k.get("tokens_out", 0), (k.get("last_activity") or "")[:44]))
    h = d.get("hidden_historical") or 0
    if h:
        print("-" * 66)
        print("另有 %d 个历史子代理会话已折叠（用 --all 查看全部）" % h)
    print("-" * 66)
    print("规则：空闲 >= %ds 判定超时，需主代理接管" % IDLE_STALL)


def main():
    ap = argparse.ArgumentParser(description="后台任务实时展示器")
    ap.add_argument("--port", type=int, default=8799)
    ap.add_argument("--once", action="store_true", help="仅打印一次状态")
    ap.add_argument("--all", action="store_true",
                    help="显示全部历史子代理（默认仅显示活跃窗口内的）")
    ap.add_argument("--window", type=int, default=ACTIVE_WINDOW,
                    help="活跃窗口秒数，默认 %d" % ACTIVE_WINDOW)
    args = ap.parse_args()

    window = 10 ** 9 if args.all else args.window
    global ACTIVE_WINDOW_CURRENT
    ACTIVE_WINDOW_CURRENT = window

    if args.once:
        print_once(window)
        return

    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print("=" * 66)
    print("后台任务展示器已启动")
    print("  看板地址: http://127.0.0.1:%d" % args.port)
    print("  数据库(只读): %s" % DB_PATH)
    print("  超时阈值: 空闲 >= %d 秒（红色告警）" % IDLE_STALL)
    print("  活跃窗口: %s" % ("全部历史" if args.all else "%d 秒" % window))
    print("  按 Ctrl+C 停止")
    print("=" * 66)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")


if __name__ == "__main__":
    main()