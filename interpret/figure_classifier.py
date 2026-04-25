"""ft-012: 对每张图用轻量多模态（qwen-vl-plus）分类.

类别：architecture / result_figure / result_table / qualitative / dataset / ablation / misc
"""
from __future__ import annotations

import logging
from pathlib import Path

from django.conf import settings

from .figure_extractor import Figure, figures_root
from .llm import LLMError, build_image_content, chat, extract_json

log = logging.getLogger(__name__)

VALID_KINDS = {
    "architecture", "result_figure", "result_table",
    "qualitative", "dataset", "ablation", "misc",
}

CLASSIFY_SYSTEM = """你是论文配图分类器。输入是论文中的一张图（含可选 caption），
输出一个类别标签和置信度。仅输出 JSON：
{"kind": "architecture|result_figure|result_table|qualitative|dataset|ablation|misc",
 "confidence": 0.0-1.0}

类别定义：
- architecture: 模型/方法架构图、pipeline、framework、overview（方法结构）
- result_figure: 实验曲线（loss / metric / bar）
- result_table: 表格形式的实验数字
- qualitative: 定性结果、生成样本、可视化对比
- dataset: 数据集样例、数据统计
- ablation: 消融分析图表
- misc: 不明或其他
只输出 JSON。"""


def classify_figures(arxiv_id: str, figures: list[Figure]) -> list[Figure]:
    """对每张图调 LLM 分类，回写 kind/confidence 字段并返回同一 list。"""
    if not figures:
        return figures
    model = settings.LLM_MODEL_VISION_CLASSIFIER or settings.LLM_MODEL_MULTIMODAL
    if not model:
        log.warning("no vision classifier model configured, skip")
        return figures

    base = figures_root() / arxiv_id
    for fig in figures:
        img_path = base / fig.path
        if not img_path.exists():
            continue
        try:
            result = _classify_one(img_path, fig.caption, model)
        except Exception as exc:  # noqa: BLE001
            log.warning("classify failed for %s: %r", fig.path, exc)
            fig.kind = "misc"
            fig.confidence = 0.0
            continue
        kind = str(result.get("kind") or "misc").strip()
        if kind not in VALID_KINDS:
            kind = "misc"
        try:
            conf = float(result.get("confidence") or 0.0)
        except (TypeError, ValueError):
            conf = 0.0
        fig.kind = kind
        fig.confidence = max(0.0, min(1.0, conf))
    return figures


def _classify_one(img_path: Path, caption: str, model: str) -> dict:
    user_text = f"caption: {caption or '(no caption)'}\n\n请分类这张图。"
    content = build_image_content(text=user_text, image_path=str(img_path),
                                   mime=_mime_of(img_path))
    res = chat(
        messages=[
            {"role": "system", "content": CLASSIFY_SYSTEM},
            {"role": "user", "content": content},
        ],
        model=model,
        temperature=0.1,
        max_tokens=80,
        timeout=120.0,   # 多模态比文本慢得多
    )
    return extract_json(res.content)


def _mime_of(path: Path) -> str:
    ext = path.suffix.lstrip(".").lower()
    return {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "gif": "image/gif",
        "webp": "image/webp",
    }.get(ext, "image/png")


def pick_architecture_figure(figures: list[Figure]) -> Figure | None:
    """从分类后的图里挑一张架构图（偏好 confidence 高、page 靠前）."""
    arch = [f for f in figures if f.kind == "architecture"]
    if not arch:
        return None
    arch.sort(key=lambda f: (-f.confidence, f.page, f.index))
    return arch[0]
