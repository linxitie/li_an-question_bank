# -*- coding: utf-8 -*-
"""上传即导题的服务层（P3，2026-11-09）。

链路（对应方案 §3.1）::

    上传原件 → parse_material()  读 docx/pdf → splitter 拆题 → 图片落草稿目录
             → 写 paper_parse_draft(status=pending)
    管理端点 → list_drafts() / get_draft() / update_items() / discard_draft()
             → confirm_draft()  题目写 question_bank + paper_question_relation
                                + 图片复制到 static/questions/{qid}/
                                + 卷 question_count 重算（服务层，不跨域直改）

**为什么确认才写库**：自动拆题是会错的（不同来源排版差异大）。草稿把风险留在管理员这一侧，
一旦错位，学生做到的就是错题 —— 这条线不能靠"事后发现"。

**图片两段式**：解析时写 `storage/parse_drafts/{draft_id}/`（草稿私有）；
确认时复制到 `app/static/questions/{qid}/` 并把正文里的占位换成真实 URL。
放弃草稿 = 删草稿目录，正式图片目录里不留垃圾。
"""
from __future__ import annotations

import json
import logging
import os
import shutil
from datetime import datetime, timedelta
from typing import List, Optional, Callable

from sqlalchemy.orm import Session

from ...core.config import settings
from ...models.models import (ExamPaper, PaperParseDraft, PaperQuestionRelation,
                              QuestionBank, StudyMaterial)
from .. import paper_stats
from . import readers, splitter

logger = logging.getLogger(__name__)

#: 保留期（用户决策 S3：解析草稿保留 30 天）
RETENTION_DAYS = 30
#: 题干/答案解析里的图片占位：确认时替换成 `/static/questions/{qid}/{name}`
IMG_PLACEHOLDER = "[[IMG:{name}]]"
#: 单选/多选在 `question_type` 里的中文名（实测库里只有这两个）
TYPE_NAME = {"单选": "单选题", "多选": "多选题", "判断": "单选题"}
#: 草稿根目录（与 material_files 同级，不进 /uploads 静态目录）
DRAFT_ROOT_NAME = "parse_drafts"


class IngestError(ValueError):
    """可预期的业务错误（调用方转 400）。"""


# ------------------------------------------------------------------ 目录工具
def _storage_root() -> str:
    """草稿根：优先 `<SQLITE_PATH 同级>/parse_drafts`，与 material_files 同口径。"""
    db_path = getattr(settings, "SQLITE_PATH", "") or ""
    base = os.path.dirname(os.path.abspath(db_path)) if db_path else ""
    if not base:
        base = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__)))))
    root = os.path.join(base, DRAFT_ROOT_NAME)
    os.makedirs(root, exist_ok=True)
    return root


def draft_dir(draft_id: int) -> str:
    path = os.path.join(_storage_root(), str(draft_id))
    os.makedirs(path, exist_ok=True)
    return path


def _questions_root() -> str:
    """正式题目图片根：`backend/app/static/questions`（与 image_service 同口径）。"""
    from ..image_service import STATIC_IMG_ROOT
    return STATIC_IMG_ROOT


# ------------------------------------------------------------------ 解析入口
def create_draft(db: Session, material: StudyMaterial, *, ext: str,
                 status: str = "pending", actor_id: Optional[int] = None,
                 message: str = "") -> PaperParseDraft:
    """建一份草稿（同资料旧 pending 先作废）。**不 commit、不解析**。

    P3（2026-11-13）：扫描件解析要几分钟，路由先建 `status="parsing"` 的草稿并立刻返回，
    再由后台 `fill_draft()` 填内容；文字版仍走 `parse_material()`（同步，行为不变）。
    """
    ext = (ext or "").lower().lstrip(".")
    for old in (db.query(PaperParseDraft)
                  .filter(PaperParseDraft.material_id == material.material_id,
                          PaperParseDraft.status.in_(("pending", "parsing"))).all()):
        old.status = "discarded"
        old.message = "被新的解析覆盖"
        old.update_time = datetime.now()

    draft = PaperParseDraft(
        material_id=material.material_id,
        paper_id=_paper_id_of(db, material),
        status=status,
        source_ext=ext,
        item_count=0,
        created_by=actor_id or material.creator_id,
        message=(message or None),
        create_time=datetime.now(),
        expires_at=datetime.now() + timedelta(days=RETENTION_DAYS),
    )
    db.add(draft)
    db.flush()                                  # 拿 draft_id（图片目录要用）
    return draft


