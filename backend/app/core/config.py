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
    DB_PASSWORD: str = Field("123456", env="DB_PASSWORD")
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