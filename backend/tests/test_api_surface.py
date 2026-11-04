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
    # F1 一致性内核健康快照（非业务端点，只读）。
    ("GET", "/health/foundation"),
    # F3 媒体资产稳定读取代理（新资产 URL；旧 /uploads 与 /static 不变）。
    # 公开只读、ETag/Range/HEAD；新增走本白名单，不重算 343 条基线。
    ("GET", "/media/{asset_id}"),
    ("HEAD", "/media/{asset_id}"),
    # R11 显式批准的新增（2026-11-01，任务「学生端练习记录可视化 + 未完成答题卡续答」）：
    # 做法与上面一致：只登记白名单，api_surface.json 仍保持 343 条冻结口径，不重算基线。
    # ① 未完成答题卡续答：只读，从 exam_record + paper_question_relation + exam_answer_detail
    #    还原断点题目与已存答案；本人校验，已完成 409，题目被撤下则跳过而非整页 404。
    ("GET", "/api/exams/records/{record_id}/resume"),
    # ② 学习分布：只读聚合，口径同 /api/practice/unified-stats（排除智能组卷双计）。
    ("GET", "/api/stats/subject-distribution"),
    # ③ 错题知识点统计：只读聚合，dimension=subcategory|point 两维可选。
    ("GET", "/api/wrong-questions/point-stats"),
    # ④ 练习草稿（服务端，30 天 TTL，唯一键 user_id+scope+scope_key）：重启浏览器/换设备可续。
    ("POST", "/api/practice/draft"),
    ("GET", "/api/practice/draft"),
    ("GET", "/api/practice/drafts"),
    ("DELETE", "/api/practice/draft"),
    # R11 显式批准的新增（2026-11-03，任务「论坛敏感词自生长知识库」）：
    # 只登记白名单，api_surface.json 仍保持 343 条冻结口径。
    # 鉴权：require_admin（role_level >= 2）；Agent 无 HTTP 入口，只能经服务层提案。
    # 输出：词条/政策/判定/任务/提案/审计哈希链/图谱/趋势/红队/Obsidian 投影/对账。
    ("GET", "/api/v1/admin/content-guard/overview"),
    ("GET", "/api/v1/admin/content-guard/terms"),
    ("POST", "/api/v1/admin/content-guard/terms"),
    ("PATCH", "/api/v1/admin/content-guard/terms/{term_id}"),
    ("GET", "/api/v1/admin/content-guard/terms/{term_id}/variants"),
    ("POST", "/api/v1/admin/content-guard/terms/{term_id}/variants"),
    ("DELETE", "/api/v1/admin/content-guard/variants/{variant_id}"),
    ("GET", "/api/v1/admin/content-guard/policies"),
    ("POST", "/api/v1/admin/content-guard/policies"),
    ("GET", "/api/v1/admin/content-guard/judgments"),
    ("GET", "/api/v1/admin/content-guard/judgments/{judgment_id}"),
    ("POST", "/api/v1/admin/content-guard/judgments/{judgment_id}/override"),
    ("GET", "/api/v1/admin/content-guard/tasks"),
    ("POST", "/api/v1/admin/content-guard/tasks/{task_id}/resolve"),
    ("GET", "/api/v1/admin/content-guard/proposals"),
    ("POST", "/api/v1/admin/content-guard/proposals"),
    ("POST", "/api/v1/admin/content-guard/proposals/{proposal_id}/approve"),
    ("POST", "/api/v1/admin/content-guard/proposals/{proposal_id}/reject"),
    ("GET", "/api/v1/admin/content-guard/audit"),
    ("GET", "/api/v1/admin/content-guard/audit/verify"),
    ("GET", "/api/v1/admin/content-guard/graph"),
    ("GET", "/api/v1/admin/content-guard/stats/trend"),
    ("POST", "/api/v1/admin/content-guard/detect"),
    ("POST", "/api/v1/admin/content-guard/redteam/run"),
    ("GET", "/api/v1/admin/content-guard/redteam/samples"),
    ("POST", "/api/v1/admin/content-guard/obsidian/export"),
    ("POST", "/api/v1/admin/content-guard/obsidian/import"),
    ("POST", "/api/v1/admin/content-guard/reconcile"),
    ("POST", "/api/v1/admin/content-guard/seed"),
    ("POST", "/api/v1/admin/content-guard/reload"),
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
