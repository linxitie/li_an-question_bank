# -*- coding: utf-8 -*-
"""答案草稿服务（P4，2026-11-09）：解析 → 校验 → 入库。

分工：
  · `extractor.py`  纯函数（读文本、四层取答案、幻影题号）—— 可单测；
  · 本文件         需要 DB 的部分：与卷的题型对齐、冲突判定、写入 `question_bank`。

**重要：只写答案与解析，不动题干/选项/题型。** 题型以 `question_bank.type_id` 为准，
用来做"单选应 1 个字母、多选应 ≥2"的交叉校验 —— 这条校验是本轮最能抓错的手段
（实测抓到 2017 江苏 #87 被读成 A，真实答案是 ABCD）。

写入策略（用户 2026-11-09 拍板）：
  · **默认只填空位**（`answer` 为空才写）；
  · 库里已有不同答案 → 计入 `kept`，只有显式 `overwrite=True` 才覆盖；
  · `answer_analysis` 一起写（解析正文是现成素材，Q3 要）；
  · **不重算历史成绩**（`exam_record` 不动），只影响之后的新考试。
"""
from __future__ import annotations

import json
import logging
import os
import shutil
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from ...models.models import (ExamPaper, PaperAnswerDraft, PaperQuestionRelation,
                              QuestionBank)
from . import extractor

logger = logging.getLogger(__name__)

#: 保留期（与导题草稿一致：30 天）
RETENTION_DAYS = 30
#: 支持的文件类型
SUPPORTED_EXTS = ("pdf", "docx", "xlsx", "xls", "txt", "csv")
#: 题型 id → 中文（实测库里只有 1=单选 / 2=多选）
TYPE_NAME = {1: "单选", 2: "多选"}


class AnswerIngestError(ValueError):
    """可预期的业务错误（调用方转 400/409）。"""


# ------------------------------------------------------------------ 读文件
def read_text_of(abs_path: str, ext: str, *, meta: Optional[dict] = None) -> str:
    """把 pdf / docx / xlsx / txt 统一读成文本（分行）。

    `meta`（可选，出参）：调用方传一个 dict 进来，扫描件走 OCR 时会把识别信息
    （页数/耗时/失败页）塞进 `meta["ocr"]`，用于在草稿提示里如实说明"这是 OCR 出来的"。
    文字版链路从不写这个键。
    """
    ext = (ext or "").lower().lstrip(".")
    if ext == "pdf":
        try:
            import pymupdf
        except ImportError as exc:                 # pragma: no cover
            raise AnswerIngestError("当前环境没有 PyMuPDF，无法解析 PDF") from exc
        try:
            doc = pymupdf.open(abs_path)
        except Exception as exc:                   # noqa: BLE001
            raise AnswerIngestError(f"这个 pdf 打不开（可能已加密或损坏）：{exc}") from exc
        try:
            text = "\n".join((doc[i].get_text() or "") for i in range(doc.page_count))
        finally:
            doc.close()
        if text.strip():
            return text
        # 文字层为空 = 扫描图片版 → OCR sidecar（P1，2026-11-12 批准）
        return _read_scanned_pdf(abs_path, meta)
    if ext == "docx":
        try:
            from docx import Document
            doc = Document(abs_path)
        except Exception as exc:                   # noqa: BLE001
            raise AnswerIngestError(f"这个 docx 打不开：{exc}") from exc
        lines = [p.text for p in doc.paragraphs if (p.text or "").strip()]
        for table in doc.tables:
            for row in table.rows:
                joined = " ".join((c.text or "").strip() for c in row.cells).strip()
                if joined:
                    lines.append(joined)
        return "\n".join(lines)
    if ext in ("xlsx", "xls"):
        try:
            import openpyxl
            wb = openpyxl.load_workbook(abs_path, data_only=True)
        except Exception as exc:                   # noqa: BLE001
            raise AnswerIngestError(f"这个 xlsx 打不开：{exc}") from exc
        out: List[str] = []
        for ws in wb.worksheets:
            for row in ws.iter_rows(values_only=True):
                cells = [str(c).strip() for c in row if c is not None and str(c).strip()]
                if not cells:
                    continue
                # `题号 | 答案 | 解析` 三列 → 拼成一行一题；纯 `1 | A` 也吃得住
                out.append(" ".join(cells[:2]))
        return "\n".join(out)
    if ext in ("txt", "csv"):
        for enc in ("utf-8-sig", "utf-8", "gbk"):
            try:
                with open(abs_path, "r", encoding=enc) as fh:
                    return fh.read()
            except UnicodeDecodeError:
                continue
        raise AnswerIngestError("文本文件编码无法识别（试过 utf-8 / gbk）")
    raise AnswerIngestError(f"暂不支持 .{ext} 的答案解析（支持 pdf / docx / xlsx / txt）")


