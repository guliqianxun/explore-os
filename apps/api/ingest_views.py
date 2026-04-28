"""ft-027: PDF / arXiv / URL ingest endpoints。

3 个入口：
- ``POST /api/ingest/upload/``  multipart 文件
- ``POST /api/ingest/arxiv/``   ``{"arxiv_id": "..."}``
- ``POST /api/ingest/url/``     ``{"url": "...", "paper_id": "..." (可选)}``

每个入口完成"取到 PDF + 推断 arxiv_id" 后调
``apps.api.ingest.chain_extract_interpret_render`` 起异步链。
"""
from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path

import httpx
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.api.ingest import chain_extract_interpret_render
from apps.core import paths

log = logging.getLogger(__name__)

ARXIV_ID_RE = re.compile(r"^\d{4}\.\d{4,5}(v\d+)?$")
HTTP_TIMEOUT = 60.0
PDF_SIZE_CAP = 100 * 1024 * 1024  # 100 MB


def _sha256_short(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def _save_pdf(content: bytes, paper_id: str) -> Path:
    """落盘到 papers_dir() / <paper_id>.pdf 并同步 Paper.pdf_path（ft-029）.

    Paper 行可能尚不存在（extract signal 后才建），所以 update_or_create
    by arxiv_id；title 兜底 "arxiv:<id>"，与 signals._ensure_paper_fk 同语义。
    后续 extract pre_save signal 会 get_or_create 命中同一行。
    """
    dst = paths.papers_dir() / f"{paper_id}.pdf"
    dst.write_bytes(content)
    # ft-029: 写入 pdf_path（避免循环 import，延迟到函数内 import）。
    # Paper 行可能尚未创建（extract signal 后才落）。get_or_create + 显式
    # update 防止覆盖 extract 后回填的 title（defaults 只在 create 时生效）。
    from apps.papers.models import Paper
    paper, _ = Paper.objects.get_or_create(
        arxiv_id=paper_id,
        defaults={"title": f"arxiv:{paper_id}", "pdf_path": str(dst)},
    )
    if paper.pdf_path != str(dst):
        paper.pdf_path = str(dst)
        paper.save(update_fields=["pdf_path"])
    return dst


# ---------------- upload ----------------

class IngestUploadView(APIView):
    """multipart upload。表单字段：

    - ``file``：必填，PDF 二进制
    - ``paper_id``：可选；缺省取文件 sha256 前 16 位
    """
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        f = request.FILES.get("file")
        if f is None:
            return Response({"detail": "file is required"},
                            status=status.HTTP_400_BAD_REQUEST)
        data = f.read()
        if len(data) == 0:
            return Response({"detail": "empty file"},
                            status=status.HTTP_400_BAD_REQUEST)
        if len(data) > PDF_SIZE_CAP:
            return Response({"detail": "pdf too large"},
                            status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
        if not data.startswith(b"%PDF"):
            return Response({"detail": "not a PDF (magic mismatch)"},
                            status=status.HTTP_400_BAD_REQUEST)

        paper_id = (request.data.get("paper_id") or "").strip() or _sha256_short(data)
        path = _save_pdf(data, paper_id)
        info = chain_extract_interpret_render(paper_id, path)
        return Response(
            {"job_id": info.job_id, "status": info.status,
             "paper_id": paper_id, "pdf_path": str(path)},
            status=status.HTTP_202_ACCEPTED,
        )


# ---------------- arxiv ----------------

class IngestArxivView(APIView):
    """JSON ``{arxiv_id}`` → 拉 arXiv PDF → 起 chain。"""
    parser_classes = [JSONParser]

    def post(self, request):
        arxiv_id = (request.data.get("arxiv_id") or "").strip()
        if not arxiv_id:
            return Response({"detail": "arxiv_id is required"},
                            status=status.HTTP_400_BAD_REQUEST)
        if not ARXIV_ID_RE.match(arxiv_id):
            return Response(
                {"detail": "invalid arxiv_id format (expect e.g. 2401.12345)"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 复用 sources.pdf_fetcher 已有的 cache + retry，绕过 Item 包装
        from sources.pdf_fetcher import _download, local_pdf_path
        path = local_pdf_path(arxiv_id)
        if not (path.exists() and path.stat().st_size > 0):
            url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
            try:
                _download(url, path)
            except Exception as exc:  # noqa: BLE001
                log.error("[ingest-arxiv] %s download failed: %r", arxiv_id, exc)
                path.unlink(missing_ok=True)
                return Response(
                    {"detail": f"arxiv PDF download failed: {exc}"},
                    status=status.HTTP_502_BAD_GATEWAY,
                )

        info = chain_extract_interpret_render(arxiv_id, path)
        return Response(
            {"job_id": info.job_id, "status": info.status,
             "paper_id": arxiv_id, "pdf_path": str(path)},
            status=status.HTTP_202_ACCEPTED,
        )


# ---------------- url ----------------

class IngestUrlView(APIView):
    """JSON ``{url, paper_id?}`` → httpx GET → 校验 PDF → 起 chain。"""
    parser_classes = [JSONParser]

    def post(self, request):
        url = (request.data.get("url") or "").strip()
        if not url:
            return Response({"detail": "url is required"},
                            status=status.HTTP_400_BAD_REQUEST)
        if not (url.startswith("http://") or url.startswith("https://")):
            return Response({"detail": "url must be http(s)"},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            with httpx.stream("GET", url, timeout=HTTP_TIMEOUT,
                              follow_redirects=True) as resp:
                resp.raise_for_status()
                ctype = (resp.headers.get("content-type") or "").lower()
                # 路径或 Content-Disposition 暗示 PDF 也算
                looks_pdf = (
                    "application/pdf" in ctype
                    or url.lower().endswith(".pdf")
                )
                if not looks_pdf:
                    return Response(
                        {"detail": f"not a PDF (content-type={ctype})"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                buf = bytearray()
                for chunk in resp.iter_bytes(chunk_size=64 * 1024):
                    buf.extend(chunk)
                    if len(buf) > PDF_SIZE_CAP:
                        return Response({"detail": "pdf too large"},
                                        status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
        except httpx.HTTPError as exc:
            log.error("[ingest-url] download failed %s: %r", url, exc)
            return Response({"detail": f"download failed: {exc}"},
                            status=status.HTTP_502_BAD_GATEWAY)

        data = bytes(buf)
        if not data.startswith(b"%PDF"):
            return Response({"detail": "not a PDF (magic mismatch)"},
                            status=status.HTTP_400_BAD_REQUEST)

        paper_id = (request.data.get("paper_id") or "").strip() or _sha256_short(data)
        path = _save_pdf(data, paper_id)
        info = chain_extract_interpret_render(paper_id, path)
        return Response(
            {"job_id": info.job_id, "status": info.status,
             "paper_id": paper_id, "pdf_path": str(path)},
            status=status.HTTP_202_ACCEPTED,
        )
