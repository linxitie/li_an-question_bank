# 按题干特征词给行测题分类，并挂到对应知识点（模块7 图谱挂题）
#
# 背景：题名匹配（题干含知识点名）实测只有 4.2%，因为行测题干是题目正文，
# 不会出现「资料分析」这类分类名。改用特征词规则分类。
#
# 用法：
#   python backend/scripts/classify_questions.py            # 预演（打印分布）
#   python backend/scripts/classify_questions.py --commit   # 写 point_id（先备份）
from __future__ import annotations

import argparse
import sqlite3
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "backend" / "data" / "question_bank.db"

# (考点名, 特征词列表)；顺序即优先级，先命中先归类
RULES: list[tuple[str, list[str]]] = [
    # 政治类放最前：题干常出现「支持/加强」等词，若放后面会被「加强削弱」误吞
    ("政治常识", ["习近平", "党的二十大", "全会", "十四五", "党的"]),
    ("图形推理", ["图形", "折叠", "截面", "三视图", "立体图形", "九宫格"]),
    ("语句排序", ["顺序排列", "排序最恰当", "语序最恰当"]),
    ("语句衔接", ["填入文中", "填入横线处最恰当", "衔接最恰当"]),
    ("病句辨析", ["没有语病", "有语病", "语病"]),
    ("逻辑填空", ["填入画横线", "依次填入", "填入横线", "最恰当的一项是"]),
    ("定义判断", ["定义", "属于", "不属于"]),
    ("类比推理", ["关系最为相似", "逻辑关系最为", "类比", "最为类似"]),
    ("真假推理", ["真话", "假话", "只有一人", "只有一个"]),
    ("加强削弱", ["最能削弱", "最能反驳", "最能加强", "最能支持", "削弱了", "加强了"]),
    ("逻辑判断", ["由此可以推出", "可以推出", "推论正确", "如果", "除非", "则以下"]),
    ("主旨概括", ["主要说明", "意在说明", "主旨", "主要观点", "概括最准确", "这段文字"]),
    ("细节判断", ["符合文意", "不符合文意", "与文意相符", "与文意不符"]),
    ("成语辨析", ["成语"]),
    ("实词辨析", ["实词", "词语"]),
    ("资料分析-增长率", ["增长率", "增幅"]),
    ("资料分析-增长量", ["增长量"]),
    ("资料分析-基期量", ["基期", "上年同期"]),
    ("资料分析-比重", ["比重", "占比"]),
    ("资料分析-平均数", ["平均", "人均"]),
    ("资料分析-倍数", ["倍", "翻番"]),
    ("资料分析-综合分析", ["以下说法", "能够从上述资料"]),
    ("工程问题", ["工程", "工作效率"]),
    ("行程问题", ["行程", "速度", "相遇", "追及"]),
    ("利润问题", ["利润", "成本", "售价", "折扣"]),
    ("浓度问题", ["浓度", "溶液"]),
    ("排列组合", ["排列", "组合", "不同的方式", "多少种"]),
    ("概率问题", ["概率"]),
    ("容斥原理", ["至少", "都参加", "既"]),
    ("几何问题", ["面积", "周长", "体积", "半径"]),
    ("等差数列", ["数列", "等差"]),
    ("法律常识", ["法", "条例", "规定", "违法", "犯罪"]),
    ("经济常识", ["经济", "GDP", "通货", "财政", "货币"]),
    ("历史常识", ["历史", "朝代", "古代", "革命"]),
    ("科技常识", ["科技", "航天", "卫星", "生物", "量子"]),
    ("地理常识", ["地理", "气候", "河流", "山脉"]),
    ("公文写作", ["公文", "函", "通报", "请示"]),
    ("时事政治", ["2024年", "2025年", "2023年"]),
]


def classify(text: str) -> str | None:
    for point, kws in RULES:
        for kw in kws:
            if kw in text:
                return point
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", action="store_true")
    args = ap.parse_args()

    conn = sqlite3.connect(str(DB))
    cur = conn.cursor()
    pmap = {n: pid for pid, n in cur.execute("SELECT point_id, point_name FROM knowledge_point WHERE subject_id=1")}
    # 规则里的 "资料分析-增长率" 这类前缀写法映射到已有点
    def resolve(name: str) -> int | None:
        if name in pmap:
            return pmap[name]
        tail = name.split("-")[-1]
        return pmap.get(tail)

    rows = cur.execute("SELECT question_id, question_content FROM question_bank").fetchall()
    plan, dist, miss = [], Counter(), Counter()
    for qid, content in rows:
        name = classify(content or "")
        pid = resolve(name) if name else None
        if name and pid:
            plan.append((qid, pid))
            dist[name] += 1
        else:
            miss[(name or "未归类")] += 1

    print(f"[PLAN] 可分类 {len(plan)} 道（覆盖率 {len(plan)/max(len(rows),1)*100:.1f}%），共扫描 {len(rows)} 道")
    print("[DIST] 前 12 类:")
    for name, n in dist.most_common(12):
        print(f"   {name}: {n}")
    if miss:
        print("[MISS] 未归类:", sum(miss.values()))

    if not args.commit:
        print("[DRY-RUN] 未写库。确认后加 --commit")
        conn.close()
        return 0

    backup = DB.with_suffix(f".db.bak_classify_{datetime.now():%Y%m%d_%H%M%S}")
    dst = sqlite3.connect(str(backup))
    with dst:
        conn.backup(dst)
    dst.close()
    print(f"[BACKUP] {backup}")

    # 注意参数顺序：SET point_id = 考点ID，WHERE question_id = 题目ID
    cur.executemany(
        "UPDATE question_bank SET point_id=? WHERE question_id=?",
        [(pid, qid) for qid, pid in plan],
    )
    conn.commit()
    left = cur.execute("SELECT COUNT(*) FROM question_bank WHERE point_id IS NULL").fetchone()[0]
    print(f"[DONE] 分类挂点 {len(plan)} 道，仍无考点 {left} 道")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())