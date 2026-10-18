"""用户行为 trigger_type 常量注册表（E1–E10）。

本模块是 `record_user_action(..., trigger_type, ...)` 事件总线中
`trigger_type` 取值的唯一权威来源，对应设计方案 §3.3「十条入边明细」。

命名约定
--------
常量名：``TRIGGER_<大写下划线>``
常量值：点分小写命名，与成就模块 `badge_task` 判据长期绑定。

E1–E10 对照
-----------
========  ========================  ==========================
事件      trigger_type              来源模块
========  ========================  ==========================
E1        practice.submit           答题练习
E2        practice.record.created   练习记录
E3        paper.completed           组卷 / 历年试卷
E4        wrong.reviewed            错题集
E5        note.created              笔记（E5 覆盖两个值）
E5        favorite.added            收藏（E5 覆盖两个值）
E6        forum.posted              论坛社区
E7        news.read                 每日新闻
E8        material.opened           备考资料
E9        shop.purchased            金币商城
E10       checkin.done              每日签到
========  ========================  ==========================

add-only 硬约定
---------------
新增行为类型**只允许追加**新的常量与新的字符串值：

- 禁止修改任何既有常量的字符串值；
- 禁止修改既有字符串值的语义（成就判据与历史事件长期引用它们）；
- 禁止删除既有常量。

因此 ``ALL_TRIGGER_TYPES`` 只会增长，历史事件永远可被成就模块回放与重算。
"""

from __future__ import annotations

# E1 —— 答题练习
TRIGGER_PRACTICE_SUBMIT = "practice.submit"

# E2 —— 练习记录
TRIGGER_PRACTICE_RECORD_CREATED = "practice.record.created"

# E3 —— 组卷 / 历年试卷
TRIGGER_PAPER_COMPLETED = "paper.completed"

# E4 —— 错题集
TRIGGER_WRONG_REVIEWED = "wrong.reviewed"

# E5 —— 笔记 + 收藏（同一事件覆盖两个 trigger_type）
TRIGGER_NOTE_CREATED = "note.created"
TRIGGER_FAVORITE_ADDED = "favorite.added"

# E6 —— 论坛社区
TRIGGER_FORUM_POSTED = "forum.posted"

# E7 —— 每日新闻
TRIGGER_NEWS_READ = "news.read"

# E8 —— 备考资料
TRIGGER_MATERIAL_OPENED = "material.opened"

# E9 —— 金币商城
TRIGGER_SHOP_PURCHASED = "shop.purchased"

# E10 —— 每日签到
TRIGGER_CHECKIN_DONE = "checkin.done"


# ---------------------------------------------------------------------------
# 历史值（早于 E1–E10 规范化）
# ---------------------------------------------------------------------------
# 这些字符串是 achievement_service 成就目录的既有建档值。可映射到 E1–E10
# 的调用点改用上方常量；无法映射的历史值保留原值，并在成就判定侧通过
# LEGACY_TRIGGER_ALIASES 与新常量对齐，确保历史语义与徽章发放行为不变。
#
# add-only 同样适用：禁止修改以下字符串值。
TRIGGER_LEGACY_VIEW_WRONG = "view_wrong"
TRIGGER_LEGACY_CHOP = "chop"
TRIGGER_LEGACY_REVIEW = "review"
TRIGGER_LEGACY_POST = "post"
TRIGGER_LEGACY_QUOTE_FAVORITE = "quote_favorite"
TRIGGER_LEGACY_SIGN_IN = "sign_in"
TRIGGER_LEGACY_FAVORITE = "favorite"
TRIGGER_LEGACY_NOTE = "note"
TRIGGER_LEGACY_DO_QUESTION = "do_question"

#: 新常量 -> 既有历史值。成就判定同时匹配两者，避免 P2-01 改名后
#: 历史徽章（按历史值建档）漏发；该映射只增不删。
LEGACY_TRIGGER_ALIASES = {
    TRIGGER_PRACTICE_SUBMIT: (TRIGGER_LEGACY_DO_QUESTION,),
    TRIGGER_WRONG_REVIEWED: (TRIGGER_LEGACY_REVIEW,),
    TRIGGER_NOTE_CREATED: (TRIGGER_LEGACY_NOTE,),
    TRIGGER_FAVORITE_ADDED: (TRIGGER_LEGACY_FAVORITE,),
    TRIGGER_FORUM_POSTED: (TRIGGER_LEGACY_POST,),
    TRIGGER_CHECKIN_DONE: (TRIGGER_LEGACY_SIGN_IN,),
}


#: 全部合法 trigger_type 字符串值（10 个，E5 两个值）。
#: add-only：仅允许在末尾追加，禁止修改/删除既有元素。
ALL_TRIGGER_TYPES = (
    TRIGGER_PRACTICE_SUBMIT,
    TRIGGER_PRACTICE_RECORD_CREATED,
    TRIGGER_PAPER_COMPLETED,
    TRIGGER_WRONG_REVIEWED,
    TRIGGER_NOTE_CREATED,
    TRIGGER_FAVORITE_ADDED,
    TRIGGER_FORUM_POSTED,
    TRIGGER_NEWS_READ,
    TRIGGER_MATERIAL_OPENED,
    TRIGGER_SHOP_PURCHASED,
    TRIGGER_CHECKIN_DONE,
)
