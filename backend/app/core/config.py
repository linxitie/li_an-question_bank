"""
数据库配置 - 支持SQLite作为开发环境备选方案
"""
import os
from typing import Optional

try:
    from pydantic_settings import BaseSettings
    from pydantic import Field
except ImportError:
    from pydantic import BaseSettings, Field

class Settings(BaseSettings):
    # 数据库配置
    DB_TYPE: str = Field("sqlite", env="DB_TYPE")
    DB_HOST: str = Field("localhost", env="DB_HOST")
    DB_PORT: int = Field(3306, env="DB_PORT")
    DB_USER: str = Field("root", env="DB_USER")
    DB_PASSWORD: Optional[str] = Field(None, env="DB_PASSWORD")
    DB_NAME: str = Field("police_exam", env="DB_NAME")
    DB_CHARSET: str = Field("utf8mb4", env="DB_CHARSET")
    
    # SQLite配置
    SQLITE_PATH: str = Field("./data/question_bank.db", env="SQLITE_PATH")
    
    # Redis配置
    REDIS_HOST: str = Field("localhost", env="REDIS_HOST")
    REDIS_PORT: int = Field(6379, env="REDIS_PORT")
    REDIS_PASSWORD: Optional[str] = Field(None, env="REDIS_PASSWORD")
    REDIS_DB: int = Field(0, env="REDIS_DB")
    
    # JWT配置
    JWT_SECRET_KEY: str = Field("your-secret-key-here-must-be-at-least-32-characters", env="JWT_SECRET_KEY")
    JWT_ALGORITHM: str = Field("HS256", env="JWT_ALGORITHM")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(120, env="JWT_ACCESS_TOKEN_EXPIRE_MINUTES")
    
    # 安全配置
    BCRYPT_ROUNDS: int = Field(12, env="BCRYPT_ROUNDS")
    
    # 服务器配置
    HOST: str = Field("0.0.0.0", env="HOST")
    PORT: int = Field(8000, env="PORT")
    DEBUG: bool = Field(True, env="DEBUG")
    
    # 文件上传配置
    MAX_UPLOAD_SIZE: int = Field(52428800, env="MAX_UPLOAD_SIZE")
    UPLOAD_DIR: str = Field("./uploads", env="UPLOAD_DIR")
    VIDEO_DIR: str = Field("./uploads/videos", env="VIDEO_DIR")
    FILE_DIR: str = Field("./uploads/files", env="FILE_DIR")
    
    # 视频转码配置
    FFMPEG_PATH: str = Field("ffmpeg", env="FFMPEG_PATH")
    
    # 大模型配置
    LLM_API_URL: str = Field("http://localhost:8080/api/v1/chat", env="LLM_API_URL")
    LLM_API_KEY: Optional[str] = Field(None, env="LLM_API_KEY")
    LLM_MODEL: str = Field("police-exam", env="LLM_MODEL")
    
    # 日志配置
    LOG_LEVEL: str = Field("INFO", env="LOG_LEVEL")
    LOG_FILE: str = Field("./logs/app.log", env="LOG_FILE")

    # 新闻爬虫配置
    NEWS_BROWSER: str = Field("chromium", env="NEWS_BROWSER")

    # ==================== MinerU 扫描件OCR（MinerU 主 + PaddleOCR 辅）====================
    # 设计规格: docs/superpowers/specs/2026-08-22-mineru-scanned-pdf-ocr-design.md
    # MINERU_PYTHON 指向独立 Python 3.11 venv 解释器（MinerU 不支持主后端的 3.13）。
    # 部署记录（solve_problems_files/mineru_deployment_log.md）：venv 位于纯 ASCII 路径
    # C:\mineru_env（FastText 无法加载非 ANSI 路径）；模型源 MINERU_MODEL_SOURCE=modelscope。
    MINERU_ENABLED: bool = Field(True, env="MINERU_ENABLED")
    MINERU_PYTHON: str = Field(r"C:\mineru_env\Scripts\python.exe", env="MINERU_PYTHON")
    # 超时按页数动态估算：MinerU CPU pipeline 实测 71.2s/页（部署日志），
    # 固定 600s 会让 24 页答案卷必然超时 → MinerU 永远被跳过。
    # 实际预算 = max(MINERU_TIMEOUT, 120 + MINERU_SECONDS_PER_PAGE*页数)，封顶 MAX。
    MINERU_TIMEOUT: int = Field(600, env="MINERU_TIMEOUT")
    MINERU_SECONDS_PER_PAGE: int = Field(75, env="MINERU_SECONDS_PER_PAGE")
    MINERU_TIMEOUT_MAX: int = Field(3600, env="MINERU_TIMEOUT_MAX")
    MINERU_BACKEND: str = Field("pipeline", env="MINERU_BACKEND")
    # PARSER_URL：容器化后的 parser sidecar 地址（如 http://parser:8080）。
    # 留空则沿用本地子进程路径，开发机工作方式完全不变。
    # 配置了则优先走 HTTP sidecar，失败或超时时自动回落子进程。
    PARSER_URL: str = Field("", env="PARSER_URL")
    # EVENT_CONSUMER_ENABLED：事件消费者（user.action 成就授予）开关。
    # P5.2 折中方案已实施：13 处调用点改发事件，消费者必须运行才能兑现授予，
    # 故默认 True。publish 失败时调用点有同步兜底，Redis 宕机也不丢成就。
    EVENT_CONSUMER_ENABLED: bool = Field(True, env="EVENT_CONSUMER_ENABLED")

    # ==================== F1 一致性内核（Outbox / 投影 / 对账）====================
    # FOUNDATION_ENABLED=false 时不建表、不启动投递器，行为与 F0 完全一致（可一键回滚）。
    FOUNDATION_ENABLED: bool = Field(True, env="FOUNDATION_ENABLED")
    # 单轮投递间隔与最大尝试次数；超限进 dead + jsonl，人工重放。
    FOUNDATION_DISPATCH_MS: int = Field(500, env="FOUNDATION_DISPATCH_MS")
    FOUNDATION_MAX_ATTEMPTS: int = Field(8, env="FOUNDATION_MAX_ATTEMPTS")
    # F2b：业务事件与业务写同事务进入 Outbox；false 回到 F2 的 events.publish + 同步兜底。
    EVENT_OUTBOX_ENABLED: bool = Field(True, env="EVENT_OUTBOX_ENABLED")
    # 同机多 worker 的 Dispatcher 单写者锁（相对路径按 backend/ 解析）。
    DISPATCHER_LOCK_PATH: str = Field("./data/foundation/dispatcher.lock", env="DISPATCHER_LOCK_PATH")

    # ==================== F2 通信统一（WS 中继 / 心跳 / 写入守卫）====================
    # WS_RELAY=redis 时跨 worker 经 Redis pub/sub 扇出；留空为单进程本地扇出。
    # WEB_CONCURRENCY>1 且未开中继时 lifespan 直接拒绝启动（见 ws_relay.validate_worker_config）。
    WS_RELAY: str = Field("", env="WS_RELAY")
    # 超过该秒数未收到任何消息（含心跳）的连接视为掉线并关闭（码 4008）。
    WS_HEARTBEAT_TIMEOUT_SECONDS: int = Field(90, env="WS_HEARTBEAT_TIMEOUT_SECONDS")
    # 写库前 6 类守卫的总开关；false 时回退到 F1 行为。
    FOUNDATION_VALIDATION_ENABLED: bool = Field(True, env="FOUNDATION_VALIDATION_ENABLED")

    # ==================== F3 对象存储与媒体资产 ====================
    # 关闭后新上传回退旧 uploads 写路径；/media 读路由仍保留，已写 URL 不裂。
    MEDIA_STORE_ENABLED: bool = Field(True, env="MEDIA_STORE_ENABLED")
    OBJECT_STORE_BACKEND: str = Field("local", env="OBJECT_STORE_BACKEND")
    OBJECT_STORE_ROOT: str = Field("./data/foundation/objects", env="OBJECT_STORE_ROOT")
    MINIO_ENDPOINT: str = Field("", env="MINIO_ENDPOINT")
    MINIO_BUCKET: str = Field("", env="MINIO_BUCKET")
    MINIO_ACCESS_KEY: str = Field("", env="MINIO_ACCESS_KEY")
    MINIO_SECRET_KEY: str = Field("", env="MINIO_SECRET_KEY")
    MINIO_SECURE: bool = Field(False, env="MINIO_SECURE")
    MINIO_REGION: str = Field("us-east-1", env="MINIO_REGION")
    # true 时 MinIO 不可达直接拒绝启动；默认 false，开发机无 MinIO 也能启动。
    MEDIA_STRICT_BACKEND: bool = Field(False, env="MEDIA_STRICT_BACKEND")
    MEDIA_ORPHAN_GRACE_DAYS: int = Field(7, env="MEDIA_ORPHAN_GRACE_DAYS")

    # ==================== F4 文档投影 ====================
    DOC_STORE_ENABLED: bool = Field(True, env="DOC_STORE_ENABLED")
    DOC_STORE_BACKEND: str = Field("local", env="DOC_STORE_BACKEND")
    DOC_STORE_ROOT: str = Field("./data/foundation/docs", env="DOC_STORE_ROOT")
    DOC_STORE_MAX_BYTES: int = Field(8388608, env="DOC_STORE_MAX_BYTES")
    DOC_STORE_MONGO_URI: str = Field("", env="DOC_STORE_MONGO_URI")
    DOC_STORE_MONGO_DB: str = Field("li_an_foundation", env="DOC_STORE_MONGO_DB")
    DOC_STORE_MONGO_PREFIX: str = Field("", env="DOC_STORE_MONGO_PREFIX")
    DOC_STORE_RECONCILE_MAX_AGE_DAYS: int = Field(7, env="DOC_STORE_RECONCILE_MAX_AGE_DAYS")

    # ==================== F5 图投影 ====================
    # 关闭后图回填/查询短路；默认 local，不要求 Neo4j 容器。
    GRAPH_STORE_ENABLED: bool = Field(True, env="GRAPH_STORE_ENABLED")
    GRAPH_BACKEND: str = Field("local", env="GRAPH_BACKEND")
    GRAPH_NEO4J_URI: str = Field("http://localhost:7474", env="GRAPH_NEO4J_URI")
    GRAPH_NEO4J_USER: str = Field("neo4j", env="GRAPH_NEO4J_USER")
    GRAPH_NEO4J_PASSWORD: str = Field("", env="GRAPH_NEO4J_PASSWORD")
    GRAPH_NEO4J_DATABASE: str = Field("neo4j", env="GRAPH_NEO4J_DATABASE")
    GRAPH_QUERY_MAX_DEPTH: int = Field(5, env="GRAPH_QUERY_MAX_DEPTH")
    GRAPH_RECONCILE_MAX_AGE_DAYS: int = Field(7, env="GRAPH_RECONCILE_MAX_AGE_DAYS")

    # ==================== F6 向量投影与 AI 端口 ====================
    # 默认关闭；local/milvus 显式开启。没有真实模型时哈希向量只用于验证。
    VECTOR_STORE_ENABLED: bool = Field(True, env="VECTOR_STORE_ENABLED")
    VECTOR_BACKEND: str = Field("off", env="VECTOR_BACKEND")
    VECTOR_DIM: int = Field(1024, env="VECTOR_DIM")
    VECTOR_COLLECTION: str = Field("text_questions", env="VECTOR_COLLECTION")
    VECTOR_LOCAL_ROOT: str = Field("./data/foundation/vectors", env="VECTOR_LOCAL_ROOT")
    VECTOR_MILVUS_URI: str = Field("http://localhost:19530", env="VECTOR_MILVUS_URI")
    VECTOR_MILVUS_TOKEN: Optional[str] = Field(None, env="VECTOR_MILVUS_TOKEN")
    VECTOR_MILVUS_PREFIX: str = Field("li_an_", env="VECTOR_MILVUS_PREFIX")
    VECTOR_SEARCH_TOP_K_MAX: int = Field(100, env="VECTOR_SEARCH_TOP_K_MAX")
    VECTOR_RECONCILE_MAX_AGE_DAYS: int = Field(7, env="VECTOR_RECONCILE_MAX_AGE_DAYS")
    EMBEDDING_ENABLED: bool = Field(False, env="EMBEDDING_ENABLED")
    EMBEDDING_PROVIDER: str = Field("off", env="EMBEDDING_PROVIDER")
    EMBEDDING_BASE_URL: str = Field("", env="EMBEDDING_BASE_URL")
    EMBEDDING_MODEL: str = Field("", env="EMBEDDING_MODEL")
    EMBEDDING_API_KEY: Optional[str] = Field(None, env="EMBEDDING_API_KEY")
    EMBEDDING_DIM: int = Field(1024, env="EMBEDDING_DIM")
    EMBEDDING_TIMEOUT_SECONDS: float = Field(30.0, env="EMBEDDING_TIMEOUT_SECONDS")
    EMBEDDING_BATCH_SIZE: int = Field(32, env="EMBEDDING_BATCH_SIZE")

    # ==================== 复合题（题组）识别（方案 v1.1，灰度开关）====================
    # 关闭后导入不再识别题组（存量数据不受影响；题组仅为展示聚合视图）
    COMPOSITE_QUESTION_ENABLED: bool = Field(True, env="COMPOSITE_QUESTION_ENABLED")

    # ==================== 材料归属 V2（三端数据流一致性修复 P0-5）====================
    # 关闭时保留旧解析/建组行为；打开后走 material_text / 文档级材料等新逻辑。
    # P3 验收通过后改为默认 True，保留一个版本周期便于回滚。
    MATERIAL_OWNERSHIP_V2: bool = Field(True, env="MATERIAL_OWNERSHIP_V2")

    # ==================== 扫描件OCR子进程（P1.1 进程隔离）====================
    # OCR 在独立子进程执行：子进程崩溃/超时被强杀，主后端进程无恙。
    # 背景：本机 Python 3.13 超出 PaddleOCR 官方支持（≤3.12），进程内 OCR 会硬崩。
    # OCR_PYTHON：独立 OCR 环境的解释器（须为 ≤3.12 的 Python，如 D:\ocr-env）；
    # 留空则用主进程解释器（3.13 下 Paddle 推理会崩，仅作降级）。
    OCR_PYTHON: str = Field(r"D:\ocr-env\Scripts\python.exe", env="OCR_PYTHON")
    # 2026-10-25：原上限 8 页会把 20~30 页的答案解析卷截断（后半答案识别不到，
    # 直接表现为"答案对不上题号"）。答案卷实测 24~30 页，故放宽到 30 页；
    # 超时按 20s/页（CPU Paddle）留足余量，仍由子进程硬超时兜底。
    OCR_MAX_PAGES: int = Field(30, env="OCR_MAX_PAGES")
    OCR_SUBPROCESS_TIMEOUT: int = Field(600, env="OCR_SUBPROCESS_TIMEOUT")

    # ==================== 题目图片压缩配置（P2-2 存储量最小）====================
    # 压缩开关：开启后导入题目图片统一缩放长边 + 转 WebP/JPEG 质量压缩
    IMAGE_COMPRESSION_ENABLED: bool = Field(True, env="IMAGE_COMPRESSION_ENABLED")
    # 压缩后长边像素上限（保持清晰度，图表/材料图可读）
    IMAGE_MAX_SIDE: int = Field(1200, env="IMAGE_MAX_SIDE")
    # 压缩质量（0-100，80 为清晰度与体积的平衡点）
    IMAGE_QUALITY: int = Field(80, env="IMAGE_QUALITY")

    # ==================== 文档提取文本缓存（导入提速 P0）====================
    # 按"文件内容 md5"缓存提取出的纯文本：同一份文件重复导入不再重付提取成本。
    # 实测依据：解析仅 0.1s/100题，而扫描件 PDF 走 MinerU OCR 需 260s/份 ——
    # 重复导入的耗时 99.6% 都在提取层，缓存命中可降至 ~0.02s（4 个数量级）。
    TEXT_CACHE_ENABLED: bool = Field(True, env="TEXT_CACHE_ENABLED")
    # 缓存目录（相对 backend/ 或绝对路径）
    TEXT_CACHE_DIR: str = Field("./data/text_cache", env="TEXT_CACHE_DIR")

    # ==================== 资料管理配置 ====================
    # 批量操作限制
    MATERIAL_BATCH_LIMIT: int = Field(100, env="MATERIAL_BATCH_LIMIT")
    # 单文件大小限制(MB)
    MATERIAL_MAX_FILE_SIZE_MB: int = Field(200, env="MATERIAL_MAX_FILE_SIZE_MB")
    # 允许的文件类型
    MATERIAL_ALLOWED_TYPES: str = Field("docx,xlsx,pdf,jpg,jpeg,png,mp4,zip,rar", env="MATERIAL_ALLOWED_TYPES")
    # 去重相似度阈值(0-1)
    MATERIAL_DEDUP_THRESHOLD: float = Field(0.85, env="MATERIAL_DEDUP_THRESHOLD")
    # 监控告警阈值
    MATERIAL_MONITOR_ERROR_THRESHOLD: int = Field(10, env="MATERIAL_MONITOR_ERROR_THRESHOLD")
    MATERIAL_MONITOR_RATE_THRESHOLD: float = Field(0.3, env="MATERIAL_MONITOR_RATE_THRESHOLD")
    # 内容清洗开关
    MATERIAL_SANITIZE_ENABLED: bool = Field(True, env="MATERIAL_SANITIZE_ENABLED")
    # 智能分类开关
    MATERIAL_CLASSIFIER_ENABLED: bool = Field(True, env="MATERIAL_CLASSIFIER_ENABLED")
    # 去重检测开关
    MATERIAL_DEDUP_ENABLED: bool = Field(True, env="MATERIAL_DEDUP_ENABLED")
    
    @property
    def DATABASE_URL(self) -> str:
        if self.DB_TYPE == "sqlite":
            return f"sqlite:///{self.SQLITE_PATH}"
        return f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset={self.DB_CHARSET}"
    
    @property
    def REDIS_URL(self) -> str:
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()