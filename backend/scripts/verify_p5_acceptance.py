#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""P5 / R8 一键验收探针（只读，不改任何数据）。

跑法（在 backend/ 下）：
    python scripts/verify_p5_acceptance.py                 # 默认 http://127.0.0.1:8001
    python scripts/verify_p5_acceptance.py --base http://127.0.0.1:8000

它检查 6 件事（全部只发 GET / 登录请求）：
  1. 学生能登录、能拿到考试列表；
  2. R8：学生请求**回收站卷**的预览 → 必须 404（修复前是 200）；
  3. R8：学生请求**已发布卷**的预览 → 200 且题目数 > 0（不能把正常功能堵掉）；
  4. R8：学生请求 `catalog` 预览口（`/api/papers/{id}/preview`）对回收站卷 → 404；
  5. 管理员请求回收站卷预览 → 200（内部预览保留）；
  6. P5：资料状态 ↔ 卷状态**漂移 0 条**（唯一真源 = study_material.status）。

退出码：0=全 PASS；1=有 FAIL；2=连不上后端/登录失败。
输出为英文短句（Windows 控制台 GBK 下也不会乱码）。
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_BASE = "http://127.0.0.1:8001"
DEFAULT_DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "data", "question_bank.db")

results: list[tuple[bool, str, str]] = []


def check(ok: bool, name: str, detail: str = "") -> None:
    results.append((bool(ok), name, detail))


def login(base: str, username: str, password: str) -> str | None:
    data = urllib.parse.urlencode({"username": username, "password": password}).encode()
    req = urllib.request.Request(
        base + "/api/auth/login", data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode())
    except Exception as exc:  # noqa: BLE001
        print(f"[ERR] login {username} failed: {exc}")
        return None
    return body.get("access_token") or body.get("token")


def get(base: str, path: str, token: str) -> tuple[int, object]:
    req = urllib.request.Request(base + path, headers={"Authorization": "Bearer " + token})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode()
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, raw
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()
    except Exception as exc:  # noqa: BLE001
        return -1, repr(exc)


def drift_report(db_path: str) -> tuple[int, list[str], int]:
    """资料状态 → 应然的卷状态，逐条对比；返回 (漂移数, 明细, 试卷数)。"""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        materials = list(conn.execute(
            "SELECT material_id, status, COALESCE(paper_code,''), COALESCE(badge,'') "
            "FROM study_material WHERE type='paper' AND status >= 0"))
        papers = {row[0]: row[1] for row in
                  conn.execute("SELECT paper_code, paper_type FROM exam_paper")}
    finally:
        conn.close()

    by_code: dict[str, list[int]] = {}
    for _mid, status, code, badge in materials:
        key = (code or badge or "").strip()
        if key:
            by_code.setdefault(key, []).append(status)

    drift: list[str] = []
    for code, statuses in by_code.items():
        actual = papers.get(code)
        if actual is None or actual == "ENDED":
            continue
        expect = "PUBLISHED" if 1 in statuses else "DRAFT"
        if actual != expect:
            drift.append(f"{code}: paper={actual} expect={expect} material_status={statuses}")
    return len(drift), drift, len(papers)


def main() -> int:
    ap = argparse.ArgumentParser(description="P5 / R8 read-only acceptance probe")
    ap.add_argument("--base", default=os.environ.get("P5_BASE", DEFAULT_BASE))
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--student", default="202516001")
    ap.add_argument("--student-password", default="test123456")
    ap.add_argument("--admin", default="cbrycc")
    ap.add_argument("--admin-password", default="cbrycc")
    args = ap.parse_args()

    print(f"base = {args.base}")
    stu = login(args.base, args.student, args.student_password)
    adm = login(args.base, args.admin, args.admin_password)
    if not stu or not adm:
        print("[ERR] login failed - is backend running on this port?")
        return 2
    check(True, "login(student+admin)")

    # 1) 学生考试列表
    status, body = get(args.base, "/api/exams/list?page_size=100", stu)
    codes = [row.get("paper_code") for row in body.get("data", [])] if status == 200 else []
    check(status == 200, "student GET /api/exams/list",
          f"status={status} codes={codes}")

    # 2) R8：学生看回收站卷（#1 ENDED）预览 → 404
    status, body = get(args.base, "/api/exams/preview/1", stu)
    check(status == 404, "R8 student preview ENDED paper -> 404",
          f"status={status} body={str(body)[:80]}")

    # 3) R8：学生看已发布卷（#2）预览 → 200 且有题
    status, body = get(args.base, "/api/exams/preview/2", stu)
    questions = len(body.get("questions", [])) if isinstance(body, dict) else 0
    check(status == 200 and questions > 0,
          "R8 student preview PUBLISHED paper -> 200 with questions",
          f"status={status} questions={questions}")

    # 4) catalog 预览口对回收站卷 → 404
    status, body = get(args.base, "/api/papers/1/preview", stu)
    check(status == 404, "R8 student preview via /api/papers/1/preview -> 404",
          f"status={status}")

    # 5) 管理员内部预览 → 200
    status, body = get(args.base, "/api/exams/preview/1", adm)
    check(status == 200, "R8 admin preview ENDED paper -> 200 (internal kept)",
          f"status={status}")

    # 6) P5 漂移
    drift_count, drift_detail, paper_count = drift_report(args.db)
    check(drift_count == 0, "P5 material<->paper drift == 0",
          f"drift={drift_count} papers={paper_count} {drift_detail or ''}")

    width = max(len(name) for _, name, _ in results) + 2
    print("-" * 78)
    failed = 0
    for ok, name, detail in results:
        flag = "PASS" if ok else "FAIL"
        if not ok:
            failed += 1
        print(f"[{flag}] {name:<{width}} {detail}")
    print("-" * 78)
    print(f"{len(results) - failed}/{len(results)} PASS, {failed} FAIL")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
