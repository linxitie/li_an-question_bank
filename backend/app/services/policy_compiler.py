"""政策库编译器：Obsidian 条款 Markdown → 可执行规则集（ruleset）。

为什么需要这一层：
- 知识库是「人读 + 机读同源」的文本，但运行时不能直接解析 Markdown——
  一条 DSL 写错就可能变成线上误判。编译把文本变成**带哈希的产物**，
  让每次上线可复现、可回滚、可对比。
- 编译只读：本模块不写 vault，发布动作由调用方在开关下完成。

两条硬约定：
1. 确定性：条款按 id 排序，哈希基于规范化 JSON，同样输入必得同样哈希。
2. 容错：坏条款收集为 issues，不让整库不可用（控制台先看错误再决定是否发布）。
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

DEFAULT_SUBVAULT = "AI舆情审核知识库"
POLICY_DIRNAME = "政策库"
SUMMARY_DIRNAME = "00-总纲"
SCHEMA_VERSION = 1

POLICY_ID_RE = re.compile(r"^P-\d{2}-\d{3}$")
LEXICON_RE = re.compile(r"^[a-z0-9_]{2,64}$")
FRONTMATTER_RE = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n", re.S)

SUPPORTED_SCOPES = frozenset({"forum.post", "forum.comment"})
MATCH_OPERATORS = frozenset(
    {"lexicon", "regex", "ner_target", "ner_org", "keyword_all", "keyword_any"}
)
CONTEXT_CONDITIONS = frozenset(
    {
        "is_quote_of_news",
        "is_news_report",
        "is_academic_discussion",
        "is_help_seeking",
        "is_self_disclosure",
        "is_medical_context",
        "is_sex_education",
        "is_official_source",
        "is_research",
        "is_counter_terror_analysis",
        "is_fiction",
        "is_peer_chat",
        "is_self_deprecation",
        "is_tech_explainer",
        "is_law_discussion",
        "is_after_exam_discussion",
        "is_anti_fraud_education",
        "is_official_notice",
        "is_security_research",
        "is_religious_study",
        "is_vent_about_study",
        "is_quote_of_report",
        "is_job_legit",
        "is_self_reference",
    }
)
SEVERITIES = frozenset({"critical", "high", "medium", "low"})
SEVERITY_WEIGHT = {"critical": 0.95, "high": 0.80, "medium": 0.60, "low": 0.40}
THRESHOLD_KEYS = ("allow", "hold", "mask", "block")


@dataclass
class CompileIssue:
    """一条编译问题。level=error 的条款不会进入规则集。"""

    policy_id: str
    level: str
    code: str
    message: str

    def as_dict(self) -> Dict[str, str]:
        return {
            "policy_id": self.policy_id,
            "level": self.level,
            "code": self.code,
            "message": self.message,
        }


@dataclass
class Policy:
    """一条已通过结构校验的条款。"""

    id: str
    domain: str
    title: str
    severity: str
    action: str
    status: str
    version: int
    owner: str
    review_due: str
    source_path: str
    scope: List[str]
    match: Dict[str, Any]
    modifiers: List[Dict[str, Any]]
    thresholds: Dict[str, str]
    examples_positive: List[str] = field(default_factory=list)
    examples_negative: List[str] = field(default_factory=list)
    raw_dsl: Dict[str, Any] = field(default_factory=dict)

    def to_summary(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "domain": self.domain,
            "title": self.title,
            "severity": self.severity,
            "action": self.action,
            "status": self.status,
            "version": self.version,
            "owner": self.owner,
            "review_due": self.review_due,
            "source_path": self.source_path,
            "scope": list(self.scope),
            "examples_positive": list(self.examples_positive),
            "examples_negative": list(self.examples_negative),
        }

    def to_detail(self) -> Dict[str, Any]:
        data = self.to_summary()
        data["policy_dsl"] = self.raw_dsl
        return data

    def to_rule(self) -> Dict[str, Any]:
        """运行时规则：只保留判定需要的东西，不带 examples。"""
        return {
            "id": self.id,
            "domain": self.domain,
            "title": self.title,
            "severity": self.severity,
            "action": self.action,
            "version": self.version,
            "scope": list(self.scope),
            "match": self.match,
            "context_modifiers": self.modifiers,
            "thresholds": self.thresholds,
        }


@dataclass
class Library:
    """一次全库读取的结果。"""

    root: str
    policies: List[Policy] = field(default_factory=list)
    issues: List[CompileIssue] = field(default_factory=list)
    scanned: int = 0
    skipped: int = 0

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.level == "error")

    def required_lexicons(self) -> List[str]:
        names = set()
        for policy in self.policies:
            for item in policy.match.get("any", []) + policy.match.get("all", []):
                if isinstance(item, dict) and "lexicon" in item:
                    names.add(str(item["lexicon"]))
        return sorted(names)


def _issue(pid: str, code: str, message: str, level: str = "error") -> CompileIssue:
    return CompileIssue(policy_id=pid or "-", level=level, code=code, message=message)


def _split_frontmatter(text: str) -> Dict[str, Any]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        raise ValueError("缺少 --- frontmatter --- 段")
    data = yaml.safe_load(match.group(1)) or {}
    if not isinstance(data, dict):
        raise ValueError("frontmatter 不是键值结构")
    return data


def _load_dsl(value: Any, pid: str, issues: List[CompileIssue]) -> Optional[Dict[str, Any]]:
    if value is None:
        issues.append(_issue(pid, "dsl_missing", "缺少 policy_dsl"))
        return None
    if isinstance(value, str):
        try:
            parsed = yaml.safe_load(value)
        except yaml.YAMLError as exc:
            issues.append(_issue(pid, "dsl_unparsable", f"policy_dsl 不是合法 YAML：{exc}"))
            return None
    else:
        parsed = value
    if not isinstance(parsed, dict):
        issues.append(_issue(pid, "dsl_not_mapping", "policy_dsl 必须是映射结构"))
        return None
    return parsed


def _validate_scope(dsl: Dict[str, Any], pid: str, issues: List[CompileIssue]) -> List[str]:
    raw = dsl.get("scope")
    if isinstance(raw, str):
        scopes = [s.strip() for s in raw.split(",") if s.strip()]
    elif isinstance(raw, list):
        scopes = [str(s).strip() for s in raw]
    else:
        issues.append(_issue(pid, "scope_missing", "policy_dsl 缺少 scope"))
        return []
    unknown = [s for s in scopes if s not in SUPPORTED_SCOPES]
    if unknown:
        issues.append(_issue(pid, "scope_unknown", f"不支持的 scope：{unknown}"))
    return [s for s in scopes if s in SUPPORTED_SCOPES]


def _validate_conditions(
    items: Any, pid: str, issues: List[CompileIssue]
) -> List[Dict[str, Any]]:
    """match.any / match.all 的算子白名单校验。"""
    if items is None:
        return []
    if not isinstance(items, list):
        issues.append(_issue(pid, "match_not_list", "match.any 必须是列表"))
        return []
    cleaned: List[Dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict) or len(item) != 1:
            issues.append(_issue(pid, "match_item_shape", f"算子项必须是单键映射：{item!r}"))
            continue
        (operator, value), = item.items()
        if operator not in MATCH_OPERATORS:
            issues.append(
                _issue(pid, "match_operator_unknown", f"未知算子：{operator}")
            )
            continue
        if operator == "regex":
            try:
                re.compile(str(value))
            except re.error as exc:
                issues.append(_issue(pid, "regex_invalid", f"正则无法编译：{exc}"))
                continue
        if operator == "lexicon" and not LEXICON_RE.match(str(value)):
            issues.append(_issue(pid, "lexicon_name_invalid", f"词表名不合法：{value}"))
            continue
        cleaned.append({operator: value})
    return cleaned


def _validate_modifiers(
    items: Any, pid: str, issues: List[CompileIssue]
) -> List[Dict[str, Any]]:
    if items is None:
        return []
    if not isinstance(items, list):
        issues.append(_issue(pid, "modifiers_not_list", "context_modifiers 必须是列表"))
        return []
    cleaned = []
    for item in items:
        if not isinstance(item, dict) or "if" not in item or "weight" not in item:
            issues.append(_issue(pid, "modifier_shape", f"修正项需含 if/weight：{item!r}"))
            continue
        condition = str(item["if"])
        if condition not in CONTEXT_CONDITIONS:
            issues.append(
                _issue(pid, "modifier_condition_unknown", f"未知上下文条件：{condition}")
            )
            continue
        try:
            weight = float(item["weight"])
        except (TypeError, ValueError):
            issues.append(_issue(pid, "modifier_weight_invalid", f"weight 不是数字：{item['weight']}"))
            continue
        if not -1.0 <= weight <= 1.0:
            issues.append(_issue(pid, "modifier_weight_range", f"weight 超范围：{weight}"))
            continue
        cleaned.append({"if": condition, "weight": weight})
    return cleaned


def _valid_threshold(raw: Any) -> bool:
    """阈值写法只认三种：< 0.40 / 0.40 - 0.80 / >= 0.92[ && FLAG=1]。"""
    text = str(raw).strip()
    if re.fullmatch(r"<\s*\d(?:\.\d+)?", text):
        return True
    if re.fullmatch(r"\d(?:\.\d+)?\s*-\s*\d(?:\.\d+)?", text):
        return True
    if re.fullmatch(r">=\s*\d(?:\.\d+)?(?:\s*&&\s*[A-Z_]+=\d+)?", text):
        return True
    return False


def _validate_thresholds(
    raw: Any, pid: str, issues: List[CompileIssue]
) -> Dict[str, str]:
    if not isinstance(raw, dict):
        issues.append(_issue(pid, "thresholds_missing", "policy_dsl 缺少 thresholds"))
        return {}
    out: Dict[str, str] = {}
    for key in THRESHOLD_KEYS:
        if key not in raw:
            issues.append(_issue(pid, "threshold_missing", f"缺少阈值档 {key}"))
            continue
        if not _valid_threshold(raw[key]):
            issues.append(
                _issue(pid, "threshold_format", f"阈值 {key} 写法不合法：{raw[key]!r}")
            )
            continue
        out[key] = str(raw[key]).strip()
    return out


def parse_policy_file(path: Path, root: Path) -> Tuple[Optional[Policy], List[CompileIssue]]:
    """解析单个条款文件；结构不合规时返回 (None, issues)。"""
    issues: List[CompileIssue] = []
    try:
        text = path.read_text(encoding="utf-8")
        meta = _split_frontmatter(text)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        return None, [_issue("-", "file_unreadable", f"{path.name}: {exc}")]

    pid = str(meta.get("id") or "")
    if not POLICY_ID_RE.match(pid):
        return None, [_issue(pid, "policy_id_invalid", f"条款 id 不合规：{pid!r}")]

    severity = str(meta.get("severity") or "")
    if severity not in SEVERITIES:
        return None, [_issue(pid, "severity_invalid", f"severity 不合法：{severity!r}")]
    action = str(meta.get("action") or "")
    if not re.match(r"^A[0-5]", action):
        return None, [_issue(pid, "action_invalid", f"action 必须从 A0–A5 起头：{action!r}")]

    dsl = _load_dsl(meta.get("policy_dsl"), pid, issues)
    if dsl is None:
        return None, issues
    unknown_keys = set(dsl) - {"scope", "match", "context_modifiers", "thresholds"}
    if unknown_keys:
        issues.append(
            _issue(pid, "dsl_unknown_key", f"DSL 含未知顶层字段：{sorted(unknown_keys)}")
        )
    scope = _validate_scope(dsl, pid, issues)
    match_raw = dsl.get("match") if isinstance(dsl.get("match"), dict) else {}
    if not isinstance(dsl.get("match"), dict):
        issues.append(_issue(pid, "match_missing", "DSL 缺少 match 映射"))
    any_items = _validate_conditions(match_raw.get("any"), pid, issues)
    all_items = _validate_conditions(match_raw.get("all"), pid, issues)
    if not any_items and not all_items:
        issues.append(_issue(pid, "match_empty", "match.any 与 match.all 均为空"))
    modifiers = _validate_modifiers(dsl.get("context_modifiers"), pid, issues)
    thresholds = _validate_thresholds(dsl.get("thresholds"), pid, issues)

    if any(i.level == "error" for i in issues) or not scope or not thresholds:
        return None, issues

    policy = Policy(
        id=pid,
        domain=str(meta.get("domain") or ""),
        title=str(meta.get("title") or pid),
        severity=severity,
        action=action,
        status=str(meta.get("status") or "draft"),
        version=int(meta.get("version") or 1),
        owner=str(meta.get("owner") or ""),
        review_due=str(meta.get("review_due") or ""),
        source_path=str(path.relative_to(root.parent.parent)).replace("\\", "/"),
        scope=scope,
        match={"any": any_items, "all": all_items},
        modifiers=modifiers,
        thresholds=thresholds,
        examples_positive=[str(x) for x in (meta.get("examples_positive") or [])],
        examples_negative=[str(x) for x in (meta.get("examples_negative") or [])],
        raw_dsl=dsl,
    )
    if len(policy.examples_positive) < 2 or len(policy.examples_negative) < 2:
        issues.append(
            _issue(pid, "examples_insufficient", "正例/反例各至少 2 条", level="warning")
        )
    return policy, issues


def resolve_policy_root(vault_dir: str) -> Path:
    """vault 根 → 政策库目录。缺目录时由调用方转成 503。"""
    return Path(vault_dir) / DEFAULT_SUBVAULT / POLICY_DIRNAME


def load_library(vault_dir: str) -> Library:
    """读取全库。00-总纲 等非条款文档跳过；非 active 条款跳过并记 warning。"""
    root = resolve_policy_root(vault_dir)
    if not root.is_dir():
        raise FileNotFoundError(f"政策库目录不存在：{root}")
    library = Library(root=str(root))
    for path in sorted(root.rglob("*.md")):
        if SUMMARY_DIRNAME in path.parts:
            continue
        library.scanned += 1
        policy, issues = parse_policy_file(path, root)
        library.issues.extend(issues)
        if policy is None:
            library.skipped += 1
            continue
        if policy.status != "active":
            library.skipped += 1
            library.issues.append(
                _issue(policy.id, "status_inactive", f"状态 {policy.status}，不参与编译", "warning")
            )
            continue
        library.policies.append(policy)
    library.policies.sort(key=lambda p: p.id)
    return library


def compile_ruleset(library: Library, include_issues: bool = True) -> Dict[str, Any]:
    """编译成规则集。哈希只覆盖规则内容（不含编译时间），保证可复算。"""
    rules = [p.to_rule() for p in library.policies]
    payload = {"schema_version": SCHEMA_VERSION, "rules": rules}
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    severity_counts = {sev: sum(1 for r in rules if r["severity"] == sev) for sev in sorted(SEVERITIES)}
    result: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "hash": digest,
        "compiled_at": datetime.now().isoformat(timespec="seconds"),
        "policy_count": len(rules),
        "domains": sorted({r["domain"] for r in rules}),
        "severity_counts": severity_counts,
        "required_lexicons": library.required_lexicons(),
        "scanned": library.scanned,
        "skipped": library.skipped,
        "error_count": library.error_count,
        "rules": rules,
    }
    if include_issues:
        result["issues"] = [i.as_dict() for i in library.issues]
    return result


def _lower_bound(spec: Optional[str]) -> Optional[float]:
    """把 '0.40 - 0.80' / '>= 0.92 && FLAG=1' / '< 0.40' 取成下界。"""
    if not spec:
        return None
    text = str(spec)
    if "&&" in text:
        text = text.split("&&")[0]
    numbers = [float(n) for n in re.findall(r"\d(?:\.\d+)?", text)]
    if not numbers:
        return None
    if text.strip().startswith(">="):
        return numbers[0]
    if "-" in text and len(numbers) >= 2:
        return numbers[0]
    return numbers[0]


def bucket_for(score: float, thresholds: Dict[str, str]) -> str:
    """按条款阈值分档：block > mask > hold > allow。"""
    block = _lower_bound(thresholds.get("block"))
    mask = _lower_bound(thresholds.get("mask"))
    hold = _lower_bound(thresholds.get("hold"))
    if block is not None and score >= block:
        return "block"
    if mask is not None and score >= mask:
        return "mask"
    if hold is not None and score >= hold:
        return "hold"
    return "allow"


def _match_rule(text: str, rule: Dict[str, Any]) -> Tuple[float, List[str]]:
    """返回 (强度 0–1, 命中原因)。lexicon 未注入时不算命中（如实说明）。"""
    strength = 0.0
    reasons: List[str] = []
    for item in rule.get("match", {}).get("any", []):
        if not isinstance(item, dict) or len(item) != 1:
            continue
        (operator, value), = item.items()
        if operator == "regex":
            try:
                if re.search(str(value), text):
                    strength = max(strength, 0.85)
                    reasons.append(f"regex:{value}")
            except re.error:
                continue
        elif operator in ("keyword_all", "keyword_any") and isinstance(value, list):
            words = [str(w) for w in value]
            hits = [w for w in words if w and w in text]
            if operator == "keyword_all" and words and len(hits) == len(words):
                strength = max(strength, 0.95)
                reasons.append("keyword_all:" + ",".join(hits))
            elif operator == "keyword_any" and hits:
                strength = max(strength, 0.75)
                reasons.append("keyword_any:" + ",".join(hits))
    return strength, reasons


def score_text(
    text: str,
    ruleset: Dict[str, Any],
    scope: str = "forum.comment",
    enforce_block: bool = False,
) -> Dict[str, Any]:
    """影子打分：仅规则骨架（词表未注入时只算正则/关键词），不是模型分。"""
    hits: List[Dict[str, Any]] = []
    unresolved = 0
    for rule in ruleset.get("rules", []):
        if scope not in rule.get("scope", []):
            continue
        strength, reasons = _match_rule(text, rule)
        if strength <= 0:
            unresolved += 1 if any(
                isinstance(i, dict) and "lexicon" in i for i in rule.get("match", {}).get("any", [])
            ) else 0
            continue
        base = SEVERITY_WEIGHT.get(rule.get("severity", ""), 0.5)
        score = round(min(0.99, base * strength), 3)
        hits.append(
            {
                "id": rule["id"],
                "title": rule.get("title", ""),
                "severity": rule.get("severity", ""),
                "score": score,
                "bucket": bucket_for(score, rule.get("thresholds", {})),
                "reasons": reasons,
                "policy_action": rule.get("action", ""),
            }
        )
    hits.sort(key=lambda h: h["score"], reverse=True)
    top = hits[0] if hits else None
    bucket = top["bucket"] if top else "allow"
    if bucket == "block" and not enforce_block:
        bucket = "mask"
    return {
        "score": top["score"] if top else 0.0,
        "bucket": bucket,
        "action": top["policy_action"] if top else "A0 放行",
        "hits": hits,
        "rules_without_lexicon": unresolved,
        "note": "词表未注入时仅正则/关键词参与打分；该分数用于影子评测，不代表线上判定。",
    }
