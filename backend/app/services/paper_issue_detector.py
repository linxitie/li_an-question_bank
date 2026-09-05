"""
试卷不合格题目检测服务

在管理员审批试卷时，对试卷题目做静态质量检测，返回问题列表供前端高亮提醒。
本期仅实现「无外部依赖」的便宜规则（题干为空/缺答案/选项不足/分值异常）；
图片 404 检测与敏感词检测因代价高/需词库，留待二期。
"""
from typing import List, Dict, Any

# 选择题题型（单选/多选），用于「选项不足」检测
_CHOICE_TYPES = ("单选题", "多选题")


def _is_blank(value) -> bool:
    """判断字符串是否为 None 或仅含空白字符"""
    if value is None:
        return True
    return not str(value).strip()


def detect_paper_issues(questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    对题目列表做静态质量检测。

    :param questions: 题目 dict 列表，每项需含：
        question_id, question_no, type_name, question_content, options, answer, score
    :return: 问题列表，每项含：
        question_id, question_no, issue_type, description, severity(error/warn)
    """
    issues: List[Dict[str, Any]] = []

    for q in questions:
        qid = q.get("question_id")
        qno = q.get("question_no")
        type_name = q.get("type_name") or ""
        content = q.get("question_content")
        options = q.get("options")
        answer = q.get("answer")
        score = q.get("score")

        # 规则1：题干为空 → error
        if _is_blank(content):
            issues.append({
                "question_id": qid,
                "question_no": qno,
                "issue_type": "empty_content",
                "description": "题干为空或仅含空白字符",
                "severity": "error",
            })

        # 规则2：缺少正确答案 → error
        if _is_blank(answer):
            issues.append({
                "question_id": qid,
                "question_no": qno,
                "issue_type": "missing_answer",
                "description": "缺少正确答案",
                "severity": "error",
            })

        # 规则3：选择题选项不足 → warn
        if type_name in _CHOICE_TYPES:
            if not isinstance(options, list) or len(options) < 2:
                issues.append({
                    "question_id": qid,
                    "question_no": qno,
                    "issue_type": "insufficient_options",
                    "description": "选择题选项不足（应至少 2 个）",
                    "severity": "warn",
                })

        # 规则4：分值异常 → warn
        try:
            score_val = float(score) if score is not None else 0
        except (TypeError, ValueError):
            score_val = 0
        if score_val <= 0:
            issues.append({
                "question_id": qid,
                "question_no": qno,
                "issue_type": "invalid_score",
                "description": "题目分值异常（≤ 0）",
                "severity": "warn",
            })

    return issues
