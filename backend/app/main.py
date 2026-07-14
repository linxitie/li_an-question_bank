"""
公安联考题库系统 - FastAPI主应用入口（增强版）
支持HTTP/HTTPS、WebSocket、gRPC协议
"""
import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware as FastAPICORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .core.config import settings
from .api.v1 import auth, questions, papers, exams, videos, llm, goals, stats, media, news, recruitment, calendar, question_actions, practice, forum
from .api.v1 import admin as admin_api
from .api.v1 import teacher as teacher_api
# from .api.v1 import wrong_questions, checkin, coins  # TODO: 待创建
from .api.v1.websocket import router as websocket_router
from .api.v1.paper_generation import router as paper_router
from .api.v1.question_import import router as question_import_router
from .core.security import ws_manager
from .exceptions import register_exception_handlers, ExceptionHandlers, create_error_response
from .middleware import setup_middlewares, RequestLoggingMiddleware, RateLimitMiddleware, CircuitBreakerMiddleware
from .monitoring import metrics_collector, get_system_metrics, PerformanceMonitor






logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(settings.LOG_FILE),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("启动公安联考题库系统服务...")
    logger.info(f"服务地址: http://{settings.HOST}:{settings.PORT}")
    logger.info(f"API文档: http://{settings.HOST}:{settings.PORT}/docs")

    # 自动创建数据库表
    from .core.database import engine, Base, SessionLocal
    from .models import models  # 确保所有模型被导入
    Base.metadata.create_all(bind=engine)
    logger.info("数据库表初始化完成")

    # 自动检测并添加缺失列（解决create_all不支持ALTER TABLE的问题）
    try:
        from sqlalchemy import inspect, text
        inspector = inspect(engine)

        # 检查 exam_calendar 表
        if 'exam_calendar' in inspector.get_table_names():
            exam_cols = [c['name'] for c in inspector.get_columns('exam_calendar')]
            for col_name, col_type in [('url', 'VARCHAR(500)'), ('description', 'TEXT')]:
                if col_name not in exam_cols:
                    with engine.connect() as conn:
                        conn.execute(text(f"ALTER TABLE exam_calendar ADD COLUMN {col_name} {col_type}"))
                        conn.commit()
                    logger.info(f"自动迁移: exam_calendar 添加列 {col_name}")

        # 检查 recruitment_info 表
        if 'recruitment_info' in inspector.get_table_names():
            rec_cols = [c['name'] for c in inspector.get_columns('recruitment_info')]
            for col_name, col_type in [('url', 'VARCHAR(500)')]:
                if col_name not in rec_cols:
                    with engine.connect() as conn:
                        conn.execute(text(f"ALTER TABLE recruitment_info ADD COLUMN {col_name} {col_type}"))
                        conn.commit()
                    logger.info(f"自动迁移: recruitment_info 添加列 {col_name}")

        # 检查 news_article 表
        if 'news_article' in inspector.get_table_names():
            news_cols = [c['name'] for c in inspector.get_columns('news_article')]
            for col_name, col_type in [('content', 'TEXT')]:
                if col_name not in news_cols:
                    with engine.connect() as conn:
                        conn.execute(text(f"ALTER TABLE news_article ADD COLUMN {col_name} {col_type}"))
                        conn.commit()
                    logger.info(f"自动迁移: news_article 添加列 {col_name}")
        # 检查 practice_record 表
        if 'practice_record' in inspector.get_table_names():
            prac_cols = [c['name'] for c in inspector.get_columns('practice_record')]
            for col_name, col_type in [
                ('subject_id', 'INTEGER'),
                ('type_id', 'INTEGER'),
                ('practice_date', 'DATE'),
            ]:
                if col_name not in prac_cols:
                    with engine.connect() as conn:
                        conn.execute(text(f"ALTER TABLE practice_record ADD COLUMN {col_name} {col_type}"))
                        conn.commit()
                    logger.info(f"自动迁移: practice_record 添加列 {col_name}")
        # === 三端分离架构：SysUser 新增字段 ===
        if 'sys_user' in inspector.get_table_names():
            user_cols = [c['name'] for c in inspector.get_columns('sys_user')]
            for col_name, col_type, col_default in [
                ('is_disabled', 'INTEGER', '0'),
                ('disabled_reason', 'VARCHAR(255)', None),
                ('last_login_ip', 'VARCHAR(45)', None),
                ('password_reset_token', 'VARCHAR(255)', None),
                ('password_reset_expire', 'DATETIME', None),
                ('created_by', 'BIGINT', None),
                ('school_id', 'INTEGER', None),
            ]:
                if col_name not in user_cols:
                    default_clause = f"DEFAULT {col_default}" if col_default else ""
                    with engine.connect() as conn:
                        conn.execute(text(f"ALTER TABLE sys_user ADD COLUMN {col_name} {col_type} {default_clause}"))
                        conn.commit()
                    logger.info(f"自动迁移: sys_user 添加列 {col_name}")

        # === 三端分离架构：新增 sys_config 默认配置 ===
        try:
            from .models.models import SysConfig
            db_sess = SessionLocal()
            try:
                default_configs = [
                    ('site_name', '砺安题库', '站点名称', 'STRING'),
                    ('site_logo', '/static/logo.png', '站点Logo', 'STRING'),
                    ('max_login_attempts', '5', '最大登录尝试次数', 'NUMBER'),
                    ('exam_auto_submit_minutes', '120', '考试自动提交时间(分钟)', 'NUMBER'),
                    ('maintenance_mode', 'false', '维护模式', 'BOOLEAN'),
                    ('register_open', 'true', '是否开放注册', 'BOOLEAN'),
                    ('password_min_length', '6', '密码最小长度', 'NUMBER'),
                    ('announcement_default_visible', 'all', '公告默认可见角色', 'STRING'),
                ]
                for key, val, desc, ctype in default_configs:
                    existing = db_sess.query(SysConfig).filter(SysConfig.config_key == key).first()
                    if not existing:
                        db_sess.add(SysConfig(config_key=key, config_value=val, config_desc=desc, config_type=ctype))
                db_sess.commit()
                logger.info("系统默认配置初始化完成")
            finally:
                db_sess.close()
        except Exception as e:
            logger.warning(f"默认配置初始化跳过: {e}")

    except Exception as mig_err:
        logger.warning(f"自动迁移检查失败（可忽略）: {mig_err}")

    # 自动修复已有题目的子科目分类（将'无'重新检测分类）
    try:
        from .api.v1.question_import import _detect_subcategory
        db = SessionLocal()
        try:
            from .models.models import QuestionBank
            uncategorized = db.query(QuestionBank).filter(
                QuestionBank.xingce_subcategory == '无',
                QuestionBank.shenlun_subcategory == '无',
                QuestionBank.gongzhuan_subcategory == '无',
                QuestionBank.status == 1
            ).all()
            if uncategorized:
                fixed_count = 0
                for q in uncategorized:
                    q.xingce_subcategory = _detect_subcategory(1, q.question_content or '', '') if q.subject_id == 1 else '无'
                    q.shenlun_subcategory = _detect_subcategory(2, q.question_content or '', '') if q.subject_id == 2 else '无'
                    q.gongzhuan_subcategory = _detect_subcategory(3, q.question_content or '', '') if q.subject_id == 3 else '无'
                    fixed_count += 1
                db.commit()
                logger.info(f"已为 {fixed_count} 道已有题目重新检测子科目分类")
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"已有题目子科目修复跳过（可能表尚未创建）: {e}")

    try:
        from .grpc_service import setup_grpc_service
        import time
        # gRPC 端口绑定重试（处理快速重启端口未释放）
        max_retries = 3
        for attempt in range(max_retries):
            try:
                setup_grpc_service(app)
                break
            except Exception as e:
                if attempt < max_retries - 1:
                    wait = (attempt + 1) * 2
                    logger.warning(f"gRPC绑定失败，{wait}秒后重试({attempt+1}/{max_retries})...")
                    time.sleep(wait)
                else:
                    raise
    except Exception as e:
        logger.warning(f"gRPC服务初始化失败（不影响 HTTP 服务）: {e}")

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(settings.LOG_FILE), exist_ok=True)

    # 启动定时任务调度器（新闻/招考/考试日历爬取）
    try:
        from .services.scheduler import init_scheduler
        init_scheduler()
        logger.info("定时任务调度器已启动")
    except Exception as e:
        logger.warning(f"定时任务调度器启动失败（服务继续运行）: {e}")

    # 执行种子数据初始化（模拟用户 + 默认配置）
    try:
        from .seed import run_seed
        run_seed()
    except Exception as e:
        logger.warning(f"种子数据初始化失败（服务继续运行）: {e}")

    yield

    logger.info("关闭公安联考题库系统服务...")
    try:
        from .services.scheduler import shutdown_scheduler
        shutdown_scheduler()
    except Exception:
        pass
    try:
        from .grpc_service import stop_grpc_service
        stop_grpc_service()
    except Exception:
        pass

