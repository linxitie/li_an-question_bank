# -*- coding: utf-8 -*-
"""给 achievement 增加 badge_tier（固定成色，按获取难度），并回填 48 枚。

档位是**绝对量**：由成就条件的门槛值决定，一次写死在库里，之后不随玩家基数变化。
稀有度（拥有比例）只在 API 里作为文字展示，不参与颜色。
"""
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")
DB = r"C:/Users/35709/OneDrive/Desktop/题库/li_an-question_bank/backend/data/question_bank.db"

# 按 condition_code → (门槛 → 成色)；未列出的门槛取该 code 的兜底档
RULES = {
    "first_login": ({}, "黑铁"),
    "streak_days": ({3: "青铜", 7: "白银", 15: "黄金", 30: "钻石"}, "青铜"),
    "month_days": ({}, "白银"),
    "morning_bird": ({}, "青铜"),
    "night_owl": ({}, "青铜"),
    "total_questions": ({100: "青铜", 300: "白银", 1000: "黄金", 3000: "黄金",
                         5000: "钻石", 10000: "钻石"}, "青铜"),
    "today_questions": ({}, "青铜"),
    "week_questions": ({}, "白银"),
    "session_perfect_any": ({}, "青铜"),
    "session_perfect": ({}, "白银"),
    "session_accuracy": ({}, "白银"),
    "accuracy80_streak": ({}, "白银"),
    "week_accuracy": ({}, "白银"),
    "month_accuracy": ({}, "黄金"),
    "perfect_streak": ({}, "黄金"),
    "view_wrong_first": ({}, "黑铁"),
    "review_count": ({50: "青铜", 200: "白银"}, "青铜"),
    "chop_count": ({10: "青铜", 100: "白银", 1000: "钻石"}, "青铜"),
    "post_count": ({1: "黑铁", 10: "青铜", 50: "白银"}, "青铜"),
    "single_post_likes": ({}, "白银"),
    "total_likes": ({50: "白银", 200: "黄金"}, "白银"),
    "three_subject_each": ({}, "白银"),
    "three_subject_accuracy": ({}, "钻石"),
    "level_reach": ({}, "黄金"),
    "total_coins": ({}, "白银"),
    "favorite_count": ({}, "黑铁"),
    "note_count": ({}, "青铜"),
    "quote_favorite_count": ({}, "白银"),
    "material_read_count": ({1: "黑铁", 5: "青铜", 20: "白银"}, "黑铁"),
}


def tier_for(code: str, threshold) -> str:
    mapping, default = RULES.get(code or "", ({}, "青铜"))
    try:
        t = int(threshold or 0)
    except (TypeError, ValueError):
        return default
    if not mapping:
        return default
    # 取「不超过 t 的最大门槛」对应档位；t 小于最小门槛时用最小档
    keys = sorted(mapping)
    if t <= keys[0]:
        return mapping[keys[0]]
    hit = mapping[keys[0]]
    for k in keys:
        if t >= k:
            hit = mapping[k]
    return hit


def main() -> int:
    apply = "--apply" in sys.argv
    con = sqlite3.connect(DB)
    con.execute("PRAGMA journal_mode=WAL")
    cols = {r[1] for r in con.execute("PRAGMA table_info(achievement)")}
    if "badge_tier" not in cols:
        if not apply:
            print("（dry-run）将新增列 achievement.badge_tier")
        else:
            con.execute("ALTER TABLE achievement ADD COLUMN badge_tier VARCHAR(20)")
            con.commit()
            print("已新增列 achievement.badge_tier")

    rows = con.execute(
        "SELECT achievement_id, name, condition_code, threshold FROM achievement "
        "ORDER BY achievement_id").fetchall()
    dist = {}
    plan = []
    for aid, name, code, th in rows:
        t = tier_for(code, th)
        dist[t] = dist.get(t, 0) + 1
        plan.append((t, aid, name, code, th))
    print("成色分布:", dist)
    for p in plan[:8]:
        print(f"  {p[0]:<3} #{p[1]:<3} {p[2]:<12} {p[3]}={p[4]}")

    if apply:
        with con:
            for t, aid, *_ in plan:
                con.execute("UPDATE achievement SET badge_tier=? WHERE achievement_id=?",
                            (t, aid))
        got = con.execute("SELECT badge_tier, COUNT(*) FROM achievement GROUP BY 1").fetchall()
        print("落库后:", dict(got))
    else:
        print("（dry-run，加 --apply 生效）")
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