def _read_scanned_pdf(abs_path: str, meta: Optional[dict]) -> str:
    """扫描图片版 PDF → OCR 文本（P1）。

    **只有"文字层为空"的 PDF 才会走到这里**，文字版/Word/Excel 一行不受影响。
    OCR 失败时抛 `AnswerIngestError`，消息里已经带页号与原因（由 sidecar 保证），
    不再出现"组件未就绪"这类一句话。
    """
    from .. import ocr_sidecar

    try:
        text, info = ocr_sidecar.read_pdf_text(abs_path)
    except ocr_sidecar.OcrError as exc:
        raise AnswerIngestError(str(exc)) from exc
    if meta is not None:
        meta["ocr"] = info
    if not (text or "").strip():
        raise AnswerIngestError("这份扫描件 OCR 跑完了但没识别出文字，"
                                "多半是拍照/扫描太糊，建议换清晰的图片版或转成文字版 Word")
    return text


# ------------------------------------------------------------------ 卷的题目
def paper_questions(db: Session, paper_id: int) -> Dict[int, dict]:
    """`{题号: {question_id, type_id, type_name, current_answer, has_analysis}}`（按卷内顺序）。"""
    rows = (db.query(PaperQuestionRelation.question_order,
                     PaperQuestionRelation.question_id,
                     QuestionBank.type_id,
                     QuestionBank.answer,
                     QuestionBank.answer_analysis)
            .join(QuestionBank, QuestionBank.question_id == PaperQuestionRelation.question_id)
            .filter(PaperQuestionRelation.paper_id == paper_id)
            .order_by(PaperQuestionRelation.question_order)
            .all())
    out: Dict[int, dict] = {}
    for order, qid, type_id, answer, analysis in rows:
        out[int(order)] = {
            "question_id": int(qid),
            "type_id": int(type_id or 0),
            "type_name": TYPE_NAME.get(int(type_id or 0), ""),
            "current_answer": (answer or "").strip(),
            "has_analysis": bool((analysis or "").strip()),
        }
    return out


# ------------------------------------------------------------------ 校验
def _validate(items: List[dict], questions: Dict[int, dict]) -> tuple:
    """逐题校验，返回 (items 里补好 flags/current 的列表, conflict_count, empty_count)。

    阻断级问题（题号不在卷里 / 答案字母非法）在解析阶段就报错，不走到这里。
    这里只做"要不要人看一眼"的标记：

      · `题型冲突`：单选却 ≥2 个字母，或多选却只有 1 个字母（最有用的一条，实测抓到 #87）
      · `已有答案不同`：库里已有答案且与本份不同（默认保留，需人工确认）
      · `未识别答案` / `仅推断建议`：见 extractor
    """
    conflict = 0
    empty = 0
    for it in items:
        q = questions.get(it["no"])
        it["question_type"] = q["type_name"] if q else ""
        it["current"] = q["current_answer"] if q else ""
        flags = list(it.get("flags") or [])
        answer = it.get("answer") or ""
        if not answer:
            empty += 1
        if q and answer:
            if q["type_id"] == 1 and len(answer) != 1:
                flags.append("题型冲突")
            elif q["type_id"] == 2 and len(answer) < 2:
                flags.append("题型冲突")
            if q["current_answer"] and q["current_answer"].upper() != answer:
                flags.append("已有答案不同")
        # 去重但保序
        seen = set()
        it["flags"] = [f for f in flags if not (f in seen or seen.add(f))]
        if it["flags"]:
            conflict += 1
    return items, conflict, empty


