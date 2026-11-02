"""关键路由注册守卫。

背景（2026-11-02）：`app.include_router(image_media.router)` 在 60ca515 合并
origin/main 时被冲突解决丢掉，但模块仍被 import，于是 `POST /api/media/image`
落到 media_assets 的 `GET /api/media/{asset_id}` 兜底路由，返回 405 而不是上传。

这类"合并丢注册"不会报 ImportError，只会让某个功能静默 404/405，因此用一张
关键路由清单做冒烟守卫：任何一条从路由表里消失，本测试立即失败。
清单只放跨端核心链路，新增条目时请同步更新本文件的注释。
"""

from app.main import app

# (HTTP 方法, 路径)：跨端核心链路 + 曾经被合并事故打掉的路由
CRITICAL_ROUTES = [
    # 论坛图片上传（60ca515 合并丢失 → 405）
    ("POST", "/api/media/image"),
    # 媒体资产读取与上传（论坛附件链路）
    ("GET", "/api/media/{asset_id}"),
    ("POST", "/api/media/upload"),
    ("POST", "/api/media/import"),
    # 论坛三端列表（教师端/管理端 404 事故）
    ("GET", "/api/forum/posts"),
    ("GET", "/api/teacher/forum/posts"),
    ("GET", "/api/admin/forum/posts"),
    # 联考小智对话与学习计划（401/503 事故）
    ("POST", "/api/llm/chat"),
    ("POST", "/api/plan/generate"),
    # 考试链路（开始考试/交卷 500 事故）
    ("GET", "/api/exams/{paper_id}/questions"),
    ("POST", "/api/exams/{paper_id}/start"),
    ("POST", "/api/exams/{record_id}/submit"),
    # 登录入口（教师账号无法登录事故）
    ("POST", "/api/auth/login"),
    # 健康检查（版本自检依赖）
    ("GET", "/health"),
]


def _registered_routes() -> set[tuple[str, str]]:
    """把 FastAPI 路由表摊平成 (method, path) 集合。"""
    result: set[tuple[str, str]] = set()
    for route in app.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None) or set()
        if not path:
            continue
        for method in methods:
            result.add((method.upper(), path))
    return result


def test_critical_routes_are_registered():
    registered = _registered_routes()
    missing = [pair for pair in CRITICAL_ROUTES if pair not in registered]
    assert not missing, f"关键路由未注册（疑似合并丢 include_router）：{missing}"
