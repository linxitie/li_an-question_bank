"""题目域图片资产登记（四库知识图谱 P1）。

职责：扫描题目正文/选项/解析/题组材料中的图片引用，解析为本地文件或
data URI，按内容 SHA-256 幂等登记到 `media_assets`。本模块只做投影，
不改变题目正文、题组关系与现有 `/static` 读取路径。

安全边界：
- 只允许 `/static/...` 映射到 `backend/app/static`，拒绝路径穿越；
- 外部 URL、历史遗留的歧义 marker 不猜测，登记为 missing；
- 默认 dry-run 由脚本控制，本模块不自行 commit。
"""
from __future__ import annotations

import base64
import hashlib
import html
import json
import mimetypes
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Iterator
from urllib.parse import unquote, urlsplit

from sqlalchemy.orm import Session

from app.foundation.config import BACKEND_DIR
from app.foundation.stores.object import build_object_store
from app.models.media_asset import MediaAsset

STATIC_ROOT = BACKEND_DIR / "app" / "static"
QUESTION_IMAGE_DIR = "questions"

KIND_BY_LOC = {
    "stem": "question_stem",
    "option": "question_option",
    "analysis": "question_analysis",
    "group_content": "group_material",
    "group_images": "group_material",
}
KIND_PRIORITY = (
    "question_stem",
    "question_option",
    "question_analysis",
    "group_material",
)
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}

_IMG_TAG_RE = re.compile(
    r"<img\b[^>]*?\bsrc\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s>]+))",
    re.IGNORECASE | re.DOTALL,
)
_MARKER_RE = re.compile(r"\[IMAGE:([^\]\s]+)\]", re.IGNORECASE)
_DATA_URI_RE = re.compile(
    r"^data:(?P<mime>[\w.+-]+/[\w.+-]+)?(?:;[^,]*)?;base64,(?P<body>.*)$",
    re.IGNORECASE | re.DOTALL,
)


@dataclass(frozen=True)
class MediaRef:
    """一条图片引用；resolved 时必有 path 或 inline，missing 时 canonical 可追溯。"""

    loc: str
    owner_type: str
    owner_id: int
    kind: str
    raw: str
    canonical: str
    status: str
    reason: str | None = None
    path: Path | None = None
    inline: bytes | None = None
    content_type: str | None = None

    @property
    def is_resolved(self) -> bool:
        return self.status == "resolved"


@dataclass
class RegisterReport:
    refs_total: int = 0
    refs_unique: int = 0
    resolved_refs: int = 0
    missing_refs: int = 0
    ambiguous_refs: int = 0
    inline_refs: int = 0
    external_refs: int = 0
    assets_unique: int = 0
    active_assets: int = 0
    missing_assets: int = 0
    inserted: int = 0
    updated: int = 0
    reused: int = 0
    by_kind: dict[str, int] = field(default_factory=dict)
    by_loc: dict[str, int] = field(default_factory=dict)
    missing: list[dict[str, Any]] = field(default_factory=list)

    def bump(self, bucket: dict[str, int], key: str) -> None:
        bucket[key] = bucket.get(key, 0) + 1

    def as_dict(self) -> dict[str, Any]:
        total = self.refs_total or 1
        return {
            "refs_total": self.refs_total,
            "refs_unique": self.refs_unique,
            "resolved_refs": self.resolved_refs,
            "missing_refs": self.missing_refs,
            "ambiguous_refs": self.ambiguous_refs,
            "inline_refs": self.inline_refs,
            "external_refs": self.external_refs,
            "resolvable_rate": round(self.resolved_refs / total, 4),
            "assets_unique": self.assets_unique,
            "active_assets": self.active_assets,
            "missing_assets": self.missing_assets,
            "inserted": self.inserted,
            "updated": self.updated,
            "reused": self.reused,
            "by_kind": dict(sorted(self.by_kind.items())),
            "by_loc": dict(sorted(self.by_loc.items())),
            "missing": self.missing,
        }


def extract_media_refs(text: Any) -> list[str]:
    """从一段富文本中提取 <img src> 与 [IMAGE:...]；去重保序。"""
    if text is None:
        return []
    if not isinstance(text, str):
        text = json.dumps(text, ensure_ascii=False)
    decoded = html.unescape(text)
    found: list[str] = []
    for match in _IMG_TAG_RE.finditer(decoded):
        value = (match.group(1) or match.group(2) or match.group(3) or "").strip()
        if value:
            found.append(value)
    for match in _MARKER_RE.finditer(decoded):
        value = match.group(1).strip()
        if value:
            found.append(value)
    seen: set[str] = set()
    unique: list[str] = []
    for value in found:
        if value not in seen:
            seen.add(value)
            unique.append(value)
    return unique