def _extract_items(text: str, ext: str) -> List[dict]:
    ext = (ext or "").lower().lstrip(".")
    if ext in ("txt", "csv", "xlsx", "xls"):
        plain = extractor.parse_plain(text)
        # Excel 里可能同时有"解析"列，用整段再跑一遍解析式，取更完整的
        rich = extractor.parse_text(text)
        if len(rich) >= len(plain):
            return rich
        return plain
    return extractor.parse_text(text)


def _ocr_note(meta: Optional[dict]) -> str:
    """扫描件的"这是 OCR 出来的"提示（非扫描件返回空串）。"""
    info = (meta or {}).get("ocr") or {}
    if not info:
        return ""
    note = (f"扫描件已 OCR {info.get('pages_done', '?')}/{info.get('pages', '?')} 页"
            f"（{info.get('seconds', '?')}s，{info.get('dpi', '?')}dpi），识别文字请逐题核对")
    if info.get("pages_failed"):
        note += f"，另有 {info['pages_failed']} 页识别失败"
    return note


# ------------------------------------------------------------------ 解析入口
def parse_answers(db: Session, *, paper_id: int, ext: str, abs_path: str,
                  source_name: str = "", actor_id: Optional[int] = None) -> PaperAnswerDraft:
    """解析答案文件 → 新建草稿（同卷旧 pending 草稿先作废）。**不 commit**。"""
    paper = db.query(ExamPaper).filter(ExamPaper.paper_id == paper_id).first()
    if paper is None:
        raise AnswerIngestError("试卷不存在")
    questions = paper_questions(db, paper_id)
    if not questions:
        raise AnswerIngestError("这张卷还没有题目：先导题，再补答案")

    for old in (db.query(PaperAnswerDraft)
                  .filter(PaperAnswerDraft.paper_id == paper_id,
                          PaperAnswerDraft.status == "pending").all()):
        old.status = "discarded"
        old.message = "被新的解析覆盖"
        old.update_time = datetime.now()

    draft = PaperAnswerDraft(
        paper_id=paper_id,
        status="pending",
        source_ext=(ext or "").lower().lstrip("."),
        source_name=(source_name or "")[:255],
        created_by=actor_id,
        create_time=datetime.now(),
        expires_at=datetime.now() + timedelta(days=RETENTION_DAYS),
    )
    db.add(draft)
    db.flush()

    try:
        ocr_meta: dict = {}
        text = read_text_of(abs_path, ext, meta=ocr_meta)
    except AnswerIngestError as exc:
        draft.status = "failed"
        draft.message = str(exc)[:500]
        return draft
    except Exception as exc:                       # noqa: BLE001
        logger.exception("[answer_ingest] 解析失败 paper=%s", paper_id)
        draft.status = "failed"
        draft.message = f"解析失败：{exc}"[:500]
        return draft

    items = _extract_items(text, ext)
    if not items:
        draft.status = "failed"
        draft.message = "没有从这份文件里识别出任何题号（是不是传错了文件？）"
        note = _ocr_note(ocr_meta)
        if note:
            draft.message = f"{note}；但没识别出任何题号"
        return draft

    # 阻断级：题号必须都落在该卷的题号范围内
    bad = sorted({it["no"] for it in items if it["no"] not in questions})
    if bad:
        draft.status = "failed"
        draft.message = (f"有 {len(bad)} 个题号不属于这张卷（{bad[:10]}"
                         f"{' 等' if len(bad) > 10 else ''}）：多半传了别的卷的答案")[:500]
        note = _ocr_note(ocr_meta)
        if note:
            draft.message = f"{note}；{draft.message}"[:500]
        return draft

    items, conflict, empty = _validate(items, questions)
    covered = len({it["no"] for it in items})
    draft.items_json = json.dumps(items, ensure_ascii=False)
    draft.item_count = len(items)
    draft.conflict_count = conflict
    draft.empty_count = empty
    next_yet = len(questions) - covered
    msgs = [f"识别 {len(items)} 题 / 卷共 {len(questions)} 题"]
    # 扫描件：把"这是 OCR 出来的"说清楚，并把失败页数带上（P1）
    note = _ocr_note(ocr_meta)
    if note:
        msgs.insert(0, note)
    if next_yet > 0:
        msgs.append(f"还差 {next_yet} 题没在这份文件里")
    if conflict:
        msgs.append(f"{conflict} 题需确认")
    draft.message = "；".join(msgs)[:500]
    draft.update_time = datetime.now()
    return draft