def fill_draft(db: Session, draft: PaperParseDraft, *, ext: str, abs_path: str,
               expected: Optional[int] = None,
               progress_cb: Optional[Callable[[str], None]] = None) -> PaperParseDraft:
    """读原件 → 拆题 → 回写草稿（成功置 pending / 失败置 failed）。**不 commit**。

    `progress_cb(文本)`：扫描件 OCR 时逐段回调（调用方负责落库+commit，用于前端进度）。
    """
    # D2（2026-11-14）：用户在 OCR 期间点了「放弃草稿」→ 后台任务跑完**不许把它救回 pending**。
    # 之前这里无条件写 pending，实测（探针）放弃后草稿又冒出来、带 1 题，弃稿语义失效。
    # 与 P4 的 `fill_answer_draft` 同款口径（answer_ingest/service.py 早退）。
    if draft.status == "discarded":
        return draft
    ext = (ext or "").lower().lstrip(".")
    try:
        payload = readers.read_any(abs_path, ext, progress=progress_cb)
    except readers.ReaderError as exc:
        draft.status = "failed"
        draft.message = str(exc)[:500]
        return draft
    except Exception as exc:                    # noqa: BLE001 — 解析异常不能把上传搞崩
        logger.exception("[paper_ingest] 解析失败 draft=%s", draft.draft_id)
        draft.status = "failed"
        draft.message = f"解析失败：{exc}"[:500]
        return draft

    items = splitter.split_questions(payload["lines"])
    if not items:
        draft.status = "failed"
        draft.message = "没有拆出题目（请确认上传的是题本而不是答案/解析，或该排版需人工处理）"
        return draft

    orphans = readers.attach_images(items, payload["images"])[0]
    for it in items:
        if it.get("images") and "依赖图" not in it["flags"]:
            it["flags"].append("有图待核对")
    warnings = splitter.draft_warnings(items, expected=expected)
    if orphans:
        warnings.append(f"{orphans} 张图没归到任何题（卷首图/页首图）已跳过，未硬塞")
    meta = payload.get("meta") or {}
    # P3：扫描件把"无图/需核对/失败页"说清楚（这些警告在确认页顶部黄条里展示）
    if meta.get("scanned"):
        warnings.insert(0, "这是扫描件 OCR 出来的文字草稿：没有原图，公式/表格/双栏可能错位，请逐题核对")
        warnings.append("题号/选项由 OCR 识别，可能与原卷不一致，请逐题核对后再入库")
        if meta.get("failed_pages"):
            warnings.append(f"有 {len(meta['failed_pages'])} 页识别失败（第 "
                            f"{'、'.join(str(p) for p in meta['failed_pages'][:5])} 页）")
        if meta.get("truncated"):
            warnings.append(f"仅解析前 {meta.get('parsed_pages') or 60} 页，后续内容请拆分上传")
        # T5（2026-11-14）：有整行被水印压住没识别出来、已局部重跑补回的，明确说一句
        retry = meta.get("ocr_retry") or {}
        if retry.get("recovered"):
            qnos = "、".join(str(n) for n in (retry.get("recovered_qnos") or [])[:6])
            warnings.append(f"有 {retry['recovered']} 处整行漏检（水印遮挡）已局部重跑补回"
                            f"（第 {qnos} 题），请对着原卷核对")
    elif meta.get("pages"):
        warnings.insert(0, f"PDF 共 {meta['pages']} 页，已按版面坐标归属图片")

    # 图片落草稿目录（只落"挂到题上"的那些；扫描件 images=[] → 空转）
    target = draft_dir(draft.draft_id)
    kept = {name for it in items for name in
            [img["name"] for img in it.get("images") or []]}
    for img in payload["images"]:
        if img["file"] not in kept:
            continue
        with open(os.path.join(target, img["file"]), "wb") as fh:
            fh.write(img["bytes"])

    draft.items_json = json.dumps(items, ensure_ascii=False)
    draft.warnings_json = json.dumps(warnings, ensure_ascii=False)
    draft.item_count = len(items)
    draft.images_dir = os.path.basename(target)
    draft.status = "pending"
    draft.message = f"拆出 {len(items)} 题，请核对后点「确认入库」"
    draft.update_time = datetime.now()
    return draft


