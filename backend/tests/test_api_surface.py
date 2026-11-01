"""A8 守门：实际 API 面不得比记录基线少任何操作（除已文档化的 2 处 feedback 迁移）。"""
import json
import re
from pathlib import Path

from app.main import app

BASELINE_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "refactor_baseline"
    / "api_surface.json"
)

CONVERTER_RE = re.compile(r":[a-zA-Z_]+")

DOCUMENTED_FEEDBACK_MOVES = {
    ("GET", "/api/feedback"),
    ("POST", "/api/feedback/{feedback_id}/reply"),
}

KNOWN_EXTRA_OPERATIONS = {
    ("GET", "/api/admin/feedback"),
    ("POST", "/api/admin/feedback/{feedback_id}/reply"),
    ("GET", "/health"),
    ("GET", "/metrics"),
    ("GET", "/metrics/endpoints"),
    ("GET", "/metrics/system"),
    ("POST", "/metrics/reset"),
    ("GET", "/{full_path}"),
    ("GET", "/api/v1/growth/checkin/status"),
    ("POST", "/api/v1/growth/checkin"),
    # R11 显式批准的新增（2026-10-25，用户指示"先1后2"后登记）：
    # 题组材料上传图片，用于复合题共享材料配图。
    # 鉴权：require_teacher_or_admin；校验：content-type 白名单 + 扩展名白名单 + 10MB 上限 + 题组存在性。
    # 只登记不重算基线 —— api_surface.json 仍保持 343 条冻结口径，新增走本白名单单独可审计。
    ("POST", "/api/questions/group/{group_id}/images"),
    # ===== 备考资料 / 徽章工作流新增（2026-11-01 补登记）=====
    # 说明：这些端点是 `feat/Study-Material-Management` 交付线里陆续加的，
    # 当时只改了代码没登记白名单，导致本守卫从那时起一直红。此处按 R11
    # 「只登记不重算基线」的口径一次性补齐，基线文件仍冻结 343 条。
    # 徽章（需求(6)：成就/金币/徽章联动）
    ("GET", "/api/badges/catalog"),
    ("GET", "/api/badges/summary"),
    ("GET", "/api/badges/my"),
    ("GET", "/api/badges/wall"),
    ("GET", "/api/badges/top"),
    ("PUT", "/api/badges/top"),
    # 成长（徽章命名库 / 管理员建成就）
    ("POST", "/api/achievements/admin"),
    ("GET", "/api/achievements/name-bank/status"),
    ("GET", "/health/foundation"),
    # 备考资料：个人库（B1 三角色建卡）
    ("POST", "/api/materials/my"),
    ("GET", "/api/materials/my"),
    ("PUT", "/api/materials/my/{material_id}"),
    ("DELETE", "/api/materials/my/{material_id}"),
    # 备考资料：共享区 / 领取 / 一卡多图
    ("GET", "/api/materials/shared"),
    ("POST", "/api/materials/{material_id}/share"),
    ("POST", "/api/materials/{material_id}/unshare"),
    ("POST", "/api/materials/{material_id}/adopt"),
    ("POST", "/api/materials/admin/cards/batch-image"),
    # 备考资料：分类规则后台（专利主张(3)）
    ("GET", "/api/materials/admin/rules"),
    ("POST", "/api/materials/admin/rules"),
    ("PUT", "/api/materials/admin/rules/{rule_id}"),
    ("PATCH", "/api/materials/admin/rules/{rule_id}/toggle"),
    # 备考资料：学生上传（表格批量，待审）
    ("POST", "/api/materials/my/upload"),
    # 备考资料：学生手动建卡（免审批，2026-11-01 本轮新增）+ 分类法只读契约
    ("POST", "/api/materials/my/card"),
    ("GET", "/api/materials/taxonomy"),
}


def _normalize(path):
    return CONVERTER_RE.sub("", path)


def _baseline_operations():
    surface = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    operations = set()
    for module in surface.values():
        prefix = module["prefix"]
        for endpoint in module["endpoints"]:
            operations.add(
                (endpoint["method"].upper(), _normalize(prefix + endpoint["path"]))
            )
    return operations


def _actual_operations():
    return {
        (method.upper(), path)
        for path, operations in app.openapi()["paths"].items()
        for method in operations
    }


def test_api_surface_has_no_undocumented_deletions():
    expected = _baseline_operations()
    actual = _actual_operations()

    missing = expected - actual - DOCUMENTED_FEEDBACK_MOVES
    assert missing == set(), f"undocumented API removals/renames: {sorted(missing)}"

    extras = actual - expected
    assert extras <= KNOWN_EXTRA_OPERATIONS, (
        f"unexpected new API operations: {sorted(extras - KNOWN_EXTRA_OPERATIONS)}"
    )


def test_documented_feedback_moves_are_the_only_ones_absent():
    missing = _baseline_operations() - _actual_operations()
    assert missing == DOCUMENTED_FEEDBACK_MOVES