def paper_brief(db: Session, paper_id: int) -> Optional[dict]:
    """卷的最小信息（编号/名称）。**放在服务层**：library 域不能直接 import `ExamPaper`
    （门禁 `check_module_boundary` 的 cross_write 规则），端点只调本函数拿展示用的字段。
    """
    paper = db.query(ExamPaper).filter(ExamPaper.paper_id == paper_id).first()
    if paper is None:
        return None
    return {"paper_id": paper.paper_id, "paper_code": paper.paper_code,
            "paper_name": paper.paper_name,
            "question_count": int(paper.question_count or 0)}


def draft_payload(db: Session, draft: PaperAnswerDraft, *,
                  with_items: bool = False) -> dict:
    """草稿的统一回包（端点只需调这一个，不必自己去查卷）。"""
    info = paper_brief(db, draft.paper_id) or {}
    data = draft_brief(draft,
                       type("P", (), {
                           "paper_code": info.get("paper_code"),
                           "paper_name": info.get("paper_name"),
                       })())
    if with_items:
        data["items"] = items_of(draft)
        data["can_edit"] = draft.status == "pending"
    return data


def items_of(draft: PaperAnswerDraft) -> List[dict]:
    try:
        return json.loads(draft.items_json or "[]")
    except (TypeError, ValueError):
        return []


def draft_brief(draft: PaperAnswerDraft, paper: Optional[ExamPaper] = None) -> dict:
    return {
        "draft_id": draft.draft_id,
        "paper_id": draft.paper_id,
        "paper_code": getattr(paper, "paper_code", None),
        "paper_name": getattr(paper, "paper_name", None),
        "status": draft.status,
        "source_ext": draft.source_ext,
        "source_name": draft.source_name,
        "item_count": int(draft.item_count or 0),
        "conflict_count": int(draft.conflict_count or 0),
        "empty_count": int(draft.empty_count or 0),
        "message": draft.message,
        "created_at": draft.create_time.strftime("%Y-%m-%d %H:%M:%S") if draft.create_time else None,
        "expires_at": draft.expires_at.strftime("%Y-%m-%d %H:%M:%S") if draft.expires_at else None,
    }


def latest_of(db: Session, paper_id: int) -> Optional[PaperAnswerDraft]:
    return (db.query(PaperAnswerDraft)
            .filter(PaperAnswerDraft.paper_id == paper_id)
            .order_by(PaperAnswerDraft.draft_id.desc()).first())


# ------------------------------------------------------------------ 改草稿
def update_items(db: Session, draft: PaperAnswerDraft, items: List[dict]) -> PaperAnswerDraft:
    """整表覆盖（与导题一致：一次校验"题号重复/字母非法"，避免半套数据）。"""
    if draft.status != "pending":
        raise AnswerIngestError("只有「待确认」的答案草稿可以修改")
    questions = paper_questions(db, draft.paper_id)
    clean: List[dict] = []
    seen = set()
    for raw in items:
        if not isinstance(raw, dict):
            raise AnswerIngestError("题目格式不对")
        try:
            no = int(raw.get("no"))
        except (TypeError, ValueError):
            raise AnswerIngestError("题号必须是数字")
        if no in seen:
            raise AnswerIngestError(f"题号重复：{no}")
        if no not in questions:
            raise AnswerIngestError(f"题号 {no} 不属于这张卷")
        seen.add(no)
        answer = extractor.normalize_letters(raw.get("answer"))
        suggestion = extractor.normalize_letters(raw.get("suggestion"))
        clean.append({
            "no": no,
            "answer": answer,
            "tier": raw.get("tier") or ("M" if answer else ""),
            "suggestion": suggestion,
            "evidence": (raw.get("evidence") or "")[:80],
            "analysis": (raw.get("analysis") or "")[:4000],
            "flags": raw.get("flags") or [],
        })
    if not clean:
        raise AnswerIngestError("至少保留一题")
    clean.sort(key=lambda x: x["no"])
    clean, conflict, empty = _validate(clean, questions)
    draft.items_json = json.dumps(clean, ensure_ascii=False)
    draft.item_count = len(clean)
    draft.conflict_count = conflict
    draft.empty_count = empty
    draft.update_time = datetime.now()
    return draft


