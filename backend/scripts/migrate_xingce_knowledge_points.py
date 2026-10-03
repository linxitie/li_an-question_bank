#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""行测考点树迁移（幂等，任务 10）

把任务 5 产出的考点清单 ``data/xingce_kao_points.json`` 落库为层级化知识点。

既有结构约束（实测）
--------------------
``knowledge_point``（126 行）现状：
  - subject_id=1（行测）34 行，**全部平铺**（parent_id=0, level=2）
  - subject_id=2（申论）25 行，全部平铺
  - subject_id=3（公专）67 行，其中 29 行 level=3 且parent_id 指向 level=2 的点

→ **既有约定：level=2 为顶层知识点，level=3 为子知识点**（无 level=1）。
   故任务 5 的层级需 **+1 映射**（path深度 1 → level 2），以保持全库一致。

落库策略
--------
1. **只INSERT，绝不 UPDATE 既有行**（126 行必须逐字段不变）
2. 按 ``(point_name, subject_id)`` 判定复用：命中则复用其 ``point_id``，
   未命中才 INSERT。清单中与既有同名的 2 个（``公文写作`` / ``文化常识``）
   由此自动复用，不产生重复点
3. 省份私有 token 先剥离 ``XX特色-`` 前缀再落库（``江苏特色-综合资料`` → ``综合资料``）
4. 层级：先建父再建子，子节点 ``parent_id`` 指向父 ``point_id``
5. 可重复执行；``--rollback`` 仅删除本次新建的行（按 point_id 精确回溯）

用法
----
    python scripts/migrate_xingce_knowledge_points.py --dry-run
    python scripts/migrate_xingce_knowledge_points.py --apply
    python scripts/migrate_xingce_knowledge_points.py --rollback
