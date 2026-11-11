"""招考职位与用户资格卡的规则匹配引擎。"""

from __future__ import annotations

import re
from typing import Any

from ..models.models import PolicePost, UserProfile

_DEGREE_RANK = {"大专": 1, "本科": 2, "硕士": 3, "博士": 4}


def _value(value: Any) -> str:
    return str(value or "").strip()


def _has_requirement(value: Any) -> bool:
    text = _value(value)
    return bool(text and text not in {"不限", "无", "无要求", "不限专业", "不限学历"})


def _reason(field: str, result: str, message: str) -> dict[str, str]:
    return {"field": field, "result": result, "message": message}


def _match_education(profile: UserProfile, post: PolicePost) -> dict[str, str]:
    req = _value(post.education_req or post.education)
    degree = _value(profile.degree)
    if not _has_requirement(req):
        return _reason("education", "pass", "学历不限")
    if not degree:
        return _reason("education", "risk", "资格卡未填写学历，请补充")
    required_rank = 0
    for name, rank in _DEGREE_RANK.items():
        if name in req:
            required_rank = max(required_rank, rank)
    if "研究生" in req:
        required_rank = max(required_rank, 3)
    current_rank = _DEGREE_RANK.get(degree, 0)
    if required_rank and current_rank < required_rank:
        return _reason("education", "fail", f"岗位要求{req}，你的学历为{degree}")
    if "仅" in req and current_rank > required_rank:
        return _reason("education", "risk", f"岗位写“{req}”，你的学历可能超出限制，请核实")
    return _reason("education", "pass", f"{degree}满足{req}")


def _match_major(profile: UserProfile, post: PolicePost) -> dict[str, str]:
    req = _value(post.major_req or post.profession)
    major = _value(profile.major_name)
    category = _value(profile.major_category)
    if not _has_requirement(req):
        return _reason("major", "pass", "专业不限")
    if not major:
        return _reason("major", "risk", "资格卡未填写专业，请补充")
    if major in req or (category and category in req):
        return _reason("major", "pass", f"{major}命中岗位专业要求")
    return _reason(
        "major",
        "risk",
        f"岗位要求{req}，你的专业为{major}；如为相近专业，请查阅专业目录并联系招录单位确认",
    )


def _match_political(profile: UserProfile, post: PolicePost) -> dict[str, str]:
    req = _value(post.political_req)
    status = _value(profile.political_status)
    if not _has_requirement(req):
        return _reason("political", "pass", "政治面貌不限")
    if not status:
        return _reason("political", "risk", "资格卡未填写政治面貌，请补充")
    if "党员" in req:
        if status in {"党员", "中共预备党员", "预备党员"}:
            return _reason("political", "pass", f"{status}满足党员要求")
        return _reason("political", "fail", "岗位要求党员，你的政治面貌不符合")
    if "团员" in req:
        if status in {"团员", "党员", "中共预备党员", "预备党员"}:
            return _reason("political", "pass", f"{status}满足团员要求")
        return _reason("political", "fail", "岗位要求团员，你的政治面貌不符合")
    return _reason("political", "risk", f"岗位政治面貌要求“{req}”，请核实")


def _match_fresh(profile: UserProfile, post: PolicePost) -> dict[str, str]:
    req = _value(post.fresh_grad_req)
    fresh = profile.fresh_grad
    if not _has_requirement(req):
        return _reason("fresh_grad", "pass", "应届身份不限")
    if fresh is None:
        return _reason("fresh_grad", "risk", "资格卡未填写应届身份，请补充")
    if "应届" in req and fresh != 1:
        return _reason("fresh_grad", "fail", "岗位要求应届生，你当前不是应届生")
    if "往届" in req and fresh == 1:
        return _reason("fresh_grad", "fail", "岗位要求往届生，你当前是应届生")
    return _reason("fresh_grad", "pass", f"应届身份满足“{req}”")


def _match_gender(profile: UserProfile, post: PolicePost) -> dict[str, str]:
    req = _value(post.sex_require)
    gender = _value(profile.gender)
    if not _has_requirement(req):
        return _reason("gender", "pass", "性别不限")
    if not gender:
        return _reason("gender", "risk", "资格卡未填写性别")
    if req in {"男", "女"} and gender != req:
        return _reason("gender", "fail", f"岗位限{req}，你的性别为{gender}")
    return _reason("gender", "pass", f"性别满足“{req}”")


def _number(text: str) -> int | None:
    match = re.search(r"\d+", text or "")
    return int(match.group()) if match else None


def _match_grassroots(profile: UserProfile, post: PolicePost) -> dict[str, str]:
    required = post.grassroots_years or _number(post.other_req or "")
    if not required:
        return _reason("grassroots", "pass", "无基层年限要求")
    years = profile.grassroots_years
    if years is None:
        return _reason("grassroots", "risk", f"岗位要求{required}年基层经历，资格卡未填写")
    if years < required:
        return _reason("grassroots", "fail", f"岗位要求{required}年基层经历，你填写{years}年")
    return _reason("grassroots", "pass", f"基层经历满足{required}年")


def _match_age(profile: UserProfile, post: PolicePost) -> dict[str, str]:
    req = _value(post.age_req)
    if not _has_requirement(req):
        return _reason("age", "pass", "年龄不限")
    age = profile.age
    if age is None:
        return _reason("age", "risk", f"岗位年龄要求“{req}”，资格卡未填写年龄")
    limits = [int(x) for x in re.findall(r"\d{2}", req)]
    if limits and age > max(limits):
        return _reason("age", "fail", f"岗位年龄要求“{req}”，你填写{age}岁")
    return _reason("age", "pass", f"年龄满足“{req}”")


def _match_physical(profile: UserProfile, post: PolicePost) -> dict[str, str]:
    req = _value(post.physical_req)
    if not _has_requirement(req):
        return _reason("physical", "pass", "无额外体能要求")
    if profile.physical_ok is None:
        return _reason("physical", "risk", "岗位有体能/体检要求，资格卡未完成体能自评")
    if profile.physical_ok == 0:
        return _reason("physical", "risk", "资格卡体能自评未通过，请以官方体测为准")
    return _reason("physical", "pass", "体能自评通过，仍需以官方体测为准")


def match_job(profile: UserProfile | None, post: PolicePost) -> dict[str, Any]:
    """返回可解释的匹配结果；未知条件只标黄，不直接判红。"""
    if profile is None:
        return {
            "level": "yellow",
            "score": 0,
            "reasons": [_reason("profile", "risk", "尚未填写资格卡，无法完成精准匹配")],
            "disclaimer": "本结果为资格预筛，不构成官方资格审核结论。",
        }
    reasons = [
        _match_education(profile, post),
        _match_major(profile, post),
        _match_political(profile, post),
        _match_fresh(profile, post),
        _match_gender(profile, post),
        _match_grassroots(profile, post),
        _match_age(profile, post),
        _match_physical(profile, post),
    ]
    if any(item["result"] == "fail" for item in reasons):
        level = "red"
    elif any(item["result"] == "risk" for item in reasons):
        level = "yellow"
    else:
        level = "green"
    passes = sum(1 for item in reasons if item["result"] == "pass")
    return {
        "level": level,
        "score": round(passes / len(reasons) * 100),
        "reasons": reasons,
        "disclaimer": "本结果为资格预筛，不构成官方资格审核结论。最终以招录单位审核为准。",
    }