def parse_material(db: Session, material: StudyMaterial, *, ext: str,
                   abs_path: str, actor_id: Optional[int] = None,
                   expected: Optional[int] = None) -> PaperParseDraft:
    """同步解析一份原件 → 草稿（文字版/docx 走这条；扫描件走 create_draft + 后台 fill_draft）。"""
    draft = create_draft(db, material, ext=ext, status="pending", actor_id=actor_id)
    return fill_draft(db, draft, ext=ext, abs_path=abs_path, expected=expected)


def _paper_id_of(db: Session, material: StudyMaterial) -> Optional[int]:
    code = (getattr(material, "paper_code", "") or getattr(material, "badge", "") or "").strip()
    if not code:
        return None
    row = db.query(ExamPaper).filter(ExamPaper.paper_code == code).first()
    return row.paper_id if row else None


# ------------------------------------------------------------------ 草稿读取
def items_of(draft: PaperParseDraft) -> List[dict]:
    try:
        return json.loads(draft.items_json or "[]")
    except (TypeError, ValueError):
        return []


def warnings_of(draft: PaperParseDraft) -> List[str]:
    try:
        return json.loads(draft.warnings_json or "[]")
    except (TypeError, ValueError):
        return []


def draft_brief(draft: PaperParseDraft, material: Optional[StudyMaterial] = None) -> dict:
    return {
        "draft_id": draft.draft_id,
        "material_id": draft.material_id,
        "paper_id": draft.paper_id,
        "status": draft.status,
        "source_ext": draft.source_ext,
        "item_count": int(draft.item_count or 0),
        "message": draft.message,
        "created_at": draft.create_time.strftime("%Y-%m-%d %H:%M:%S") if draft.create_time else None,
        "expires_at": draft.expires_at.strftime("%Y-%m-%d %H:%M:%S") if draft.expires_at else None,
        "title": getattr(material, "title", None),
    }


def latest_pending(db: Session, material_id: int) -> Optional[PaperParseDraft]:
    return (db.query(PaperParseDraft)
            .filter(PaperParseDraft.material_id == material_id,
                    PaperParseDraft.status == "pending")
            .order_by(PaperParseDraft.draft_id.desc()).first())


def latest_of(db: Session, material_id: int) -> Optional[PaperParseDraft]:
    """最近一条草稿（含 failed/confirmed）—— 列表要给"待确认 N 题 / 解析失败 / 已入库"三态。"""
    return (db.query(PaperParseDraft)
            .filter(PaperParseDraft.material_id == material_id)
            .order_by(PaperParseDraft.draft_id.desc()).first())


# ------------------------------------------------------------------ 改草稿
def update_items(db: Session, draft: PaperParseDraft, items: List[dict]) -> PaperParseDraft:
    """整表覆盖（前端把编辑后的完整列表发回来，避免逐条 patch 的顺序/并发问题）。"""
    if draft.status != "pending":
        raise IngestError("只有「待确认」的草稿可以修改")
    clean: List[dict] = []
    seen = set()
    for raw in items:
        if not isinstance(raw, dict):
            raise IngestError("题目格式不对")
        try:
            no = int(raw.get("no"))
        except (TypeError, ValueError):
            raise IngestError("题号必须是数字")
        if no in seen:
            raise IngestError(f"题号重复：{no}")
        seen.add(no)
        qtype = (raw.get("type") or "单选").strip()
        if qtype not in TYPE_NAME:
            raise IngestError("题型只能是 单选 / 多选 / 判断")
        opts = raw.get("options") or {}
        if not isinstance(opts, dict):
            raise IngestError("选项格式不对")
        stem = (raw.get("stem") or "").strip()
        if not stem:
            raise IngestError(f"第 {no} 题题干为空")
        clean.append({
            "no": no,
            "type": qtype,
            "stem": stem,
            "options": {k: (opts.get(k) or "").strip() for k in ("A", "B", "C", "D")},
            "shared": (raw.get("shared") or "").strip(),
            "section": int(raw.get("section") or 0),
            "images": raw.get("images") or [],
            "flags": raw.get("flags") or [],
        })
    if not clean:
        raise IngestError("草稿里至少要留一道题")
    clean.sort(key=lambda x: x["no"])
    draft.items_json = json.dumps(clean, ensure_ascii=False)
    draft.item_count = len(clean)
    draft.update_time = datetime.now()
    return draft


