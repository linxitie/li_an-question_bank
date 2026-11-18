# -*- coding: utf-8 -*-
"""周任务设计分配 Obsidian 知识库 · 构建器 v2（2026-11-15）。

数据来源：
- 只读读取 backend/data/example_db.sqlite 的 weekly_task_* / knowledge_point 表；
- 大纲骨架读取同目录 outline_2025.json（机器可读的三科大纲，含官方来源）。

产出：完整的 Obsidian 子库（默认 D:/Obsidian仓库/周任务设计分配）。

用法：
    python scripts/weekly_vault/build_vault.py --out "D:/Obsidian仓库/周任务设计分配"
    python scripts/weekly_vault/build_vault.py --out ... --check-only   # 只校验已有库
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "backend" / "data" / "example_db.sqlite"
OUTLINE = Path(__file__).resolve().parent / "outline_2025.json"

WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
FENCE = chr(96) * 3
TICK = chr(96)


def load_db():
    conn = sqlite3.connect("file:" + str(DB).replace("\\", "/") + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    def rows(sql, args=()):
        return [dict(r) for r in conn.execute(sql, args)]

    themes = rows("select * from weekly_task_theme order by subject, theme_id")
    templates = rows("select * from weekly_task_template order by subject, template_id")
    plans = rows("select * from weekly_task_plan order by week_no")
    instances = rows("select * from weekly_task_instance order by task_date, instance_id")
    kp = rows("select subject_id, count(*) c from knowledge_point group by subject_id")
    subjects = rows("select subject_id, subject_name from question_subject")
    conn.close()
    for t in instances:
        try:
            t["anchors"] = json.loads(t.get("anchors") or "[]")
        except json.JSONDecodeError:
            t["anchors"] = []
    return {
        "themes": themes,
        "templates": templates,
        "plans": plans,
        "instances": instances,
        "knowledge_points": {r["subject_id"]: r["c"] for r in kp},
        "subjects": {r["subject_id"]: r["subject_name"] for r in subjects},
    }


def load_outline():
    return json.loads(OUTLINE.read_text(encoding="utf-8"))


class Vault:
    def __init__(self, root: Path):
        self.root = root
        self.written = []
        self.files = set()

    def w(self, rel, content):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        # .ps1 必须带 UTF-8 BOM：Windows PowerShell 5.1 默认按 ANSI 读，无 BOM 会把中文注释读成乱码后报语法错
        enc = "utf-8-sig" if rel.endswith(".ps1") else "utf-8"
        p.write_text(content, encoding=enc, newline="\n")
        self.written.append(rel)
        self.files.add(Path(rel).stem)

    def wj(self, rel, data):
        self.w(rel, json.dumps(data, ensure_ascii=False, indent=2))


def fm(**kwargs):
    lines = ["---"]
    for k, val in kwargs.items():
        if isinstance(val, list):
            lines.append(str(k) + ":")
            for item in val:
                lines.append("  - " + str(item))
        elif val is None:
            continue
        else:
            lines.append(str(k) + ": " + str(val))
    lines.append("---")
    return "\n".join(lines) + "\n"


def link(name, alias=None):
    return "[[" + name + "|" + alias + "]]" if alias else "[[" + name + "]]"


def table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for r in rows:
        out.append("| " + " | ".join("" if c is None else str(c) for c in r) + " |")
    return "\n".join(out)


def compute_stats(data):
    themes, templates, plans, instances = data["themes"], data["templates"], data["plans"], data["instances"]
    supply = Counter(t["supply"] for t in templates)
    anchors = defaultdict(set)
    for i in instances:
        for a in i["anchors"]:
            parts = a.split("-")
            if len(parts) >= 3 and parts[2].isdigit():
                anchors[parts[1]].add(int(parts[2]))
    week_themes = {}
    for p in plans:
        week_themes[p["plan_id"]] = [i["theme_id"] for i in instances if i["plan_id"] == p["plan_id"]]
    repeats = 0
    ordered = [p["plan_id"] for p in plans]
    for a, b in zip(ordered, ordered[1:]):
        repeats += len(set(week_themes.get(a, [])) & set(week_themes.get(b, [])))
    no_point = [t for t in themes if not (t.get("point_count") or 0)]
    return {
        "supply": dict(supply),
        "anchors": {k: sorted(val) for k, val in anchors.items()},
        "adjacent_week_repeats": repeats,
        "themes_without_points": len(no_point),
        "knowledge_points": data["knowledge_points"],
        "subjects": data["subjects"],
    }

def gen_home(v, data, outline, st):
    pending = [p for p in data["plans"] if p["status"] == "待审批"]
    pending_days = sorted({i["task_date"] for i in data["instances"] if i["status"] == "待周批"})
    subj = st["knowledge_points"]
    body = fm(type="index", version=1, build="2026-11-15", builder="scripts/weekly_vault/build_vault.py")
    body += """
# 周任务设计分配 · 知识库总入口

> 以历年公安联考大纲为骨架，回答三件事：**练什么、怎么发、谁来批**。
> 本库是设计态与审批态，不是学生运行时；任何写库都走「编译产出 → 发布包 → 人工审批」。

> [!approval] 今日审批铃
> 待审批周计划：**PENDING_PLANS** 个（最早：FIRST_PLAN）
> 待周批日批：**PENDING_DAYS** 天（最早：FIRST_DAY）
> 入口：TASK_BAR　供给可试点：**PILOT** / 165 个模板

## 八个数字

| 指标 | 值 |
|---|---|
| 科目权重 | 行测 40% / 申论 30% / 公专 30% |
| 知识域 | 16（行测 8 + 申论 5 + 公专 3；按大纲应补警务技能 → 17） |
| 周任务主题 | THEMES |
| 任务模板 | TEMPLATES |
| 周计划 | PLANS 周 |
| 任务实例 | INSTANCES |
| 题库知识点 | 行测 KP1 / 申论 KP2 / 公专 KP3 |
| 锚点（任务挂点） | 行测 A1 / 申论 A2 / 公专 A3 |

## 怎么用（按角色）

| 角色 | 第一站 | 用途 |
|---|---|---|
| 管理者 | LINK_MANAGER | 周批、日批、发布、回滚 |
| 教研 | LINK_TEACH | 主题供给、模板补题、难度校准 |
| 合作方 | LINK_PARTNER | 目录、构建器、维护边界、验收 |
| 学生 | LINK_STUDENT | 今天做什么、多少分钟、多少金币 |
| 每日审批 | LINK_TASK_BAR | 待批日批与一键跳转 |

## 目录

- 02-大纲框架：大纲 → 知识域 → 主题 → 模板 的四层映射与官方依据
- 03-任务库：主题卡 + 模板卡（每个主题 3 个模板：基础/强化/冲刺）
- 04-周计划：12 周节奏（基础 1—4 / 强化 5—8 / 冲刺 9—12）
- 05-日批：每周 7 天 × 12 周的审批单元
- 06-接口契约：系统对接（已实现 / 待实现分开写）
- 07-编译产出：机器可读的节点、边、主题、模板、实例、发布包
- 08-视图：Dataview 看板 + Canvas
- 09-治理：RACI、每日审批 SOP、发布回滚、合作方维护
- 10-模板：新建主题/模板/周计划/日批/提案/变更的卡模板
- 11-变更日志：每次构建的差异

## 构建信息