app = FastAPI(
    title="公安联考题库系统",
    description="""
## 公安联考题库系统 API

支持以下核心功能：

- **用户管理**: 学生、教师、管理员三种角色
- **题库管理**: 支持申论、行测、公安专业知识等题型
- **试卷管理**: 手动组卷、自动组卷、智能组卷
- **考试执行**: 实时监控、答题卡提交、自动评分
- **成绩分析**: 多维度分析、薄弱点识别、改进建议
- **视频资源**: 题目讲解视频上传与播放
- **大模型集成**: 智能问答、内容生成

## 协议支持

- HTTP/HTTPS: 标准RESTful API
- WebSocket: 实时通信、在线监考
- gRPC: 高性能远程调用

## 认证方式

- JWT Bearer Token
- OAuth2.0 (支持密码模式、刷新令牌)
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

app.add_middleware(
    FastAPICORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

setup_middlewares(app)
register_exception_handlers(app)

app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")
# 题目图片静态服务
import os as _os
_img_dir = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'static', 'questions')
_os.makedirs(_img_dir, exist_ok=True)
app.mount("/static/questions", StaticFiles(directory=_img_dir), name="question_images")

app.include_router(auth.router)
app.include_router(questions.router)
app.include_router(paper_router, tags=["试卷管理"])
app.include_router(papers.router)
app.include_router(question_import_router)
app.include_router(exams.router)
app.include_router(videos.router)
app.include_router(llm.router)
app.include_router(goals.router)
app.include_router(stats.router)
app.include_router(media.router)
app.include_router(websocket_router)
app.include_router(news.router)
app.include_router(recruitment.router)
app.include_router(calendar.router)
app.include_router(practice.router)
app.include_router(question_actions.router)
app.include_router(forum.router)
app.include_router(admin_api.router, tags=["管理员端"])
app.include_router(teacher_api.router, tags=["教师端"])

@app.get("/health", tags=["系统"])
async def health_check():
    """
    健康检查接口
    """
    return {
        "status": "healthy",
        "service": "公安联考题库系统",
        "version": "1.0.0"
    }

@app.get("/metrics", tags=["系统"])
async def get_metrics():
    return metrics_collector.get_metrics_summary()

@app.get("/metrics/system", tags=["系统"])
async def get_system_metrics_endpoint():
    return get_system_metrics()

# ==================== 前端生产版本托管（SPA） ====================
import os.path as _ospath
_dist = _ospath.join(_ospath.dirname(_ospath.dirname(_ospath.dirname(_ospath.abspath(__file__)))), 'dist')
if _ospath.exists(_dist):
    # 托管 JS/CSS 等静态资源
    _assets = _ospath.join(_dist, 'assets')
    if _ospath.exists(_assets):
        app.mount("/assets", StaticFiles(directory=_assets), name="spa_assets")

    # SPA fallback：非 API 路径返回 index.html
    from fastapi.responses import FileResponse as _FileResponse
    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        """所有非 API 路径返回前端 index.html，由 Vue Router 接管路由"""
        file_path = _ospath.join(_dist, full_path)
        if full_path and _ospath.isfile(file_path):
            return _FileResponse(file_path)
        return _FileResponse(_ospath.join(_dist, 'index.html'))

@app.get("/metrics/endpoints", tags=["系统"])
async def get_endpoint_metrics(
    method: str = None,
    path: str = None
):
    """
    获取各端点性能指标

    - **method**: HTTP方法过滤（可选）
    - **path**: URL路径前缀过滤（可选）
    """
    return metrics_collector.get_endpoint_stats(method=method, path=path)

@app.post("/metrics/reset", tags=["系统"])
async def reset_metrics():
    """
    重置性能指标数据
    """
    metrics_collector.reset_metrics()
    return {"message": "指标已重置"}

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    全局异常处理
    """
    request_id = request.headers.get("X-Request-ID", "unknown")
    logger.error(f"全局异常 [Request-ID: {request_id}]: {str(exc)}", exc_info=True)

    return JSONResponse(
        status_code=500,
        content=create_error_response(
            status_code=500,
            message="系统内部错误，请稍后重试",
            code="INTERNAL_ERROR",
            request_id=request_id
        )
    )

@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    """
    性能监控中间件
    """
    with PerformanceMonitor.track_request(request.method, request.url.path):
        response = await call_next(request)
        return response

def create_app() -> FastAPI:
    return app

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
        ssl_certfile=None,
        ssl_keyfile=None
    )