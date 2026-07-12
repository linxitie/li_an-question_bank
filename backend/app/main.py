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
from .api.v1 import auth, questions, papers, exams, videos, llm, goals, stats, media
from .api.v1.websocket import router as websocket_router
from .api.v1.paper_generation import router as paper_router
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

    try:
        from .grpc_service import setup_grpc_service
        setup_grpc_service(app)
    except Exception as e:
        logger.warning(f"gRPC服务初始化失败: {e}")

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(settings.LOG_FILE), exist_ok=True)

    yield

    logger.info("关闭公安联考题库系统服务...")
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

app.include_router(auth.router, tags=["认证"])  # ← auth已有prefix
app.include_router(questions.router, tags=["题库"])  # ← questions已有prefix
app.include_router(paper_router, tags=["试卷管理"])  # ← 使用新的组卷路由
app.include_router(exams.router, prefix="/api/exams", tags=["考试"])
app.include_router(videos.router, prefix="/api/videos", tags=["视频"])
app.include_router(llm.router, prefix="/api/llm", tags=["大模型"])
app.include_router(goals.router, prefix="/api/goals", tags=["学习目标"])
app.include_router(stats.router, prefix="/api/stats", tags=["统计"])
app.include_router(media.router, prefix="/api/media", tags=["媒体"])
app.include_router(websocket_router)

app.include_router(auth.router, prefix="/api/auth", tags=["认证"])
app.include_router(questions.router, prefix="/api/questions", tags=["题库"])
app.include_router(papers.router, prefix="/api/papers", tags=["试卷"])
app.include_router(exams.router, prefix="/api/exams", tags=["考试"])
app.include_router(videos.router, prefix="/api/videos", tags=["视频"])
app.include_router(llm.router, prefix="/api/llm", tags=["大模型"])
app.include_router(goals.router, prefix="/api/goals", tags=["学习目标"])
app.include_router(stats.router, prefix="/api/stats", tags=["统计"])
app.include_router(media.router, prefix="/api/media", tags=["媒体"])
app.include_router(websocket_router)

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

@app.get("/", tags=["系统"])
async def root():
    """
    系统首页
    """
    return {
        "message": "欢迎使用公安联考题库系统",
        "version": "1.0.0",
        "docs": "/docs",
        "redoc": "/redoc",
        "openapi": "/openapi.json"
    }

@app.get("/metrics", tags=["系统"])
async def get_metrics():
    """
    获取系统性能指标
    """
    return metrics_collector.get_metrics_summary()

@app.get("/metrics/system", tags=["系统"])
async def get_system_metrics_endpoint():
    """
    获取系统级性能指标
    """
    return get_system_metrics()

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