# 生成知识图谱语义边（模块7 · P6 补全）
# 目标：在 contains 结构边之外，补两类语义关系
#   1) prerequisite_of  前置：同模块内按频次档位 high -> medium -> low 建立学习先后链
#   2) confusable      易混：同模块内名称高度相似的考点对（共享 2 字以上核心词）
# 幂等：以 (src,dst,relation) 去重，可重复执行
import sqlite3
from itertools import combinations
from pathlib import Path

DB = Path(__file__).resolve().parents[1] / "data" / "question_bank.db"
TIER_RANK = {"high": 0, "medium": 1, "low": 2, "rare": 3}


def tier_of(desc: str) -> str:
    for t in TIER_RANK:
        if t in (desc or ""):
            return t
    return "rare"


def ensure_edge(cur, src: int, dst: int, relation: str, weight: float, origin: str) -> bool:
    row = cur.execute(
        "SELECT 1 FROM kg_edge WHERE src_type='knowledge_point' AND src_id=? AND dst_type='knowledge_point' AND dst_id=? AND relation=?",
        (src, dst, relation),
    ).fetchone()
    if row:
        return False
    cur.execute(
        "INSERT INTO kg_edge (src_type, src_id, dst_type, dst_id, relation, weight, confidence, origin, created_at) "
        "VALUES ('knowledge_point', ?, 'knowledge_point', ?, ?, ?, 0.8, ?, datetime('now'))",
        (src, dst, relation, weight, origin),
    )
    return True


def similar(a: str, b: str) -> bool:
    if not a or not b or a == b:
        return False
    core = lambda s: "".join(ch for ch in s if "\u4e00" <= ch <= "\u9fff")
    ca, cb = core(a), core(b)
    if len(ca) < 2 or len(cb) < 2:
        return False
    shared = len(set(ca) & set(cb))
    shorter, longer = sorted((len(ca), len(cb)))
    # 严格要求：短串几乎被长串包含（差 1 字以内），才判为易混，避免“共字即相似”的噪声
    if shared < 2:
        return False
    if shorter <= 3:
        return shared >= shorter
    return shared >= longer - 1 and shared >= shorter - 1


def main() -> int:
    conn = sqlite3.connect(str(DB))
    cur = conn.cursor()

    modules = cur.execute(
        "SELECT point_id, point_name FROM knowledge_point WHERE level=1 AND IFNULL(status,1)!=0"
    ).fetchall()
    print(f"[MODULES] {len(modules)} 个模块")

    pre_cnt = 0
    conf_cnt = 0
    for mod_id, mod_name in modules:
        points = cur.execute(
            "SELECT point_id, point_name, description FROM knowledge_point WHERE parent_id=? AND IFNULL(status,1)!=0",
            (mod_id,),
        ).fetchall()
        if not points:
            continue
        ranked = sorted(points, key=lambda p: (TIER_RANK.get(tier_of(p[2]), 3), -(len(p[1] or ""))))
        # 前置链：按频次档位排序后，相邻两两建立 prerequisite_of（high 先学）
        for a, b in zip(ranked, ranked[1:]):
            ta, tb = tier_of(a[2]), tier_of(b[2])
            if TIER_RANK.get(ta, 3) >= TIER_RANK.get(tb, 3):
                continue
            if ensure_edge(cur, a[0], b[0], "prerequisite_of", 0.6, "heuristic_tier"):
                pre_cnt += 1
        # 易混：同模块内名称相似的考点对
        for a, b in combinations(points, 2):
            if similar(a[1] or "", b[1] or ""):
                if ensure_edge(cur, a[0], b[0], "confusable", 0.5, "heuristic_name"):
                    conf_cnt += 1

    conn.commit()
    total = cur.execute("SELECT COUNT(*) FROM kg_edge").fetchone()[0]
    by_rel = cur.execute("SELECT relation, COUNT(*) FROM kg_edge GROUP BY relation").fetchall()
    print(f"[DONE] 新增 prerequisite_of {pre_cnt} 条、confusable {conf_cnt} 条；kg_edge 合计 {total}")
    print("[BY_REL]", by_rel)
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
