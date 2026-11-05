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


def _iter_routes(routes, prefix: str = ""):
    """递归展开路由表，产出 (path, methods)。

    为什么不能直接遍历 `app.routes`：
    FastAPI 0.156 起 `include_router` 改为惰性实现，路由表里存的是
    `_IncludedRouter` 对象（fastapi/routing.py），它**没有** `.path` 和 `.methods`，
    真正的路由挂在 `.original_router.routes` 上，前缀在 `.include_context.prefix`。
    旧写法会把这些路由全部当成「未注册」，导致本守卫对任何版本都误报缺失。
    """
    for route in routes:
        included = getattr(route, "original_router", None)
        if included is not None:
            context = getattr(route, "include_context", None)
            sub_prefix = getattr(context, "prefix", "") or ""
            yield from _iter_routes(getattr(included, "routes", []), prefix + sub_prefix)
            continue

        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None) or set()
        if not path:
            continue
        # Mount / Host 之类没有 methods 的容器跳过，它们不是可断言的端点
        if not methods:
            continue
        yield prefix + path, methods


def _registered_routes() -> set[tuple[str, str]]:
    """把 FastAPI 路由表摊平成 (method, path) 集合。"""
    result: set[tuple[str, str]] = set()
    for path, methods in _iter_routes(app.routes):
        for method in methods:
            result.add((method.upper(), path))
    return result


def test_route_expansion_actually_walks_included_routers():
    """自检：展开逻辑必须真的走进 include_router，否则守卫会永远「通过」。"""
    registered = _registered_routes()
    assert len(registered) > 300, f"展开后的路由数异常偏少（{len(registered)}），遍历逻辑可能失效"
    # 正例：真实存在的端点必须在集合里
    assert ("POST", "/api/media/image") in registered
    # 反例：不存在的端点不能凭空出现，否则等于没有守卫
    assert ("POST", "/api/__not_a_real_route__") not in registered


def test_critical_routes_are_registered():
    registered = _registered_routes()
    missing = [pair for pair in CRITICAL_ROUTES if pair not in registered]
    assert not missing, f"关键路由未注册（疑似合并丢 include_router）：{missing}"
