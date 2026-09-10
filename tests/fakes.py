"""测试专用的确定性假实现（不下载真实模型）。"""

import hashlib
import re

import numpy as np

DIM = 64
_TOKEN = re.compile(r"\w+", re.UNICODE)


class FakeEmbeddingService:
    """词袋假向量：相同词 → 相同桶，词重叠越多余弦相似度越高。

    确定性、无需网络，用于验证「上传→向量化→检索」整条管线。
    """

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            vec = np.zeros(DIM, dtype=np.float32)
            for token in _TOKEN.findall(text.lower()):
                digest = hashlib.md5(token.encode("utf-8")).hexdigest()
                vec[int(digest, 16) % DIM] += 1.0
            norm = float(np.linalg.norm(vec))
            if norm > 0:
                vec /= norm
            vectors.append(vec.tolist())
        return vectors


class FakeLLMService:
    """确定性假 LLM：记录收到的完整 messages，返回可断言的固定回答。"""

    mode = "fake"

    def __init__(self) -> None:
        self.last_messages: list[dict[str, str]] | None = None

    def chat(self, messages: list[dict[str, str]]) -> str:
        self.last_messages = list(messages)
        last_user = next(
            (m["content"] for m in reversed(messages) if m["role"] == "user"), ""
        )
        return f"fake-answer::{last_user[:30]}"
