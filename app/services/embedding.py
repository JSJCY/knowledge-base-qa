"""向量化服务：fastembed 本地 ONNX 模型（默认 BAAI/bge-small-zh-v1.5）。

- 懒加载：首次调用才下载/加载模型（约 100MB，之后走本地缓存）；
- 向量统一 L2 归一化后返回，落盘时用 float32 字节存储；
- 国内网络可通过 HF_ENDPOINT（如 https://hf-mirror.com）加速模型下载。
"""

import os

import numpy as np

from app.core.config import get_settings


def vec_to_bytes(vector: list[float] | np.ndarray) -> bytes:
    return np.asarray(vector, dtype=np.float32).tobytes()


def bytes_to_vec(data: bytes) -> np.ndarray:
    return np.frombuffer(data, dtype=np.float32)


def normalize(vec: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vec))
    return vec / norm if norm > 0 else vec


class EmbeddingService:
    """文本向量化服务（可被测试中的假实现替换）。"""

    def __init__(self, model_name: str, hf_endpoint: str = "") -> None:
        self.model_name = model_name
        self.hf_endpoint = hf_endpoint
        self._model = None

    def _load(self):
        if self._model is None:
            if self.hf_endpoint:
                os.environ["HF_ENDPOINT"] = self.hf_endpoint
                # 镜像源不支持 HF Xet 传输协议，回退普通 HTTP 下载
                os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
            from fastembed import TextEmbedding

            self._model = TextEmbedding(model_name=self.model_name)
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        """批量向量化，返回 L2 归一化后的向量列表。"""
        if not texts:
            return []
        model = self._load()
        vectors = list(model.embed(texts))
        return [normalize(np.asarray(v, dtype=np.float32)).tolist() for v in vectors]


_embedding_service: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    """FastAPI 依赖入口（进程内单例，测试可 override）。"""
    global _embedding_service
    if _embedding_service is None:
        settings = get_settings()
        _embedding_service = EmbeddingService(settings.embedding_model, settings.hf_endpoint)
    return _embedding_service
