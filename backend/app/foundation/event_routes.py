"""F2b：user.action.v1 -> data-changed 的定向路由表。

触发类型是成就判据的稳定标识（E1–E10，add-only）；这里只描述「哪个域变了、
通知谁」。新增 trigger 必须同时在这里登记，L7-17 会检查覆盖度。

隐私边界：
- 私有域（错题/笔记/收藏/金币/签到/资料/新闻）只通知本人；
- 学习行为（练习/组卷）通知本人 + 教师/管理员，便于教师端看板刷新；
- 论坛是公共域，三角色广播；试卷发布同理。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from app.core.trigger_types import (
    ALL_TRIGGER_TYPES,
    TRIGGER_CHECKIN_DONE,
    TRIGGER_FAVORITE_ADDED,
    TRIGGER_FORUM_POSTED,
    TRIGGER_MATERIAL_OPENED,
    TRIGGER_NEWS_READ,
    TRIGGER_NOTE_CREATED,
    TRIGGER_PAPER_COMPLETED,
    TRIGGER_PRACTICE_RECORD_CREATED,
    TRIGGER_PRACTICE_SUBMIT,
    TRIGGER_SHOP_PURCHASED,
    TRIGGER_WRONG_REVIEWED,
)

ALL_ROLES = ("student", "teacher", "admin")


@dataclass(frozen=True)
class Route:
    domain: str
    type: str
    roles: tuple[str, ...] = field(default_factory=tuple)
    self_only: bool = True

    def recipients(self, user_id: int) -> tuple[list[int], tuple[str, ...]]:
        if self.self_only:
            return [user_id], ()
        return [user_id], self.roles


_ROUTES = {
    TRIGGER_PRACTICE_SUBMIT: Route("exam", TRIGGER_PRACTICE_SUBMIT, ("teacher", "admin"), False),
    TRIGGER_PRACTICE_RECORD_CREATED: Route(
        "exam", TRIGGER_PRACTICE_RECORD_CREATED, ("teacher", "admin"), False
    ),
    TRIGGER_PAPER_COMPLETED: Route("exam", TRIGGER_PAPER_COMPLETED, ("teacher", "admin"), False),
    TRIGGER_WRONG_REVIEWED: Route("wrong", TRIGGER_WRONG_REVIEWED),
    TRIGGER_NOTE_CREATED: Route("note", TRIGGER_NOTE_CREATED),
    TRIGGER_FAVORITE_ADDED: Route("favorite", TRIGGER_FAVORITE_ADDED),
    TRIGGER_FORUM_POSTED: Route("community", TRIGGER_FORUM_POSTED, ALL_ROLES, False),
    TRIGGER_NEWS_READ: Route("news", TRIGGER_NEWS_READ),
    TRIGGER_MATERIAL_OPENED: Route("library", TRIGGER_MATERIAL_OPENED),
    TRIGGER_SHOP_PURCHASED: Route("reward", TRIGGER_SHOP_PURCHASED),
    TRIGGER_CHECKIN_DONE: Route("growth", TRIGGER_CHECKIN_DONE),
}

# 未知 trigger 仍只通知本人，domain 用 user，避免静默丢弃。
_FALLBACK = Route("user", "user.action")


def route_for(trigger_type: str) -> Route:
    return _ROUTES.get(trigger_type, _FALLBACK)


def covered_triggers() -> Iterable[str]:
    return _ROUTES.keys()


def missing_triggers() -> list[str]:
    return [t for t in ALL_TRIGGER_TYPES if t not in _ROUTES]
