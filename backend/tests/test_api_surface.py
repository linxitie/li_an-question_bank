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
    # 2026-11-04 合并远端 main 后复核：反馈工单化保留了 POST /api/feedback/{feedback_id}/reply，
    # 仅 GET /api/feedback 仍为「已文档化下线」，故本集合只留这一条。
    ("GET", "/api/feedback"),
}

KNOWN_EXTRA_OPERATIONS = {
    # ===== 周任务 M2（2026-11-05）=====
    ("GET", "/api/tasks/weekly/pool"),
    ("POST", "/api/tasks/weekly/pool/pin"),
    ("POST", "/api/tasks/weekly/recalc"),
    ("POST", "/api/tasks/weekly/expire"),
    # ===== 金币购 M1.5（2026-11-05，卡密交付/待处理订单）=====
    ("POST", "/api/admin/shop/products/{product_id}/codes"),
    ("GET", "/api/admin/shop/products/{product_id}/codes/stats"),
    ("GET", "/api/admin/shop/orders"),
    ("POST", "/api/admin/shop/orders/{order_id}/ship"),
    # ===== 金币购 M1（2026-11-04，R11：只登记不重算基线）=====
    ("GET", "/api/coins/expiring"),
    ("GET", "/api/coupons/mine"),
    ("POST", "/api/coupons/grant"),
    ("GET", "/api/shop/products/{product_id}/quote"),
    ("GET", "/api/shop/exchange/mine"),
    ("GET", "/api/admin/shop/stock-alerts"),
    ("POST", "/api/admin/shop/products/{product_id}/shelf"),
    ("GET", "/api/admin/shop/metrics"),
    # ===== 论坛本轮新增（2026-11-03/04，R11：只登记不重算基线）=====
    ("POST", "/api/forum/drafts"),
    ("GET", "/api/forum/drafts/mine"),
    ("DELETE", "/api/forum/drafts/mine"),
    ("GET", "/api/admin/forum/dashboard"),
    ("POST", "/api/admin/forum/posts/batch"),
    ("POST", "/api/admin/forum/posts/{post_id}/hide"),
    ("POST", "/api/admin/forum/posts/{post_id}/unhide"),
    ("POST", "/api/admin/forum/posts/{post_id}/pin"),
    ("POST", "/api/forum/ai-title/suggest"),
    ("POST", "/api/admin/forum/ai-titles/backfill"),
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
    # 2026-11-04：徽章展示模块下线（/api/badges/* 六个端点随 badges.py 删除），
    # 白名单里对应条目一并移除；成就/金币相关端点仍保留登记。
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
    # ===== 远端 main（模块4/7 与 F3）新增，合并时保留 =====
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
    # ===== 远端 main 合并补登记（2026-11-04）=====
    # 来源：模块4（学习计划/能力雷达/成就）、模块7（联考小智/知识图谱/记忆/学习仪表盘）、
    # 论坛治理与练习管理员、媒体资产 F3、OCR 候选等端点随远端 main 合入；
    # 此前只在代码里、未登记本白名单，按 R11「只登记不重算基线」一次补齐（基线仍冻结 343 条）。
    ("DELETE", "/api/admin/forum/comments/{comment_id}"),
    ("DELETE", "/api/admin/forum/comments/{comment_id}/purge"),
    ("DELETE", "/api/admin/forum/posts/{post_id}"),
    ("DELETE", "/api/admin/forum/posts/{post_id}/purge"),
    ("DELETE", "/api/admin/practice-admins/{user_id}"),
    ("DELETE", "/api/agent/memory/{memory_id}"),
    ("DELETE", "/api/forum/comments/{comment_id}"),
    ("DELETE", "/api/forum/comments/{comment_id}/reactions"),
    ("DELETE", "/api/forum/posts/{post_id}/reactions"),
    ("DELETE", "/api/forum/stickers/{sticker_id}"),
    ("DELETE", "/api/knowledge/relation/{rel_id}"),
    ("DELETE", "/api/llm/sessions/{session_id}"),
    ("DELETE", "/api/plan/{plan_id}"),
    ("DELETE", "/api/teacher/practice-admins/{user_id}"),
    ("GET", "/api/admin/forum/comments"),
    ("GET", "/api/admin/forum/moderation"),
    ("GET", "/api/admin/forum/posts"),
    ("GET", "/api/admin/forum/recycle"),
    ("GET", "/api/admin/forum/recycle/audit"),
    ("GET", "/api/admin/news/pending"),
    ("GET", "/api/admin/practice-admins"),
    ("GET", "/api/agent/memories"),
    ("GET", "/api/agent/tasks"),
    ("GET", "/api/agent/trajectory"),
    ("GET", "/api/exams/{paper_id}"),
    ("GET", "/api/feedback/{feedback_id}"),
    ("GET", "/api/forum/my-favorites"),
    ("GET", "/api/forum/my-likes"),
    ("GET", "/api/forum/stickers"),
    ("GET", "/api/knowledge/categories"),
    ("GET", "/api/knowledge/graph"),
    ("GET", "/api/knowledge/nodes"),
    ("GET", "/api/knowledge/nodes/{node_id}/detail"),
    ("GET", "/api/knowledge/relations"),
    ("GET", "/api/knowledge/stats"),
    ("GET", "/api/knowledge/vault"),
    ("GET", "/api/llm/context/assemble"),
    ("GET", "/api/llm/sessions"),
    ("GET", "/api/llm/sessions/{session_id}/messages"),
    ("GET", "/api/news/categories"),
    ("GET", "/api/news/digest"),
    ("GET", "/api/news/timeline"),
    ("GET", "/api/notifications"),
    ("GET", "/api/plan/current"),
    ("GET", "/api/plan/notifies"),
    ("GET", "/api/plan/today"),
    ("GET", "/api/plan/{plan_id}/tasks"),
    ("GET", "/api/post/search"),
    ("GET", "/api/post/stats"),
    ("GET", "/api/profile"),
    ("GET", "/api/profile/questions"),
    ("GET", "/api/questions/group/{group_id}/ocr-candidates"),
    ("GET", "/api/questions/{question_id}/ocr-candidates"),
    ("GET", "/api/teacher/forum/posts"),
    ("GET", "/api/teacher/forum/posts/{post_id}/comments"),
    ("GET", "/api/teacher/practice-admins"),
    ("GET", "/api/teacher/scores/class-compare"),
    ("POST", "/api/admin/forum/comments/{comment_id}/restore"),
    ("POST", "/api/admin/forum/moderation/{moderation_id}/approve"),
    ("POST", "/api/admin/forum/moderation/{moderation_id}/reject"),
    ("POST", "/api/admin/forum/posts/{post_id}/restore"),
    ("POST", "/api/admin/news/{news_id}/review"),
    ("POST", "/api/admin/practice-admins"),
    ("POST", "/api/agent/import-today"),
    ("POST", "/api/agent/run"),
    ("POST", "/api/forum/comments/{comment_id}/reactions/{reaction_code}"),
    ("POST", "/api/forum/posts/{post_id}/favorite"),
    ("POST", "/api/forum/posts/{post_id}/reactions/{reaction_code}"),
    ("POST", "/api/forum/reports"),
    ("POST", "/api/forum/stickers"),
    ("POST", "/api/knowledge/nodes"),
    ("POST", "/api/knowledge/nodes/{node_id}/approve"),
    ("POST", "/api/knowledge/nodes/{node_id}/reject"),
    ("POST", "/api/knowledge/relation"),
    ("POST", "/api/knowledge/relation/suggest"),
    ("POST", "/api/knowledge/vault/import"),
    ("POST", "/api/llm/sessions"),
    ("POST", "/api/plan/adjust"),
    ("POST", "/api/plan/generate"),
    ("POST", "/api/plan/notify/{notify_id}/read"),
    ("POST", "/api/plan/task/{goal_id}/claim"),
    ("POST", "/api/plan/task/{goal_id}/toggle"),
    ("POST", "/api/post/import"),
    ("POST", "/api/profile/upsert"),
    ("POST", "/api/questions/group/{group_id}/ocr-apply"),
    ("POST", "/api/questions/{question_id}/ocr-apply"),
    ("POST", "/api/teacher/forum/comments/{comment_id}/hide"),
    ("POST", "/api/teacher/forum/posts/{post_id}/hide"),
    ("POST", "/api/teacher/practice-admins"),
    ("PUT", "/api/forum/comments/{comment_id}/pin"),
    ("PUT", "/api/forum/posts/{post_id}"),
    ("PUT", "/api/notifications/read-all"),
    ("PUT", "/api/notifications/{notification_id}/read"),
    # ===== 本次合并补登记（2026-11-04）=====
    # 管理员端用户/权限工作台、知识图谱查询、媒体资产 /api 别名与 Agent 反馈入口
    # 在两侧分支各自新增，合并冲突解决时白名单取并集后仍缺这批条目；
    # 仍按 R11「只登记不重算基线」补齐，api_surface.json 保持 343 条冻结口径。
    ("DELETE", "/api/admin/users/{user_id}"),
    ("GET", "/api/admin/permission-audit"),
    ("GET", "/api/admin/permission-health"),
    ("GET", "/api/admin/permissions/catalog"),
    ("GET", "/api/admin/quotes/candidates"),
    ("GET", "/api/admin/users/stats"),
    ("GET", "/api/admin/users/{user_id}"),
    ("GET", "/api/admin/users/{user_id}/permissions"),
    ("GET", "/api/kg/nodes/{node_type}/{node_id}"),
    ("GET", "/api/kg/search"),
    ("GET", "/api/kg/subgraph"),
    ("GET", "/api/kg/topics"),
    ("GET", "/api/media/{asset_id}"),
    ("HEAD", "/api/media/{asset_id}"),
    ("POST", "/api/admin/permission-batches/{batch_id}/undo"),
    ("POST", "/api/admin/quotes/{quote_ref}/review"),
    ("POST", "/api/admin/users/batch"),
    ("POST", "/api/admin/users/permissions/apply"),
    ("POST", "/api/admin/users/permissions/preview"),
    ("POST", "/api/admin/users/{user_id}/purge"),
    ("POST", "/api/admin/users/{user_id}/restore"),
    ("POST", "/api/agent/feedback"),
    ("POST", "/api/agent/upload"),
    ("POST", "/api/media/image"),
    ("PUT", "/api/admin/users/{user_id}/permissions"),
    ("PUT", "/api/admin/users/{user_id}/role"),
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
