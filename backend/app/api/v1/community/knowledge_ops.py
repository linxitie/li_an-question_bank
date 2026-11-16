"""知识运营接口（M0 影子期）：政策库读取 / 试编译 / 试判 / 提案列表。

边界（为什么这样设计）：
- 全部接口只读 vault；唯一写动作「发布规则集」由 MODERATION_VAULT_WRITE 控制，
  默认关闭——知识库与生产运行时之间必须有一道人工闸门。
- 编译不落盘、不缓存到数据库：控制台先看错误，再决定是否发布；
  线上判定只读编译产物，不直接读 Markdown。
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ....core.config import settings
from ....core.security import require_admin
from ....models.models import SysUser
from ....services.policy_compiler import (
    DEFAULT_SUBVAULT,
    POLICY_DIRNAME,
    compile_ruleset,
    load_library,
    score_text,
)

router = APIRouter(prefix="/api/admin/knowledge-ops", tags=["管理员端-知识运营"])

FRONTMATTER_RE = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n", re.S)
PROPOSAL_DIR = "收件箱/提案"
CHANGESET_SUBDIR = "产出/变更集"


class CompileRequest(BaseModel):
    dry_run: bool = Field(True, description="true=只试编译；false=按开关决定是否落盘")


class PreviewRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)
    scope: str = Field("forum.comment", pattern="^(forum\\.post|forum\\.comment)$")


def _vault_root() -> Path:
    return Path(settings.MODERATION_VAULT_DIR)


def _subvault() -> Path:
    return _vault_root() / DEFAULT_SUBVAULT


def _library_or_503():
    try:
        return load_library(settings.MODERATION_VAULT_DIR)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"{exc}；请设置环境变量 MODERATION_VAULT_DIR 指向 Obsidian vault 根目录",
        ) from exc


def _frontmatter_of(path: Path) -> Dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}
    try:
        data = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


@router.get("/summary", summary="知识库概览与编译健康度")
def knowledge_summary(_: SysUser = Depends(require_admin)) -> Dict[str, Any]:
    library = _library_or_503()
    ruleset = compile_ruleset(library, include_issues=False)
    warnings = [i.as_dict() for i in library.issues if i.level == "warning"]
    return {
        "vault_dir": str(_vault_root()),
        "policy_root": library.root,
        "scanned": library.scanned,
        "compiled": ruleset["policy_count"],
        "skipped": library.skipped,
        "domains": ruleset["domains"],
        "severity_counts": ruleset["severity_counts"],
        "required_lexicons": ruleset["required_lexicons"],
        "hash": ruleset["hash"],
        "error_count": ruleset["error_count"],
        "warning_count": len(warnings),
        "warnings": warnings[:20],
        "flags": {
            "vault_write": settings.MODERATION_VAULT_WRITE,
            "forum_ai_shadow": settings.FORUM_AI_SHADOW,
        },
    }


@router.get("/policies", summary="条款列表（可按域/严重度筛选）")
def list_policies(
    domain: Optional[str] = Query(None, description="如 07-未成年人保护"),
    severity: Optional[str] = Query(None, description="critical|high|medium|low"),
    _: SysUser = Depends(require_admin),
) -> Dict[str, Any]:
    library = _library_or_503()
    items = [p.to_summary() for p in library.policies]
    if domain:
        items = [p for p in items if p["domain"] == domain]
    if severity:
        items = [p for p in items if p["severity"] == severity]
    return {"total": len(items), "items": items}


@router.get("/policies/{policy_id}", summary="条款详情（含 policy_dsl）")
def get_policy(policy_id: str, _: SysUser = Depends(require_admin)) -> Dict[str, Any]:
    library = _library_or_503()
    for policy in library.policies:
        if policy.id == policy_id:
            detail = policy.to_detail()
            detail["issues"] = [
                i.as_dict() for i in library.issues if i.policy_id == policy_id
            ]
            return detail
    raise HTTPException(status_code=404, detail=f"条款不存在或未启用：{policy_id}")


@router.post("/compile", summary="试编译（dry_run=true 时绝不写盘）")
def compile_policies(
    payload: CompileRequest,
    _: SysUser = Depends(require_admin),
) -> Dict[str, Any]:
    library = _library_or_503()
    ruleset = compile_ruleset(library)
    issues = ruleset.get("issues", [])
    result: Dict[str, Any] = {
        "hash": ruleset["hash"],
        "policy_count": ruleset["policy_count"],
        "domains": ruleset["domains"],
        "severity_counts": ruleset["severity_counts"],
        "required_lexicons": ruleset["required_lexicons"],
        "error_count": ruleset["error_count"],
        "issues": issues[:50],
        "dry_run": payload.dry_run,
        "written_to": None,
    }
    if payload.dry_run:
        return result
    if not settings.MODERATION_VAULT_WRITE:
        raise HTTPException(
            status_code=403,
            detail="发布已禁用：设置 MODERATION_VAULT_WRITE=1 并重启后才能写盘",
        )
    if ruleset["error_count"]:
        raise HTTPException(status_code=409, detail="存在编译错误，禁止发布")
    out_dir = _subvault() / CHANGESET_SUBDIR
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = out_dir / f"ruleset_{stamp}_{ruleset['hash'][:8]}.json"
    target.write_text(
        json.dumps(ruleset, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    result["written_to"] = str(target)
    return result


@router.post("/preview", summary="影子试判一条文本（不写库、不影响展示）")
def preview_score(
    payload: PreviewRequest, _: SysUser = Depends(require_admin)
) -> Dict[str, Any]:
    library = _library_or_503()
    ruleset = compile_ruleset(library, include_issues=False)
    scored = score_text(
        payload.text,
        ruleset,
        scope=payload.scope,
        enforce_block=settings.MODERATION_ENFORCE_BLOCK,
    )
    scored["hash"] = ruleset["hash"]
    scored["policy_count"] = ruleset["policy_count"]
    return scored


@router.get("/proposals", summary="待审提案列表（收件箱/提案）")
def list_proposals(_: SysUser = Depends(require_admin)) -> Dict[str, Any]:
    proposal_dir = _subvault() / PROPOSAL_DIR
    if not proposal_dir.is_dir():
        return {"total": 0, "items": [], "proposal_dir": str(proposal_dir)}
    items: List[Dict[str, Any]] = []
    for path in sorted(proposal_dir.glob("*.md")):
        if path.name.startswith("_"):
            continue
        meta = _frontmatter_of(path)
        items.append(
            {
                "file": path.name,
                "id": meta.get("id"),
                "title": meta.get("title"),
                "status": meta.get("status", "pending"),
                "updated": meta.get("updated"),
                "path": str(path.relative_to(_vault_root())).replace("\\", "/"),
            }
        )
    return {"total": len(items), "items": items, "proposal_dir": str(proposal_dir)}
