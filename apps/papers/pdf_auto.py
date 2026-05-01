"""ft-031.5 / ft-029a: 详情页打开时按需异步下载 arXiv PDF。

订阅链路（``run_subscription``）只走 skim/deep email pipeline，**不**触发
``extract`` / ``interpret``，因此订阅 paper 在落库后没有本地 PDF。用户从订阅
brief 跳到详情页时，希望 PDF 缓存自动到位（之后点 PDF 查看 / 触发 extract
均能命中），所以在 ``GET /api/papers/<id>/`` 时按需 fire-and-forget 拉一份。

约束:
- **不阻塞 detail 响应**：走 ``apps.api.jobs.enqueue``，立即返回。
- **去重**：同一 ``arxiv_id`` 已有 in-flight job 时不再排第二个 — 进程内
  ``_INFLIGHT`` set 守门。
- **缓存命中跳过**：``local_pdf_path`` 已存在 & 非零字节 → 直接 noop。
- **非 arxiv 来源跳过**：``arxiv_id`` 为空（人工 ingest URL / PDF 上传）时
  detail 页该能直接命中 paper.pdf_path（ingest 链路写过），不在本模块范围。
"""
from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.papers.models import Paper

log = logging.getLogger(__name__)

# 进程内 in-flight 守门 — 详情页连点 / 多个 tab 打开同一 paper 时去重。
_INFLIGHT: set[str] = set()
_LOCK = threading.Lock()


def _do_download(arxiv_id: str) -> dict:
    """job worker：调 sources.pdf_fetcher 的下载链路。"""
    from sources.pdf_fetcher import _download, local_pdf_path

    path = local_pdf_path(arxiv_id)
    try:
        if path.exists() and path.stat().st_size > 0:
            return {"arxiv_id": arxiv_id, "path": str(path), "status": "cached"}
        url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        _download(url, path)
        # 写回 paper.pdf_path，让后续 resolve_pdf_path / extract 链路命中
        from apps.papers.models import Paper
        Paper.objects.filter(arxiv_id=arxiv_id).update(pdf_path=str(path))
        return {"arxiv_id": arxiv_id, "path": str(path), "status": "downloaded"}
    except Exception as exc:  # noqa: BLE001
        log.warning("[pdf_auto] %s download failed: %r", arxiv_id, exc)
        path.unlink(missing_ok=True)
        path.with_suffix(path.suffix + ".part").unlink(missing_ok=True)
        return {"arxiv_id": arxiv_id, "status": "failed", "error": str(exc)}
    finally:
        with _LOCK:
            _INFLIGHT.discard(arxiv_id)


# ---- figures-fast 守门 ----
_FAST_INFLIGHT: set[str] = set()


def _do_figures_fast(arxiv_id: str, pdf_path_str: str) -> dict:
    """job worker：跑 pdfplumber 抽 fast figures。"""
    from pathlib import Path
    from apps.extract.figure_pdfplumber import extract_figures_fast

    try:
        out = extract_figures_fast(Path(pdf_path_str), arxiv_id)
        return {"arxiv_id": arxiv_id, "n_figures": len(out)}
    except Exception as exc:  # noqa: BLE001
        log.warning("[figures-fast] %s failed: %r", arxiv_id, exc)
        return {"arxiv_id": arxiv_id, "error": str(exc)}
    finally:
        with _LOCK:
            _FAST_INFLIGHT.discard(arxiv_id)


def ensure_figures_fast_async(paper: "Paper") -> bool:
    """详情页 GET 时调用 — 若 fast figures 缺失且本地 PDF 已存在 → enqueue
    后台抽。失败 swallow。返回 True 表示排了 job。

    幂等：figures-fast 目录非空时 noop；同 arxiv_id in-flight 时不重复入队。
    """
    arxiv_id = (paper.arxiv_id or "").strip()
    if not arxiv_id:
        return False
    from apps.papers.paths import resolve_pdf_path
    from apps.extract.figure_pdfplumber import figures_fast_dir

    pdf = resolve_pdf_path(paper)
    if pdf is None:
        return False  # 等 ensure_pdf_async 完成；用户下次进来再触发
    out_dir = figures_fast_dir(arxiv_id)
    if any(out_dir.glob("*.png")):
        return False
    with _LOCK:
        if arxiv_id in _FAST_INFLIGHT:
            return False
        _FAST_INFLIGHT.add(arxiv_id)
    try:
        from apps.api import jobs
        jobs.enqueue(_do_figures_fast, arxiv_id, str(pdf), name=f"figures-fast:{arxiv_id}")
        log.info("[figures-fast] enqueued %s", arxiv_id)
        return True
    except Exception:
        with _LOCK:
            _FAST_INFLIGHT.discard(arxiv_id)
        raise


def ensure_pdf_async(paper: "Paper") -> bool:
    """详情页 GET 时调用。返回 True 表示新排了一个下载 job；False 表示
    无需下载（已缓存 / 非 arxiv / 已在排队）。

    幂等：可在每次 detail GET 安全调用。
    """
    arxiv_id = (paper.arxiv_id or "").strip()
    if not arxiv_id:
        return False
    # 已有本地 PDF（pdf_path / legacy fallback）→ noop
    from apps.papers.paths import resolve_pdf_path
    if resolve_pdf_path(paper) is not None:
        return False
    with _LOCK:
        if arxiv_id in _INFLIGHT:
            return False
        _INFLIGHT.add(arxiv_id)
    try:
        from apps.api import jobs
        jobs.enqueue(_do_download, arxiv_id, name=f"pdf-auto:{arxiv_id}")
        log.info("[pdf_auto] enqueued download for %s", arxiv_id)
        return True
    except Exception:
        with _LOCK:
            _INFLIGHT.discard(arxiv_id)
        raise