"""
from __future__ import annotations

import argparse
import datetime
import io
import json
import os
import re
import shutil
import sqlite3
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BACKEND_DIR, "data", "question_bank.db")
INV_PATH = os.path.join(BACKEND_DIR, "data", "xingce_kao_points.json")
MANIFEST = os.path.join(BACKEND_DIR, "data", "xingce_kp_manifest.json")

SUBJECT_XINGCE = 1
# 既有约定：顶层为 level 2（无 level 1）。故 db_level = path深度 + 1。
LEVEL_OFFSET = 1


def snapshot(cur) -> dict:
    return {
        r[0]: r[1:]
        for r in cur.execute(
            "select point_id, point_name, subject_id, parent_id, level,"
            " sort_order, status from knowledge_point")
    }


def build_plan(inv: dict) -> list:
    """把清单展开为「按层级排序」的节点计划。

    Returns: ``[{'name','parent_path','level','section','count','freq_tier'}, ...]``
    ``parent_path`` 用 ``/`` 连接，用于先建父再建子时定位父节点。
    """
    nodes = {}
    for it in inv["items"]:
        parts = it["path"] or [it["normalized"]]
        for depth in range(1, len(parts) + 1):
            path = parts[:depth]
            key = "/".join(path)
            if key in nodes:
                # 父节点也累计出现次数，便于排序
                nodes[key]["count"] += it["count"]
                continue
            nodes[key] = {
                "name": path[-1],
                "parent_path": "/".join(path[:-1]),
                "path": path,
                "level": depth + LEVEL_OFFSET,
                "count": it["count"],
                "freq_tier": it["freq_tier"],
            }
    return sorted(nodes.values(), key=lambda n: (len(n["path"]), -n["count"]))


def main() -> int:
    ap = argparse.ArgumentParser(description="行测考点树迁移（幂等）")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--apply", action="store_true")
    g.add_argument("--rollback", action="store_true")
    args = ap.parse_args()

    if not os.path.exists(INV_PATH):
        print("[error] 考点清单不存在: %s（先跑 scripts/build_xingce_kao_points.py）" % INV_PATH)
        return 2
    with io.open(INV_PATH, encoding="utf-8") as f:
        inv = json.load(f)
    plan = build_plan(inv)

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    before = snapshot(cur)
    print("迁移前 knowledge_point 行数: %d" % len(before))
    print("清单节点数: %d（root %d / 层级化 %d）"
          % (len(plan), inv["meta"]["distinct_roots"], inv["meta"]["hier_tokens"]))

    # ── rollback ────────────────────────────────────────────────────────
    if args.rollback:
        if not os.path.exists(MANIFEST):
            print("[rollback] 无本次迁移清单 %s，无需回滚" % os.path.basename(MANIFEST))
            con.close()
            return 0
        with io.open(MANIFEST, encoding="utf-8") as f:
            ids = json.load(f)["created_point_ids"]
        if not ids:
            print("[rollback] 清单为空，无需回滚")
            con.close()
            return 0
        qs = ",".join(str(i) for i in ids)
        cur.execute("delete from knowledge_point where point_id in (%s)" % qs)
        con.commit()
        after = snapshot(cur)
        # 基线必须取「首次 apply 之前」的快照（即 manifest 里的 pre_apply），
        # 而不是回滚前的当前状态 —— 后者包含本次要删的行，比对必然 KeyError。
        with io.open(MANIFEST, encoding="utf-8") as f:
            man = json.load(f)
        base = {int(k): tuple(v) for k, v in man.get("pre_apply", {}).items()}
        if not base:
            print("  [warn] manifest 无 pre_apply 基线，跳过逐字段校验")
            kept = None
        else:
            missing = [k for k in base if k not in after]
            changed = [k for k in base if k in after and after[k] != base[k]]
            kept = not missing and not changed
            print("  基线 %d 行：缺失 %d，被改 %d"
                  % (len(base), len(missing), len(changed)))
        print("[rollback] 已删除 %d 行；行数 %d -> %d（基线 %d）"
              % (len(ids), len(before), len(after), len(base)))
        if kept is not None:
            print("  基线逐字段未变: %s" % kept)
        os.remove(MANIFEST)
        con.close()
        return 0 if kept is not False else 1

    # ── 预演：区分「复用既有」与「新建」 ────────────────────────────────
    name_index = {r[1]: r[0] for r in cur.execute(
        "select point_id, point_name from knowledge_point where subject_id=?",
        (SUBJECT_XINGCE,))}
    reuse, create = [], []
    for n in plan:
        if n["name"] in name_index:
            reuse.append((n["name"], name_index[n["name"]]))
        else:
            create.append(n)

    print("  复用既有行测点: %d  %s" % (len(reuse), reuse[:5]))
    print("  需新建        : %d" % len(create))

    if args.dry_run:
        print("[dry-run] 未写库")
        con.close()
        return 0

    # 写入前强制备份。
    # 必须用 SQLite 备份 API 而非 shutil.copy2：库是 WAL 模式
    #（journal_mode=wal，实测存在 6MB 的 -wal 文件），只拷主库文件无法保证
    # 完整性，且恢复时若残留旧 -wal 会被回放，把126 行的基线还原成 631 行。
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = os.path.join(os.path.dirname(DB_PATH),
                       "question_bank.db.bak_xingce_kp_%s" % ts)
    src = sqlite3.connect(DB_PATH)
    dst = sqlite3.connect(bak)
    with dst:
        src.backup(dst)          # 一致性快照，含 WAL 中已提交数据
    dst.close()
    src.close()
    chk = sqlite3.connect(bak).execute(
        "select count(*) from knowledge_point").fetchone()[0]
    print("已备份: %s（校验 knowledge_point=%d 行）" % (os.path.basename(bak), chk))
    if chk != len(before):
        print("  [abort] 备份行数与迁移前不一致，中止")
        return 1

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    path_to_id: dict = {k: v for k, v in name_index.items()}
    created: list = []
    order = 0
    for n in create:
        parent_id = 0
        if n["parent_path"]:
            pid = path_to_id.get(n["parent_path"])
            if pid is None:
                print("  [跳过] 父节点缺失: %s" % n["parent_path"])
                continue
            parent_id = pid
        elif n["name"] in path_to_id:
            continue  # 幂等：已存在
        order += 1
        cur.execute(
            "insert into knowledge_point"
            " (point_name, subject_id, parent_id, level, description, sort_order, status)"
            " values (?,?,?,?,?,?,1)",
            (n["name"], SUBJECT_XINGCE, parent_id, n["level"],
             "行测考点（源自【考点】字段，%s 档，出现 %d 次）" % (n["freq_tier"], n["count"]),
             order))
        pid = cur.lastrowid
        created.append(pid)
        path_to_id["/".join(n["path"])] = pid
        path_to_id.setdefault(n["name"], pid)
    con.commit()

    # ── 验证 ────────────────────────────────────────────────────────────
    after = snapshot(cur)
    ok = True
    n_xc = cur.execute("select count(*) from knowledge_point where subject_id=?",
                       (SUBJECT_XINGCE,)).fetchone()[0]
    n_all = len(after)
    print("迁移后 knowledge_point 行数: %d（新增 %d）" % (n_all, n_all - len(before)))
    print("  行测点数 = %d（原 34）" % n_xc)

    touched = [k for k in before if before[k] != after.get(k)]
    print("  既有行被改动: %s" % (touched if touched else "无"))
    ok = ok and not touched

    # 省份私有 token 不得入库。
    # 形态是「XX特色-值」（如 江苏特色-综合资料），故须匹配「特色 + 分隔符」。
    # 注意：不能用 like '%特色%' —— 它会误判既有知识点
    #「习近平新时代中国特色社会主义思想」「中国特色社会主义法治理论」
    #（"特色社会主义" 里的"特色"）。
    prov = [n for (n,) in cur.execute(
        "select point_name from knowledge_point where subject_id=?", (SUBJECT_XINGCE,))
        if re.search(r"特色\s*[-－—–]", n)]
    print("  含「特色-」的省级私有点 = %d（期望 0）%s" % (len(prov), prov[:5]))
    ok = ok and not prov

    # 层级链抽样
    for root in ("中心理解题", "词的辨析", "综合资料"):
        r = cur.execute(
            "select point_id, parent_id, level from knowledge_point"
            " where point_name=? and subject_id=? and parent_id=0",
            (root, SUBJECT_XINGCE)).fetchone()
        if r:
            kids = cur.execute(
                "select count(*) from knowledge_point where parent_id=?", (r[0],)).fetchone()[0]
            print("  根节点 %-8s id=%-5s level=%s 子节点数=%d" % (root, r[0], r[2], kids))

    # 幂等
    n2 = cur.execute("select count(*) from knowledge_point where subject_id=?",
                     (SUBJECT_XINGCE,)).fetchone()[0]
    print("  幂等校验（行测点数，重复执行应不变）= %d" % n2)
    ok = ok and n2 == n_xc

    # manifest 必须「并集」而非覆盖：幂等重跑时 created 为空，若直接覆盖会抹掉
    # 首次 apply 写入的 id，导致后续 --rollback 读到空清单而无法回滚。
    prev_ids = []
    prev_base = None
    if os.path.exists(MANIFEST):
        try:
            with io.open(MANIFEST, encoding="utf-8") as f:
                old = json.load(f)
            prev_ids = old.get("created_point_ids", [])
            # 基线只在「首次 apply」确立一次。若每次都写入，则幂等重跑时before
            # 已是迁移后的行数，基线被污染成迁移后状态，--rollback 会拿它去校验
            # 回退后的库，误报全部新增行「缺失」。
            prev_base = old.get("pre_apply")
        except (ValueError, OSError):
            prev_ids, prev_base = [], None
    merged = sorted(set(prev_ids) | set(created))
    base_out = prev_base if prev_base else {str(k): list(v) for k, v in before.items()}
    with io.open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump({"created_point_ids": merged,
                   "created_at": ts,
                   "inventory": os.path.basename(INV_PATH),
                   # 迁移前基线：供 --rollback 逐字段校验「既有行未被破坏」
                   "pre_apply": base_out},
                  f, ensure_ascii=False)
    print("  迁移清单（供 rollback）: %s" % os.path.basename(MANIFEST))

    con.close()
    print("RESULT = %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())