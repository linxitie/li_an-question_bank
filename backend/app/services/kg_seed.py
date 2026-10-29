"""R0 主题种子（theme + exam_type）。"""
from __future__ import annotations

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..models.models import Topic

# (name, slug, kind)
TOPIC_SEED: tuple[tuple[str, str, str], ...] = (
    # 30 个 theme
    ("忠诚教育", "loyalty-education", "theme"),
    ("执法素养", "law-enforcement-literacy", "theme"),
    ("心理韧性", "psychological-resilience", "theme"),
    ("法律法规", "laws-regulations", "theme"),
    ("社会治理", "social-governance", "theme"),
    ("民生保障", "livelihood-security", "theme"),
    ("廉政建设", "integrity-building", "theme"),
    ("青年担当", "youth-responsibility", "theme"),
    ("科技强警", "tech-policing", "theme"),
    ("公平正义", "fairness-justice", "theme"),
    ("法治思维", "rule-of-law-thinking", "theme"),
    ("群众路线", "mass-line", "theme"),
    ("调查研究", "investigation-research", "theme"),
    ("底线思维", "bottom-line-thinking", "theme"),
    ("斗争精神", "fighting-spirit", "theme"),
    ("自我革命", "self-revolution", "theme"),
    ("基层治理", "grassroots-governance", "theme"),
    ("应急管理", "emergency-management", "theme"),
    ("舆情处置", "public-opinion-response", "theme"),
    ("队伍建设", "team-building", "theme"),
    ("政治理论", "political-theory", "theme"),
    ("党史学习", "party-history", "theme"),
    ("公安要闻", "police-news", "theme"),
    ("政策法规", "policies-regulations", "theme"),
    ("重大会议", "major-meetings", "theme"),
    ("领导活动", "leadership-activities", "theme"),
    ("地方动态", "local-updates", "theme"),
    ("国际视野", "global-perspective", "theme"),
    ("职业规划", "career-planning", "theme"),
    ("备考方法", "exam-prep-methods", "theme"),
    # 6 个 exam_type（招考分类映射）
    ("国考省考", "national-provincial-exam", "exam_type"),
    ("教师招聘", "teacher-recruitment", "exam_type"),
    ("事业单位", "public-institutions", "exam_type"),
    ("国企招聘", "state-owned-enterprise", "exam_type"),
    ("医疗卫生", "healthcare", "exam_type"),
    ("三支一扶", "three-supports", "exam_type"),
)


def seed_topics(db: Session) -> int:
    """按 name/slug 幂等插入主题，返回新增数。"""
    created = 0
    for name, slug, kind in TOPIC_SEED:
        exists = (
            db.query(Topic)
            .filter(or_(Topic.name == name, Topic.slug == slug))
            .first()
        )
        if exists:
            continue
        db.add(Topic(name=name, slug=slug, kind=kind, aliases=[]))
        created += 1
    db.commit()
    return created