def discard_draft(db: Session, draft: PaperAnswerDraft, *, reason: str = "") -> PaperAnswerDraft:
    if draft.status == "applied":
        raise AnswerIngestError("已写入的草稿不能放弃（要改答案请重新解析）")
    draft.status = "discarded"
    draft.message = (reason or "人工放弃")[:500]
    draft.update_time = datetime.now()
    return draft


# ------------------------------------------------------------------ 写入
def apply_draft(db: Session, draft: PaperAnswerDraft, *,
                overwrite: bool = False) -> dict:
    """把草稿里的答案写进 `question_bank`。**不 commit**（与审计同事务）。

    只写两列：`answer` 与 `answer_analysis`；题干/选项/题型/分值一概不动。

    返回 `{"filled": n, "overwritten": n, "kept": n, "skipped": n,
           "analysis_only": n, "kept_numbers": [...]}`

    `filled` **只算答案**；"没答案但有解析"的题单独计入 `analysis_only`（素材不浪费，但不装作补了答案）。
    """
    if draft.status == "applied":
        raise AnswerIngestError("这份答案已经写入过了")
    if draft.status != "pending":
        raise AnswerIngestError("只有「待确认」的答案草稿可以写入")

    questions = paper_questions(db, draft.paper_id)
    if not questions:
        raise AnswerIngestError("这张卷还没有题目")

    filled = overwritten = kept = skipped = analysis_only = 0
    conflicts: List[int] = []
    for it in items_of(draft):
        q = questions.get(int(it["no"]))
        if q is None:
            skipped += 1
            continue
        answer = extractor.normalize_letters(it.get("answer"))
        analysis = (it.get("analysis") or "").strip()
        if not answer:
            # 没有答案但有解析：只补解析（学生仍看不到答案，但至少不丢素材）
            if analysis and not q["has_analysis"]:
                row = db.query(QuestionBank).filter(
                    QuestionBank.question_id == q["question_id"]).first()
                if row is not None:
                    row.answer_analysis = analysis
                    analysis_only += 1
                    continue
            skipped += 1
            continue
        row = db.query(QuestionBank).filter(
            QuestionBank.question_id == q["question_id"]).first()
        if row is None:
            skipped += 1
            continue
        current = (row.answer or "").strip().upper()
        if current and current != answer:
            if not overwrite:
                kept += 1
                conflicts.append(int(it["no"]))
                continue
            row.answer = answer
            overwritten += 1
        elif current == answer:
            kept += 1                     # 已经一致，不算改动
        else:
            row.answer = answer
            filled += 1
        if analysis and not (row.answer_analysis or "").strip():
            row.answer_analysis = analysis

    draft.status = "applied"
    draft.message = (f"写入答案 {filled} 题"
                     + (f"、覆盖 {overwritten} 题" if overwritten else "")
                     + (f"、仅补解析 {analysis_only} 题" if analysis_only else "")
                     + (f"、保留原有 {kept} 题" if kept else "")
                     + (f"、跳过 {skipped} 题" if skipped else ""))[:500]
    draft.update_time = datetime.now()
    return {"filled": filled, "overwritten": overwritten, "kept": kept,
            "skipped": skipped, "analysis_only": analysis_only,
            "kept_numbers": conflicts[:50]}


def cleanup_expired(db: Session, *, days: int = RETENTION_DAYS,
                    now: Optional[datetime] = None) -> dict:
    """30 天清理：applied 只清 items_json（可追溯），其余标 discarded。"""
    now = now or datetime.now()
    cutoff = now - timedelta(days=days)
    rows = db.query(PaperAnswerDraft).filter(PaperAnswerDraft.create_time < cutoff).all()
    cleared = 0
    for row in rows:
        if row.status == "applied":
            if row.items_json:
                row.items_json = None
                cleared += 1
            continue
        row.items_json = None
        if row.status == "pending":
            row.status = "discarded"
            row.message = f"超过 {days} 天未确认，已自动清理"
        cleared += 1
    return {"scanned": len(rows), "cleared": cleared}
