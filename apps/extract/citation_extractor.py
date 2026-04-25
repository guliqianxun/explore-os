"""ft-019: 最简 citation 抽取（references 段 best-effort 解析）.

MVP 仅存 bibkey + 标题 + 年份；arXiv id / DOI 反解延后（独立异步任务）。

启发流程：
  1. 取 PDF 全文（pymupdf 纯文本）。
  2. 定位 ``References`` 章节起点。
  3. 逐条切分（编号 ``[1]`` / ``1.`` / 空行分隔）。
  4. 从每条抽 bibkey（首作者姓+年份） + 标题 + 年份。
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

REFERENCES_HEADING_RE = re.compile(
    r"(?im)^\s*(references|bibliography|参考文献)\s*$"
)
# 编号条目：``[12]``、``12.``、``12)``、``(12)``
ENTRY_NUM_RE = re.compile(r"^\s*(?:\[(\d+)\]|\((\d+)\)|(\d+)[.\)])\s+")
YEAR_RE = re.compile(r"\b(19|20)\d{2}[a-z]?\b")
# 首作者姓抓取：行首到第一个逗号/句号，取末尾的纯字母 token（粗启发）
FIRST_AUTHOR_TOKEN_RE = re.compile(r"^([A-Z][A-Za-z\-']+)")


@dataclass(slots=True)
class Citation:
    arxiv_id: str
    bibkey: str
    raw_text: str
    title: str = ""
    year: int | None = None


def extract_citations(arxiv_id: str, pdf_path: Path) -> list[Citation]:
    """从 PDF 抽 references 段，解析每条为 Citation。"""
    if not pdf_path.exists():
        return []
    try:
        import pymupdf
    except ImportError:
        log.error("pymupdf not installed")
        return []

    try:
        with pymupdf.open(pdf_path) as doc:
            full_text = "\n".join(page.get_text() for page in doc)
    except Exception as exc:  # noqa: BLE001
        log.error("extract_citations: pdf read failed: %r", exc)
        return []

    refs_block = _slice_references(full_text)
    if not refs_block:
        return []

    entries = _split_entries(refs_block)
    out: list[Citation] = []
    seen_keys: set[str] = set()
    for raw in entries:
        cit = _parse_entry(arxiv_id, raw)
        if cit is None:
            continue
        # 同一 bibkey 重复时追加序号避免覆盖
        key = cit.bibkey
        suffix = 2
        while key in seen_keys:
            key = f"{cit.bibkey}#{suffix}"
            suffix += 1
        cit.bibkey = key
        seen_keys.add(key)
        out.append(cit)

    log.info("extract_citations: %s -> %d citations", arxiv_id, len(out))
    return out


# ---------------- internals ----------------

def _slice_references(text: str) -> str:
    """截取最后一个 References / Bibliography 标题之后的内容。"""
    matches = list(REFERENCES_HEADING_RE.finditer(text))
    if not matches:
        return ""
    return text[matches[-1].end():].strip()


def _split_entries(block: str) -> list[str]:
    """按编号条目或空行切分 references."""
    lines = block.splitlines()
    entries: list[list[str]] = []
    current: list[str] = []

    def flush():
        if current:
            joined = " ".join(s.strip() for s in current).strip()
            if joined:
                entries.append([joined])
            current.clear()

    for line in lines:
        stripped = line.strip()
        if not stripped:
            flush()
            continue
        if ENTRY_NUM_RE.match(stripped):
            flush()
            current.append(ENTRY_NUM_RE.sub("", stripped, count=1))
        else:
            current.append(stripped)
    flush()

    return [e[0] for e in entries if e and len(e[0]) > 8]


def _parse_entry(arxiv_id: str, raw: str) -> Citation | None:
    """从一条 raw reference 字符串抽 bibkey/title/year."""
    raw = raw.strip()
    if not raw:
        return None

    year_match = YEAR_RE.search(raw)
    year = int(year_match.group(0)[:4]) if year_match else None

    author_match = FIRST_AUTHOR_TOKEN_RE.match(raw)
    author = author_match.group(1).lower() if author_match else "ref"

    bibkey_year = str(year) if year else "n.d."
    bibkey = f"{author}{bibkey_year}"

    title = _guess_title(raw, year_match)

    return Citation(
        arxiv_id=arxiv_id,
        bibkey=bibkey,
        raw_text=raw[:1000],
        title=title,
        year=year,
    )


def _guess_title(raw: str, year_match: re.Match | None) -> str:
    """粗启发：年份后第一个完整句子（直到 ``.``）作为 title。"""
    if year_match:
        tail = raw[year_match.end():].lstrip(" ,.):")
    else:
        # 跳过首作者团到第一个 "."
        first_dot = raw.find(".")
        tail = raw[first_dot + 1:].lstrip() if first_dot != -1 else raw
    # 截到下一个 "." 之前作为标题
    end = tail.find(".")
    title = tail[:end] if end != -1 else tail
    return title.strip()[:480]
