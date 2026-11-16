"""P2：用 LLM 从招考公告中提取可核验的岗位条件。"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from ..models.models import JobParseRun, PolicePost, RecruitmentInfo
from . import llm_client

_SYSTEM = (
    "你是招考公告职位信息抽取器。只输出 JSON，不输出 Markdown。"
    "只抽取公告中明确写出的岗位；没有明确岗位表或岗位明细时返回空 positions。"
    "严禁根据常识补全，严禁编造单位、岗位、人数、学历、专业、年龄。"
    "找不到的字段填 null；不限填“不限”。每个关键字段必须附原文 evidence。"
)
_JSON_RE = re.compile(r"\{.*\}", re.S)


def _prompt(rec: RecruitmentInfo) -> str:
    body = (rec.content or "")[:14000]
    html_table = (rec.content_html or "")[:14000]
    return f"""从下面公告中抽取岗位。

输出 JSON：
{{
  "positions": [
    {{
      "job_name": "岗位名称",
      "employer": "招录单位",
      "province": "省份",
      "city": "地市",
      "job_code": "职位代码或null",
      "plan_count": 1,
      "education_req": "学历要求，没有则null",
      "major_req": "专业要求，没有则null",
      "political_req": "政治面貌，没有则null",
      "fresh_grad_req": "应届要求，没有则null",
      "grassroots_years": null,
      "age_req": "年龄要求或null",
      "gender_req": "性别要求或null",
      "physical_req": "体能/体检要求或null",
      "registration_end": "报名截止或null",
      "evidence": {{"education_req": "原文片段", "major_req": "原文片段"}},
      "confidence": 0.0
    }}
  ],
  "announcement": {{"organization": "发布单位", "province": "省份"}}
}}

规则：
- 只抽取明确列出的岗位；
- 没有岗位明细时 positions 为空数组；
- 表格中的每一行是一个岗位；
- 表格列名可能是“岗位名称/职位名称/招录单位/学历/专业/人数”；
- 不要把公告标题当岗位名称；
- 不要抽取新闻、评论、公示名单中的人名；
- 置信度 0-1。

标题：{rec.title}
分类：{rec.category or ""}
来源：{rec.source_name or ""}
正文：
{body}
HTML 表格片段：
{html_table}
"""


def _extract_json(text: str) -> dict[str, Any]:
    match = _JSON_RE.search(text or "")
    if not match:
        raise ValueError("LLM response has no JSON")
    data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise ValueError("LLM response must be object")
    return data


def _call(prompt: str) -> str:
    async def run() -> str:
        return await llm_client._post(
            [
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            prompt_name="recruitment_job_parse",
        )

    return asyncio.run(run())


def _clean(value: Any) -> str | None:
    if value in (None, "", "null", "None"):
        return None
    return str(value).strip()[:500]


def _int(value: Any) -> int | None:
    match = re.search(r"\d+", str(value or ""))
    return int(match.group()) if match else None


def _valid_position(item: dict[str, Any]) -> bool:
    name = _clean(item.get("job_name"))
    employer = _clean(item.get("employer"))
    if not name or not employer:
        return False
    if len(name) < 2 or name in {"岗位", "职位", "招聘岗位"}:
        return False
    requirements = [
        item.get("education_req"),
        item.get("major_req"),
        item.get("political_req"),
        item.get("fresh_grad_req"),
        item.get("age_req"),
        item.get("physical_req"),
    ]
    return any(_clean(x) for x in requirements)


def parse_announcement(db: Session, rec: RecruitmentInfo) -> dict[str, Any]:
    run = JobParseRun(
        recruitment_id=rec.recruitment_id,
        status="running",
        model=None,
        created_at=datetime.now(),
    )
    db.add(run)
    db.flush()
    try:
        raw = _call(_prompt(rec))
        data = _extract_json(raw)
        positions = [item for item in (data.get("positions") or []) if isinstance(item, dict)]
        valid = [item for item in positions if _valid_position(item)]
        inserted = []
        for item in valid:
            post = PolicePost(
                recruitment_id=rec.recruitment_id,
                job_name=_clean(item.get("job_name")),
                employer=_clean(item.get("employer")),
                province=_clean(item.get("province")) or (rec.region or "")[:50],
                city=_clean(item.get("city")),
                job_code=_clean(item.get("job_code")),
                category=rec.category,
                plan_count=_int(item.get("plan_count")),
                education_req=_clean(item.get("education_req")),
                major_req=_clean(item.get("major_req")),
                political_req=_clean(item.get("political_req")),
                fresh_grad_req=_clean(item.get("fresh_grad_req")),
                grassroots_years=_int(item.get("grassroots_years")),
                age_req=_clean(item.get("age_req")),
                physical_req=_clean(item.get("physical_req")),
                registration_end=_clean(item.get("registration_end")) or rec.registration_end,
                official_url=rec.url,
                source=rec.source_name or "招考公告",
                evidence_json=item.get("evidence") or {},
                parse_status="parsed",
                parse_confidence=float(item.get("confidence") or 0),
                status=1,
                updated_at=datetime.now(),
            )
            db.add(post)
            db.flush()
            inserted.append(post.post_id)
        rec.parse_status = "parsed" if inserted else "needs_review"
        rec.parsed_at = datetime.now()
        rec.parse_confidence = max([float(i.get("confidence") or 0) for i in valid] or [0])
        run.status = "ok" if inserted else "no_positions"
        run.error = None if inserted else "公告未提供明确岗位明细"
        db.commit()
        return {
            "recruitment_id": rec.recruitment_id,
            "title": rec.title,
            "status": run.status,
            "positions": valid,
            "inserted_post_ids": inserted,
            "error": run.error,
        }
    except Exception as exc:
        rec.parse_status = "failed"
        run.status = "failed"
        run.error = str(exc)[:500]
        db.commit()
        return {
            "recruitment_id": rec.recruitment_id,
            "title": rec.title,
            "status": "failed",
            "positions": [],
            "inserted_post_ids": [],
            "error": str(exc)[:500],
        }
