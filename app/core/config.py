"""应用配置：从环境变量与 .env 文件加载。"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "知识库问答系统"
    version: str = "1.0.0"
    debug: bool = False

    # 数据库
    database_url: str = "sqlite:///./kb.db"

    # 文档处理
    upload_dir: str = "data/uploads"
    max_upload_mb: int = 20
    chunk_size: int = 500
    chunk_overlap: int = 50

    # 向量化（fastembed 本地推理）
    embedding_model: str = "BAAI/bge-small-zh-v1.5"
    hf_endpoint: str = ""  # 国内镜像加速可填 https://hf-mirror.com

    # DeepSeek LLM
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    llm_timeout_seconds: float = 60.0
    llm_temperature: float = 0.3

    # RAG 问答
    rag_history_limit: int = 10

    @property
    def llm_enabled(self) -> bool:
        """是否配置了真实 LLM（否则问答走 Mock 模式）。"""
        return bool(self.deepseek_api_key.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