- 构建器：scripts/weekly_vault/build_vault.py
- 大纲：scripts/weekly_vault/outline_2025.json（vVER）
- 生成文件数：见 LINK_CHECK / LINK_HEALTH
"""
    body = (body.replace("PENDING_PLANS", str(len(pending)))
                .replace("FIRST_PLAN", pending[0]["plan_id"] if pending else "无")
                .replace("PENDING_DAYS", str(len(pending_days)))
                .replace("FIRST_DAY", pending_days[0] if pending_days else "无")
                .replace("LINK_TASK_BAR", link("00-今日任务栏"))
                .replace("TASK_BAR", link("00-今日任务栏"))
                .replace("PILOT", str(st["supply"].get("可试点", 0)))
                .replace("THEMES", str(len(data["themes"])))
                .replace("TEMPLATES", str(len(data["templates"])))
                .replace("PLANS", str(len(data["plans"])))
                .replace("INSTANCES", str(len(data["instances"])))
                .replace("KP1", str(subj.get(1, 0)))
                .replace("KP2", str(subj.get(2, 0)))
                .replace("KP3", str(subj.get(3, 0)))
                .replace("A1", str(len(st["anchors"].get("行测", []))))
                .replace("A2", str(len(st["anchors"].get("申论", []))))
                .replace("A3", str(len(st["anchors"].get("公专", []))))
                .replace("LINK_MANAGER", link("01-管理者入口"))
                .replace("LINK_TEACH", link("02-教研入口"))
                .replace("LINK_PARTNER", link("03-合作方入口"))
                .replace("LINK_STUDENT", link("04-学生视角"))
                .replace("LINK_CHECK", link("08-校验"))
                .replace("LINK_HEALTH", link("09-健康度"))
                .replace("VER", outline["version"]))
    v.w("首页.md", body)


def gen_inbox(v):
    items = {
        "00-收件箱/README.md": "收件箱规则：AI 只写这里；人审后进入正式区；退役进 99-归档，不删除。",
        "00-收件箱/01-任务提案.md": "任务提案：一句话目标 → 挂哪个大纲模块 → 形态 A/B/C → 题量/难度/时长 → 需要什么题。",
        "00-收件箱/02-大纲变更.md": "大纲变更：变更来源（官方文件/年份）→ 影响模块 → 影响主题清单 → 需要换哪些模板。",
        "00-收件箱/03-缺陷报告.md": "缺陷：锚点打不开 / 主题无考点 / 相邻周原样重复 / 时长超预算。",
        "00-收件箱/04-变更申请.md": "变更申请：改哪个正式卡 → 为什么 → 影响面 → 回滚方式。",
    }
    for name, text in items.items():
        v.w(name, fm(type="inbox", status="待处理") + "\n# " + Path(name).stem + "\n\n" + text + "\n")

    guides = {
        "01-入口/01-管理者入口.md": "管理者：周批与日批、发布与回滚。关注「12 周节奏是否均衡」「待批是否积压」「试点模板够不够」。",
        "01-入口/02-教研入口.md": "教研：主题供给、模板补题、难度校准。先看 05-供给看板，再看「无考点主题」清单。",
        "01-入口/03-合作方入口.md": "合作方：目录、构建器、维护边界、验收。先读 09-治理/合作方维护手册，再跑 build_vault.py。",
        "01-入口/04-学生视角.md": "学生：每天 2—3 个任务，40—110 分钟，20—30 金币。学生看不到本库，只看系统「今日任务」。",
        "01-入口/05-快速上手.md": "10 分钟上手：首页 → 今日任务栏 → 日批卡 → 改 status → 填审批人。",
        "01-入口/06-术语.md": "主题=一周内可教可练可审的颗粒；模板=任务 DNA（题量/难度/时长/金币）；实例=某天某人的一件事；日批=一天的审批单元。",
        "01-入口/07-边界.md": "本库不写数据库、不做调度、不算金币；一切写库走发布包 + 人工审批。",
    }
    for name, text in guides.items():
        v.w(name, fm(type="guide", version=1) + "\n# " + Path(name).stem + "\n\n" + text + "\n")


def dataview(query):
    return FENCE + "dataview\n" + query.strip() + "\n" + FENCE


def gen_task_bar(v, data, st):
    plans = data["plans"]
    static_rows = [[p["plan_id"], p["week_no"], p["stage"], p["status"], p["task_count"], p["minutes"], p["coins"]] for p in plans]
    content = fm(type="index", updated="2026-11-15")
    content += """
# 今日任务栏（每日审批）

> [!tip] 每天 3 分钟
> 打开本页 → 点最早待批日批 → 核对三科配比 / 难度 / 时长 → 把 status 改成 已批准 → 填审批人。

## 待审批周计划（Dataview）

""" + dataview("""
TABLE week_no AS "周次", stage AS "阶段", task_count AS "任务数", minutes AS "分钟", coins AS "金币"
FROM "04-周计划"
WHERE contains(status, "待审批")
SORT week_no ASC
""") + """

## 待周批日批（Dataview）

""" + dataview("""
TABLE task_date AS "日期", weekday AS "星期", subject_mix AS "三科配比", total_minutes AS "分钟", total_coins AS "金币"
FROM "05-日批"
WHERE contains(status, "待周批")
SORT task_date ASC
LIMIT 14
""") + """

## 无插件降级：周计划静态索引（构建时生成）

""" + table(["周计划", "周次", "阶段", "状态", "任务数", "分钟", "金币"], static_rows) + """

## 审批记录

- 审批人：______　　审批时间：______
- 结论：已批准 / 退回（原因：______）
- 备注：改动点写进 11-变更日志。
"""
    v.w("01-入口/00-今日任务栏.md", content)

def outline_module_for(outline, subject, domain):
    for s in outline["subjects"]:
        if s["code"] != subject:
            continue
        for m in s["modules"]:
            if m["code"] == domain or domain in m["code"] or m["code"] in domain:
                return m
        for m in s["modules"]:
            for area in m.get("areas", []) or []:
                if area["name"] == domain or domain in area["name"] or area["name"] in domain:
                    return {"code": m["code"] + "/" + area["name"], "points": area.get("points", [])}
    return None


def gen_outline_pages(v, outline, data, st):
    subj_rows = [[s["code"], str(round(s["weight"] * 100)) + "%", s["exam"].get("total_questions", "-"), s["exam"].get("mode", "")] for s in outline["subjects"]]
    v.w("02-大纲框架/00-总览.md", fm(type="outline", version=outline["version"]) + """
# 大纲框架总览

""" + table(["科目", "权重", "题量", "形式"], subj_rows) + """

## 四层模型

""" + FENCE + """text
科目（3） → 知识域（16） → 周任务主题（55） → 任务模板（165） → 任务实例（216）
""" + FENCE + """

## 官方依据

""" + "\n".join("- [" + s["name"] + "](" + s["url"] + ") ｜ " + s["used_for"] for s in outline["sources"]) + """

## 与题库实体的对应

"""+ table(["知识库层", "系统表", "说明"], [
        ["知识域/考点", "knowledge_point / sub_categories", "大纲考点落到题库知识点"],
        ["自生长状态", "KgUserNodeState / KgUserEdge", "掌握度、热度、边权"],
        ["主题", "weekly_task_theme", "一周内可教可练可审的颗粒"],
        ["模板", "weekly_task_template", "任务 DNA"],
        ["周计划", "weekly_task_plan", "12 周节奏"],
        ["实例", "weekly_task_instance", "某天某人的一件事"],
        ["进度/领币", "study_goal / user_task_progress / coin_record", "复用既有奖励链路"],
    ]))

    for idx, s in enumerate(outline["subjects"], start=1):
        code = s["code"]
        lines = [fm(type="outline", subject=code, version=outline["version"]), "# " + code + " 大纲映射", ""]
        lines.append("> 权重 " + str(round(s["weight"] * 100)) + "%；" + str(s["exam"].get("note", s["exam"].get("mode", ""))))
        lines.append("")
        rows = []
        for m in s["modules"]:
            rows.append([
                m["code"],
                m.get("questions", "-"),
                (str(round(m["weight_share"] * 100, 1)) + "%") if m.get("weight_share") else "—",
                m.get("note", ""),
            ])
        lines.append(table(["模块 / 方面", "题量", "模块内占比", "说明"], rows))
        lines.append("")
        lines.append("## 考点清单")
        lines.append("")
        for m in s["modules"]:
            lines.append("### " + m["code"])
            if m.get("points"):
                lines.append("- 考点：" + "、".join(m["points"]))
            for area in m.get("areas", []) or []:
                lines.append("- **" + area["name"] + "**：" + "、".join(area["points"]))
            lines.append("")
        lines.append("## 对应周任务主题")
        lines.append("")
        themed = [t for t in data["themes"] if t["subject"] == code]
        if themed:
            lines.append(table(["主题", "域", "族", "挂点数", "模板数"], [
                [link(t["theme_id"], t["title"]), t["domain"], t["family"], t["point_count"],
                 len([x for x in data["templates"] if x["theme_id"] == t["theme_id"]])]
                for t in themed
            ]))
            missing = [m["code"] for m in s["modules"] if not any(
                (t["domain"] == m["code"]) or (t["domain"] in m["code"]) for t in themed)]
            if missing:
                lines.append("")
                lines.append("> [!warning] 大纲模块无对应主题：" + "、".join(missing))
        else:
            lines.append("（该科目暂无主题卡）")
        v.w("02-大纲框架/%02d-%s大纲映射.md" % (idx, code), "\n".join(lines))

    q = outline["weekly_quota"]
    v.w("02-大纲框架/04-三科配比与权重.md", fm(type="outline") + """
