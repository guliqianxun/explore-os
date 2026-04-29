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

from django.conf import settings


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
    return settings.LLM_MODEL_TEXT or settings.LLM_MODEL


def _vision_model() -> str:
    """优先使用专门的 vision classifier model；缺失则降级到 multimodal；再缺失则降级到 text。

    注意：``LLM_MODEL_VISION`` 不是 settings 里既有项；为兼容文档表述使用 getattr。
    """
    explicit = getattr(settings, "LLM_MODEL_VISION", None)
    return (
        explicit
        or settings.LLM_MODEL_VISION_CLASSIFIER
        or settings.LLM_MODEL_MULTIMODAL
        or _text_model()
    )


def _vision_model_strict() -> str:
    """vision 强约束：未配置任何 vision/multimodal model 时返回空串（不降级到 text）。

    用于 figure_classifier 这类必须真喂图像的能力，调用方据此 early-skip。
    """
    return (
        getattr(settings, "LLM_MODEL_VISION", "")
        or settings.LLM_MODEL_VISION_CLASSIFIER
        or settings.LLM_MODEL_MULTIMODAL
        or ""
    )


def _deep_model() -> str:
    """deep_interpret 优先用 ``LLM_MODEL_DEEP``，缺失降级到 text。

    ``LLM_MODEL_DEEP`` 不是 settings 既有项；通过 getattr 容错。
    """
    return getattr(settings, "LLM_MODEL_DEEP", None) or _text_model()


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
        "tldr": ModelProfile(
            name="tldr",
            model=_text_model(),
            max_tokens=200,
            temperature=0.3,
            system_prompt_name="tldr",
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
            # 应该走 text model；spec 表述里的 LLM_MODEL_VISION 缺省项不存在时
            # 自然落到 text，符合现状。
            name="figure_picker",
            model=getattr(settings, "LLM_MODEL_VISION", None) or _text_model(),
            max_tokens=80,
            temperature=0.2,
            system_prompt_name="figure_picker",
        ),
        "figure_classifier": ModelProfile(
            # strict 模式：未配置 vision model 时 model="" — 调用方应据此 early-skip
            # （保留 ft-012 原始的 "no vision classifier model configured, skip" 行为）
            name="figure_classifier",
            model=_vision_model_strict(),
            max_tokens=200,
            temperature=0.2,
            system_prompt_name="figure_classifier",
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
