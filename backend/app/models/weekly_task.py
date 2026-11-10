"""周任务设计分配（2027.1）导入模型：主题 / 模板 / 周计划 / 任务实例。

边界（与 AGENTS.md §2 一致）：
- 只新增 `weekly_task_*` 前缀表，不改既有 Task / badge_task / StudyGoal；
- 主键沿用设计包里的 TEXT 编号，便于与 Obsidian 卡片一一对应；
- raw_json 保留原始行，导入可回放、可核对。
"""
from __future__ import annotations

from sqlalchemy import Column, Integer, String, Text

from ..core.database import Base


class WeeklyTaskTheme(Base):
    """任务主题（55）：科目 × 知识域 × 族。"""

    __tablename__ = "weekly_task_theme"

    theme_id = Column(String(64), primary_key=True, comment="包内编号，如 主题-行测-政治-01")
    title = Column(String(200), nullable=False)
    subject = Column(String(16), nullable=False, index=True)
    domain = Column(String(64), nullable=True, index=True)
    family = Column(String(32), nullable=True)
    anchor_count = Column(Integer, default=0)
    point_count = Column(Integer, default=0)
    template_count = Column(Integer, default=0)
    raw_json = Column(Text, nullable=True)


class WeeklyTaskTemplate(Base):
    """任务模板（165）：形态 A/B/C × 难度 × 题量 × 分钟 × 金币。"""

    __tablename__ = "weekly_task_template"

    template_id = Column(String(96), primary_key=True, comment="如 模板-行测-言语-02-基础精练")
    title = Column(String(200), nullable=False)
    theme_id = Column(String(64), nullable=False, index=True)
    subject = Column(String(16), nullable=False, index=True)
    domain = Column(String(64), nullable=True)
    form = Column(String(8), nullable=True)
    difficulty = Column(Integer, default=1)
    qty = Column(Integer, default=0)
    unit = Column(String(8), nullable=True)
    minutes = Column(Integer, default=0)
    coins = Column(Integer, default=0)
    supply = Column(String(16), nullable=True, index=True)
    available_qty = Column(Integer, default=0)
    raw_json = Column(Text, nullable=True)


class WeeklyTaskPlan(Base):
    """周计划（12）：第01周已批准，其余待批/计划中。"""

    __tablename__ = "weekly_task_plan"

    plan_id = Column(String(64), primary_key=True, comment="如 周计划-第01周")
    week_no = Column(Integer, nullable=False, index=True)
    week_key = Column(String(16), nullable=True, index=True)
    title = Column(String(200), nullable=False)
    stage = Column(String(32), nullable=True)
    start_date = Column(String(10), nullable=False, index=True)
    end_date = Column(String(10), nullable=False)
    seed = Column(Integer, nullable=True)
    status = Column(String(16), nullable=False, index=True)
    task_count = Column(Integer, default=0)
    minutes = Column(Integer, default=0)
    coins = Column(Integer, default=0)
    raw_json = Column(Text, nullable=True)


class WeeklyTaskInstance(Base):
    """任务实例（216）：按天 × 科目 × 主题 × 模板。供给=待补题 时不可开始。"""

    __tablename__ = "weekly_task_instance"

    instance_id = Column(String(96), primary_key=True, comment="如 周任-第01周-01")
    plan_id = Column(String(64), nullable=False, index=True)
    week_no = Column(Integer, nullable=False, index=True)
    task_date = Column(String(10), nullable=False, index=True)
    weekday = Column(String(8), nullable=True)
    subject = Column(String(16), nullable=False, index=True)
    domain = Column(String(64), nullable=True)
    theme_id = Column(String(64), nullable=True)
    template_id = Column(String(96), nullable=True)
    title = Column(String(200), nullable=False)
    form = Column(String(16), nullable=True)
    difficulty = Column(Integer, default=1)
    qty = Column(Integer, default=0)
    unit = Column(String(8), nullable=True)
    minutes = Column(Integer, default=0)
    coins = Column(Integer, default=0)
    supply = Column(String(16), nullable=True, index=True)
    status = Column(String(16), nullable=True, index=True)
    anchors = Column(Text, nullable=True, comment="挂点 JSON 数组，如 [\"知-行测-0054\"]")
    raw_json = Column(Text, nullable=True)
