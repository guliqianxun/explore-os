"""ft-011 (搬迁自 interpret/pdf_chunker): parse PDF to markdown via pymupdf4llm,
chunk by section heading.

分档归桶：intro / method / experiments / conclusion / other
每桶按字符数截断控 token。下游 ft-012 的 deep_interpret 消费。
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

# 章节关键词映射到桶
BUCKET_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("intro", ("introduction", "background", "motivation")),
    ("related", ("related work", "related works", "prior work", "literature")),
    ("method", ("method", "approach", "architecture", "model", "framework",
                "proposed", "algorithm", "design")),
    ("experiments", ("experiment", "evaluation", "results", "analysis",
                     "ablation", "study", "benchmark")),
    ("conclusion", ("conclusion", "discussion", "limitation", "future work",
                    "closing", "broader impact")),
]
# 每桶字符上限（约等于 token × 3 中文 / × 4 英文，保守估算）
BUCKET_CHAR_CAP = {
    "intro": 4000,
    "method": 8000,
    "experiments": 6000,
    "conclusion": 3000,
    "related": 0,   # MVP drop
    "other": 0,     # MVP drop
}

# markdown heading: "## 1 Introduction" / "# Method" / etc.
HEADING_RE = re.compile(r"^(#{1,3})\s+(.+?)\s*$")


@dataclass(slots=True)
class Section:
    bucket: str
    title: str
    text: str


@dataclass(slots=True)
class PaperChunks:
    arxiv_id: str
    sections: list[Section] = field(default_factory=list)
    parser: str = "pymupdf4llm"

    def by_bucket(self, bucket: str) -> str:
        """合并某桶的全部文本。"""
        return "\n\n".join(s.text for s in self.sections if s.bucket == bucket).strip()


def chunk_pdf(arxiv_id: str, pdf_path: Path, cache_dir: Path | None = None) -> PaperChunks | None:
    """解析 PDF，按章节切分归桶。失败返回 None。"""
    if not pdf_path.exists() or pdf_path.stat().st_size == 0:
        return None

    cache_dir = cache_dir or pdf_path.parent
    cache_file = cache_dir / f"{arxiv_id}.chunks.json"
    if cache_file.exists():
        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            return PaperChunks(
                arxiv_id=data["arxiv_id"],
                sections=[Section(**s) for s in data["sections"]],
                parser=data.get("parser", "pymupdf4llm"),
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("chunks cache corrupt, re-parse: %r", exc)

    text = _parse_to_markdown(pdf_path)
    if not text:
        return None
    sections = _split_by_heading(text)
    chunks = PaperChunks(arxiv_id=arxiv_id, sections=sections)

    try:
        cache_file.write_text(
            json.dumps(
                {
                    "arxiv_id": chunks.arxiv_id,
                    "sections": [asdict(s) for s in chunks.sections],
                    "parser": chunks.parser,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("chunks cache write failed: %r", exc)

    return chunks


# ---------------- internals ----------------

def _parse_to_markdown(pdf_path: Path) -> str:
    """优先 pymupdf4llm（保留结构），失败降级 pymupdf 纯文本。"""
    try:
        import pymupdf4llm
        return pymupdf4llm.to_markdown(str(pdf_path))
    except Exception as exc:  # noqa: BLE001
        log.warning("pymupdf4llm failed, fallback to pymupdf: %r", exc)

    try:
        import pymupdf
        with pymupdf.open(pdf_path) as doc:
            return "\n\n".join(page.get_text() for page in doc)
    except Exception as exc:  # noqa: BLE001
        log.error("pdf parse totally failed: %r", exc)
        return ""


def _classify_bucket(title: str) -> str:
    low = title.lower().strip()
    # strip leading numbers / dots / spaces: "3.2 Architecture" → "architecture"
    low = re.sub(r"^[\d\.\s]+", "", low)
    for bucket, keywords in BUCKET_KEYWORDS:
        for kw in keywords:
            if kw in low:
                return bucket
    return "other"


def _split_by_heading(md: str) -> list[Section]:
    """按 heading 切分，归桶并按桶字符上限截断。"""
    lines = md.splitlines()
    sections_raw: list[tuple[str, list[str]]] = []
    current_title = "Preamble"
    buf: list[str] = []

    for line in lines:
        m = HEADING_RE.match(line)
        if m:
            if buf:
                sections_raw.append((current_title, buf))
            current_title = m.group(2).strip()
            buf = []
        else:
            buf.append(line)
    if buf:
        sections_raw.append((current_title, buf))

    result: list[Section] = []
    # 按桶累计已用字符
    used: dict[str, int] = {}
    for title, body in sections_raw:
        bucket = _classify_bucket(title)
        cap = BUCKET_CHAR_CAP.get(bucket, 0)
        if cap <= 0:
            continue
        text = "\n".join(body).strip()
        if not text:
            continue
        remaining = cap - used.get(bucket, 0)
        if remaining <= 0:
            continue
        if len(text) > remaining:
            text = text[:remaining].rstrip() + "\n…（截断）"
        used[bucket] = used.get(bucket, 0) + len(text)
        result.append(Section(bucket=bucket, title=title, text=text))
    return result
