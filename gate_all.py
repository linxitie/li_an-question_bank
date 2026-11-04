# -*- coding: utf-8 -*-
"""
模块4/7 端到端全量回归门禁（gate_all）。
一次跑通：画像 → 计划生成(mock) → 每日任务闭环 → 工作台/多Agent → 知识库(骨架/可视化/检索/vault导入)
→ AI调整计划 → 长期记忆(轨迹/复盘/管理) → 岗位库+选岗 → 对话自动记忆。
所有子验证脚本独立 TestClient + mock LLM，任意失败即门禁 FAIL 并输出明细。

用法：python gate_all.py   （子脚本默认目录：脚本同级 verify_*.py）
"""
import os
import subprocess
import sys
import time
import glob

GATE_SCRIPTS = [
    "verify_profile.py",      # 画像系统 + PlanAgent 推理注入
    "verify_planb.py",        # 每日任务闭环（金币+提醒+今日面板）
    "verify_phase2b.py",      # 工作台双模式 + 一键写入今日任务
    "verify_phase3.py",       # Obsidian 自生长知识库骨架
    "verify_kb_agent.py",     # D 知识库接入 Agent 检索
    "verify_adjust.py",       # E AI 调整计划
    "verify_efg.py",          # E/F/G 综合（入口/轨迹/里程碑）
    "verify_hi.py",           # H/I 记忆管理+周复盘+vault 导入(幂等/穿越防护)
    "verify_kl.py",           # K/L 岗位库+选岗注入+对话自动记忆
    "verify_nop.py",          # N/O/P 学情+错题接入对话 + 桌面通知模块 + 知识图谱关系管理
    "verify_b.py",            # B 错题明细（科目/题干/错选/正解/掌握度）接入对话上下文
    "verify_c.py",            # C 多Agent身份路由 + 面试教练结构化题库（框架+示例题抽取）
    "verify_d.py",            # D 知识图谱深化：统计端点 + 节点详情 + graph摘要配色/关系中文名
]


def _resolve_script_dir():
    """验证脚本优先同目录；开发环境（脚本在项目父目录）自动回退。"""
    here = os.path.dirname(os.path.abspath(__file__))
    for cand in (here, os.path.dirname(here)):
        if all(os.path.exists(os.path.join(cand, s)) for s in GATE_SCRIPTS):
            return cand
    return here


def main():
    here = _resolve_script_dir()
    py = sys.executable
    results = []
    start_all = time.time()
    for script in GATE_SCRIPTS:
        path = os.path.join(here, script)
        if not os.path.exists(path):
            results.append((script, "SKIP", "脚本不存在"))
            continue
        t0 = time.time()
        try:
            p = subprocess.run(
                [py, path],
                capture_output=True, text=True, timeout=600,
                encoding="utf-8", errors="replace",
            )
            cost = round(time.time() - t0, 1)
            status = "PASS" if p.returncode == 0 else "FAIL"
            tail = (p.stdout or "").strip().splitlines()
            tail = tail[-6:]
            results.append((script, status, f"{cost}s", " | ".join(tail)))
        except subprocess.TimeoutExpired:
            results.append((script, "FAIL", "timeout>600s", ""))
        except Exception as e:
            results.append((script, "FAIL", "exc", str(e)[:120]))

    total_cost = round(time.time() - start_all, 1)
    passed = [r for r in results if r[1] == "PASS"]
    failed = [r for r in results if r[1] != "PASS"]
    print("=" * 60)
    print(f"GATE_ALL 模块4/7 全量回归  |  通过 {len(passed)}/{len(results)}  |  总耗时 {total_cost}s")
    print("=" * 60)
    for script, status, extra, note in results:
        print(f"[{status}] {script} ({extra})")
        if note:
            print(f"        {note}")
    print("=" * 60)
    if failed:
        print("门禁失败项：")
        for script, status, extra, note in failed:
            print(f"  - {script} [{status}] {extra}")
        return 1
    print("GATE_ALL PASS ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