def _iter_strings(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _iter_strings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _iter_strings(item)


def parse_jsonish(value: Any) -> Any:
    """options/shared_content_images 可能是 JSON 字符串、list 或 dict。"""
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith(("{", "[")):
            try:
                return json.loads(stripped)
            except (TypeError, ValueError):
                return value
    return value


def _safe_static_path(static_root: Path, relative: str) -> Path | None:
    relative = unquote(relative).replace("\\", "/").lstrip("/")
    if not relative or ".." in relative.split("/"):
        return None
    candidate = (static_root / relative).resolve()
    root = static_root.resolve()
    if candidate != root and root not in candidate.parents:
        return None
    return candidate


def _content_type_for_path(path: Path | None, fallback: str | None = None) -> str:
    if fallback:
        return fallback
    if path is not None:
        guessed, _ = mimetypes.guess_type(str(path))
        if guessed:
            return guessed
    return "application/octet-stream"


def _canonical_for_path(path: Path, static_root: Path) -> str:
    try:
        return path.resolve().relative_to(static_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def resolve_media_ref(
    raw: str,
    *,
    loc: str,
    owner_type: str,
    owner_id: int,
    static_root: Path = STATIC_ROOT,
) -> MediaRef:
    """把一条引用解析为本地文件 / data URI；无法唯一解析一律 missing。"""
    kind = KIND_BY_LOC.get(loc, "question_media")
    value = raw.strip()

    data_match = _DATA_URI_RE.match(value)
    if data_match:
        mime = (data_match.group("mime") or "application/octet-stream").lower()
        try:
            payload = base64.b64decode(data_match.group("body"), validate=False)
        except (ValueError, TypeError):
            return MediaRef(loc, owner_type, owner_id, kind, raw, "inline:invalid",
                            "missing", "invalid_data_uri")
        if not payload:
            return MediaRef(loc, owner_type, owner_id, kind, raw, "inline:empty",
                            "missing", "invalid_data_uri")
        digest = hashlib.sha256(payload).hexdigest()
        return MediaRef(
            loc, owner_type, owner_id, kind, raw, f"inline:{digest}",
            "resolved", path=None, inline=payload, content_type=mime,
        )

    parsed = urlsplit(value)
    if parsed.scheme in {"http", "https"}:
        return MediaRef(loc, owner_type, owner_id, kind, raw, value,
                        "missing", "external_url")
    if parsed.scheme and parsed.scheme != "file":
        return MediaRef(loc, owner_type, owner_id, kind, raw, value,
                        "missing", "unsupported_scheme")

    if value.startswith("/static/"):
        relative = value[len("/static/"):].split("?", 1)[0].split("#", 1)[0]
        path = _safe_static_path(static_root, relative)
        if path is None:
            return MediaRef(loc, owner_type, owner_id, kind, raw,
                            f"static:{relative}", "missing", "path_traversal")
        canonical = _canonical_for_path(path, static_root)
    elif value.startswith("/"):
        return MediaRef(loc, owner_type, owner_id, kind, raw, value,
                        "missing", "unsupported_absolute_path")
    else:
        # 历史 [IMAGE:] marker：优先按原名找文件（允许显式扩展名），
        # 找不到再补 .png；多义 marker 不做跨文件猜测。
        marker = value.split("?", 1)[0].split("#", 1)[0]
        candidates = [marker] if Path(marker).suffix else [marker, f"{marker}.png"]
        path = None
        for candidate in candidates:
            probe = _safe_static_path(static_root, f"{QUESTION_IMAGE_DIR}/{candidate}")
            if probe is not None and probe.is_file():
                path = probe
                break
        canonical = f"bare:{marker}"
        if path is None:
            return MediaRef(loc, owner_type, owner_id, kind, raw, canonical,
                            "missing", "legacy_marker_unresolved")
        return MediaRef(
            loc, owner_type, owner_id, kind, raw,
            _canonical_for_path(path, static_root), "resolved", path=path,
            content_type=_content_type_for_path(path),
        )

    if not path.is_file():
        return MediaRef(loc, owner_type, owner_id, kind, raw, canonical,
                        "missing", "file_not_found")
    return MediaRef(
        loc, owner_type, owner_id, kind, raw, canonical, "resolved",
        path=path, content_type=_content_type_for_path(path),
    )


def collect_db_refs(
    session: Session,
    *,
    static_root: Path = STATIC_ROOT,
    limit_questions: int | None = None,
    limit_groups: int | None = None,
) -> list[MediaRef]:
    """扫描关系库四类来源，返回去重后的引用清单（按 loc/owner/raw）。"""
    from app.models.models import QuestionBank, QuestionGroup

    refs: list[MediaRef] = []
    seen: set[tuple[str, int, str]] = set()

    def add(loc: str, owner_type: str, owner_id: int, raw: str) -> None:
        key = (loc, owner_id, raw)
        if key in seen:
            return
        seen.add(key)
        refs.append(resolve_media_ref(
            raw, loc=loc, owner_type=owner_type, owner_id=owner_id,
            static_root=static_root,
        ))

    query = session.query(QuestionBank)
    if limit_questions:
        query = query.limit(limit_questions)
    for question in query:
        qid = int(question.question_id)
        for raw in extract_media_refs(question.question_content):
            add("stem", "question", qid, raw)
        options = parse_jsonish(question.options)
        for text in _iter_strings(options):
            for raw in extract_media_refs(text):
                add("option", "question", qid, raw)
        for raw in extract_media_refs(question.answer_analysis):
            add("analysis", "question", qid, raw)

    group_query = session.query(QuestionGroup)
    if limit_groups:
        group_query = group_query.limit(limit_groups)
    for group in group_query:
        gid = int(group.id)
        for raw in extract_media_refs(group.shared_content):
            add("group_content", "group", gid, raw)
        images = parse_jsonish(group.shared_content_images)
        for text in _iter_strings(images):
            for raw in extract_media_refs(text):
                add("group_images", "group", gid, raw)
            # shared_content_images 也可能是纯 URL 列表，不含 <img>/[IMAGE:]。
            value = text.strip()
            if value and not _IMG_TAG_RE.search(value) and not _MARKER_RE.search(value):
                add("group_images", "group", gid, value)
    return refs


def _load_bytes(ref: MediaRef, cache: dict[Path, bytes]) -> bytes:
    if ref.inline is not None:
        return ref.inline
    if ref.path is None:
        raise ValueError(f"引用未解析: {ref.raw!r}")
    data = cache.get(ref.path)
    if data is None:
        data = ref.path.read_bytes()
        cache[ref.path] = data
    return data


def _missing_key(canonical: str) -> tuple[str, str]:
    sha = hashlib.sha256(f"missing:{canonical}".encode("utf-8")).hexdigest()
    return sha, sha[:32]


def _content_type_for_missing(canonical: str) -> str:
    suffix = Path(canonical).suffix.lower()
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }.get(suffix, "application/octet-stream")


def register_media_refs(
    session: Session,
    refs: Iterable[MediaRef],
    *,
    apply: bool = False,
) -> RegisterReport:
    """幂等登记引用对应的媒体资产；apply=False 只统计，不写库/不写对象存储。"""
    refs = list(refs)
    report = RegisterReport()
    report.refs_total = len(refs)
    report.refs_unique = len({(r.loc, r.owner_id, r.raw) for r in refs})

    for ref in refs:
        report.bump(report.by_kind, ref.kind)
        report.bump(report.by_loc, ref.loc)
        if ref.status != "resolved":
            report.missing_refs += 1
            if ref.reason == "legacy_marker_unresolved":
                report.ambiguous_refs += 1
            if ref.reason in {"external_url", "unsupported_scheme"}:
                report.external_refs += 1
        else:
            report.resolved_refs += 1
            if ref.inline is not None:
                report.inline_refs += 1

    cache: dict[Path, bytes] = {}
    active: dict[str, dict[str, Any]] = {}
    missing: dict[str, dict[str, Any]] = {}
    for ref in refs:
        if ref.status != "resolved":
            entry = missing.setdefault(ref.canonical, {
                "kind": ref.kind, "canonical": ref.canonical,
                "loc": ref.loc, "raw": ref.raw, "reason": ref.reason,
            })
            if _kind_rank(ref.kind) < _kind_rank(entry["kind"]):
                entry["kind"] = ref.kind
            continue
        data = _load_bytes(ref, cache)
        digest = hashlib.sha256(data).hexdigest()
        entry = active.setdefault(digest, {
            "kind": ref.kind, "canonical": ref.canonical, "data": data,
            "content_type": ref.content_type or _content_type_for_path(ref.path),
            "original_name": ref.canonical,
        })
        if _kind_rank(ref.kind) < _kind_rank(entry["kind"]):
            entry["kind"] = ref.kind
        entry["data"] = data

    report.assets_unique = len(active) + len(missing)
    report.active_assets = len(active)
    report.missing_assets = len(missing)
    report.missing = sorted(
        (
            {"loc": item["loc"], "owner": f"{_owner_prefix(item['loc'])}",
             "raw": item["raw"], "reason": item["reason"]}
            for item in missing.values()
        ),
        key=lambda item: (item["loc"], item["raw"]),
    )

    if not apply:
        return report

    store = build_object_store()
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    existing_by_sha = _existing_by_sha(session, list(active))
    existing_missing = _existing_missing(session, list(missing))
    resolved_missing: set[str] = set()

    for digest in sorted(active):
        entry = active[digest]
        object_key = f"{digest[:2]}/{digest}"
        store.put(
            object_key, _BytesReader(entry["data"]), entry["content_type"],
            sha256=digest, size=len(entry["data"]),
        )
        row = existing_by_sha.get(digest)
        if row is not None:
            if row.status == "active":
                report.reused += 1
                continue
            row.status = "active"
            row.object_key = object_key
            row.size_bytes = len(entry["data"])
            row.content_type = entry["content_type"]
            row.kind = entry["kind"]
            row.original_name = entry["original_name"][:255]
            row.deleted_at = None
            report.updated += 1
            continue
        placeholder = existing_missing.get(entry["original_name"])
        if placeholder is not None:
            placeholder.sha256 = digest
            placeholder.object_key = object_key
            placeholder.size_bytes = len(entry["data"])
            placeholder.content_type = entry["content_type"]
            placeholder.kind = entry["kind"]
            placeholder.status = "active"
            placeholder.deleted_at = None
            resolved_missing.add(entry["original_name"])
            report.updated += 1
            continue
        session.add(MediaAsset(
            asset_id=uuid.uuid4().hex,
            sha256=digest,
            object_key=object_key,
            size_bytes=len(entry["data"]),
            content_type=entry["content_type"],
            kind=entry["kind"],
            original_name=entry["original_name"][:255],
            created_by=0,
            status="active",
            created_at=now,
        ))
        report.inserted += 1

    for canonical in sorted(missing):
        entry = missing[canonical]
        if canonical in resolved_missing:
            continue
        placeholder = existing_missing.get(canonical)
        if placeholder is not None:
            if placeholder.status == "missing":
                report.reused += 1
            continue
        digest, asset_id = _missing_key(canonical)
        session.add(MediaAsset(
            asset_id=asset_id,
            sha256=digest,
            object_key=f"missing/{digest[:40]}",
            size_bytes=0,
            content_type=_content_type_for_missing(canonical),
            kind=entry["kind"],
            original_name=canonical[:255],
            created_by=0,
            status="missing",
            created_at=now,
        ))
        report.inserted += 1

    session.flush()
    return report


class _BytesReader:
    """把 bytes 包成 store.put 需要的 read() 接口。"""

    def __init__(self, data: bytes):
        self._data = data
        self._pos = 0

    def read(self, size: int = -1) -> bytes:
        if size is None or size < 0:
            size = len(self._data) - self._pos
        chunk = self._data[self._pos:self._pos + size]
        self._pos += len(chunk)
        return chunk


def _kind_rank(kind: str) -> int:
    try:
        return KIND_PRIORITY.index(kind)
    except ValueError:
        return len(KIND_PRIORITY)


def _owner_prefix(loc: str) -> str:
    return "group" if loc.startswith("group") else "question"


def _existing_by_sha(session: Session, shas: list[str]) -> dict[str, MediaAsset]:
    if not shas:
        return {}
    rows = session.query(MediaAsset).filter(MediaAsset.sha256.in_(shas)).all()
    result: dict[str, MediaAsset] = {}
    for row in rows:
        result.setdefault(row.sha256, row)
    return result


def _existing_missing(
    session: Session, canonicals: list[str]
) -> dict[str, MediaAsset]:
    if not canonicals:
        return {}
    names = [name[:255] for name in canonicals]
    rows = session.query(MediaAsset).filter(
        MediaAsset.original_name.in_(names),
        MediaAsset.status == "missing",
    ).all()
    result: dict[str, MediaAsset] = {}
    for row in rows:
        result.setdefault(row.original_name or "", row)
    return result
