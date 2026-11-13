#!/usr/bin/env python
"""导入《周任务设计分配 2027.1》编译产出到 weekly_task_* 四张表（幂等）。

用法（backend 目录）：
  python scripts/import_weekly_task_pack.py --pack "D:\\...\\周任务设计分配" --dry-run
  python scripts/import_weekly_task_pack.py --pack "D:\\...\\周任务设计分配" --apply

规则：
- 以包内「编号」为主键 upsert，重复执行不新增行；
- 只写 weekly_task_* 四张表，不碰 Task / badge_task / StudyGoal；
- --dry-run 只统计不写库。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.database import SessionLocal, engine  # noqa: E402
from app.core.weekly_task_schema import ensure_weekly_task_schema  # noqa: E402
from app.models.weekly_task import (  # noqa: E402
    WeeklyTaskInstance,
    WeeklyTaskPlan,
    WeeklyTaskTemplate,
    WeeklyTaskTheme,
)


def _load(path: Path) -> list[dict]:
    if not path.is_file():
        raise SystemExit(f"缺少编译产出：{path}")
    rows: list[dict] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _theme(row: dict) -> dict:
    return {
        "theme_id": row["编号"],
        "title": row.get("标题") or row["编号"],
        "subject": row.get("科目") or "",
        "domain": row.get("知识域"),
        "family": row.get("族"),
        "anchor_count": int(row.get("挂点数") or 0),
        "point_count": int(row.get("考点数") or 0),
        "template_count": int(row.get("模板数") or 0),
        "raw_json": json.dumps(row, ensure_ascii=False),
    }


def _template(row: dict) -> dict:
    return {
        "template_id": row["编号"],
        "title": row.get("标题") or row["编号"],
        "theme_id": row.get("主题") or "",
        "subject": row.get("科目") or "",
        "domain": row.get("知识域"),
        "form": row.get("形态"),
        "difficulty": int(row.get("难度") or 1),
        "qty": int(row.get("题量") or 0),
        "unit": row.get("单位"),
        "minutes": int(row.get("分钟") or 0),
        "coins": int(row.get("金币") or 0),
        "supply": row.get("供给"),
        "available_qty": int(row.get("可用题") or 0),
        "raw_json": json.dumps(row, ensure_ascii=False),
    }


def _plan(row: dict) -> dict:
    return {
        "plan_id": row["编号"],
        "week_no": int(row.get("周次") or 0),
        "week_key": row.get("周键"),
        "title": row.get("标题") or row["编号"],
        "stage": row.get("阶段"),
        "start_date": row.get("起始") or "",
        "end_date": row.get("结束") or "",
        "seed": int(row["种子"]) if row.get("种子") is not None else None,
        "status": row.get("状态") or "计划中",
        "task_count": int(row.get("任务数") or 0),
        "minutes": int(row.get("分钟") or 0),
        "coins": int(row.get("金币") or 0),
        "raw_json": json.dumps(row, ensure_ascii=False),
    }


def _instance(row: dict) -> dict:
    week_no = int(row.get("周次") or 0)
    return {
        "instance_id": row["编号"],
        "plan_id": f"周计划-第{week_no:02d}周",
        "week_no": week_no,
        "task_date": row.get("日期") or "",
        "weekday": row.get("星期"),
        "subject": row.get("科目") or "",
        "domain": row.get("知识域"),
        "theme_id": row.get("主题"),
        "template_id": row.get("模板"),
        "title": row.get("标题") or row["编号"],
        "form": row.get("形态"),
        "difficulty": int(row.get("难度") or 1),
        "qty": int(row.get("题量") or 0),
        "unit": row.get("单位"),
        "minutes": int(row.get("分钟") or 0),
        "coins": int(row.get("金币") or 0),
        "supply": row.get("供给"),
        "status": row.get("状态"),
        "anchors": json.dumps(row.get("挂点") or [], ensure_ascii=False),
        "raw_json": json.dumps(row, ensure_ascii=False),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="导入周任务设计分配")
    parser.add_argument("--pack", required=True, help="解包后的「周任务设计分配」目录")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="只统计不写库")
    mode.add_argument("--apply", action="store_true", help="写库（幂等）")
    args = parser.parse_args()

    pack = Path(args.pack)
    out = pack / "07-编译产出"
    if not out.is_dir():
        alt = pack
        out = alt if (alt / "03-主题.jsonl").is_file() else out
    if not out.is_dir():
        raise SystemExit(f"找不到 07-编译产出：{pack}")

    payload = {
        "weekly_task_theme": (_load(out / "03-主题.jsonl"), _theme),
        "weekly_task_template": (_load(out / "04-模板.jsonl"), _template),
        "weekly_task_plan": (_load(out / "05-周计划.jsonl"), _plan),
        "weekly_task_instance": (_load(out / "06-任务实例.jsonl"), _instance),
    }

    models = {
        "weekly_task_theme": WeeklyTaskTheme,
        "weekly_task_template": WeeklyTaskTemplate,
        "weekly_task_plan": WeeklyTaskPlan,
        "weekly_task_instance": WeeklyTaskInstance,
    }

    ensure_weekly_task_schema(engine)
    db = SessionLocal()
    report: dict[str, dict] = {}
    try:
        for table, (rows, mapper) in payload.items():
            model = models[table]
            existing = {row[0] for row in db.query(model).with_entities(
                getattr(model, {"weekly_task_theme": "theme_id", "weekly_task_template": "template_id",
                                "weekly_task_plan": "plan_id", "weekly_task_instance": "instance_id"}[table])
            ).all()}
            created = updated = 0
            for row in rows:
                data = mapper(row)
                key = data[{"weekly_task_theme": "theme_id", "weekly_task_template": "template_id",
                            "weekly_task_plan": "plan_id", "weekly_task_instance": "instance_id"}[table]]
                if key in existing:
                    updated += 1
                else:
                    created += 1
                if args.apply:
                    db.merge(model(**data))
            report[table] = {"total": len(rows), "created": created, "updated": updated}
            if args.apply:
                db.commit()
        if args.apply:
            db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    supplies: dict[str, int] = {}
    for row in payload["weekly_task_instance"][0]:
        supplies[row.get("供给") or "未知"] = supplies.get(row.get("供给") or "未知", 0) + 1

    print(json.dumps({
        "mode": "apply" if args.apply else "dry-run",
        "pack": str(pack),
        "report": report,
        "instance_supply": supplies,
        "publishable": supplies.get("可试点", 0),
        "note": "可试点实例才允许开始；其余为待补题，学生端只展示不可开始",
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
