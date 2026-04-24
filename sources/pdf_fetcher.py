"""ft-011: arXiv PDF downloader with local cache.

仅处理 arxiv source（dedup_key 以 'arxiv:' 开头或 source_key=='arxiv'）。
落盘到 media/papers/<arxiv_id>.pdf；二次请求命中缓存不发 HTTP。
"""
from __future__ import annotations

import logging
from pathlib import Path

import httpx
from django.conf import settings
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from sources.base import Item

log = logging.getLogger(__name__)

PDF_SIZE_CAP = 30 * 1024 * 1024  # 30 MB
HTTP_TIMEOUT = 60.0


def cache_root() -> Path:
    root = Path(getattr(settings, "BASE_DIR", Path.cwd())) / "media" / "papers"
    root.mkdir(parents=True, exist_ok=True)
    return root


def arxiv_id_of(item: Item) -> str | None:
    """从 Item.dedup_key 提取 arxiv id。仅 `arxiv:xxx.yyyyy` 形式返回。"""
    key = item.dedup_key or ""
    if key.startswith("arxiv:"):
        return key[6:]
    return None


def local_pdf_path(arxiv_id: str) -> Path:
    return cache_root() / f"{arxiv_id}.pdf"


def fetch_pdf(item: Item) -> Path | None:
    """下载 arxiv PDF；失败或非 arxiv 源返回 None。"""
    arxiv_id = arxiv_id_of(item)
    if not arxiv_id:
        log.info("pdf_fetcher: not arxiv, skip %s", item.dedup_key)
        return None
    path = local_pdf_path(arxiv_id)
    if path.exists() and path.stat().st_size > 0:
        return path

    url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    try:
        _download(url, path)
    except Exception as exc:  # noqa: BLE001
        log.error("pdf_fetcher: download failed %s: %r", arxiv_id, exc)
        path.unlink(missing_ok=True)
        path.with_suffix(path.suffix + ".part").unlink(missing_ok=True)
        return None
    return path


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
)
def _download(url: str, dst: Path) -> None:
    """流式下载，强制 size cap。"""
    tmp = dst.with_suffix(dst.suffix + ".part")
    written = 0
    with httpx.stream("GET", url, timeout=HTTP_TIMEOUT, follow_redirects=True) as resp:
        resp.raise_for_status()
        with tmp.open("wb") as f:
            for chunk in resp.iter_bytes(chunk_size=64 * 1024):
                written += len(chunk)
                if written > PDF_SIZE_CAP:
                    raise ValueError(
                        f"pdf too large: > {PDF_SIZE_CAP // (1024 * 1024)}MB"
                    )
                f.write(chunk)
    tmp.replace(dst)
