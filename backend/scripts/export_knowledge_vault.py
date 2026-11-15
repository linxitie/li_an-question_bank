# 知识库采集脚本（模块7 · P6 / 2-1）
# 方向：SQLite（事实源） -> docs/knowledge-vault/联考知识库（可重建投影），单向，禁止回写。
# 规则：只重写 GENERATED 段，保留「我的批注」段；重复执行结果稳定。
import re
import sqlite3
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
DB = BACKEND / "data" / "question_bank.db"
VAULT = ROOT / "docs" / "knowledge-vault" / "联考知识库"
MARK_BEGIN = "<!-- GENERATED:BEGIN -->"
MARK_END = "<!-- GENERATED:END -->"
NOTE_HEAD = "## 我的批注"


def safe(name: str) -> str:
    return re.sub(r"[\\/:*?\"<>|]", "-", (name or "未命名")).strip() or "未命名"


def write_page(path: Path, title: str, meta: dict, body: str) -> None:
    keep = ""
    if path.exists():
        old = path.read_text(encoding="utf-8")
        idx = old.find(NOTE_HEAD)
        if idx >= 0:
            keep = old[idx:]
    fm = "\n".join([f"{k}: {v}" for k, v in meta.items()])
    text = (
        f"---\n{fm}\n---\n\n# {title}\n\n"
        f"{MARK_BEGIN}\n{body}{MARK_END}\n\n"
    )
    if keep:
        text += keep if keep.startswith(NOTE_HEAD) else NOTE_HEAD + "\n\n"
    else:
        text += NOTE_HEAD + "\n\n（这里写你自己的理解、踩坑、口诀，脚本不会覆盖这段）\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> int:
    if not DB.exists():
        print(f"[SKIP] 数据库不存在: {DB}")
        return 1
    conn = sqlite3.connect(str(DB))
    cur = conn.cursor()

    subjects = {sid: name for sid, name in cur.execute("SELECT subject_id, subject_name FROM question_subject")}
    modules = cur.execute(
        "SELECT point_id, point_name, subject_id FROM knowledge_point WHERE level=1 AND IFNULL(status,1)!=0 ORDER BY sort_order"
    ).fetchall()

    pages = 0
    index_lines = []
    for mod_id, mod_name, sid in modules:
        subj = subjects.get(sid, f"科目{sid}")
        points = cur.execute(
            "SELECT point_name, description FROM knowledge_point WHERE parent_id=? AND IFNULL(status,1)!=0 ORDER BY sort_order",
            (mod_id,),
        ).fetchall()
        if not points:
            continue
        body = [f"共 {len(points)} 个考点。\\n"]
        for pname, desc in points:
            body.append(f"- **{pname}**：{desc or '（暂无描述）'}")
        body.append("")
        rel = f"02-考点/{safe(subj)}/{safe(mod_name)}.md"
        write_page(
            VAULT / rel,
            f"{subj} · {mod_name}",
            {
                "title": f"{subj}-{mod_name}",
                "subject": subj,
                "chapter": mod_name,
                "generated": "true",
                "tags": "[考点]",
            },
            "\n".join(body),
        )
        index_lines.append("| {} | {} | {} | [[{}查看]] |".format(subj, mod_name, len(points), rel[:-3] + "\\|"))
        pages += 1

    # 科目总览
    if index_lines:
        table = "\n".join(
            ["| 科目 | 模块 | 考点数 | 链接 |", "|---|---|---|---|"] + index_lines
        )
        write_page(
            VAULT / "01-科目" / "行测.md",
            "行测 · 科目总览",
            {"title": "行测", "subject": "行测", "generated": "true", "tags": "[科目]"},
            table + "\n",
        )
        pages += 1

    conn.close()
    print(f"[DONE] 导出 {pages} 个页面 -> {VAULT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