def discard_draft(db: Session, draft: PaperParseDraft, *, reason: str = "") -> PaperParseDraft:
    if draft.status == "confirmed":
        raise IngestError("已入库的草稿不能放弃（要删题请去题库）")
    draft.status = "discarded"
    draft.message = (reason or "人工放弃")[:500]
    draft.update_time = datetime.now()
    _cleanup_images(draft)
    return draft


# ------------------------------------------------------------------ 确认入库
def confirm_draft(db: Session, draft: PaperParseDraft, *,
                  actor_id: Optional[int] = None,
                  replace: bool = False,
                  subject_id: Optional[int] = None,
                  auto_paper: bool = True) -> dict:
    """草稿 → 题目入库并挂卷。**不 commit**（与审计同事务）。

    Args:
        replace: 该卷已有题目时是否清空重挂。默认 False → 直接 409，避免"又导一遍"把卷搞重。
        auto_paper: 资料还没有可作答卷时是否**自动建一张**（D10，2026-11-15）。
            今天之前这里是直接 400 → 管理员被卡在最后一步且界面上没有补救入口
            （material 139 就是这么撞上的）。编号规则见 `suggest_paper_code`。

    返回::

        {"paper_id": int|None, "created": int, "question_ids": [...],
         "replaced": int, "warnings": [...], "paper_auto_created": bool,
         "paper_code": str|None}
    """
    if draft.status == "confirmed":
        raise IngestError("这份草稿已经入库过了")
    if draft.status != "pending":
        raise IngestError("只有「待确认」的草稿可以入库")

    items = items_of(draft)
    if not items:
        raise IngestError("草稿是空的")

    material = db.query(StudyMaterial).filter(
        StudyMaterial.material_id == draft.material_id).first()
    if material is None:
        raise IngestError("来源资料已不存在")

    paper_id = draft.paper_id or _paper_id_of(db, material)
    paper_auto_created = False
    if paper_id is None:
        if not auto_paper:
            raise IngestError(
                "这条资料还没有可作答卷：先点该行的「建卷」（没有编号也能建），"
                "或在「改信息」里补编号后再入库")
        if (material.type or "") != "paper":
            raise IngestError("只有「试卷」类资料才能导题入库")
        from ..material_paper_link import ensure_paper_for_material
        from ..paper_meta_parser import suggest_paper_code
        code = suggest_paper_code(
            material.title or "", material.subject or "",
            existing=(material.paper_code or material.badge or ""),
            material_id=material.material_id)
        material.paper_code = code[:40]
        db.flush()
        created = ensure_paper_for_material(db, material, actor_id=actor_id)
        paper_id = int(created["paper"].paper_id)
        draft.paper_id = paper_id          # 留痕：这份草稿最终入到了哪张卷
        paper_auto_created = True
    paper = db.query(ExamPaper).filter(ExamPaper.paper_id == paper_id).first()
    if paper is None:
        raise IngestError("可作答卷不存在")

    existing = (db.query(PaperQuestionRelation)
                  .filter(PaperQuestionRelation.paper_id == paper_id).count())
    if existing and not replace:
        raise IngestError(
            f"这张卷已有 {existing} 道题；要重新导入请勾选「覆盖已有题目」")
    replaced = 0
    if existing and replace:
        # 只删关系，不删题目本身：题目可能被别的卷/错题本引用
        replaced = (db.query(PaperQuestionRelation)
                    .filter(PaperQuestionRelation.paper_id == paper_id)
                    .delete(synchronize_session=False))

    sid = subject_id or paper.subject_id or 3
    type_ids = _type_ids(db)
    qtype_default = type_ids.get("单选题") or min(type_ids.values() or [1])
    created_ids: List[int] = []
    src_dir = os.path.join(_storage_root(), draft.images_dir or str(draft.draft_id))
    # 情境组的"材料图"挂在组内第一题上；组里其它题也要能看到同一张图
    # （2024 国考 71–100 的 8 组材料就是这种：材料 + 图，组内共用）。
    section_imgs: Dict[int, List[dict]] = {}
    for it in items:
        sec = int(it.get("section") or 0)
        if sec and sec not in section_imgs and it.get("images"):
            section_imgs[sec] = it["images"]

    for order, item in enumerate(items, 1):
        qtype = item.get("type") or "单选"
        type_id = type_ids.get(TYPE_NAME.get(qtype, "单选题"), qtype_default)
        q = QuestionBank(
            subject_id=sid,
            type_id=type_id,
            question_content="",          # 下面按图片归属拼好再赋
            options=[{"key": k, "value": v} for k, v in (item.get("options") or {}).items()
                     if v],
            answer="",                     # 决策 ⑤：答案后补（P4）
            answer_analysis="",
            difficulty=splitter.DEFAULT_DIFFICULTY,
            score=splitter.DEFAULT_SCORE,
            creator_id=actor_id or material.creator_id,
            status=1,
            audit_status=1,
            question_level=2 if item.get("section") else 1,
            # D8（2026-11-15）：把题号也写进 question_number —— 以前只写 question_order，
            # 导致"按题号定序"（paper_stats.normalize_question_orders）对导题入库的卷不成立。
            question_number=(str(item["no"]) if str(item.get("no") or "").isdigit() else None),
            sort_order=order,
        )
        db.add(q)
        db.flush()                        # 拿 question_id 才能放图
        extra = [img for img in section_imgs.get(int(item.get("section") or 0), [])
                 if img["name"] not in {x["name"] for x in item.get("images") or []}]
        q.question_content = _render_html(q.question_id, item, src_dir, extra)
        db.add(PaperQuestionRelation(paper_id=paper_id, question_id=q.question_id,
                                     question_order=order,
                                     question_score=splitter.DEFAULT_SCORE))
        created_ids.append(q.question_id)

    # 卷题量以关系表实数重算（`question_count` 是缓存值，见 paper_stats 的说明）
    paper.question_count = paper_stats.recount_paper_questions(db, paper)
    # 满分跟着题量/分值走（97 题 × 1 分 = 97），否则结果页会出现「得分 0 / 满分 100」这种
    # 分母比可得分还大的怪数字（#128 实测）。
    new_total = sync_total_score(db, paper)
    draft.status = "confirmed"
    draft.paper_id = paper_id
    draft.item_count = len(created_ids)
    draft.message = f"已入库 {len(created_ids)} 题" + (f"，覆盖 {replaced} 题" if replaced else "")
    draft.update_time = datetime.now()
    _cleanup_images(draft)
    return {
        "paper_id": paper_id,
        "created": len(created_ids),
        "question_ids": created_ids,
        "replaced": replaced,
        "total_score": new_total,
        "warnings": warnings_of(draft),
        # D10：无卷时自动建的那张卷（前端据此提示"记得上架"）
        "paper_auto_created": paper_auto_created,
        "paper_code": (paper.paper_code or None),
    }


