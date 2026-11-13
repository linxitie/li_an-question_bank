"""知识库初始目录：政策条款 + 分级词条 + 变体 + 图谱边。

只做幂等 upsert，不覆盖人工已修改的等级/状态；首次启动时由
content_guard_schema.ensure_schema 调用，测试可显式调用。
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ...models.content_guard import CgPolicy, CgTerm, CgVariant
from . import graph, normalizer

POLICIES: tuple[dict[str, Any], ...] = (
    {"code": "PG-01", "title": "政治安全与政权制度", "category": "political", "level": "blocked", "severity": 5, "priority": 100, "legal_basis": "《网络安全法》《互联网信息服务管理办法》"},
    {"code": "PG-02", "title": "暴力恐怖与极端主义", "category": "violence", "level": "blocked", "severity": 5, "priority": 95, "legal_basis": "《反恐怖主义法》"},
    {"code": "PG-03", "title": "淫秽色情信息", "category": "porn", "level": "blocked", "severity": 5, "priority": 90, "legal_basis": "《治安管理处罚法》第六十八条"},
    {"code": "PG-04", "title": "赌博与私彩", "category": "gambling", "level": "blocked", "severity": 5, "priority": 90, "legal_basis": "《治安管理处罚法》第七十条"},
    {"code": "PG-05", "title": "毒品与吸毒工具", "category": "drug", "level": "blocked", "severity": 5, "priority": 92, "legal_basis": "《禁毒法》"},
    {"code": "PG-06", "title": "考试作弊与泄题", "category": "exam_fraud", "level": "reviewed", "severity": 4, "priority": 80, "legal_basis": "《公务员考试录用违纪违规行为处理办法》"},
    {"code": "PG-07", "title": "侮辱谩骂与人身攻击", "category": "abuse", "level": "masked", "severity": 3, "priority": 60, "legal_basis": "《网络信息内容生态治理规定》"},
    {"code": "PG-08", "title": "广告引流与诈骗", "category": "ad", "level": "masked", "severity": 3, "priority": 55, "legal_basis": "《广告法》《反电信网络诈骗法》"},
    {"code": "PG-09", "title": "公序良俗与低俗擦边", "category": "social_ethics", "level": "reviewed", "severity": 2, "priority": 40, "legal_basis": "《网络信息内容生态治理规定》"},
    {"code": "PG-10", "title": "文化偏好与备考秩序", "category": "culture", "level": "reviewed", "severity": 2, "priority": 30, "legal_basis": "校园社区管理规范"},
    {"code": "PG-99", "title": "其他待研判内容", "category": "other", "level": "reviewed", "severity": 1, "priority": 10, "legal_basis": "人工复核兜底"},
)

# 词条按违规域分桶；level 与政策条款默认等级一致
TERM_BUCKETS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("porn", "blocked", ("嫖娼", "卖淫", "色情", "av女优", "一夜情", "找小姐", "包夜", "裸聊", "裸照", "黄色视频", "成人电影", "性服务", "援交")),
    ("gambling", "blocked", ("赌博", "六合彩", "私彩", "开盘", "押注", "赌场", "网络赌博", "赌资", "赔率", "庄家", "出千", "赌局")),
    ("drug", "blocked", ("贩毒", "吸毒", "冰毒", "大麻", "海洛因", "摇头丸", "k粉", "可卡因", "毒品交易", "吸毒工具")),
    ("violence", "blocked", ("炸弹制作", "杀人方法", "自制刀具", "爆炸物配方", "恐怖袭击", "极端组织", "圣战")),
    ("political", "blocked", ("反动", "颠覆政权", "分裂国家")),
    ("abuse", "masked", ("傻逼", "草泥马", "我操", "卧槽", "妈的", "他妈的", "滚蛋", "去死", "废物", "脑残", "白痴", "贱人", "婊子", "王八蛋", "狗屎", "屁眼")),
    ("social_ethics", "masked", ("约炮", "撩妹", "泡妞", "老司机", "开车")),
    ("ad", "masked", ("加微信", "加qq", "扫码", "点击链接", "免费领取", "中奖了", "代刷", "兼职加我")),
    ("exam_fraud", "reviewed", ("代考", "包过", "真题泄露", "试题答案", "考前答案", "保过班", "内部题库", "泄露题", "卖答案", "透题")),
    ("culture", "reviewed", ("漏洞", "后门", "破解", "绕过")),
)

# 红队用的单字同音替换表：命中后由提案流程决定是否入库
HOMOPHONES: dict[str, str] = {
    "赌": "堵", "毒": "独", "嫖": "飘", "娼": "昌", "淫": "银",
    "黄": "皇", "色": "涩", "傻": "沙", "逼": "比", "妈": "马",
    "操": "草", "贱": "溅", "婊": "表", "骚": "扫", "赌": "睹",
    "杀": "沙", "枪": "抢", "炸": "诈", "骗": "偏",
}


def _category_policy(db: Session) -> dict[str, CgPolicy]:
    rows = db.query(CgPolicy).filter(CgPolicy.status == "active").all()
    return {p.category: p for p in rows}


def seed_policies(db: Session) -> int:
    created = 0
    existing = {p.code for p in db.query(CgPolicy).all()}
    for item in POLICIES:
        if item["code"] in existing:
            continue
        db.add(
            CgPolicy(
                code=item["code"],
                title=item["title"],
                category=item["category"],
                level=item["level"],
                severity=item["severity"],
                priority=item["priority"],
                status="active",
                legal_basis=item["legal_basis"],
                content=item["title"],
                effective_from=datetime.now(),
                version=1,
            )
        )
        created += 1
    db.flush()
    return created


_DATA_FILE = Path(__file__).resolve().parent / "data" / "seed_terms.json"


def _load_portable_terms() -> list[tuple[str, str, str, list[str]]]:
    """读取随仓库分发的完整词表（2026-11-07）。

    背景：vault 词表不进版本库，换一台电脑只拉代码时，仅 88 条内置种子会漏掉
    人工/知识库补充的词，表现为「敏感词不打码」。这里把当前库 180 条导出为
    JSON 一起发版，任何机器首次启动即可得到同一套词表。
    """
    try:
        payload = json.loads(_DATA_FILE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return []
    out: list[tuple[str, str, str, list[str]]] = []
    for item in payload.get("terms") or []:
        word = str(item.get("term") or "").strip()
        if not word:
            continue
        out.append(
            (
                word,
                str(item.get("level") or "reviewed"),
                str(item.get("category") or "other"),
                [str(v) for v in (item.get("variants") or []) if str(v).strip()],
            )
        )
    return out


_PORTABLE_TERMS = _load_portable_terms()


def _variant_candidates(term: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for idx, ch in enumerate(term):
        replacement = HOMOPHONES.get(ch)
        if replacement and replacement != ch:
            out.append((term[:idx] + replacement + term[idx + 1 :], "homophone"))
        if len(out) >= 2:
            break
    return out


def _ensure_term(
    db: Session,
    word: str,
    level: str,
    category: str,
    policies: dict[str, CgPolicy],
    extra_variants: tuple[str, ...] = (),
) -> tuple[int, int]:
    norm = normalizer.normalize(word)
    if not norm:
        return 0, 0
    policy = policies.get(category)
    term = db.query(CgTerm).filter(CgTerm.normalized == norm).first()
    created_terms = 0
    if term is None:
        term = CgTerm(
            term=word,
            normalized=norm,
            level=level,
            category=category,
            weight=0.9 if level == "blocked" else (0.8 if level == "masked" else 0.65),
            confidence=0.9 if level == "blocked" else (0.8 if level == "masked" else 0.65),
            status="active",
            source="seed",
            policy_clause_id=policy.clause_id if policy else None,
            created_by=0,
            first_seen_at=datetime.now(),
            note="内置/随仓库词表",
        )
        db.add(term)
        db.flush()
        created_terms = 1
    graph.add_edge(db, "term", term.term_id, "cites", "policy", policy.clause_id if policy else "none")
    graph.add_edge(db, "term", term.term_id, "belongs_to", "category", category)

    candidates = list(_variant_candidates(term.term))
    for extra in extra_variants:
        candidates.append((extra, "manual"))
    created_variants = 0
    for variant_text, kind in candidates:
        vnorm = normalizer.normalize(variant_text)
        if not vnorm or vnorm == term.normalized:
            continue
        exists = (
            db.query(CgVariant)
            .filter(CgVariant.term_id == term.term_id, CgVariant.normalized == vnorm)
            .first()
        )
        if exists:
            continue
        db.add(
            CgVariant(
                term_id=term.term_id,
                variant=variant_text,
                normalized=vnorm,
                kind=kind,
                status="active",
                created_by=0,
            )
        )
        db.flush()
        created_variants += 1
        graph.add_edge(db, "variant", db.query(CgVariant).filter(CgVariant.term_id == term.term_id, CgVariant.normalized == vnorm).first().variant_id, "variant_of", "term", term.term_id)
    return created_terms, created_variants


def seed_terms(db: Session, actor: str = "system") -> dict[str, int]:
    policies = _category_policy(db)
    created_terms = 0
    created_variants = 0
    for category, level, words in TERM_BUCKETS:
        for word in words:
            t, v = _ensure_term(db, word, level, category, policies)
            created_terms += t
            created_variants += v
    # 随仓库分发的完整词表（包含 vault / 人工补充的词）
    for word, level, category, variants in _PORTABLE_TERMS:
        t, v = _ensure_term(db, word, level, category, policies, tuple(variants))
        created_terms += t
        created_variants += v
    return {"terms": created_terms, "variants": created_variants}
