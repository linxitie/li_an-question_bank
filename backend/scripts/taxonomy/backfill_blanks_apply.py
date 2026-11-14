# -*- coding: utf-8 -*-
"""把「Word 下划线空格丢失」的选词填空题回填 ____。

背景：原文里横线是「带下划线格式的空格」，docx 解析只拿到一个半角空格，
题干变成「把人民群众 ，作为…」。前端渲染自然看不到横线。

为什么不用通用正则批量替换空格：docx 每 ~40 字换行，解析后同样留下半角空格，
正则无法区分「换行空格」与「横线空格」，误替换会把正文切断（实测 3669 有 5 个空格，
只有 3 个是横线）。因此本脚本逐题给出「上下文 + 期望替换」，每题先断言
上下文在题干里唯一出现，命中才改，改完再校验 ____ 数量与预期一致。

用法：
  python scripts/taxonomy/backfill_blanks_apply.py --dry-run
  python scripts/taxonomy/backfill_blanks_apply.py --apply
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
DB_PATH = BACKEND_DIR / "data" / "question_bank.db"
BACKUP_DIR = BACKEND_DIR / "data" / "backups"
OUT = BACKEND_DIR.parent / "docs" / "design" / "横线回填结果_v1.json"

# question_id -> [(原文片段, 回填后片段), ...]
# 片段均含横线左右各 2~6 字上下文，保证唯一命中；括号内是人工判读依据。
REPLACEMENTS: dict[int, list[tuple[str, str]]] = {
    2661: [("把人民群众 ，作为", "把人民群众____，作为")],              # 空白位于逗号前
    2689: [("按照 的总要求", "按照____的总要求")],                      # 「的总要求」前的空白
    3666: [("在岗位上 的写照", "在岗位上____的写照")],
    3667: [("精神秩序的 。", "精神秩序的____。")],
    3668: [("特点 出来", "特点____出来")],
    3669: [("科技赋能下的 、", "科技赋能下的____、"),
           ("艺术 将永远镌刻", "艺术____将永远镌刻"),
           ("奥林匹克的 历史中", "奥林匹克的____历史中")],           # 3 空：下的__、/艺术__将/的__历史
    3670: [("47米。 ，沙珠玉人", "47米。____，沙珠玉人"),
           ("沙珠玉人开始 。", "沙珠玉人开始____。")],
    3671: [("都有着 的闪光点", "都有着____的闪光点"),
           ("古人 的记录", "古人____的记录")],                        # 「至今 都」是换行空格，不改
    3672: [("之中是 的。", "之中是____的。"),
           ("几乎 是充盈", "几乎____是充盈"),
           ("对称感与 感", "对称感与____感")],
    3673: [("老字号所 的独特", "老字号所____的独特"),
           ("具有 的品牌价值", "具有____的品牌价值"),
           ("它们 着优秀的", "它们____着优秀的")],                    # 「经营理 念」是换行空格
    3674: [("诗坛尽管 ，", "诗坛尽管____，"),
           ("诗人理想 ，", "诗人理想____，"),
           ("与理 论 的文本", "与理论____的文本")],                   # 保留「理 论」中的换行空格，只补 论_的
    3675: [("时代的 ，", "时代的____，"),
           ("这面镜子 出", "这面镜子____出"),
           ("语言的 ，也让", "语言的____，也让")],
    3676: [("······ ，成为我国", "······____，成为我国")],
    3798: [("航空成就， 出", "航空成就，____出")],
    3799: [("大多 ，彰显", "大多____，彰显")],
    3808: [("可见， ，在蝶类", "可见，____，在蝶类")],
    3809: [("叙事过程， 。", "叙事过程，____。")],
    3921: [("重要性 。", "重要性____。")],
    3922: [("后者 ，对于", "后者____，对于")],
}

# 材料（question_groups.shared_content）里的横线：题干只是「填入文中画横线处」，
# 空位在材料正文里，必须改材料表。
MATERIAL_REPLACEMENTS: dict[int, list[tuple[str, str]]] = {  # group_id -> 替换对
    51: [("想它。” 。人们", "想它。”____。人们")],       # 4069 材料一
    54: [("软硬件工具， 。", "软硬件工具，____。")],       # 4084 材料五（原文此处换行）
}

# 明确不自动回填、留给人工的题
SKIPPED = {
    3800: "「研究 地均居于」语义不通，横线原文可能吞掉了「地位」，需核对原始 PDF/docx",
    4214: "划线对象是整句（下列与画横线部分意思相符），文中无空位可插入 ____",
}


def backup(db_path: Path) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    dst = BACKUP_DIR / f"question_bank_pre_blanks_{datetime.now():%Y%m%d_%H%M%S}.db"
    src = sqlite3.connect(str(db_path))
    out = sqlite3.connect(str(dst))
    try:
        src.backup(out)
    finally:
        out.close()
        src.close()
    return dst


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    results = []
    plan: list[tuple[str, int]] = []
    for qid, pairs in REPLACEMENTS.items():
        row = conn.execute("SELECT question_content FROM question_bank WHERE question_id=?",
                           (qid,)).fetchone()
        if not row:
            results.append({"qid": qid, "status": "missing"})
            continue
        text = row["question_content"] or ""
        new = text
        ok = True
        for old, repl in pairs:
            if new.count(old) != 1:
                ok = False
                results.append({"qid": qid, "status": "context_not_unique",
                                "fragment": old, "count": new.count(old)})
                break
            new = new.replace(old, repl)
        if not ok:
            continue
        added = new.count("____") - text.count("____")
        results.append({"qid": qid, "status": "ok", "blanks_added": added,
                        "before": text[:80], "after": new[:80]})
        if added != len(pairs):
            results.append({"qid": qid, "status": "count_mismatch",
                            "expected": len(pairs), "got": added})
            continue
        plan.append((new, qid))

    mat_plan: list[tuple[str, int]] = []
    for gid, pairs in MATERIAL_REPLACEMENTS.items():
        row = conn.execute("SELECT shared_content FROM question_groups WHERE id=?", (gid,)).fetchone()
        if not row:
            results.append({"group_id": gid, "status": "missing"})
            continue
        text = row["shared_content"] or ""
        new = text
        ok = True
        for old, repl in pairs:
            if new.count(old) != 1:
                ok = False
                results.append({"group_id": gid, "status": "context_not_unique",
                                "fragment": old, "count": new.count(old)})
                break
            new = new.replace(old, repl)
        if ok and new != text:
            mat_plan.append((new, gid))

    print(f"可回填 {len(plan)} 题 / 计划 {len(REPLACEMENTS)} 题；材料 {len(mat_plan)} 组")
    print(f"跳过 {len(SKIPPED)} 题：" + "；".join(f"{k} {v}" for k, v in SKIPPED.items()))
    if a.apply and (plan or mat_plan):
        dst = backup(DB_PATH)
        print(f"备份：{dst}")
        with conn:
            if plan:
                conn.executemany("UPDATE question_bank SET question_content=? WHERE question_id=?", plan)
            if mat_plan:
                conn.executemany("UPDATE question_groups SET shared_content=? WHERE id=?", mat_plan)
        print(f"已回填 {len(plan)} 题、材料 {len(mat_plan)} 组")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"generated_at": datetime.now().isoformat(timespec="seconds"),
                               "applied": bool(a.apply and plan),
                               "results": results, "skipped": SKIPPED},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"report -> {OUT}")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