# 三科配比与权重

## 考试权重（官方口径）

行测 40% / 申论 30% / 公专 30%。

""" + table(["科目", "任务数/周", "分钟预算/周"], [
        ["行测", q["by_subject"]["行测"], q["minutes_budget"]["行测"]],
        ["申论", q["by_subject"]["申论"], q["minutes_budget"]["申论"]],
        ["公专", q["by_subject"]["公专"], q["minutes_budget"]["公专"]],
        ["合计", sum(q["by_subject"].values()), sum(q["minutes_budget"].values())],
    ]) + """

- 每日任务数：DAILY_TASKS
- 阶段微调：基础期行测 +15%、申论 −10%；冲刺期行测 +10%、申论 +5%、公专 −5%。
- 理由：申论单篇 35—50 分钟，任务数少但分钟数要够；公专题型短平快（10—18 题 / 20—30 分钟），靠频次保覆盖。
- 记录：现库按「行测 7 / 申论 4 / 公专 7」发任务，分钟比约 34/32/34，偏离官方 40/30/30；
  本版按**时长**对齐，任务数调到 8/3/7（合计 18 不变）。落地方式见 06-接口契约/01-查询接口.md。
""".replace("DAILY_TASKS", "、".join(str(x) for x in q["daily_tasks"])))

    rows = [[t["theme_id"], t["title"], t["subject"], t["domain"], t["family"],
             len([x for x in data["templates"] if x["theme_id"] == t["theme_id"]]), t["point_count"]]
            for t in data["themes"]]
    v.w("02-大纲框架/05-任务主题映射总表.md", fm(type="outline") + "\n# 任务主题映射总表（" + str(len(rows)) + " 个）\n\n" +
        table(["主题编号", "标题", "科目", "知识域", "族", "模板数", "挂点数"], rows) + "\n")

    a = st["anchors"]
    def rng(k):
        vv = a.get(k) or []
        return (str(vv[0]) + "—" + str(vv[-1])) if vv else "-"
    v.w("02-大纲框架/06-考点锚点映射.md", fm(type="outline") + """
# 考点锚点映射（知-科目-序号 ↔ 题库知识点）

## 现状

""" + table(["科目", "锚点序号范围", "锚点个数", "题库知识点", "待建/待映射"], [
        ["行测", rng("行测"), len(a.get("行测", [])), st["knowledge_points"].get(1, 0), max(0, len(a.get("行测", [])) - st["knowledge_points"].get(1, 0))],
        ["申论", rng("申论"), len(a.get("申论", [])), st["knowledge_points"].get(2, 0), max(0, len(a.get("申论", [])) - st["knowledge_points"].get(2, 0))],
        ["公专", rng("公专"), len(a.get("公专", [])), st["knowledge_points"].get(3, 0), max(0, len(a.get("公专", [])) - st["knowledge_points"].get(3, 0))],
    ]) + """

## 规则

1. 锚点编号 知-<科目>-<四位序号> 是**任务层编号**，不等于 knowledge_point.point_id；
2. 映射表落 07-编译产出/05-锚点映射.json，系统导入时按映射把 anchors 换成 point_id 数组；
3. 没有对应知识点的锚点进 00-收件箱/03-缺陷报告：不阻断任务，但阻断「考点溯源」统计。
""")

    v.w("02-大纲框架/07-大纲变更流程.md", fm(type="process") + """
# 大纲变更流程

1. 官方大纲更新 → 写 00-收件箱/02-大纲变更.md（来源、年份、变更条目）；
2. 更新 scripts/weekly_vault/outline_2025.json 与版本号（2025.1 → 2026.1）；
3. 跑 build_vault.py 重新生成，对比 07-编译产出/差异.json 看受影响主题；
4. 人工评审 → 改主题/模板 → 新发布包 → 系统导入；
5. 旧版本进 99-归档，不删除。
""")

def gen_library(v, data, outline):
    themes = data["themes"]
    templates = data["templates"]
    by_theme = {}
    for t in templates:
        by_theme.setdefault(t["theme_id"], []).append(t)
    inst_by_theme = {}
    for i in data["instances"]:
        inst_by_theme.setdefault(i["theme_id"], []).append(i)

    v.w("03-任务库/00-总览.md", fm(type="index") + """
# 任务库总览

- 主题：" + str(len(themes)) + " 个（行测 / 申论 / 公专），每个主题 3 个模板（A 基础 / B 强化 / C 冲刺）。
- 模板：" + str(len(templates)) + " 个；供给分 可试点 / 待补题，待补题不阻断计划、阻断发布。
- 命名：主题 主题-<科目>-<域简称>-<序号>；模板 模板-<科目>-<域>-<序号>-<形态名>。
""" + """

