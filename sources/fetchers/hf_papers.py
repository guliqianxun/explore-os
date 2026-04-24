"""ft-004: HuggingFace Daily Papers fetcher.

端点：GET https://huggingface.co/api/daily_papers?date=YYYY-MM-DD
按 since -> today 逐日请求；每条 paper 与 arXiv 源跨源去重（dedup_key=arxiv:<id>）。
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from sources.base import Item, SourceQuery, register

logger = logging.getLogger(__name__)

API_BASE = "https://huggingface.co/api/daily_papers"
HTTP_TIMEOUT = 15.0
ARXIV_ID_PATTERN = re.compile(r"^\d{4}\.\d{4,5}$")


@dataclass(slots=True)
class HFPapersFetcher:
    key: str = "hf_papers"
    group: str = "papers"
    # 允许测试注入自定义 transport / client
    transport: httpx.BaseTransport | None = None

    def fetch(
        self,
        query: SourceQuery,
        since: datetime,
        limit: int = 50,
    ) -> list[Item]:
        keywords = query.hf_keywords or query.keywords
        today = datetime.now(timezone.utc).date()
        start = _to_date(since)
        if start > today:
            return []

        items: list[Item] = []
        seen: set[str] = set()

        with self._client() as client:
            cur = start
            while cur <= today and len(items) < limit:
                try:
                    payload = self._get_day(client, cur)
                except Exception as exc:  # noqa: BLE001
                    logger.error("hf_papers: fetch failed for %s: %s", cur, exc)
                    cur += timedelta(days=1)
                    continue

                for entry in payload:
                    item = _to_item(entry)
                    if item is None:
                        continue
                    if not _matches(item, keywords):
                        continue
                    if item.dedup_key in seen:
                        continue
                    seen.add(item.dedup_key)
                    items.append(item)
                    if len(items) >= limit:
                        break
                cur += timedelta(days=1)

        return items

    # ------- internal -------

    def _client(self) -> httpx.Client:
        return httpx.Client(
            transport=self.transport,
            timeout=HTTP_TIMEOUT,
            headers={"User-Agent": "explore-os/0.1 (+hf_papers fetcher)"},
        )

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
    )
    def _get_day(self, client: httpx.Client, day: date) -> list[dict[str, Any]]:
        resp = client.get(API_BASE, params={"date": day.isoformat()})
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, list):
            return []
        return data


# ---------------- helpers ----------------

def _to_date(dt: datetime) -> date:
    if dt.tzinfo is None:
        return dt.date()
    return dt.astimezone(timezone.utc).date()


def _parse_iso(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        # HF returns e.g. "2024-01-15T00:00:00.000Z"
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _to_item(entry: dict[str, Any]) -> Item | None:
    paper = entry.get("paper") if isinstance(entry, dict) else None
    if not isinstance(paper, dict):
        return None
    external_id = str(paper.get("id") or "").strip()
    if not external_id:
        return None

    title = str(paper.get("title") or "").strip()
    abstract = str(paper.get("summary") or paper.get("abstract") or "").strip()
    authors_raw = paper.get("authors") or []
    authors: list[str] = []
    if isinstance(authors_raw, list):
        for a in authors_raw:
            if isinstance(a, dict):
                name = a.get("name") or a.get("fullname")
                if name:
                    authors.append(str(name))
            elif isinstance(a, str):
                authors.append(a)

    published_at = (
        _parse_iso(paper.get("publishedAt"))
        or _parse_iso(entry.get("publishedAt"))
        or _parse_iso(entry.get("submittedOnDailyAt"))
    )

    if ARXIV_ID_PATTERN.match(external_id):
        dedup_key = f"arxiv:{external_id}"
        url = f"https://huggingface.co/papers/{external_id}"
    else:
        dedup_key = f"hf_papers:{external_id}"
        url = f"https://huggingface.co/papers/{external_id}"

    return Item(
        external_id=external_id,
        title=title,
        abstract=abstract,
        url=url,
        source_key="hf_papers",
        group="papers",
        authors=authors,
        venue="",
        published_at=published_at,
        dedup_key=dedup_key,
        raw=entry,
    )


def _matches(item: Item, keywords: list[str]) -> bool:
    if not keywords:
        return True
    haystack = f"{item.title}\n{item.abstract}".lower()
    return any(kw.strip().lower() in haystack for kw in keywords if kw.strip())


register(HFPapersFetcher())
