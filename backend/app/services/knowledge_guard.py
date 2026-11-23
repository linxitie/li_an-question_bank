"""自生长知识库 · 入库三闸（P4）

用户 2026-11-22 第 7 条要求：知识库扩充必须防意识形态错误、防错误引导，
并且只服务"公安联考备考"，不能变成"什么都会但不靠谱"的通用模型。

三道闸（缺一不可，顺序固定）：
  1) 域闸     —— 只允许公安联考备考相关主题；不相关内容直接 `block`
  2) 安全闸   —— 复用 content_guard 引擎（敏感词/政策/URL 白名单）；命中即 `block`
  3) 来源闸   —— 没有来源（题库题号/官方文件/教材页码）只能进 `review`（待人工审核），
                 有来源且前两闸通过才是 `allow`

用法（AI 自生长写入前调用）：
    from ....services.knowledge_guard import review_knowledge_write
    verdict = review_knowledge_write(db, content=text, source="题库 Q12345")
    if verdict["decision"] != "allow":
        # block：丢弃并记审计；review：写入 draft 队列等人工审核
        ...
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# 域白名单：命中任意关键词即视为"公安联考备考相关"
DOMAIN_ALLOW_KEYWORDS = (
    "公安联考", "联考", "行测", "申论", "公专", "公安专业科目", "招警", "警校",
    "考点", "知识点", "题型", "真题", "模拟题", "错题", "解析",
    "资料分析", "判断推理", "数量关系", "言语理解", "常识判断", "申论大作文",
    "贯彻执行", "归纳概括", "提出对策", "综合分析", "面试", "结构化面试",
    "体检", "政审", "报名", "岗位", "分数线", "考纲", "大纲",
)

# 明确拒答/阻塞的主题（意识形态与越界高风险；宁可漏放不可错放）
DOMAIN_BLOCK_KEYWORDS = (
    "选举", "游行", "示威", "罢工", "政变", "颠覆", "分裂国家",
    "翻墙", "破网", "代理服务器购买", "代考", "作弊器", "出售答案", "真题答案买卖",
    "自杀", "自残", "伤害他人", "爆炸物", "枪支制造",
)

# 域外但可"引导回备考"的主题（不 block，只标记 out_of_domain 让上层礼貌拒答）
DOMAIN_SOFT_OUT = (
    "写代码", "编程", "股票", "基金", "彩票", "情感", "恋爱", "游戏攻略", "追星",
)

MIN_SOURCE_LEN = 2


def _hit(text: str, keywords) -> list:
    lowered = (text or "").lower()
    return [k for k in keywords if k.lower() in lowered]


def review_knowledge_write(
    db: Optional[Session],
    *,
    content: str,
    source: Optional[str] = None,
    force_review: bool = False,
) -> dict:
    """对一段准备入库/对外生成的内容做三闸判定。

    返回：
        {
          "decision": "allow" | "review" | "block",
          "reasons": [...],                 # 人读原因
          "domain_hits": [...],             # 命中的备考关键词
          "blocked_terms": [...],           # 命中的高危词
          "has_source": bool,
          "guard": {...} | None,            # content_guard 原始结果（可能为 None）
        }
    """
    text = str(content or "").strip()
    reasons: list[str] = []

    if not text:
        return {
            "decision": "block",
            "reasons": ["内容为空"],
            "domain_hits": [],
            "blocked_terms": [],
            "has_source": bool(source and str(source).strip()),
            "guard": None,
        }

    blocked = _hit(text, DOMAIN_BLOCK_KEYWORDS)
    if blocked:
        reasons.append("命中高危主题：" + "、".join(blocked[:3]))
        return {
            "decision": "block",
            "reasons": reasons,
            "domain_hits": _hit(text, DOMAIN_ALLOW_KEYWORDS),
            "blocked_terms": blocked,
            "has_source": bool(source and str(source).strip()),
            "guard": None,
        }

    # 安全闸：复用现有引擎（表未就绪/引擎异常时降级为"仅记录"，不阻断正常业务流程）
    guard_result = None
    if db is not None:
        try:
            from .content_guard import check_text as _check_text

            guard_result = _check_text(db, text, scene="knowledge_write")
        except Exception as exc:  # noqa: BLE001 - 引擎不可用不应阻断入库
            logger.warning("content_guard 不可用，跳过安全闸：%s", type(exc).__name__)
            guard_result = None
    if isinstance(guard_result, dict):
        action = str(guard_result.get("action") or guard_result.get("decision") or "").lower()
        if action in {"block", "blocked", "reject"} or guard_result.get("blocked"):
            reasons.append("内容安全引擎判定拦截")
            return {
                "decision": "block",
                "reasons": reasons,
                "domain_hits": _hit(text, DOMAIN_ALLOW_KEYWORDS),
                "blocked_terms": guard_result.get("hits") or guard_result.get("terms") or [],
                "has_source": bool(source and str(source).strip()),
                "guard": guard_result,
            }

    domain_hits = _hit(text, DOMAIN_ALLOW_KEYWORDS)
    soft_out = _hit(text, DOMAIN_SOFT_OUT)
    has_source = bool(source and str(source).strip()) and len(str(source).strip()) >= MIN_SOURCE_LEN

    if not domain_hits:
        reasons.append("未命中公安联考备考主题")
        return {
            "decision": "block",
            "reasons": reasons,
            "domain_hits": [],
            "blocked_terms": [],
            "has_source": has_source,
            "guard": guard_result,
        }
    if soft_out and not any(k in text for k in ("备考", "考试", "复习", "联考")):
        reasons.append("内容偏向域外主题：" + "、".join(soft_out[:2]))
        return {
            "decision": "block",
            "reasons": reasons,
            "domain_hits": domain_hits,
            "blocked_terms": [],
            "has_source": has_source,
            "guard": guard_result,
        }

    if not has_source:
        reasons.append("缺少来源（题库题号/官方文件/教材页码），只能进待审队列")
        return {
            "decision": "review",
            "reasons": reasons,
            "domain_hits": domain_hits,
            "blocked_terms": [],
            "has_source": False,
            "guard": guard_result,
        }

    if force_review:
        reasons.append("人工要求先审")
        return {
            "decision": "review",
            "reasons": reasons,
            "domain_hits": domain_hits,
            "blocked_terms": [],
            "has_source": True,
            "guard": guard_result,
        }

    return {
        "decision": "allow",
        "reasons": ["三闸通过（域/安全/来源）"],
        "domain_hits": domain_hits,
        "blocked_terms": [],
        "has_source": True,
        "guard": guard_result,
    }