""" + table(["科目", "主题数", "模板数", "可试点"], [
        [s, str(len([t for t in themes if t["subject"] == s])),
         str(len([t for t in templates if t["subject"] == s])),
         str(len([t for t in templates if t["subject"] == s and t["supply"] == "可试点"]))]
        for s in ("行测", "申论", "公专")
    ]))

    for t in themes:
        mid = t["theme_id"]
        mod = outline_module_for(outline, t["subject"], t["domain"])
        anchors = sorted({a for i in inst_by_theme.get(mid, []) for a in i["anchors"]})
        tpls = by_theme.get(mid, [])
        lines = [fm(type="theme", theme_id=mid, title=t["title"], subject=t["subject"], domain=t["domain"],
                    family=t["family"], anchor_count=t["anchor_count"], point_count=t["point_count"],
                    status="正式", version=1),
                 "# " + t["title"], ""]
        lines.append("## 定位")
        lines.append("")
        lines.append("- 科目：" + t["subject"] + "　知识域：" + t["domain"] + "　族：" + t["family"])
        if mod:
            lines.append("- 大纲条目：" + mod.get("code", "") + (("　考点：" + "、".join(mod.get("points", [])[:8])) if mod.get("points") else ""))
        lines.append("- 颗粒度：一周内可教、可练、可审；不复制题目内容。")
        lines.append("")
        lines.append("## 任务模板（" + str(len(tpls)) + "）")
        lines.append("")
        lines.append(table(["模板", "形态", "难度", "题量", "分钟", "金币", "供给"],
                           [[link(x["template_id"], x["title"]), x["form"], x["difficulty"], x["qty"], x["minutes"], x["coins"], x["supply"]] for x in tpls]))
        lines.append("")
        lines.append("## 锚点（任务挂点）")
        lines.append("")
        if anchors:
            lines.append("、".join(TICK + a + TICK for a in anchors))
        else:
            lines.append("> [!warning] 该主题暂无锚点：任务可做，但无法溯源到考点。处理见 [[06-考点锚点映射]]。")
        if not (t["point_count"] or 0):
            lines.append("")
            lines.append("> [!caution] point_count = 0：主题卡没填考点数，健康度会把它计入「无考点主题」。")
        lines.append("")
        lines.append("## 关联")
        lines.append("")
        lines.append("- [[05-任务主题映射总表]]　[[04-三科配比与权重]]　[[00-总览]]")
        v.w("03-任务库/主题/" + mid + ".md", "\n".join(lines))

    for x in templates:
        lines = [fm(type="template", template_id=x["template_id"], theme_id=x["theme_id"], title=x["title"],
                    subject=x["subject"], domain=x["domain"], form=x["form"], difficulty=x["difficulty"],
                    qty=x["qty"], unit=x.get("unit") or "题", minutes=x["minutes"], coins=x["coins"],
                    supply=x["supply"], version=1),
                 "# " + x["title"], ""]
        lines.append("## 任务 DNA")
        lines.append("")
        lines.append(table(["项", "值"], [
            ["所属主题", link(x["theme_id"])],
            ["科目 / 域", x["subject"] + " / " + str(x["domain"])],
            ["形态", x["form"] + "（A 基础精练 / B 限时专项 / C 错题回炉）"],
            ["难度", x["difficulty"]],
            ["题量", str(x["qty"]) + " " + (x.get("unit") or "题")],
            ["预计时长", str(x["minutes"]) + " 分钟"],
            ["金币", x["coins"]],
            ["供给", x["supply"]],
        ]))
        lines.append("")
        lines.append("## 发布校验清单")
        lines.append("")
        lines.append("- [ ] 题量够：" + str(x["qty"]) + " 题已在题库对齐知识点")
        lines.append("- [ ] 难度与阶段匹配（基础 1—2 / 强化 2—3 / 冲刺 3—4）")
        lines.append("- [ ] 时长实测与 " + str(x["minutes"]) + " 分钟偏差 ≤ 15%")
        lines.append("- [ ] 锚点可映射到 knowledge_point")
        lines.append("- [ ] supply 改为 可试点 后才进发布包")
        lines.append("")
        lines.append("## 关联")
        lines.append("")
        lines.append("- " + link(x["theme_id"]) + "　[[00-总览]]　[[06-供给看板]]")
        v.w("03-任务库/模板/" + x["template_id"] + ".md", "\n".join(lines))


def week_of_plan(data, plan_id):
    return [i for i in data["instances"] if i["plan_id"] == plan_id]


def subject_mix(items):
    c = Counter(i["subject"] for i in items)
    return "·".join(k + str(c[k]) for k in ("行测", "申论", "公专") if c[k])


def gen_weeks(v, data, outline):
    for p in data["plans"]:
        items = week_of_plan(data, p["plan_id"])
        by_subject = Counter(i["subject"] for i in items)
        lines = [fm(type="plan", plan_id=p["plan_id"], week_no=p["week_no"], week_key=p["week_key"],
                    title=p["title"], stage=p["stage"], start_date=p["start_date"], end_date=p["end_date"],
                    status=p["status"], task_count=p["task_count"], minutes=p["minutes"], coins=p["coins"], version=1),
                 "# " + p["title"], ""]
        lines.append("## 周信息")
        lines.append("")
        lines.append(table(["项", "值"], [
            ["周次", str(p["week_no"]) + "（" + str(p["week_key"]) + "）"],
            ["阶段", p["stage"]],
            ["日期", str(p["start_date"]) + " → " + str(p["end_date"])],
            ["任务数 / 分钟 / 金币", str(p["task_count"]) + " / " + str(p["minutes"]) + " / " + str(p["coins"])],
            ["状态", p["status"]],
        ]))
        lines.append("")
        lines.append("## 三科配比")
        lines.append("")
        lines.append(table(["科目", "任务数", "分钟", "金币"], [
            [s, by_subject.get(s, 0), sum(i["minutes"] or 0 for i in items if i["subject"] == s), sum(i["coins"] or 0 for i in items if i["subject"] == s)]
            for s in ("行测", "申论", "公专")
        ]))
        lines.append("")
        lines.append("## 每日任务")
        lines.append("")
        lines.append(table(["日期", "星期", "任务数", "分钟", "三科配比", "日批卡"],
                           [[d, WEEKDAYS[datetime.strptime(d, "%Y-%m-%d").weekday()],
                             len([i for i in items if i["task_date"] == d]),
                             sum(i["minutes"] or 0 for i in items if i["task_date"] == d),
                             subject_mix([i for i in items if i["task_date"] == d]),
                             link(day_card_name(p["week_no"], d))] for d in sorted({i["task_date"] for i in items})]))
        lines.append("")
        lines.append("## 审批")
        lines.append("")
        lines.append("- [ ] 三科配比符合 40/30/30（按分钟）")
        lines.append("- [ ] 难度梯度符合阶段（" + p["stage"] + "）")
        lines.append("- [ ] 与上周不出现原样重复主题")
        lines.append("- [ ] 供给够：可试点模板 ≥ 本周任务数")
        lines.append("")
        lines.append("审批人：______　日期：______　结论：已批准 / 退回（______）")
        v.w("04-周计划/" + p["plan_id"] + ".md", "\n".join(lines))

    rows = [[p["plan_id"], p["week_no"], p["week_key"], p["stage"], p["start_date"], p["end_date"], p["status"], p["task_count"], p["minutes"], p["coins"]] for p in data["plans"]]
    v.w("04-周计划/00-总览.md", fm(type="index") + "\n# 周计划总览（12 周）\n\n" +
        table(["周计划", "周次", "周键", "阶段", "起", "止", "状态", "任务数", "分钟", "金币"], rows) + "\n")


def day_card_name(week_no, task_date):
    wd = WEEKDAYS[datetime.strptime(task_date, "%Y-%m-%d").weekday()]
    return "第%02d周-%s-%s" % (week_no, wd, task_date)


def gen_batches(v, data):
    plans = {p["plan_id"]: p for p in data["plans"]}
    by_date = {}
    for i in data["instances"]:
        by_date.setdefault(i["task_date"], []).append(i)
    for date, items in sorted(by_date.items()):
        plan_id = items[0]["plan_id"]
        p = plans[plan_id]
        wd = WEEKDAYS[datetime.strptime(date, "%Y-%m-%d").weekday()]
        name = day_card_name(p["week_no"], date)
        status = "待周批" if any(i["status"] == "待周批" for i in items) else ("未到窗口" if any(i["status"] == "未到窗口" for i in items) else "待发布")
        lines = [fm(type="batch", plan_id=plan_id, week_no=p["week_no"], task_date=date, weekday=wd,
                    status=status, subject_mix=subject_mix(items), task_count=len(items),
                    total_minutes=sum(i["minutes"] or 0 for i in items),
                    total_coins=sum(i["coins"] or 0 for i in items), version=1),
                 "# " + name, ""]
        lines.append("## 今日任务（" + str(len(items)) + " 个 / " + str(sum(i["minutes"] or 0 for i in items)) + " 分钟 / " + str(sum(i["coins"] or 0 for i in items)) + " 金币）")
        lines.append("")
        lines.append(table(["实例", "科目", "主题", "模板", "题量", "分钟", "金币", "供给", "状态"],
                           [[i["instance_id"], i["subject"], link(i["theme_id"], i["title"]), link(i["template_id"]),
                             i["qty"], i["minutes"], i["coins"], i["supply"], i["status"]] for i in items]))
        lines.append("")
        lines.append("## 三科配比")
        lines.append("")
        lines.append(table(["科目", "任务数", "分钟"],
                           [[s, sum(1 for i in items if i["subject"] == s), sum(i["minutes"] or 0 for i in items if i["subject"] == s)] for s in ("行测", "申论", "公专")]))
        lines.append("")
        lines.append("## 锚点")
        lines.append("")
        anchors = sorted({a for i in items for a in i["anchors"]})
        lines.append("、".join(TICK + a + TICK for a in anchors) if anchors else "（本日任务无锚点）")
        lines.append("")
        lines.append("## 审批")
        lines.append("")
        lines.append("- [ ] 三科配比与周计划一致")
        lines.append("- [ ] 时长 " + str(sum(i["minutes"] or 0 for i in items)) + " 分钟在 40—110 区间")
        lines.append("- [ ] 供给全部为 可试点（否则不能发布）")
        lines.append("")
        lines.append("审批人：______　时间：______　结论：已批准 / 退回")
        v.w("05-日批/" + name + ".md", "\n".join(lines))

    rows = []
    for date, items in sorted(by_date.items()):
        p = plans[items[0]["plan_id"]]
        rows.append([link(day_card_name(p["week_no"], date)), date, WEEKDAYS[datetime.strptime(date, "%Y-%m-%d").weekday()],
                     len(items), sum(i["minutes"] or 0 for i in items), subject_mix(items)])
    v.w("05-日批/00-总览.md", fm(type="index") + "\n# 日批总览（" + str(len(rows)) + " 天）\n\n" +
        table(["日批卡", "日期", "星期", "任务数", "分钟", "三科配比"], rows) + "\n")

def gen_contracts(v, data):
    v.w("06-接口契约/00-总览.md", fm(type="contract") + """
