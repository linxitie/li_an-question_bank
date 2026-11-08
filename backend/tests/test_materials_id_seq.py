# -*- coding: utf-8 -*-
"""ID 方案 A（2026-11-08）：列表默认按「列表时间」倒序 + 连续序号 `seq`。

用户要求（原文）：
①列表按 ID 降序（ID 就是上传先后）；②删除中间一条后，比它大的号都 -1、最大号 == 总资料数；
③从回收站恢复的资料放回列表最前面，拿"当前最大号"，不复用旧号。

实现选择：**展示序号**而不是重排主键（理由见
`docs/plans/资料管理_ID连续与排序_修复方案_v1.md` §3：重排要级联 3 表 31 行 +
518 条审计文本错位，不可逆）。
  · 排序键 `list_time`（平时 == create_time，恢复时刷成 now）→ 恢复项天然置顶；
  · `seq` = 当前筛选内的倒序名次（首行 = total），删除自动前移，永不重复使用旧号。
"""
from datetime import datetime, timedelta

from app.models.models import StudyMaterial


def _mk(db, *, mid_title, status=1, subject="gongzhuan", mtype="card",
        created=None, list_time=None):
    """建一条资料；显式给 create_time/list_time，避免 ORM 默认值把顺序压成同一时刻。"""
    base = created or datetime(2026, 10, 1, 12, 0, 0)
    m = StudyMaterial(
        subject=subject, type=mtype, title=mid_title, status=status,
        card_front="正面", card_back="背面",
        create_time=base, list_time=list_time or base,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def _list(client, headers, **params):
    r = client.get("/api/materials/admin/list", params={"page_size": 100, **params},
                   headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def test_default_order_is_list_time_desc_with_continuous_seq(
        client, db_session, admin_headers):
    """T1/T3/T4：默认倒序 = list_time desc；seq 从 total 递减到 1。"""
    base = datetime(2026, 10, 1, 12, 0, 0)
    for i in range(3):
        _mk(db_session, mid_title=f"顺序-{i}", created=base + timedelta(minutes=i))

    body = _list(client, admin_headers)
    ids = [row["id"] for row in body["items"]]
    seqs = [row["seq"] for row in body["items"]]
    assert ids == sorted(ids, reverse=True), ids
    assert seqs == [body["total"], body["total"] - 1, body["total"] - 2], seqs


def test_paging_stable_no_dup_no_gap(client, db_session, admin_headers):
    """T1：翻页不重不漏，seq 连续（25 条 / 每页 10）。"""
    base = datetime(2026, 10, 1, 12, 0, 0)
    for i in range(25):
        _mk(db_session, mid_title=f"分页-{i:02d}", created=base + timedelta(minutes=i))

    ids, seqs = [], []
    for page in (1, 2, 3):
        r = client.get("/api/materials/admin/list",
                       params={"page": page, "page_size": 10}, headers=admin_headers)
        assert r.status_code == 200, r.text
        items = r.json()["items"]
        ids += [row["id"] for row in items]
        seqs += [row["seq"] for row in items]

    assert len(ids) == 25 and len(set(ids)) == 25, "跨页不得重复/遗漏"
    assert ids == sorted(ids, reverse=True)
    assert seqs == list(range(25, 0, -1)), seqs


def test_delete_middle_shifts_seq_and_keeps_max_equal_total(
        client, db_session, admin_headers):
    """T5：删除中间一条 → 序号整体前移，最大序号 == 总资料数。"""
    base = datetime(2026, 10, 1, 12, 0, 0)
    made = [_mk(db_session, mid_title=f"删除-{i}", created=base + timedelta(minutes=i))
            for i in range(5)]
    middle = made[2]

    r = client.delete(f"/api/materials/admin/{middle.material_id}", headers=admin_headers)
    assert r.status_code == 200, r.text

    body = _list(client, admin_headers)
    ids = [row["id"] for row in body["items"]]
    seqs = [row["seq"] for row in body["items"]]
    assert middle.material_id not in ids
    assert body["total"] == 4
    assert seqs == [4, 3, 2, 1], seqs
    assert max(seqs) == body["total"]


def test_restore_puts_material_on_top_with_max_seq(
        client, db_session, admin_headers):
    """T7：恢复 → 出现在第一行，seq == total；`create_time`（上传时间）保持真实不变。"""
    base = datetime(2026, 10, 1, 12, 0, 0)
    _mk(db_session, mid_title="旧的-1", created=base)
    _mk(db_session, mid_title="旧的-2", created=base + timedelta(minutes=1))
    dead = _mk(db_session, mid_title="被删的", status=-1, created=base - timedelta(days=3))
    original_created = dead.create_time

    r = client.put(f"/api/materials/admin/{dead.material_id}/status",
                   json={"status": 0}, headers=admin_headers)
    assert r.status_code == 200, r.text

    body = _list(client, admin_headers)
    first = body["items"][0]
    assert first["id"] == dead.material_id, "恢复的资料应排在列表最前"
    assert first["seq"] == body["total"], "倒序编号下它就是「最大号」"
    row = db_session.query(StudyMaterial).filter(
        StudyMaterial.material_id == dead.material_id).first()
    db_session.refresh(row)
    assert row.create_time == original_created, "上传时间不得被恢复动作改写"
    assert row.list_time is not None and row.list_time > original_created


def test_seq_is_scoped_to_current_filter(client, db_session, admin_headers):
    """T9：序号口径 = 当前筛选结果内（D2）。"""
    base = datetime(2026, 10, 1, 12, 0, 0)
    _mk(db_session, mid_title="公专-A", subject="gongzhuan", created=base)
    _mk(db_session, mid_title="行测-B", subject="xingce", created=base + timedelta(minutes=1))
    _mk(db_session, mid_title="行测-C", subject="xingce", created=base + timedelta(minutes=2))

    body = _list(client, admin_headers, subject="xingce")
    assert body["total"] == 2
    assert [row["seq"] for row in body["items"]] == [2, 1]


def test_created_time_sorting_still_available(client, db_session, admin_headers):
    """T8（回归）：`order=created_asc/desc` 仍按真实上传时间排序。"""
    base = datetime(2026, 10, 1, 12, 0, 0)
    _mk(db_session, mid_title="时间-早", created=base)
    _mk(db_session, mid_title="时间-晚", created=base + timedelta(hours=1))

    asc = [row["id"] for row in _list(client, admin_headers, order="created_asc")["items"]]
    assert asc == sorted(asc), asc
    desc = [row["id"] for row in _list(client, admin_headers, order="created_desc")["items"]]
    assert desc == sorted(desc, reverse=True), desc


def test_asc_mode_seq_counts_up(client, db_session, admin_headers):
    """id_asc 时序号 1..N（正序阅读友好）。"""
    base = datetime(2026, 10, 1, 12, 0, 0)
    for i in range(3):
        _mk(db_session, mid_title=f"正序-{i}", created=base + timedelta(minutes=i))

    body = _list(client, admin_headers, order="id_asc")
    assert [row["seq"] for row in body["items"]] == [1, 2, 3]


def test_new_uploaded_material_lands_on_top(client, db_session, admin_headers):
    """T10：新建资料自动带 list_time=now → 出现在第一行、seq == total。"""
    base = datetime(2026, 10, 1, 12, 0, 0)
    _mk(db_session, mid_title="比我早的", created=base + timedelta(days=1))

    r = client.post("/api/materials/admin", json={
        "subject": "gongzhuan", "type": "card", "title": "刚建的",
        "card_front": "正", "card_back": "反", "publish": False,
    }, headers=admin_headers)
    assert r.status_code == 200, r.text
    new_id = r.json()["id"]

    body = _list(client, admin_headers)
    assert body["items"][0]["id"] == new_id
    assert body["items"][0]["seq"] == body["total"]
