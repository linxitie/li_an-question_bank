"""十域清单：路由归属 / 事件 / 契约。

数据来源：路由前缀与端点数为**实测**（见 :func:`measure_routes`），
域划分与模块归属取自设计规格 §3.2 的十域表。

⚠️ 与规格的一处已知偏差
---------------------
规格给 ``reward`` 域记 9 个端点，实测只有 5 个（``shop`` 3 + ``coins`` 2）。
差额 4 来自 ``admin_shop``：它的路由物理挂载在 ``/api/admin`` 下，
按前缀归属会被计入 ``platform``（实测 90，与规格的 90 完全一致）。
故 ``reward`` 的 9 是「按职责算」，而路由表上只有 5。本清单以**实测路由归属**
为准并在此标注，不擅自把 admin_shop 划归 reward——那会与 platform 的实测数冲突。

P3B 目录搬迁时，本清单是校验归属是否正确的唯一依据。
"""
from __future__ import annotations

import collections
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class Domain:
    name: str
    capability: str
    modules: tuple[str, ...]
    route_prefixes: tuple[str, ...]
    endpoint_count: int
    events: tuple[str, ...] = ()
    consumers: tuple[str, ...] = ()


_D = (
    Domain(
        "identity", "登录/鉴权/设备",
        ("auth", "auth_qrcode", "devices"),
        ("api/auth",),
        16,
        events=("identity.user.updated",),
    ),
    Domain(
        "catalog", "题目/试卷/错题/导入",
        ("questions", "question_actions", "question_import",
         "wrong_questions", "papers", "paper_generation"),
        ("api/questions", "api/papers", "api/wrong-questions"),
        78,
        events=("catalog.question.imported", "catalog.paper.published"),
    ),
    Domain(
        "exam", "练习/模考/成绩",
        ("practice", "quick_practice", "smart_exam", "exams",
         "exam_records", "stats"),
        ("api/exams", "api/stats", "api/smart-exam", "api/exam-records",
         "api/practice", "api/quick-practice"),
        54,
        events=("exam.exam.submitted", "exam.exam.graded"),
    ),
    Domain(
        "reward", "金币/商城",
        ("coins", "shop", "admin_shop"),
        ("api/coins", "api/shop"),
        5,  # 规格记 9，差额 4 为 admin_shop，其路由在 api/admin 下，见模块文档
        events=("reward.coins.awarded",),
    ),
    Domain(
        "growth", "任务/目标/成就",
        ("tasks", "goals", "achievements"),
        ("api/goals", "api/tasks", "api/achievements"),
        19,
        events=("growth.goal.progressed",),
    ),
    Domain(
        "community", "论坛/金句",
        ("forum", "quotes"),
        ("api/forum", "api/quotes"),
        19,
    ),
    Domain(
        "library", "备考资料/视频/媒体",
        ("materials", "videos", "media"),
        ("api/materials", "api/video", "api/media"),
        31,
        events=("library.material.published",),
    ),
    Domain(
        "content", "新闻/招考/日历/图谱",
        ("news", "recruitment", "calendar", "kg"),
        ("api/news", "api/recruitment", "api/calendar", "api/kg"),
        17,  # R0 新增 /api/kg 4 个只读端点
    ),
    Domain(
        "personal", "收藏/笔记",
        ("collection", "notes"),
        ("api/notes", "api/collection"),
        14,
    ),
    Domain(
        "platform", "管理/教师/反馈/WS/AI",
        ("admin", "admin_approval", "teacher", "feedback",
         "websocket", "llm"),
        ("api/teacher", "api/admin", "api/feedback", "api/llm"),
        90,
    ),
)

DOMAINS: dict[str, Domain] = {d.name: d for d in _D}
DOMAIN_NAMES: tuple[str, ...] = tuple(DOMAINS)
ALL_ROUTE_PREFIXES: frozenset[str] = frozenset(
    p for d in DOMAINS.values() for p in d.route_prefixes
)
ALL_MODULES: frozenset[str] = frozenset(
    m for d in DOMAINS.values() for m in d.modules
)


def get(domain: str) -> Domain | None:
    return DOMAINS.get(domain)


def owner_of_prefix(prefix: str) -> str | None:
    for d in DOMAINS.values():
        if prefix in d.route_prefixes:
            return d.name
    return None


def module_count() -> int:
    return sum(len(d.modules) for d in DOMAINS.values())


def endpoint_count() -> int:
    return sum(d.endpoint_count for d in DOMAINS.values())


def events_of(domain: str) -> tuple[str, ...]:
    d = DOMAINS.get(domain)
    return d.events if d else ()


def measure_routes() -> dict[str, int]:
    """实测当前应用的 ``/api`` 路由数，按两段前缀归并。

    这是本清单的校验基准：P3B 搬迁后重跑，若数字变化即说明路由归属被破坏。
    """
    from app.main import app
    counter: collections.Counter[str] = collections.Counter()
    for route in app.routes:
        path = getattr(route, "path", "")
        if not path.startswith("/api"):
            continue
        seg = [s for s in path.split("/") if s]
        key = "/".join(seg[:2]) if len(seg) >= 2 else "/".join(seg)
        counter[key] += 1
    return dict(counter)


def verify_against_app() -> list[str]:
    """把清单与实��路由比对，返回差异清单（空表示一致）。

    两类差异都算问题：
    - 清单里的前缀在应用中不存在（模块被搬走或改名）
    - 应用里存在未被任何域认领的 ``/api`` 前缀（新增模块未登记）
    """
    live = measure_routes()
    problems: list[str] = []
    for prefix, n in live.items():
        if owner_of_prefix(prefix) is None:
            problems.append(f"未登记前缀: {prefix} ({n} 个端点)")
    for d in DOMAINS.values():
        declared = sum(live.get(p, 0) for p in d.route_prefixes)
        if declared != d.endpoint_count:
            problems.append(
                f"{d.name}: 清单记 {d.endpoint_count}，实测 {declared}")
    return problems


def validate() -> list[str]:
    """静态自检：模块不重复、前缀不重复、事件须在 events.ALL_EVENTS 中登记。"""
    from . import events as _events

    problems: list[str] = []
    mods: list[str] = list(ALL_MODULES)
    for m in mods:
        if mods.count(m) > 1:
            problems.append(f"模块重复登记: {m}")
    seen: list[str] = []
    for d in DOMAINS.values():
        seen.extend(d.route_prefixes)
    for p in seen:
        if seen.count(p) > 1:
            problems.append(f"路由前缀重复认领: {p}")
    for d in DOMAINS.values():
        for ev in d.events:
            if ev not in _events.ALL_EVENTS:
                problems.append(f"{d.name} 引用未注册事件: {ev}")
    return problems


def summary() -> str:
    lines = [f"域数 {len(DOMAINS)}  模块数 {module_count()}  端点数 {endpoint_count()}"]
    lines.append(f"{'域':<11}{'能力':<18}{'模块':>4}{'端点':>6}  前缀")
    for d in DOMAINS.values():
        lines.append(
            f"{d.name:<11}{d.capability:<18}{len(d.modules):>4}"
            f"{d.endpoint_count:>6}  {', '.join(d.route_prefixes)}")
    return "\n".join(lines)