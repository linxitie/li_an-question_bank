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
    SQLITE_PATH: str = Field("./data/example_db.sqlite", env="SQLITE_PATH")
    
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
    MINERU_TIMEOUT: int = Field(600, env="MINERU_TIMEOUT")
    MINERU_BACKEND: str = Field("pipeline", env="MINERU_BACKEND")
    # PARSER_URL：容器化后的 parser sidecar 地址（如 http://parser:8080）。
    # 留空则沿用本地子进程路径，开发机工作方式完全不变。
    # 配置了则优先走 HTTP sidecar，失败或超时时自动回落子进程。
    PARSER_URL: str = Field("", env="PARSER_URL")
    # EVENT_CONSUMER_ENABLED：事件消费者（user.action 成就授予）开关。
    # P5.2 调用点改造完成前保持 False——消费者只在事件驱动路径启用时才有意义，
    # 过早启动会与同步直调产生双写。
    EVENT_CONSUMER_ENABLED: bool = Field(False, env="EVENT_CONSUMER_ENABLED")

    # ==================== 复合题（题组）识别（方案 v1.1，灰度开关）====================
    # 关闭后导入不再识别题组（存量数据不受影响；题组仅为展示聚合视图）
    COMPOSITE_QUESTION_ENABLED: bool = Field(True, env="COMPOSITE_QUESTION_ENABLED")

    # ==================== 扫描件OCR子进程（P1.1 进程隔离）====================
    # OCR 在独立子进程执行：子进程崩溃/超时被强杀，主后端进程无恙。
    # 背景：本机 Python 3.13 超出 PaddleOCR 官方支持（≤3.12），进程内 OCR 会硬崩。
    # OCR_PYTHON：独立 OCR 环境的解释器（须为 ≤3.12 的 Python，如 D:\ocr-env）；
    # 留空则用主进程解释器（3.13 下 Paddle 推理会崩，仅作降级）。
    OCR_PYTHON: str = Field(r"D:\ocr-env\Scripts\python.exe", env="OCR_PYTHON")
    OCR_MAX_PAGES: int = Field(8, env="OCR_MAX_PAGES")
    OCR_SUBPROCESS_TIMEOUT: int = Field(240, env="OCR_SUBPROCESS_TIMEOUT")

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