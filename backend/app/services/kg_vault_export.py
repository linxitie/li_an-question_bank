"""知识图谱 → Obsidian 自生长知识库（服务层，2026-11-18）。

为什么从 scripts 挪到 app/services：
    新用户注册后就该有自己的知识库文件夹，而不是等谁手动跑脚本；
    后端需要直接 import，所以把核心逻辑放服务层，scripts/kg_vault/export_kg_vault.py 只做 CLI 薄壳。

多用户隔离模型：
    用户/<学号>/ 是一个独立 Obsidian vault（自带 .obsidian/app.json）。
    用学号而不是昵称：学号唯一且稳定，昵称可改、可空、可能重名。

自生长：
    每次运行按 kg_user_node_state / kg_user_edge / kg_user_event 重写笔记；
    每日 07:10 由 APScheduler 自动刷新；新注册学生注册完成即建空库。
"""
from __future__ import annotations

import json
import logging
import re
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

REPO = Path(__file__).resolve().parents[3]
DEFAULT_DB = REPO / "backend" / "data" / "example_db.sqlite"
DEFAULT_OUT = REPO / "docs" / "obsidian" / "知识图谱自生长"

WEAK_MASTERY = 0.5
WEAK_HEAT = 0.4


# ------------------------------ 数据读取 ------------------------------

def default_db_path() -> Path:
    """优先用运行期配置（backend/.env 的 SQLITE_PATH），保证和业务读写同一个库。"""
    try:
        from app.core.config import settings
        from app.core.db_guard import resolve_sqlite_path

        return resolve_sqlite_path(settings.SQLITE_PATH)
    except Exception:  # noqa: BLE001 - 独立脚本/测试环境退回仓库默认路径
        return DEFAULT_DB


