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
    """阶段 1：调 apps.extract.extractor.extract + persist。

    ft-040 follow-up: 回填 ``Paper.abstract``（如果空）— 取第一条 SectionMaterial
    的 raw_text 头部 ~2000 字。订阅链路在 source 层写 abstract，ingest 链路
    （PDF / arxiv id / URL）原本不写，导致 brief view 看不到 abstract。
    """
    from apps.extract.extractor import extract, persist_result
    result = extract(Path(pdf_path), arxiv_id)
    counts = persist_result(result)
    _backfill_abstract_from_sections(arxiv_id)
    return {"arxiv_id": arxiv_id, "counts": counts}


def _backfill_abstract_from_sections(arxiv_id: str) -> None:
    """ft-040: 用 docling Section 的头部段落回填 ``Paper.abstract``。幂等。"""
    try:
        from apps.papers.models import Paper
        from apps.extract.models import Section

        paper = Paper.objects.filter(arxiv_id=arxiv_id).first()
        if paper is None or (paper.abstract or "").strip():
            return
        sec = Section.objects.filter(
            paper_arxiv_id=arxiv_id,
        ).order_by("seq").first()
        if not sec or not (sec.raw_text or "").strip():
            return
        # 头 ~2000 字符够 abstract 容量；多了 brief generator 也用不上
        paper.abstract = sec.raw_text.strip()[:2000]
        paper.save(update_fields=["abstract"])
        log.info("[ingest-chain] %s abstract backfilled (%d chars)",
                 arxiv_id, len(paper.abstract))
    except Exception:  # noqa: BLE001
        log.warning("[ingest-chain] %s abstract backfill failed", arxiv_id, exc_info=True)


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


def _run_brief(arxiv_id: str) -> dict:
    """阶段 4 (ft-040)：LLM brief 生成（abstract_zh / key_innovation / limitations
    / for_you / method_summary）。**best-effort** —— 失败不抛出，把 error
    塞 result 让前端可见，但 chain 整体仍报 success。

    LLM 未配置 / 限额 / 网络问题都不应阻断 ingest 链路。
    """
    try:
        from apps.papers.brief_generator import generate_brief
        from apps.papers.models import Paper

        paper = Paper.objects.filter(arxiv_id=arxiv_id).first()
        if paper is None:
            return {"arxiv_id": arxiv_id, "skipped": "paper not found"}
        brief = generate_brief(paper)
        return {
            "arxiv_id": arxiv_id,
            "lang": getattr(brief, "lang", "") or "",
            "has_abstract_zh": bool((brief.abstract_zh or "").strip()),
            "n_key_innovation": len(brief.key_innovation or []),
            "n_limitations": len(brief.limitations or []),
        }
    except Exception as exc:  # noqa: BLE001
        log.warning("[ingest-chain] %s brief failed (non-fatal): %r", arxiv_id, exc)
        return {"arxiv_id": arxiv_id, "error": str(exc)}


def _chain_body(arxiv_id: str, pdf_path: str, fmt: str = "excalidraw") -> dict:
    """单个 worker 内顺序跑三阶段；任一失败 raise（jobs.py 标 failed）。

    chain 完成后 fire-and-forget 起一个**独立** brief 生成 job
    （``ingest-brief:<arxiv_id>``），让 chain 早早 succeed → 前端及时
    显示 "Read →"；brief 在后台 ~15-30s 后落库，下次刷新 detail 就有。

    LLM 失败不阻断 ingest UX。
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

    # ft-040: 独立 brief job，非链路阻塞，失败不影响主流程
    try:
        jobs.enqueue(_run_brief, arxiv_id, name=f"ingest-brief:{arxiv_id}")
    except Exception:  # noqa: BLE001
        log.warning("[ingest-chain] %s brief enqueue failed", arxiv_id, exc_info=True)

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
