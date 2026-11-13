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

SUPPORTED_SCOPES = frozenset({"forum.post", "forum.comment", "forum.media", "forum.all"})
# media 视为 comment（当前无多模态模型）；all 展开为 post+comment
SCOPE_ALIASES = {"forum.media": ["forum.comment"], "forum.all": ["forum.post", "forum.comment"]}
MATCH_OPERATORS = frozenset(
    {
        "lexicon", "regex", "pattern", "keyword_all", "keyword_any",
        "ner_target", "ner_org",
        "object_in", "behavior_in", "topic_in",
        # 声明式算子：条款可写、编译保留，但当前无执行器（不参与打分，不报错）
        "intent", "multimodal", "claim_type", "source", "repetitive_posting", "target",
    }
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
# 声明式算子：保留在规则里但不参与打分
DECLARATIVE_OPERATORS = frozenset(
    {"intent", "multimodal", "claim_type", "source", "repetitive_posting", "target"}
)
# 枚举类算子：按"文本是否包含枚举值"粗判（中文枚举可用，英文枚举不命中）
ENUM_OPERATORS = frozenset({"object_in", "behavior_in", "topic_in", "ner_target", "ner_org"})
CONTEXT_DETECTORS = {
    "is_news_report": re.compile(r"(警方通报|据.{0,6}报道|新闻|通告|官方通报|案件的?通报)"),
    "is_anti_fraud_education": re.compile(r"(如何防范|防骗|反诈|警惕|识别.{0,4}诈骗|避免上当)"),
    "is_help_seeking": re.compile(r"(求助|怎么办|有人威胁我|我被|谁能帮|求救)"),
    "is_quote_of_news": re.compile(r"(引用|转自|来源[:：])"),
    "is_legal_discussion": re.compile(r"(法律|第.{1,3}条|判例|司法解释)"),
}
PERSON_REF_RE = re.compile(r"(@|你|您|他|她|楼主|同学|老师|这位|那人|这货|家伙)")
SELF_REF_RE = re.compile(r"(我|自己|本人|俺)")
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
            # 修饰条件需要 target 等原始信息（自嘲/他人指代判定）
            "raw_dsl": self.raw_dsl,
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
    out: List[str] = []
    for item in scopes:
        if item not in SUPPORTED_SCOPES:
            continue
        for expanded in SCOPE_ALIASES.get(item, [item]):
            if expanded not in out:
                out.append(expanded)
    return out


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
        if operator == "pattern":
            operator = "regex"
        if operator in DECLARATIVE_OPERATORS:
            issues.append(
                _issue(pid, "match_operator_deferred", f"算子 {operator} 暂未实现，仅保留声明", "warning")
            )
            cleaned.append({operator: value})
            continue
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
                _issue(pid, "modifier_condition_unknown", f"未注册上下文条件：{condition}", "warning")
            )
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
            if key == "mask":
                out["mask"] = "0.75 - 0.90"
                issues.append(
                    _issue(pid, "threshold_defaulted", "缺少 mask 档，已按 0.75 - 0.90 兜底", "warning")
                )
                continue
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
    unknown_keys = set(dsl) - {"scope", "match", "target", "context_modifiers", "thresholds"}
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


def lexicon_dir(vault_dir: str) -> Path:
    """词表目录：<vault>/AI舆情审核知识库/模型与规则/词表。"""
    return Path(vault_dir) / DEFAULT_SUBVAULT / "模型与规则" / "词表"


def load_lexicons(vault_dir: str) -> Dict[str, List[str]]:
    """读取 <词表>/<name>.yaml|txt|json → {name: [词条]}。

    词表缺失时返回空 dict；编译器只告警不报错（由调用方决定是否阻断发布）。
    """
    root = lexicon_dir(vault_dir)
    out: Dict[str, List[str]] = {}
    if not root.is_dir():
        return out
    for path in sorted(root.glob("*")):
        if path.suffix.lower() not in (".yaml", ".yml", ".json", ".txt"):
            continue
        name = path.stem
        if not LEXICON_RE.match(name):
            continue
        try:
            if path.suffix.lower() == ".txt":
                terms = [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines()]
            else:
                data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                terms = data.get("terms") if isinstance(data, dict) else data
        except (OSError, yaml.YAMLError):
            continue
        if isinstance(terms, list):
            clean = sorted({str(t).strip() for t in terms if str(t).strip()})
            if clean:
                out[name] = clean
    return out


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


