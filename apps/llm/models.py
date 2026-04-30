"""ModelProfile registry：能力 → (model, max_tokens, temperature, prompt_name).

ft-034 P0-2：把散落的 ``settings.LLM_MODEL_*`` 直读集中到此处。

使用：

    from apps.llm.models import get_profile

    profile = get_profile("skim")
    chat(messages, model=profile.model,
         temperature=profile.temperature,
         max_tokens=profile.max_tokens)

注意：本文件 *只读* settings，不引入新配置项；name 维持不变（``LLM_MODEL_TEXT``
``LLM_MODEL_MULTIMODAL`` ``LLM_MODEL_VISION_CLASSIFIER``）。
"""
from __future__ import annotations

from dataclasses import dataclass

from apps.llm.runtime_config import llm_config


# ---------------- embedding 顶级常量（迁自 interpret/embedding.py） ----------------

EMBEDDING_MODEL: str = "text-embedding-v3"
EMBEDDING_DIM: int = 1024


# ---------------- ModelProfile dataclass ----------------


@dataclass(frozen=True, slots=True)
class ModelProfile:
    """单个 LLM 能力的配置档。"""

    name: str
    model: str
    max_tokens: int
    temperature: float
    system_prompt_name: str | None = None  # 对应 apps.llm.prompts 的 key；多模态分类等无 prompt 注册项可为 None


def _text_model() -> str:
    return llm_config().model_text


def _vision_model() -> str:
    """vision classifier > multimodal > text。"""
    cfg = llm_config()
    return (
        cfg.model_vision_classifier
        or cfg.model_multimodal
        or cfg.model_text
    )


def _deep_model() -> str:
    """deep_interpret 优先 model_deep，缺失降级到 text。"""
    cfg = llm_config()
    return cfg.model_deep or cfg.model_text


def _build_registry() -> dict[str, ModelProfile]:
    """每次调用都重读 settings，避免测试中 override_settings 失效。"""
    return {
        "skim": ModelProfile(
            name="skim",
            model=_text_model(),
            max_tokens=600,
            temperature=0.3,
            system_prompt_name="skim",
        ),
        "deep": ModelProfile(
            name="deep",
            model=_deep_model(),
            max_tokens=900,
            temperature=0.3,
            system_prompt_name="deep",
        ),
        "narrative": ModelProfile(
            name="narrative",
            model=_text_model(),
            max_tokens=400,
            temperature=0.4,
            system_prompt_name="narrative",
        ),
        "rewriter": ModelProfile(
            name="rewriter",
            model=_text_model(),
            max_tokens=300,
            temperature=0.5,
            system_prompt_name="rewriter",
        ),
        "figure_picker": ModelProfile(
            # 注意：figure_picker LLM 兜底"仅 caption 文本，不喂图"，
            # 走 text model 而不是 vision；旧 spec 留的 LLM_MODEL_VISION 顾及现状。
            name="figure_picker",
            model=_text_model(),
            max_tokens=80,
            temperature=0.2,
            system_prompt_name="figure_picker",
        ),
        "extract_claims": ModelProfile(
            name="extract_claims",
            model=_text_model(),
            max_tokens=2048,
            temperature=0.2,
            system_prompt_name=None,  # L1/L2 prompts 仍由 apps/interpret/prompts.py 维护
        ),
    }


def get_profile(name: str) -> ModelProfile:
    """取一个能力的 ModelProfile；name 不存在时 raise KeyError。"""
    registry = _build_registry()
    if name not in registry:
        raise KeyError(f"unknown LLM profile: {name!r}; known={sorted(registry)}")
    return registry[name]


def list_profiles() -> list[str]:
    """枚举所有已注册的 profile 名称（测试用）。"""
    return sorted(_build_registry().keys())


__all__ = [
    "EMBEDDING_MODEL",
    "EMBEDDING_DIM",
    "ModelProfile",
    "get_profile",
    "list_profiles",
]