def _type_ids(db: Session) -> dict:
    """中文题型名 → type_id（库里只有"单选题/多选题"两行，申报式读取，缺了兜底）。"""
    from ...models.models import QuestionType
    try:
        rows = db.query(QuestionType).all()
    except Exception:                         # noqa: BLE001
        return {"单选题": 1, "多选题": 2}
    out = {(r.type_name or "").strip(): r.type_id for r in rows if r.type_id}
    return out or {"单选题": 1, "多选题": 2}


def sync_total_score(db: Session, paper: ExamPaper) -> float:
    """让卷的「满分」= 各题**分值之和**（取 `question_bank.score`）。**不 commit**。

    为什么用 `question_bank.score` 而不是 `paper_question_relation.question_score`：
    评分代码（`exams.py` 交卷）用的是 `question.score`，而关系表里的分值在历史导入里是残值
    （实测 #2/#3 关系表写着每题 5 分 = 500，而题库里每题 1 分、卷满分 100，两者对不上）。
    以**实际参与打分的那一列**为准，才不会再出现"分母和得分口径不一致"。

    #128 实测：97 题 × 1 分 = 97，而卷满分还是早先的 100 → 学生看到「0 / 100」，
    容易以为被扣了 3 分，其实是分母不对。
    """
    from sqlalchemy import func
    total = (db.query(func.coalesce(func.sum(QuestionBank.score), 0))
             .join(PaperQuestionRelation,
                   PaperQuestionRelation.question_id == QuestionBank.question_id)
             .filter(PaperQuestionRelation.paper_id == paper.paper_id).scalar())
    total = float(total or 0)
    if total > 0:
        paper.total_score = total
    return total


