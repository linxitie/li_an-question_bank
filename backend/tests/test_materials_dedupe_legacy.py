# -*- coding: utf-8 -*-
"""老资料去重：hash 回填 + 兜底（2026-11-12 静默失效修复）。

事故：W2 之后建资料会写 `content_hash`，去重只比这一列；但**W2 之前入库的 98 条是 NULL**，
于是重传同一份老资料永远查不到重、又生成一条。

本文件锁死：
  1. 老行（hash=NULL）与新内容同 → 仍判重复（409 + 回老 id）；
  2. 内容不同 → 正常创建（不误杀）；
  3. 行哈希与建资料哈希**同口径**（`_row_content_hash` == `_material_content_hash`）；
  4. 回填脚本对"正文为空"的行不拿标题兜底（保持 NULL，避免假重复）。
"""
import importlib.util
import pathlib

from app.api.v1.library import materials as materials_api
from app.models.models import StudyMaterial


def _legacy_card(db, *, front="老卡正面·传唤", back="老卡背面·出示证件",
                 title="老卡片（W2 之前）"):
    """造一条"W2 之前"的卡片：有内容、`content_hash` 为 NULL。"""
    m = StudyMaterial(subject="gongzhuan", type="card", title=title,
                      card_front=front, card_back=back, status=1,
                      content_hash=None)
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def _create_card(client, headers, front, back, title="新卡片"):
    return client.post("/api/materials/admin", headers=headers,
                       json={"subject": "gongzhuan", "type": "card", "title": title,
                             "card_front": front, "card_back": back})


def test_duplicate_against_legacy_row_without_hash(client, admin_headers, db_session):
    """老行 hash=NULL，同内容新建仍要拦（修复前这里会成功建出第二条）。"""
    legacy = _legacy_card(db_session)
    resp = _create_card(client, admin_headers, legacy.card_front, legacy.card_back)
    assert resp.status_code == 409, resp.text
    assert str(legacy.material_id) in resp.text


def test_different_content_is_not_mistaken(client, admin_headers, db_session):
    """内容不同不能误杀（兜底只认同哈希）。"""
    _legacy_card(db_session)
    resp = _create_card(client, admin_headers, "完全不同的正面", "完全不同的背面")
    assert resp.status_code == 200, resp.text
    assert resp.json()["id"] > 0


def test_row_hash_matches_create_hash(db_session):
    """行哈希与建资料哈希同口径（回填/兜底不会算出两个值）。"""
    legacy = _legacy_card(db_session)
    row_hash = materials_api._row_content_hash(legacy)
    create_hash = materials_api._material_content_hash({
        "type": "card", "card_front": legacy.card_front, "card_back": legacy.card_back,
    })
    assert row_hash == create_hash
    assert len(row_hash) == 32


def test_backfill_script_skips_empty_body():
    """回填脚本：卡片按正反面、其它按正文；正文为空**不**拿标题兜底。"""
    path = (pathlib.Path(__file__).resolve().parents[1]
            / "scripts" / "migrate" / "backfill_material_content_hash.py")
    spec = importlib.util.spec_from_file_location("_bf_hash", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    assert mod._raw_text({"type": "card", "card_front": "a", "card_back": "b",
                          "content": None}) == "ab"
    assert mod._raw_text({"type": "lecture", "content": "正文", "card_front": None,
                          "card_back": None}) == "正文"
    assert mod._raw_text({"type": "paper", "content": "", "title": "某卷",
                          "card_front": None, "card_back": None}) == ""