def compile_ruleset(
    library: Library,
    include_issues: bool = True,
    vault_dir: Optional[str] = None,
    lexicons: Optional[Dict[str, List[str]]] = None,
) -> Dict[str, Any]:
    """编译成规则集。哈希只覆盖规则内容（不含编译时间），保证可复算。"""
    if lexicons is None and vault_dir:
        lexicons = load_lexicons(vault_dir)
    lexicons = lexicons or {}
    rules = [p.to_rule() for p in library.policies]
    for rule in rules:
        needed = {
            str(item["lexicon"])
            for item in rule.get("match", {}).get("any", [])
            if isinstance(item, dict) and "lexicon" in item
        }
        if needed:
            rule["lexicon_terms"] = {n: lexicons.get(n, []) for n in sorted(needed)}
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
        "lexicons": lexicons,
        "missing_lexicons": sorted(set(library.required_lexicons()) - set(lexicons)),
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


def _apply_modifiers(text: str, rule: Dict[str, Any], strength: float) -> Tuple[float, List[str]]:
    """只实现可判定的修饰条件：自指/自嘲、他人指代。

    其余条件（如 is_quote_of_news）无执行器，返回原强度并记 note。
    """
    notes: List[str] = []
    target = (rule.get("raw_dsl") or {}).get("target") or {}
    modifiers = rule.get("modifiers") or []
    self_ref = bool(SELF_REF_RE.search(text))
    other_ref = bool(PERSON_REF_RE.search(text))

    for item in modifiers:
        cond = item.get("if")
        weight = float(item.get("weight") or 0)
        detector = CONTEXT_DETECTORS.get(str(cond))
        if detector is not None:
            if detector.search(text):
                strength = max(0.0, strength * (1 + weight))
                notes.append(f"{cond}:{weight}")
            continue
        if cond in ("target_is_self", "is_self_deprecation", "is_self_reference"):
            if self_ref:
                strength = max(0.0, strength * (1 + weight))
                notes.append(f"{cond}:{weight}")
        elif cond == "target_is_public_figure" and other_ref:
            strength = max(0.0, strength * (1 + weight))
            notes.append(f"{cond}:{weight}")

    if target.get("requires_person_reference") and not other_ref and self_ref:
        strength = max(0.0, strength * 0.4)
        notes.append("target:requires_person_reference(自指降权)")
    return strength, notes


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
        elif operator == "lexicon":
            terms = rule.get("lexicon_terms") or {}
            words = terms.get(str(value)) or []
            hit = [w for w in words if w and w in text]
            if hit:
                strength = max(strength, 0.80)
                reasons.append(f"lexicon:{value}:" + ",".join(hit[:3]))
        elif operator in ENUM_OPERATORS and isinstance(value, list):
            hits = [str(v) for v in value if str(v) and str(v) in text]
            if hits:
                strength = max(strength, 0.70)
                reasons.append(f"{operator}:" + ",".join(hits[:3]))
        elif operator in ("keyword_all", "keyword_any") and isinstance(value, list):
            words = [str(w) for w in value]
            hits = [w for w in words if w and w in text]
            if operator == "keyword_all" and words and len(hits) == len(words):
                strength = max(strength, 0.95)
                reasons.append("keyword_all:" + ",".join(hits))
            elif operator == "keyword_any" and hits:
                strength = max(strength, 0.75)
                reasons.append("keyword_any:" + ",".join(hits))
    strength, notes = _apply_modifiers(text, rule, strength)
    reasons.extend(notes)
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