# 接口契约总览

## 已实现（本系统实测存在）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | /api/tasks/weekly/pool | 本周周任务池（含置顶槽位） |
| POST | /api/tasks/weekly/pool/pin | 管理员设置/取消置顶槽位 1..3 |
| POST | /api/tasks/weekly/recalc | 重算某用户周任务进度 |
| POST | /api/tasks/weekly/expire | 过期未完成任务置为失效 |
| GET | /api/tasks/overview | 任务中心总览（含周任务卡） |

## 待实现（本库设计目标）

| 命名空间 | 用途 | 优先级 |
|---|---|---|
| /api/v1/weekly-tasks/catalog/* | 只读目录：主题、模板、周计划、日批 | P1 |
| /api/v1/weekly-tasks/plans/* | 周计划与日批查询 | P1 |
| /api/v1/weekly-tasks/my/* | 学生：今日、进度、领币 | P1 |
| /api/v1/weekly-tasks/admin/* | 发布、回滚、发布包导入 | P2 |
| /api/v1/weekly-tasks/events/* | SSE / 轮询 | P2 |

> 现状：12 周 × 18 任务 = 216 条实例只在 weekly_task_instance 里，**没有学生侧读取接口**；
> 学生端现在只能看到 weekly_task_pool 的置顶任务。这是本轮设计要补的第一块。
""")

    v.w("06-接口契约/01-查询接口.md", fm(type="contract") + """
# 查询接口

## 目录（只读）

""" + FENCE + """http
GET /api/v1/weekly-tasks/catalog/themes?subject=行测&domain=判断推理
GET /api/v1/weekly-tasks/catalog/templates?theme_id=主题-行测-判断-01
GET /api/v1/weekly-tasks/catalog/plans?status=已发布
GET /api/v1/weekly-tasks/catalog/batches?from=2026-11-09&to=2026-11-15
""" + FENCE + """

## 学生今日

""" + FENCE + """http
GET /api/v1/weekly-tasks/my/today?date=2026-11-09
=> {
  "date": "2026-11-09",
  "week": "周计划-第01周",
  "items": [
    {"instance_id": "周任-第01周-01", "subject": "行测", "title": "数字推理·基础精练",
     "minutes": 25, "coins": 10, "status": "未开始", "supply": "可试点",
     "theme_id": "主题-行测-数量-01", "template_id": "模板-行测-数量-01-基础精练"}
  ],
  "totals": {"tasks": 3, "minutes": 85, "coins": 30}
}
""" + FENCE + """

## 性能口径

- my/today：18 条实例一次查完，禁止 N+1；P95 不超过 120 ms。
- catalog/plans：12 周一次返回；P95 不超过 200 ms。
- 列表用 cursor（after），不做深翻页。
""")

    v.w("06-接口契约/02-学生动作.md", fm(type="contract") + """
# 学生动作

""" + FENCE + """http
POST /api/v1/weekly-tasks/my/{instance_id}/start
POST /api/v1/weekly-tasks/my/{instance_id}/progress   { "answered": 5, "correct": 4 }
POST /api/v1/weekly-tasks/my/{instance_id}/submit     { "answered": 12, "correct": 9 }
POST /api/v1/weekly-tasks/my/{instance_id}/claim
""" + FENCE + """

状态机：

""" + FENCE + """text
未开始 → 进行中 → 已提交 → 已领币
                    ↘ 已失效（过期）
""" + FENCE + """

规则：

1. 写接口必须带 Idempotency-Key（重复提交返回同一结果）；
2. 领币幂等：coin_record(source_type=TASK, related_id=instance_id) 只允许一条；
3. 与 study_goal 的对接：实例完成写一条 study_goal(source_type=WEEKLY_TASK, source_ref=instance_id)，复用自动领币。
""")

    v.w("06-接口契约/03-金币联动.md", fm(type="contract") + """
# 金币联动

- 唯一发币入口：app/api/v1/reward/contract.py 的 grant_coins（跨域写必须走契约）。
- source_type 固定 TASK，related_id 用实例主键的可哈希形式（如 wt:+实例编号）。
- 金币由模板 coins 决定，周计划可整体加成（阶段系数：基础 1.0 / 强化 1.15 / 冲刺 1.25）。
- 领币前置：status=已提交 且 答题数 不低于 模板题量 × 80%。
""")

    v.w("06-接口契约/04-发布与回滚.md", fm(type="contract") + """
# 发布与回滚

## 发布包（本库 07-编译产出/07-发布包）

""" + FENCE + """text
清单.json      版本、生成时间、条目数、校验哈希
主题.jsonl     55 条
模板.jsonl     165 条
周计划.jsonl   12 条
实例.jsonl     216 条
锚点映射.json  知-科目-序号 → point_id
""" + FENCE + """

## 发布流程

1. 管理员在库内把周计划/日批改成 已批准；
2. 跑构建器 build_vault.py --publish 生成发布包；
3. 导入前 sqlite3.backup()（R10：禁止 copy2）；
4. dry-run 只校验不写库；apply 在事务内 upsert；
5. 失败整包回滚，记 11-变更日志。

## 回滚

- 保留上一版发布包哈希；回滚 = 重新 apply 上一版 + 关掉本周批次。
- 已发放金币不回滚（避免负余额），只回滚任务可见性。
""")

    v.w("06-接口契约/05-错误码.md", fm(type="contract") + """
# 错误码

| code | HTTP | 含义 | 处理 |
|---|---|---|---|
| WEEKLY_TASK_NOT_OPEN | 409 | 未到窗口 | 提示到日期再开 |
| WEEKLY_TASK_SUPPLY | 409 | 供给=待补题 | 提示任务暂不可用 |
| IDEMPOTENCY_CONFLICT | 409 | 幂等键复用但载荷不同 | 客户端重取 |
| TASK_STATE_INVALID | 409 | 状态机不允许 | 刷新后重试 |
| CLAIM_ALREADY | 409 | 已领过 | 返回原结果 |
| FORBIDDEN_ROLE | 403 | 学生调 admin 接口 | 前端隐藏入口 |
""")

    v.w("06-接口契约/06-数据模型.md", fm(type="contract") + """
# 数据模型

## 已存在（本系统实测）

""" + table(["表", "作用", "主键"], [
        ["weekly_task_theme", "任务主题", "theme_id"],
        ["weekly_task_template", "任务模板", "template_id"],
        ["weekly_task_plan", "周计划", "plan_id"],
        ["weekly_task_instance", "任务实例", "instance_id"],
        ["weekly_task_pool", "周任务置顶池", "week_key + slot"],
    ]) + """

## 待增（P2）

- weekly_task_progress（user_id, instance_id, status, answered, correct, started_at, submitted_at, claimed_at）
- weekly_task_outbox（事件，SSE 通知）
- study_goal.source_type / source_ref（可空列，只增不改）
""")

    v.w("06-接口契约/07-兼容与迁移.md", fm(type="contract") + """
# 兼容与迁移

- 旧 /api/plan/today、/api/plan/task/{goal_id}/toggle|claim 保持可用（2026-11-15 已做自动领币）。
- 新周任务完成 → 生成 study_goal 一条（可空 source_type/source_ref），复用既有金币链路，不另起账本。
- 表只增不改：不删列、不改既有枚举；新字段可空。
- 迁移顺序：建表 → 导入目录 → 灰度一个班 → 全量。
""")

    v.w("06-接口契约/08-联调与验收.md", fm(type="contract") + """
# 联调与验收

| 场景 | 期望 |
|---|---|
| 学生今日 | 只返回当天 2—3 条，分钟合计 40—110 |
| 供给不足 | 待补题模板不出现在今日任务 |
| 重复领币 | 第二次返回 409 + 原结果，不重复加币 |
| 过期 | 未完成实例转 已失效，不补发 |
| 审批未通过 | 未批准批次对所有学生不可见 |
""")

def canvas(nodes, edges):
    return {"nodes": nodes, "edges": edges}


def tnode(i, text, x, y, w=260, h=120, color=None):
    n = {"id": "n" + str(i), "type": "text", "text": text, "x": x, "y": y, "width": w, "height": h}
    if color:
        n["color"] = color
    return n


def edge(a, b, label=None):
    e = {"id": "e-" + a["id"] + "-" + b["id"], "fromNode": a["id"], "toNode": b["id"]}
    if label:
        e["label"] = label
    return e


def gen_views(v, data, outline, st):
    v.w("08-视图/00-总览.md", fm(type="view") + """
# 视图总览

- 8 张 Dataview 看板：总览、今日审批、周计划、日批、覆盖矩阵、供给、审批时效、健康度。
- 5 张 Canvas：任务图谱全景、任务锚点、十二周节奏、审批闭环、域覆盖。
- 没有装 Dataview 也能用：每张看板底部都有构建时生成的静态表。

> 注意：Dataview 需要社区插件；本库不强制安装，静态表就是兜底。
""")

    dashboards = {
        "01-总览看板": dataview("""
TABLE length(rows) AS "数量"
FROM "03-任务库/主题" OR "03-任务库/模板" OR "04-周计划" OR "05-日批"
GROUP BY type
""") + "\n\n" + table(["层", "数量"], [
            ["主题", len(data["themes"])], ["模板", len(data["templates"])],
            ["周计划", len(data["plans"])], ["日批", len({i["task_date"] for i in data["instances"]})],
            ["实例", len(data["instances"])]]),
        "02-今日审批看板": dataview("""
TABLE task_date AS "日期", subject_mix AS "配比", total_minutes AS "分钟", status AS "状态"
FROM "05-日批"
WHERE contains(status, "待周批") OR contains(status, "待发布")
SORT task_date ASC
LIMIT 20
"""),
        "03-周计划看板": dataview("""
TABLE week_no AS "周次", stage AS "阶段", status AS "状态", task_count AS "任务", minutes AS "分钟", coins AS "金币"
FROM "04-周计划"
SORT week_no ASC
"""),
        "04-日批看板": dataview("""
TABLE task_date AS "日期", week_no AS "周次", weekday AS "星期", subject_mix AS "配比", total_minutes AS "分钟"
FROM "05-日批"
SORT task_date ASC
"""),
        "05-覆盖矩阵看板": dataview("""
TABLE length(rows) AS "主题数", sum(rows.point_count) AS "挂点合计"
FROM "03-任务库/主题"
GROUP BY subject, domain
"""),
        "06-供给看板": dataview("""
TABLE form AS "形态", difficulty AS "难度", qty AS "题量", minutes AS "分钟", supply AS "供给"
FROM "03-任务库/模板"
WHERE contains(supply, "待补题")
SORT subject ASC, theme_id ASC
LIMIT 200
"""),
        "07-审批时效看板": dataview("""
TABLE task_date AS "日期", status AS "状态", file.mtime AS "最后修改"
FROM "05-日批"
WHERE contains(status, "待审批") OR contains(status, "待周批")
SORT file.mtime ASC
"""),
        "08-健康度看板": dataview("""
TABLE subject AS "科目", point_count AS "挂点数", anchor_count AS "锚点数"
FROM "03-任务库/主题"
WHERE point_count = 0
SORT subject ASC
"""),
    }
    for name, body in dashboards.items():
        v.w("08-视图/" + name + ".md", fm(type="view") + "\n# " + name + "\n\n" + body + "\n")

    # Canvas 1：大纲骨架
    nodes, edges = [], []
    i = 0
    subject_nodes = {}
    for s in outline["subjects"]:
        i += 1
        n = tnode(i, "# " + s["code"] + "\n权重 " + str(round(s["weight"] * 100)) + "%", 0, i * 220, 240, 120, "2")
        nodes.append(n)
        subject_nodes[s["code"]] = n
        for j, m in enumerate(s["modules"]):
            i += 1
            mn = tnode(i, m["code"] + (("\n" + str(m["questions"]) + " 题") if m.get("questions") else ""),
                       340, (i % 14) * 90, 220, 70, "4")
            nodes.append(mn)
            edges.append(edge(n, mn))
    v.wj("08-视图/Canvas/10-任务图谱全景.canvas", canvas(nodes, edges))

    # Canvas 2：十二周节奏
    nodes, edges = [], []
    prev = None
    for k, p in enumerate(data["plans"], start=1):
        n = tnode(k, "第%02d周" % p["week_no"] + "\n" + str(p["stage"]) + "\n" + str(p["status"]),
                  (k - 1) * 240, 0 if p["stage"] == "基础" else (160 if p["stage"] == "强化" else 320), 200, 110)
        nodes.append(n)
        if prev:
            edges.append(edge(prev, n))
        prev = n
    v.wj("08-视图/Canvas/11-十二周节奏.canvas", canvas(nodes, edges))

    # Canvas 3：审批闭环
    labels = ["周计划", "日批", "发布包", "学生今日任务", "完成", "领币"]
    nodes = [tnode(k + 1, l, k * 240, 0, 200, 90, "3") for k, l in enumerate(labels)]
    edges = [edge(nodes[k], nodes[k + 1]) for k in range(len(nodes) - 1)]
    v.wj("08-视图/Canvas/12-审批闭环.canvas", canvas(nodes, edges))

    # Canvas 4：域覆盖
    nodes, edges = [], []
    by_domain = defaultdict(list)
    for t in data["themes"]:
        by_domain[(t["subject"], t["domain"])].append(t)
    rootn = tnode(0, "# 大纲 16 域", -260, 0, 200, 90, "5")
    nodes.append(rootn)
    k = 0
    for (subject, domain), items in sorted(by_domain.items()):
        k += 1
        n = tnode(k, subject + " / " + domain + "\n主题 " + str(len(items)), (k % 4) * 260, (k // 4) * 130, 220, 90)
        nodes.append(n)
        edges.append(edge(rootn, n))
    v.wj("08-视图/Canvas/13-域覆盖.canvas", canvas(nodes, edges))

    # Canvas 5：任务锚点
    nodes, edges = [], []
    sample = [t for t in data["themes"] if t["point_count"]][:10]
    a = tnode(0, "任务主题", -260, 0, 200, 90, "6")
    nodes.append(a)
    for k, t in enumerate(sample, start=1):
        n = tnode(k, t["theme_id"] + "\n" + t["title"], (k % 3) * 280, (k // 3) * 140, 240, 100)
        nodes.append(n)
        edges.append(edge(a, n))
    v.wj("08-视图/Canvas/14-任务锚点.canvas", canvas(nodes, edges))


def gen_compile(v, data, outline, st):
    v.wj("07-编译产出/01-大纲框架.json", outline)
    v.wj("07-编译产出/02-主题.json", data["themes"])
    v.wj("07-编译产出/03-模板.json", data["templates"])
    v.wj("07-编译产出/04-周计划.json", data["plans"])
    v.wj("07-编译产出/05-实例.json", data["instances"])

    # 锚点映射骨架：序号 → point_id（未知留空，待人工/导入器填）
    anchors = {}
    for subject, seqs in st["anchors"].items():
        anchors[subject] = [{"anchor": "知-" + subject + "-" + str(s).zfill(4), "seq": s, "point_id": None} for s in seqs]
    v.wj("07-编译产出/06-锚点映射.json", anchors)

    publish = {
        "version": "2026-11-15.1",
        "built_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "outline_version": outline["version"],
        "counts": {
            "themes": len(data["themes"]),
            "templates": len(data["templates"]),
            "plans": len(data["plans"]),
            "instances": len(data["instances"]),
        },
        "gate": {"pilot_templates": st["supply"].get("可试点", 0), "pending_templates": st["supply"].get("待补题", 0)},
        "note": "只含 supply=可试点 的模板才允许进正式发布包",
    }
    v.wj("07-编译产出/07-发布包/清单.json", publish)

    v.w("07-编译产出/08-校验.md", fm(type="compile") + """
# 校验

由构建器在生成结束时写入（见 11-变更日志/2026-11-15-基线.md 的验收段落）：

- 文件总数 / Markdown / Canvas / JSON
- Wikilink 断链数（应为 0）
- Canvas 引用断链数（应为 0）
- schema 必填字段缺失数（应为 0）
""")
    v.w("07-编译产出/09-健康度.md", fm(type="compile") + """
# 健康度

| 指标 | 值 | 判读 |
|---|---|---|
| 任务卡 | """ + str(len(data["themes"]) + len(data["templates"])) + """ | 主题 + 模板 |
| 可试点模板 | """ + str(st["supply"].get("可试点", 0)) + """ | 可进发布包 |
| 待补题模板 | """ + str(st["supply"].get("待补题", 0)) + """ | 阻断发布，不阻断计划 |
| 无考点主题 | """ + str(st["themes_without_points"]) + """ | 任务能做，考点溯源会断 |
| 相邻周重复主题 | """ + str(st["adjacent_week_repeats"]) + """ | 允许复现，须换形态/难度 |
""")

def gen_governance(v, data, st):
    v.w("09-治理/00-总览.md", fm(type="governance") + """
# 治理总览

- 一顶帽子：内容质量归教研，发布节奏归管理者，长期维护归合作方。
- 两条线：**内容线**（大纲 → 主题 → 模板）与**运行线**（周计划 → 日批 → 发布 → 学生）。
- 三个门：审批门（人工）、供给门（可试点）、发布门（发布包）。
""")
    v.w("09-治理/01-RACI.md", fm(type="governance") + """
# RACI

| 事项 | 教研 | 管理者 | 合作方 | AI |
|---|---|---|---|---|
| 大纲变化 | A/R | C | I | 起草 |
| 主题/模板设计 | R | A | C | 起草 |
| 周计划生成 | C | A/R | I | 计算 |
| 每日审批 | I | R/A | I | 汇总 |
| 发布与回滚 | I | R/A | C | 生成包 |
| 供给补题 | R/A | C | C | 统计 |
| 月度复盘 | C | R | A | 出数 |
""")
    v.w("09-治理/02-每日审批SOP.md", fm(type="process") + """
# 每日审批 SOP（3 分钟）

1. 打开 00-今日任务栏，看待批数量与最早日期；
2. 打开最早日批卡，核对：三科配比、总时长 40—110 分钟、任务数 2—3、供给全部可试点；
3. 通过 → 把 frontmatter 的 status 改成 已批准，填审批人与日期；
4. 退回 → 写原因，status 保持 待审批，并在 11-变更日志 留痕；
5. 周五加做一次：下周周计划审批（18 个任务、配比 40/30/30、无原样重复主题）。
""")
    v.w("09-治理/03-发布与回滚.md", fm(type="process") + """
# 发布与回滚 SOP

发布前：sqlite3.backup() 备份数据库（R10）；确认发布包版本唯一。
发布中：先 dry-run，再 apply；观察错误日志与金币流水。
发布后：抽查 3 名学生今日任务；核对 coin_record 只增一条。
回滚：重新 apply 上一版发布包 + 关闭本周批次；已发金币不回滚。
""")
    v.w("09-治理/04-质量控制.md", fm(type="process") + """
# 质量控制

| 检查 | 频率 | 通过线 |
|---|---|---|
| 断链 / Canvas 断链 | 每次构建 | 0 |
| 无考点主题 | 每周 | 逐周下降 |
| 相邻周原样重复 | 每周 | 0（允许换形态） |
| 时长超预算 | 每周 | 0 |
| 供给不足导致发布阻塞 | 每周 | < 1 天 |
| 锚点可映射率 | 每月 | 逐月上升 |
""")
    v.w("09-治理/05-合作方维护手册.md", fm(type="manual", version=1) + """
# 合作方维护手册（接手必读）

## 1. 你会拿到什么

- 一个 Obsidian 子库（本仓库）：设计态 + 审批态；
- 一个构建器 scripts/weekly_vault/build_vault.py 与大纲 scripts/weekly_vault/outline_2025.json；
- 一份只读数据源：题库系统 SQLite（每周任务四表 + knowledge_point）。

## 2. 每天做什么

按 02-每日审批SOP 走。只改日批卡的 status / 审批人 / 备注。

## 3. 每周做什么

1. 审批下周周计划；2. 看 05-供给看板，把已补题的模板改成 可试点；3. 跑一次构建器刷新索引。

## 4. 每月做什么

运营月报（06-运营月报模板）：审批时效、试点数、补题数、覆盖变化、锚点映射率。

## 5. 不能做什么

- 不直接改数据库、不做调度、不在库里算金币；
- 不删除任务卡（进 99-归档）；
- 不绕过审批发布；
- 不手工改 07-编译产出（由构建器生成）。

## 6. 换人怎么交接

1. 交接构建器 + 大纲 JSON + 本手册；
2. 让对方独立跑一次构建并核对 08-校验（断链 0）；
3. 让对方独立审批一天的日批；
4. 确认对方能解释「主题 / 模板 / 实例 / 日批 / 发布包」五个词。
""")
    v.w("09-治理/06-运营月报模板.md", fm(type="template") + """
# 运营月报（模板）

- 本月待审批/已审批/退回数
- 平均审批时长（天）
- 可试点模板数变化
- 无考点主题数变化
- 相邻周重复主题数
- 锚点可映射率
- 学生完成率 / 领币率（数据由系统提供）
""")
    v.w("09-治理/07-安全与权限.md", fm(type="governance") + """
# 安全与权限

- 本库不含学生个人数据；只含任务结构与审批记录。
- 发布包写库需要管理员账号；学生无写权限。
- 审计：审批人、时间、结论写进日批卡；变更写 11-变更日志。
- 勿把真实密钥/连接串写进库内任何笔记。
""")
    v.w("09-治理/08-验收清单.md", fm(type="checklist") + """
# 验收清单

- [ ] 构建器可重复运行，输出一致（同一 DB + 同一大纲 → 同一结果）
- [ ] 断链 0、Canvas 引用 0
- [ ] 55 主题 / 165 模板 / 12 周 / 84 日批 / 216 实例 数量一致
- [ ] 每日 2—3 任务、40—110 分钟
- [ ] 三科分钟比接近 40/30/30
- [ ] 供给门：待补题模板不出现在发布包
- [ ] 审批门：未批准批次学生不可见
- [ ] 合作方按手册独立跑通一次
""")

    ps = """# 每日审批提醒（只读扫描 05-日批）
# 用法：powershell -File 每日审批提醒.ps1 [-Test]
param([switch]$Test)
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$batch = Join-Path $root '05-日批'
if (-not (Test-Path $batch)) { Write-Host "未找到日批目录：$batch"; exit 1 }
$pending = @()
Get-ChildItem $batch -Filter *.md | ForEach-Object {
  $text = Get-Content $_.FullName -Raw -Encoding UTF8
  if ($text -match '(?m)^status:\\s*(待审批|待周批)\\s*$') {
    $date = if ($text -match '(?m)^task_date:\\s*(.+)$') { $matches[1].Trim() } else { $_.BaseName }
    $pending += [pscustomobject]@{ Date = $date; File = $_.Name }
  }
}
$count = $pending.Count
Write-Host ("待审批/待周批日批：{0}" -f $count)
if ($count -gt 0) {
  $pending | Sort-Object Date | Select-Object -First 7 | Format-Table -AutoSize
  if (-not $Test) {
    try {
      Add-Type -AssemblyName System.Windows.Forms
      $notify = New-Object System.Windows.Forms.NotifyIcon
      $notify.Icon = [System.Drawing.SystemIcons]::Information
      $notify.Visible = $true
      $notify.ShowBalloonTip(8000, '砺安题库 · 周任务审批', ("有 {0} 个日批待审批" -f $count), 'Info')
      Start-Sleep -Seconds 2
      $notify.Dispose()
    } catch { Write-Host "（通知不可用，已只打印结果）" }
  }
}
exit 0
"""
    v.w("09-治理/工具/每日审批提醒.ps1", ps)
    v.w("09-治理/工具/README.md", fm(type="tool") + """
# 工具

- 每日审批提醒.ps1：只读扫描 05-日批 的 status，统计待审批并弹 Windows 通知；加 -Test 只打印。
- 建议：Windows 任务计划程序，每天 09:00 执行。

""" + FENCE + """powershell
powershell -NoProfile -File "09-治理/工具/每日审批提醒.ps1" -Test
""" + FENCE)


def gen_templates(v):
    items = {
        "01-主题卡模板.md": "frontmatter: type=theme / theme_id / subject / domain / family / point_count / version；正文：定位、模板清单、锚点、供给状态。",
        "02-模板卡模板.md": "frontmatter: type=template / template_id / theme_id / form / difficulty / qty / minutes / coins / supply；正文：任务 DNA、发布校验清单。",
        "03-周计划卡模板.md": "frontmatter: type=plan / week_no / stage / start_date / end_date / status / task_count；正文：配比、每日任务、审批块。",
        "04-日批卡模板.md": "frontmatter: type=batch / task_date / weekday / status / subject_mix / total_minutes；正文：今日任务、三科配比、锚点、审批。",
        "05-任务提案模板.md": "目标一句话 / 挂大纲模块 / 形态 / 题量难度时长 / 需要的题 / 验收方式。",
        "06-变更申请模板.md": "改哪张卡 / 为什么 / 影响面 / 回滚方式 / 审批人。",
        "07-大纲变更模板.md": "来源文件 / 年份 / 变更条目 / 受影响模块 / 受影响主题。",
        "08-复盘模板.md": "本周做对了什么 / 卡在哪 / 下周改什么。",
        "09-月报模板.md": "见 09-治理/06-运营月报模板。",
    }
    for name, text in items.items():
        v.w("10-模板/" + name, fm(type="template") + "\n# " + Path(name).stem + "\n\n" + text + "\n")


def verify(vault_root, files_written):
    root = Path(vault_root)
    md = [p for p in root.rglob("*.md")]
    canvas = [p for p in root.rglob("*.canvas")]
    js = [p for p in root.rglob("*.json")] + [p for p in root.rglob("*.ps1")]
    stems = {p.stem for p in root.rglob("*.md")} | {p.stem for p in root.rglob("*.canvas")}
    broken = []
    link_re = re.compile(r"\[\[([^\]|#]+)")
    for p in md:
        text = p.read_text(encoding="utf-8")
        for target in link_re.findall(text):
            t = target.strip()
            if t and Path(t).stem not in stems:
                broken.append((str(p.relative_to(root)), t))
    canvas_broken = 0
    for p in canvas:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            canvas_broken += 1
            continue
        for n in data.get("nodes", []):
            if n.get("type") == "file":
                f = n.get("file", "")
                if Path(f).stem not in stems:
                    canvas_broken += 1
    return {
        "files_total": len(md) + len(canvas) + len(js),
        "markdown": len(md),
        "canvas": len(canvas),
        "json_or_ps1": len(js),
        "broken_links": len(broken),
        "broken_samples": broken[:10],
        "canvas_broken": canvas_broken,
        "written": len(files_written),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="D:/Obsidian仓库/周任务设计分配")
    ap.add_argument("--check-only", action="store_true")
    args = ap.parse_args()

    out = Path(args.out)
    if args.check_only:
        print(json.dumps(verify(out, []), ensure_ascii=False, indent=2))
        return

    data = load_db()
    outline = load_outline()
    st = compute_stats(data)
    v = Vault(out)
    gen_home(v, data, outline, st)
    gen_inbox(v)
    gen_task_bar(v, data, st)
    gen_outline_pages(v, outline, data, st)
    gen_library(v, data, outline)
    gen_weeks(v, data, outline)
    gen_batches(v, data)
    gen_contracts(v, data)
    gen_views(v, data, outline, st)
    gen_compile(v, data, outline, st)
    gen_governance(v, data, st)
    gen_templates(v)

    log = [fm(type="changelog", date="2026-11-15"), "# 2026-11-15 基线", ""]
    log.append("## 来源")
    log.append("")
    log.append("- 题库库表：weekly_task_theme / template / plan / instance（只读）")
    log.append("- 大纲：scripts/weekly_vault/outline_2025.json v" + outline["version"])
    log.append("")
    v.w("11-变更日志/2026-11-15-基线.md", "\n".join(log))
    v.w("11-变更日志/README.md", fm(type="changelog") + """
# 变更日志

- 每次构建追加一条：日期、版本、条目数、关键差异、审批人。
- 不删除历史条目。
""")

    res = verify(out, v.written)
    # 把校验结果回写
    check = fm(type="compile", generated=datetime.now().strftime("%Y-%m-%d %H:%M")) + """
# 校验（构建器自动生成）

""" + table(["项", "值"], [
        ["文件总数", res["files_total"]],
        ["Markdown", res["markdown"]],
        ["Canvas", res["canvas"]],
        ["JSON / PS1", res["json_or_ps1"]],
        ["Wikilink 断链", res["broken_links"]],
        ["Canvas 断链", res["canvas_broken"]],
    ]) + """

## 断链样本（前 10）

""" + ("\n".join("- " + a + " → " + b for a, b in res["broken_samples"]) if res["broken_samples"] else "无")
    (out / "07-编译产出" / "08-校验.md").write_text(check, encoding="utf-8", newline="\n")

    res2 = verify(out, v.written)
    summary = {
        "out": str(out),
        "written": len(v.written),
        "files_total": res2["files_total"],
        "markdown": res2["markdown"],
        "canvas": res2["canvas"],
        "broken_links": res2["broken_links"],
        "canvas_broken": res2["canvas_broken"],
        "themes": len(data["themes"]),
        "templates": len(data["templates"]),
        "plans": len(data["plans"]),
        "batches": len({i["task_date"] for i in data["instances"]}),
        "instances": len(data["instances"]),
        "supply": st["supply"],
        "themes_without_points": st["themes_without_points"],
        "adjacent_week_repeats": st["adjacent_week_repeats"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if res2["broken_links"] or res2["canvas_broken"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