def open_db(db_path: Optional[Path] = None) -> sqlite3.Connection:
    path = Path(db_path or default_db_path())
    if not path.exists():
        raise FileNotFoundError("数据库不存在：" + str(path))
    conn = sqlite3.connect("file:" + path.as_posix() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def load_students(conn: sqlite3.Connection, only: Optional[str] = None) -> list[dict[str, Any]]:
    """全部在读学生（含还没有任何图谱节点的），按学号排序。"""
    rows = conn.execute(
        """
        SELECT user_id, username, COALESCE(NULLIF(user_no,''), username) AS user_no,
               COALESCE(nickname,'') AS nickname
        FROM sys_user
        WHERE COALESCE(is_deleted, 0) = 0
          AND (user_type = 'student' OR role_level = 0)
        ORDER BY COALESCE(NULLIF(user_no,''), username)
        """
    ).fetchall()
    users = [dict(r) for r in rows]
    if only:
        key = str(only).strip()
        users = [
            u for u in users
            if u["username"] == key or u["user_no"] == key or str(u["user_id"]) == key
        ]
    return users


def load_nodes(conn: sqlite3.Connection, user_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT s.point_id, s.mastery, s.heat, s.attempt_count, s.correct_count,
               p.point_name, q.subject_name
        FROM kg_user_node_state s
        JOIN knowledge_point p ON p.point_id = s.point_id
        LEFT JOIN question_subject q ON q.subject_id = p.subject_id
        WHERE s.user_id = ?
        ORDER BY (s.heat * (1 - s.mastery)) DESC, s.heat DESC
        """,
        (user_id,),
    ).fetchall()
    nodes = []
    for r in rows:
        d = dict(r)
        d["mastery"] = float(d["mastery"] or 0)
        d["heat"] = float(d["heat"] or 0)
        d["subject"] = d.get("subject_name") or "未分科目"
        d["contribution"] = round(d["heat"] * (1 - d["mastery"]), 2)
        nodes.append(d)
    return nodes


def load_edges(conn: sqlite3.Connection, user_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT src_point, dst_point, rel_type, weight FROM kg_user_edge "
        "WHERE user_id = ? ORDER BY weight DESC",
        (user_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def load_events(conn: sqlite3.Connection, user_id: int, limit: int = 60) -> dict[int, list[dict[str, Any]]]:
    rows = conn.execute(
        "SELECT point_id, event_type, weight, created_at FROM kg_user_event "
        "WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    grouped: dict[int, list[dict[str, Any]]] = {}
    for r in rows:
        grouped.setdefault(int(r["point_id"]), []).append(dict(r))
    return grouped


def load_question_counts(conn: sqlite3.Connection) -> dict[int, int]:
    rows = conn.execute(
        "SELECT point_id, COUNT(*) AS c FROM question_bank WHERE point_id IS NOT NULL GROUP BY point_id"
    ).fetchall()
    return {int(r["point_id"]): int(r["c"]) for r in rows}


# ------------------------------ 文本渲染 ------------------------------

def safe_name(text: str, fallback: str = "未命名") -> str:
    name = re.sub(r'[\\/:*?"<>|#^\[\]]+', "-", str(text or "")).strip(" .-")
    return name[:60] or fallback


def fmt_pct(v: float) -> str:
    return "%.0f%%" % (max(0.0, min(1.0, float(v or 0))) * 100)


def user_dir_name(user: dict[str, Any]) -> str:
    """知识库文件夹名：优先学号（稳定唯一），没有才退回 username / user_id。"""
    return safe_name(user.get("user_no") or user.get("username") or str(user["user_id"]))


def node_note(node: dict[str, Any], neighbors: list[dict[str, Any]],
              events: list[dict[str, Any]], q_count: int) -> str:
    lines = [
        "---",
        "point_id: %s" % node["point_id"],
        "subject: %s" % node["subject"],
        "mastery: %.3f" % node["mastery"],
        "heat: %.3f" % node["heat"],
        "contribution: %s" % node["contribution"],
        "attempt_count: %s" % (node["attempt_count"] or 0),
        "correct_count: %s" % (node["correct_count"] or 0),
        "question_count: %s" % q_count,
        "updated: %s" % date.today().isoformat(),
        "---",
        "",
        "# " + node["point_name"],
        "",
        "> 科目：[[%s]] ｜ 掌握度 **%s** ｜ 生长热度 **%.2f** ｜ 贡献度 **%s**"
        % (node["subject"], fmt_pct(node["mastery"]), node["heat"], node["contribution"]),
        "",
    ]
    bar_len = 20
    filled = int(round(bar_len * node["mastery"]))
    lines.append("掌握度：[%s%s] %s" % ("█" * filled, "░" * (bar_len - filled), fmt_pct(node["mastery"])))
    lines.append("")
    if node["mastery"] < WEAK_MASTERY and node["heat"] >= WEAK_HEAT:
        lines += [
            "## 为什么它出现在这里",
            "",
            "- 生长热度 %.2f 说明最近在频繁碰它；掌握度只有 %s，属于**正在长但还没长牢**的节点；"
            % (node["heat"], fmt_pct(node["mastery"])),
            "- 题库里该考点共 %s 道题，可用来做针对性训练。" % q_count,
            "",
        ]
    lines += ["## 关联节点（来自你自己的行为共现边）", ""]
    if neighbors:
        lines += [
            "- [[%s]] ｜ 权重 %.2f ｜ %s" % (n["name"], float(n["weight"]), n["rel_type"])
            for n in neighbors
        ]
    else:
        lines.append("- 暂无关联边（做过相邻考点的错题/笔记后会自动长出来）")
    lines += ["", "## 最近行为", ""]
    if events:
        lines.append("| 时间 | 事件 | 权重 |")
        lines.append("|---|---|---|")
        for e in events[:8]:
            label = {"answer_wrong": "答错", "answer_correct": "答对", "note_edit": "编辑笔记"}.get(
                e["event_type"], e["event_type"]
            )
            lines.append("| %s | %s | %s |" % (e["created_at"], label, e["weight"]))
    else:
        lines.append("- 暂无事件记录")
    lines.append("")
    return "\n".join(lines)


def subject_note(subject: str, nodes: list[dict[str, Any]]) -> str:
    lines = ["# " + subject, "", "> 本科目共 %d 个已生长节点（按贡献度排序）" % len(nodes), "",
             "| 考点 | 掌握度 | 热度 | 贡献度 | 题量 |", "|---|---|---|---|---|"]
    for n in nodes:
        lines.append("| [[%s]] | %s | %.2f | %s | %s |" % (
            n["name"], fmt_pct(n["mastery"]), n["heat"], n["contribution"], n["question_count"]))
    lines.append("")
    return "\n".join(lines)


def dashboard_note(user: dict[str, Any], nodes: list[dict[str, Any]], edges: list[dict[str, Any]],
                   recommend: list[dict[str, Any]]) -> str:
    title = user["user_no"] or user["username"]
    total = len(nodes)
    weak = [n for n in nodes if n["mastery"] < WEAK_MASTERY and n["heat"] >= WEAK_HEAT]
    mastered = [n for n in nodes if n["mastery"] >= 0.85]
    avg = sum(n["mastery"] for n in nodes) / total if total else 0
    lines = [
        "# 弱项看板 · " + title,
        "",
        "> 自动生成于 %s ｜ 数据源：backend/data/example_db.sqlite（只读）"
        % datetime.now().strftime("%Y-%m-%d %H:%M"),
        "",
        "## 总览", "", "| 指标 | 数值 |", "|---|---|",
        "| 已生长节点 | %d |" % total,
        "| 平均掌握度 | %s |" % fmt_pct(avg),
        "| 正在长但没长牢 | %d |" % len(weak),
        "| 已掌握（85%% 及以上） | %d |" % len(mastered),
        "| 共现边 | %d |" % len(edges),
        "",
    ]
    if total == 0:
        lines += [
            "## 还没有学习数据",
            "",
            "这个知识库是空库：账号已建立，但还没有做第一道题。",
            "",
            "- 去题库做 1 道题（错对都算），系统会创建第一批考点节点；",
            "- 任务中心会按「热度 × (1 − 掌握度)」自动挑 2 个薄弱点，生成「知识图谱生成」周任务；",
            "- 次日 07:10 自动刷新后，这里会开始出现节点与关联。",
            "",
        ]
    else:
        lines += ["## 最该补的 10 个节点", "", "| 考点 | 掌握度 | 热度 | 贡献度 |", "|---|---|---|---|"]
        for n in weak[:10]:
            lines.append("| [[%s]] | %s | %.2f | %s |" % (
                n["name"], fmt_pct(n["mastery"]), n["heat"], n["contribution"]))
        lines += ["", "## 本周个性化任务候选（与系统采样同口径）", "",
                  "> 口径：score = 热度 × (1 − 掌握度)，取前 2；系统每周自动按这个口径生成 2 条「知识图谱生成」周任务。", ""]
        for i, n in enumerate(recommend, 1):
            lines.append(
                "%d. [[%s]] ｜ 掌握度 %s ｜ 热度 %.2f ｜ 建议 30 题（题库共 %s 题）"
                % (i, n["name"], fmt_pct(n["mastery"]), n["heat"], n["question_count"]))
        lines.append("")
    lines += ["## 每日快照", "", "- 本目录 历史/YYYY-MM-DD.md 每天累积一份快照，用来对比成长曲线。", ""]
    return "\n".join(lines)


def snapshot_note(nodes: list[dict[str, Any]]) -> str:
    total = len(nodes)
    avg = sum(n["mastery"] for n in nodes) / total if total else 0
    weak = [n for n in nodes if n["mastery"] < WEAK_MASTERY and n["heat"] >= WEAK_HEAT]
    lines = ["# %s 图谱快照" % date.today().isoformat(), "",
             "- 节点 %d 个 ｜ 平均掌握度 %s ｜ 弱项 %d 个" % (total, fmt_pct(avg), len(weak)), ""]
    if weak:
        lines += ["| 考点 | 掌握度 | 热度 |", "|---|---|---|"]
        for n in weak[:20]:
            lines.append("| [[%s]] | %s | %.2f |" % (n["name"], fmt_pct(n["mastery"]), n["heat"]))
        lines.append("")
    return "\n".join(lines)


def canvas_json(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> str:
    top = nodes[:30]
    ids = {n["point_id"]: "kg%d" % idx for idx, n in enumerate(top)}
    canvas_nodes = []
    for idx, n in enumerate(top):
        canvas_nodes.append({
            "id": ids[n["point_id"]],
            "type": "text",
            "text": "%s\n掌握 %s · 热度 %.2f" % (n["point_name"], fmt_pct(n["mastery"]), n["heat"]),
            "x": (idx % 5) * 260,
            "y": (idx // 5) * 130,
            "width": 200,
            "height": 60,
        })
    canvas_edges = []
    for e in edges:
        if e["src_point"] in ids and e["dst_point"] in ids:
            canvas_edges.append({
                "id": "e%s-%s" % (ids[e["src_point"]], ids[e["dst_point"]]),
                "fromNode": ids[e["src_point"]],
                "toNode": ids[e["dst_point"]],
                "label": str(e.get("rel_type") or ""),
            })
    return json.dumps({"nodes": canvas_nodes, "edges": canvas_edges}, ensure_ascii=False, indent=2)


# ------------------------------ 写盘 ------------------------------

def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_vault_config(user_dir: Path) -> None:
    cfg_dir = user_dir / ".obsidian"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "app.json").write_text(json.dumps({
        "newFileLocation": "current",
        "attachmentFolderPath": "附件",
        "alwaysUpdateLinks": True,
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def migrate_old_dir(vault: Path, user: dict[str, Any], target: Path) -> None:
    """昵称时代生成过 用户/<昵称>/：目标目录不存在时整体改名，保留用户自己的笔记。"""
    candidates = []
    if user.get("nickname"):
        candidates.append(safe_name(user["nickname"]))
    if user.get("username"):
        candidates.append(safe_name(user["username"]))
    for name in candidates:
        old = vault / "用户" / name
        if old.exists() and not target.exists() and old != target:
            try:
                old.rename(target)
                logger.info("知识库目录迁移：%s -> %s", name, target.name)
            except OSError as exc:
                logger.warning("知识库目录迁移失败 %s: %s", name, exc)
            return


def export_user(conn: sqlite3.Connection, user: dict[str, Any], vault: Path,
                q_counts: dict[int, int]) -> dict[str, Any]:
    nodes = load_nodes(conn, user["user_id"])
    edges = load_edges(conn, user["user_id"])
    events = load_events(conn, user["user_id"])
    for n in nodes:
        n["name"] = safe_name(n["point_name"], "考点%s" % n["point_id"])
        n["question_count"] = q_counts.get(n["point_id"], 0)
    by_id = {n["point_id"]: n for n in nodes}

    neighbors: dict[int, list[dict[str, Any]]] = {}
    for e in edges:
        src, dst = by_id.get(e["src_point"]), by_id.get(e["dst_point"])
        if not src or not dst:
            continue
        neighbors.setdefault(src["point_id"], []).append(
            {"name": dst["name"], "weight": e["weight"], "rel_type": e["rel_type"]})
        neighbors.setdefault(dst["point_id"], []).append(
            {"name": src["name"], "weight": e["weight"], "rel_type": e["rel_type"]})

    folder = user_dir_name(user)
    user_dir = vault / "用户" / folder
    migrate_old_dir(vault, user, user_dir)
    write_vault_config(user_dir)
    (user_dir / "节点").mkdir(parents=True, exist_ok=True)
    (user_dir / "科目").mkdir(parents=True, exist_ok=True)

    for n in nodes:
        write(user_dir / "节点" / (n["name"] + ".md"),
              node_note(n, neighbors.get(n["point_id"], []), events.get(n["point_id"], []),
                        n["question_count"]))

    subjects: dict[str, list[dict[str, Any]]] = {}
    for n in nodes:
        subjects.setdefault(n["subject"], []).append(n)
    for subject, items in subjects.items():
        write(user_dir / "科目" / (safe_name(subject, "未分科目") + ".md"),
              subject_note(subject, items))

    recommend = sorted(nodes, key=lambda x: (x["heat"] * (1 - x["mastery"])), reverse=True)[:2]
    write(user_dir / "弱项看板.md", dashboard_note(user, nodes, edges, recommend))
    write(user_dir / "历史" / (date.today().isoformat() + ".md"), snapshot_note(nodes))
    write(user_dir / "图谱.canvas", canvas_json(nodes, edges))
    display = user["user_no"] or user["username"]
    nick = ("（%s）" % user["nickname"]) if user.get("nickname") else ""
    write(user_dir / "README.md", "\n".join([
        "# %s%s · 我的知识图谱" % (display, nick),
        "",
        "> 自动生成 %s ｜ 节点 %d ｜ 边 %d" % (
            datetime.now().strftime("%Y-%m-%d %H:%M"), len(nodes), len(edges)),
        "",
        "## 入口",
        "",
        "- [[弱项看板]] —— 最该补的节点 + 本周任务候选",
        "- 图谱.canvas —— Obsidian 画布版图谱（拖拽查看关联）",
        "- 科目/ —— 按科目分组的考点表",
        "- 节点/ —— 每个考点一篇笔记（含关联节点与最近行为）",
        "- 历史/ —— 每日快照，用来对比成长",
        "",
    ]))
    return {
        "user": display,
        "nickname": user.get("nickname") or "",
        "folder": folder,
        "nodes": len(nodes),
        "edges": len(edges),
    }


def export_vault(db_path: Optional[Path] = None, out: Optional[Path] = None,
                 only: Optional[str] = None) -> dict[str, Any]:
    vault = Path(out) if out else DEFAULT_OUT
    conn = open_db(db_path)
    try:
        users = load_students(conn, only)
        if not users:
            return {"vault": str(vault), "users": 0, "notes": 0, "mode": "write",
                    "error": "no students"}
        q_counts = load_question_counts(conn)
        rows = [export_user(conn, user, vault, q_counts) for user in users]
        index_rows = [
            "- %s%s ｜ vault：用户/%s/ ｜ 节点 %d ｜ 边 %d" % (
                r["user"], ("（%s）" % r["nickname"]) if r["nickname"] else "",
                r["folder"], r["nodes"], r["edges"])
            for r in rows
        ]
        write(vault / "知识图谱索引.md", "\n".join([
            "# 知识图谱自生长索引",
            "",
            "> 生成于 %s ｜ 学生数 %d ｜ 每人的库在 用户/<学号>/，用 Obsidian 单独打开该文件夹作为仓库"
            % (datetime.now().strftime("%Y-%m-%d %H:%M"), len(rows)),
            "",
            "## 学生",
            "",
            *index_rows,
            "",
            "## 多用户隔离（重要）",
            "",
            "- 每个 用户/<学号>/ 都是独立 Obsidian vault（自带 .obsidian 配置）；",
            "- 用 Obsidian「打开文件夹作为仓库」时选自己的 用户/<学号>/，不要打开外层目录；",
            "- 原因：Obsidian 双链（考点名）在同一个 vault 内全局解析，多用户同名考点会串到一起；",
            "- 外层的 知识图谱索引.md 只做总览，不属于任何 vault。",
            "",
            "## 自动刷新",
            "",
            "- 后端每天 07:10 自动刷新（APScheduler）；新注册学生注册成功即建空库；",
            "- 需要立即刷新时可运行 python scripts/kg_vault/export_kg_vault.py。",
            "",
        ]))
        return {
            "vault": str(vault),
            "users": len(rows),
            "notes": sum(r["nodes"] for r in rows),
            "edges": sum(r["edges"] for r in rows),
            "mode": "write",
            "users_detail": rows,
        }
    finally:
        conn.close()


def export_user_by_name(username: str, out: Optional[Path] = None) -> dict[str, Any]:
    """注册后调用：给单个学生建/刷新知识库（空库也建）。"""
    return export_vault(out=out, only=username)
