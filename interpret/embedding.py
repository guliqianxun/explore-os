"""Embedding client (DashScope/OpenAI 兼容 /embeddings 端点)."""
from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx
from django.conf import settings
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

log = logging.getLogger(__name__)

EMBEDDING_MODEL = "text-embedding-v3"
EMBEDDING_BATCH = 25   # 百炼 v3 限制：≤25/req
EMBEDDING_DIM = 1024


class EmbeddingError(RuntimeError):
    pass


@dataclass(slots=True)
class EmbeddingResult:
    vectors: list[list[float]]
    usage: dict[str, int]


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
)
def embed(
    texts: list[str],
    *,
    model: str = EMBEDDING_MODEL,
    timeout: float = 30.0,
) -> EmbeddingResult:
    """批量 embedding；自动分批。返回向量与 texts 顺序一一对应。"""
    if not texts:
        return EmbeddingResult(vectors=[], usage={})
    if not settings.LLM_API_KEY:
        raise EmbeddingError("LLM_API_KEY is not configured")

    url = f"{settings.LLM_API_BASE.rstrip('/')}/embeddings"
    all_vectors: list[list[float]] = []
    total_usage: dict[str, int] = {}

    with httpx.Client(timeout=timeout) as client:
        for start in range(0, len(texts), EMBEDDING_BATCH):
            batch = texts[start : start + EMBEDDING_BATCH]
            resp = client.post(
                url,
                headers={
                    "Authorization": f"Bearer {settings.LLM_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={"model": model, "input": batch, "encoding_format": "float"},
            )
            resp.raise_for_status()
            data = resp.json()
            try:
                items = sorted(data["data"], key=lambda x: x["index"])
                all_vectors.extend(x["embedding"] for x in items)
            except (KeyError, TypeError) as exc:
                raise EmbeddingError(f"unexpected embedding response: {data!r}") from exc

            u = data.get("usage") or {}
            for k, v in u.items():
                if isinstance(v, int):
                    total_usage[k] = total_usage.get(k, 0) + v

    return EmbeddingResult(vectors=all_vectors, usage=total_usage)


def cosine(a: list[float], b: list[float]) -> float:
    """纯 Python 余弦相似度。对向量长度低的场景够用，不引 numpy。"""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na == 0.0 or nb == 0.0:
        return 0.0
    import math
    return dot / (math.sqrt(na) * math.sqrt(nb))