def _render_html(question_id: int, item: dict, src_dir: str,
                 extra_images: Optional[List[dict]] = None) -> str:
    """题干 + 共享材料 + 图片 → 题库的 `question_content`（HTML）。

    图片放**题干下方**（与既有真题一致：材料/图在问句之后、选项之前），
    文件名按 `/static/questions/{qid}/{name}` 落地。
    `extra_images`：情境组内共享的材料图（本组第一题那张），组里每道题都要带上。
    """
    parts: List[str] = []
    shared = (item.get("shared") or "").strip()
    stem = (item.get("stem") or "").strip()
    if shared:
        parts.append(f"<p>{_esc(shared)}</p>")
    if stem:
        parts.append(f"<p>{_esc(stem)}</p>")
    dest_dir = os.path.join(_questions_root(), str(question_id))
    seen = set()
    for img in list(item.get("images") or []) + list(extra_images or []):
        name = img.get("name") if isinstance(img, dict) else None
        if not name or name in seen:
            continue
        seen.add(name)
        src = os.path.join(src_dir, name)
        if not os.path.isfile(src):
            continue
        os.makedirs(dest_dir, exist_ok=True)
        final = f"q{question_id}_{name}"
        shutil.copyfile(src, os.path.join(dest_dir, final))
        parts.append(f'<p><img src="/static/questions/{question_id}/{final}" /></p>')
    return "".join(parts)


def _esc(text: str) -> str:
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _cleanup_images(draft: PaperParseDraft) -> None:
    """删草稿私有图片目录（确认入库/放弃后都不再需要）。"""
    path = os.path.join(_storage_root(), draft.images_dir or str(draft.draft_id))
    if os.path.isdir(path):
        shutil.rmtree(path, ignore_errors=True)
    draft.images_dir = None


# ------------------------------------------------------------------ 过期清理
def cleanup_expired(db: Session, *, days: int = RETENTION_DAYS,
                    now: Optional[datetime] = None) -> dict:
    """清理过期草稿（S3：30 天）。**confirmed 只清 items_json，不删记录**（可追溯）。

    为什么不是"定时任务"：与考试开关同理 —— 单机部署没有 supervisor，
    这里做成可被启动期/管理端点调用的幂等函数，谁调都安全。
    """
    now = now or datetime.now()
    cutoff = now - timedelta(days=days)
    rows = (db.query(PaperParseDraft)
            .filter(PaperParseDraft.create_time < cutoff)
            .all())
    cleared = kept = 0
    for row in rows:
        if row.status == "confirmed":
            if row.items_json:
                row.items_json = None
                row.message = (row.message or "")[:100] + "｜超期清理明细"
                cleared += 1
            continue
        _cleanup_images(row)
        row.items_json = None
        row.warnings_json = None
        if row.status == "pending":
            row.status = "discarded"
            row.message = f"超过 {days} 天未确认，已自动清理"
        kept += 1
    return {"scanned": len(rows), "cleared": cleared, "closed": kept}
