"""ft-021: LaTeX → PNG via matplotlib.mathtext（公式渲染）.

把 docling 抽出的 LaTeX 源码（如 ``\\mathcal{L} = ...``）渲染为 PNG，
作为 claim 卡片内嵌图像。比纯 monospace 文本可读性高一个量级。

约束：
* mathtext 不是完整 LaTeX 引擎，只支持子集（参考
  https://matplotlib.org/stable/users/explain/text/mathtext.html ）。
  解析失败 → 降级为 None，调用方退回 monospace 文本。
* 输出落 ``media/equations/<arxiv_id>/eq_<seq>.png``，幂等：
  存在则直接返回路径，不重算（同 paper 重复 render_graph 不付出代价）。
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

log = logging.getLogger(__name__)


# mathtext 不认 \text{} \colon \begin{array} 等，这里做轻量预处理
def _sanitize_for_mathtext(latex: str) -> str:
    s = latex or ""
    # 折叠多余空白
    s = re.sub(r"\s+", " ", s).strip()
    # \colon → :
    s = s.replace(r"\colon", ":")
    # \text{...} → 直接保留内容（mathtext 不识别 \text）
    s = re.sub(r"\\text\s*\{([^}]*)\}", r"\\mathrm{\1}", s)
    # \triangle q / \stackrel 等 mathtext 不支持的，简单替换
    s = s.replace(r"\triangle q", r"\triangleq")
    # \begin{array}{ll} ... \end{array} → 用 \begin{matrix}（mathtext 不支持 array，先剥列定义）
    s = re.sub(
        r"\\begin\{array\}\{[^}]*\}",
        r"\\begin{matrix}",
        s,
    )
    s = s.replace(r"\end{array}", r"\end{matrix}")
    return s


def render_latex_to_png(
    latex: str,
    out_path: Path,
    *,
    fontsize: int = 22,
    dpi: int = 220,
    color: str = "#212529",
) -> bool:
    """把 LaTeX 渲染到 ``out_path``（高 DPI 高字号，可读性优先）。

    失败返回 False；幂等。
    """
    out_path = Path(out_path)
    if out_path.is_file() and out_path.stat().st_size > 0:
        return True
    out_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        log.warning("[eq] matplotlib 不可用，公式无法渲染")
        return False

    cleaned = _sanitize_for_mathtext(latex)
    if not cleaned:
        return False

    # mathtext 要求公式包在 $...$ 中
    expr = f"${cleaned}$"
    try:
        fig = plt.figure(figsize=(0.01, 0.01))
        fig.text(0, 0, expr, fontsize=fontsize, color=color)
        fig.savefig(
            out_path,
            dpi=dpi,
            bbox_inches="tight",
            pad_inches=0.05,
            transparent=False,
            facecolor="white",
        )
        plt.close(fig)
    except Exception as exc:  # noqa: BLE001 (mathtext 错误类型很多)
        log.debug("[eq] 渲染失败: %r | %r", exc, latex[:60])
        plt.close("all")
        if out_path.is_file():
            try:
                out_path.unlink()
            except OSError:
                pass
        return False

    if not out_path.is_file() or out_path.stat().st_size == 0:
        return False
    return True


def png_size(path: Path) -> tuple[int, int] | None:
    """读 PNG 文件 IHDR chunk 拿原始宽高（不引 PIL）。"""
    try:
        with open(path, "rb") as f:
            data = f.read(24)
        if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
            return None
        # 16..23: width(4) + height(4) big-endian
        w = int.from_bytes(data[16:20], "big")
        h = int.from_bytes(data[20:24], "big")
        return (w, h)
    except OSError:
        return None
