"""红队 Agent：主动生成规避样本，测出当前词库的盲区。

它不参与生产审核，只做两件事：
1. 用插入符号/零宽/同音/繁体等手法改写已知词条；
2. 未被拦截的写法生成 add_variant 提案，进入人工审阅队列。

这样系统从"被动响应举报"变成"主动发现自身漏放"。
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from ...models.content_guard import CgRedteamSample, CgTerm, CgVariant
from . import engine, normalizer, proposals

TRADITIONAL = {
    "国": "國", "党": "黨", "赌": "賭", "钱": "錢", "杀": "殺",
    "枪": "槍", "骗": "騙", "黄": "黃", "网": "網", "毒": "毒",
    "赌": "賭", "妈": "媽", "门": "門", "开": "開", "车": "車",
}

HOMOPHONES = {
    "赌": "堵", "毒": "独", "嫖": "飘", "娼": "昌", "淫": "银",
    "黄": "皇", "色": "涩", "傻": "沙", "逼": "比", "妈": "马",
    "操": "草", "贱": "溅", "婊": "表", "骚": "扫", "杀": "沙",
    "枪": "抢", "炸": "诈", "骗": "偏", "赌": "睹",
}


def _evasions(term: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    chars = list(term)
    if len(chars) >= 2:
        out.append(("\u200b".join(chars), "zero_width"))
        out.append(("·".join(chars), "symbol"))
    for idx, ch in enumerate(chars):
        replacement = HOMOPHONES.get(ch)
        if replacement and replacement != ch:
            out.append((term[:idx] + replacement + term[idx + 1 :], "homophone"))
            break
    for idx, ch in enumerate(chars):
        replacement = TRADITIONAL.get(ch)
        if replacement and replacement != ch:
            out.append((term[:idx] + replacement + term[idx + 1 :], "traditional"))
            break
    ascii_term = "".join(
        chr(ord(c) + 0xFEE0) if "!" <= c <= "~" else c for c in term
    )
    if ascii_term != term:
        out.append((ascii_term, "fullwidth"))
    seen = set()
    result = []
    for text, kind in out:
        key = normalizer.normalize(text)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append((text, kind))
    return result


def run(
    db: Session,
    *,
    limit: int = 30,
    create_proposals: bool = True,
) -> dict:
    terms = (
        db.query(CgTerm)
        .filter(CgTerm.status == "active")
        .order_by(CgTerm.hit_count.desc(), CgTerm.term_id.asc())
        .limit(max(1, min(limit, 200)))
        .all()
    )
    eng = engine.get_engine(db)
    generated = 0
    detected = 0
    undetected = 0
    created_proposals: list[int] = []
    samples: list[dict] = []

    for term in terms:
        for text, kind in _evasions(term.term):
            generated += 1
            result = eng.detect(text)
            hit = bool(result.get("has_sensitive"))
            if hit:
                detected += 1
            else:
                undetected += 1
            sample = CgRedteamSample(
                term_id=term.term_id,
                text=text[:500],
                kind=kind,
                detected=hit,
            )
            db.add(sample)
            db.flush()
            samples.append(
                {
                    "sample_id": sample.sample_id,
                    "term_id": term.term_id,
                    "term": term.term,
                    "text": text,
                    "kind": kind,
                    "detected": hit,
                }
            )
            if hit or not create_proposals:
                continue
            vnorm = normalizer.normalize(text)
            exists = (
                db.query(CgVariant)
                .filter(CgVariant.term_id == term.term_id, CgVariant.normalized == vnorm)
                .first()
            )
            if exists:
                continue
            proposal = proposals.create_proposal(
                db,
                kind="add_variant",
                title=f"红队发现绕过写法：{term.term} → {text}",
                payload={
                    "term_id": term.term_id,
                    "variant": text,
                    "kind": kind,
                    "term": term.term,
                },
                evidence=[
                    {"source": "redteam", "sample_id": sample.sample_id, "kind": kind},
                    {"detected": False, "engine_version": result.get("engine_version")},
                ],
                proposer="redteam",
                dedupe_key=f"redteam:{term.term_id}:{vnorm}",
            )
            if proposal and proposal.proposal_id not in created_proposals:
                created_proposals.append(proposal.proposal_id)

    return {
        "terms_scanned": len(terms),
        "generated": generated,
        "detected": detected,
        "undetected": undetected,
        "detection_rate": round(detected / generated, 4) if generated else 1.0,
        "proposals": created_proposals,
        "samples": samples[:50],
    }


def list_samples(db: Session, limit: int = 50, detected: Optional[bool] = None) -> dict:
    query = db.query(CgRedteamSample)
    if detected is not None:
        query = query.filter(CgRedteamSample.detected.is_(detected))
    total = query.count()
    rows = query.order_by(CgRedteamSample.sample_id.desc()).limit(min(limit, 200)).all()
    return {
        "total": total,
        "items": [
            {
                "sample_id": r.sample_id,
                "term_id": r.term_id,
                "text": r.text,
                "kind": r.kind,
                "detected": bool(r.detected),
                "created_at": r.created_at.isoformat(timespec="seconds") if r.created_at else None,
            }
            for r in rows
        ],
    }
