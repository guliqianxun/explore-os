"""ft-027: PDF/arXiv/URL ingest 链式调度。

把 ``extract → interpret → render`` 串成一个异步任务（用 ``apps.api.jobs.enqueue``）。
任一阶段失败就短路，job error 里写明哪一步挂了；全部成功则在 ``result``
里返回三步的 counts 概要。

入口：
    chain_extract_interpret_render(arxiv_id, pdf_path) -> JobInfo

返回的 JobInfo 是 root job（front-end 轮询这一个 id 即可拿到全链状态）。
"""
from __future__ import annotations

import logging
from pathlib import Path

from apps.api import jobs

log = logging.getLogger(__name__)


def _run_extract(arxiv_id: str, pdf_path: str) -> dict:
    """阶段 1：调 apps.extract.extractor.extract + persist。"""
    from apps.extract.extractor import extract, persist_result
    result = extract(Path(pdf_path), arxiv_id)
    counts = persist_result(result)
    return {"arxiv_id": arxiv_id, "counts": counts}


def _run_interpret(arxiv_id: str, pdf_path: str) -> dict:
    """阶段 2：调 apps.interpret.interpreter.DefaultInterpreter。"""
    from apps.interpret.interpreter import DefaultInterpreter
    from apps.interpret.persist import persist_result
    result = DefaultInterpreter().interpret(arxiv_id, Path(pdf_path))
    counts = persist_result(result)
    return {"arxiv_id": arxiv_id, "counts": counts}


def _run_render(arxiv_id: str, fmt: str = "excalidraw") -> dict:
    """阶段 3：调 apps.render."""
    from apps.core import paths
    from apps.render.excalidraw_renderer import ExcalidrawRenderer
    from apps.render.graph import build_graph
    from apps.render.persist import persist_artifact
    from apps.render.svg_renderer import SvgRenderer

    graph = build_graph(arxiv_id)
    out_dir = paths.render_dir(arxiv_id)
    renderer = ExcalidrawRenderer() if fmt == "excalidraw" else SvgRenderer()
    path = renderer.render(graph, out_dir)
    artifact = persist_artifact(arxiv_id, fmt, path, payload_meta={
        "n_nodes": len(graph.nodes), "n_edges": len(graph.edges),
    })
    return {
        "arxiv_id": arxiv_id, "fmt": fmt,
        "artifact_id": artifact.artifact_id, "path": str(path),
    }


def _chain_body(arxiv_id: str, pdf_path: str, fmt: str = "excalidraw") -> dict:
    """单个 worker 内顺序跑三阶段；任一失败 raise（jobs.py 标 failed）。

    成功 result schema::

        {
            "arxiv_id": "...",
            "stages": {
                "extract":   {... counts ...},
                "interpret": {... counts ...},
                "render":    {... artifact info ...},
            },
        }
    """
    log.info("[ingest-chain] %s start (pdf=%s)", arxiv_id, pdf_path)

    # stage 1
    try:
        ex = _run_extract(arxiv_id, pdf_path)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"extract failed: {exc}") from exc

    # stage 2
    try:
        it = _run_interpret(arxiv_id, pdf_path)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"interpret failed: {exc}") from exc

    # stage 3
    try:
        rd = _run_render(arxiv_id, fmt)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"render failed: {exc}") from exc

    log.info("[ingest-chain] %s done", arxiv_id)
    return {
        "arxiv_id": arxiv_id,
        "stages": {"extract": ex, "interpret": it, "render": rd},
    }


def chain_extract_interpret_render(
    arxiv_id: str,
    pdf_path: Path | str,
    *,
    fmt: str = "excalidraw",
    inline: bool = False,
) -> jobs.JobInfo:
    """把 extract→interpret→render 链做成一个 job。

    inline=True 走 ``jobs.run_inline``（测试用），否则走 background scheduler。
    """
    name = f"ingest:{arxiv_id}"
    if inline:
        return jobs.run_inline(_chain_body, arxiv_id, str(pdf_path), fmt, name=name)
    return jobs.enqueue(_chain_body, arxiv_id, str(pdf_path), fmt, name=name)
