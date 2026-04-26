"""ft-013: 订阅级记忆线（确定性工具，无 LLM）.

每订阅一个 namespace：media/memory/<sub_name>/
- runs.jsonl     每次运行追加一条（date, item_count, deep, skim, cost）
- papers.jsonl   每篇推送过的论文追加一条（dedup_key, title, ..., one_liner, keywords, score, tier, pushed_at）
- digests.md     累积速览，每天追加一段 (hero_sentence + bullets)
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from apps.core.paths import memory_dir

log = logging.getLogger(__name__)


def memory_root() -> Path:
    return memory_dir()


def sub_dir(name: str) -> Path:
    d = memory_root() / _safe(name)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _safe(s: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in s)[:80]


# ---------------- run record ----------------

@dataclass(slots=True)
class RunRecord:
    target_date: str       # YYYY-MM-DD
    started_at: str        # ISO
    item_count: int
    deep_count: int
    skim_count: int
    sources: list[str] = field(default_factory=list)
    notes: str = ""


def append_run(sub_name: str, rec: RunRecord) -> None:
    path = sub_dir(sub_name) / "runs.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(rec), ensure_ascii=False) + "\n")


def list_runs(sub_name: str, limit: int = 30) -> list[RunRecord]:
    path = sub_dir(sub_name) / "runs.jsonl"
    if not path.exists():
        return []
    out: list[RunRecord] = []
    for line in path.read_text(encoding="utf-8").splitlines()[-limit:]:
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
            out.append(RunRecord(**d))
        except Exception as exc:  # noqa: BLE001
            log.warning("runs.jsonl bad line: %r", exc)
    return out


# ---------------- paper record ----------------

@dataclass(slots=True)
class PaperRecord:
    dedup_key: str
    title: str
    authors: list[str]
    url: str
    source_key: str
    pushed_at: str         # ISO
    target_date: str       # YYYY-MM-DD（论文所属"今日"）
    score: float
    tier: str              # deep | skim
    abstract_zh: str = ""        # ft-014 中文摘要
    keywords: list[str] = field(default_factory=list)
    # 兼容旧 ft-013 文件：one_liner 字段会被读，但新代码不再写
    one_liner: str = ""


def append_papers(sub_name: str, recs: list[PaperRecord]) -> None:
    if not recs:
        return
    path = sub_dir(sub_name) / "papers.jsonl"
    with path.open("a", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(asdict(r), ensure_ascii=False) + "\n")


def load_papers(sub_name: str, limit: int = 200) -> list[PaperRecord]:
    """读最近 N 条已推送论文（供 deep_interpret 提供上下文）."""
    path = sub_dir(sub_name) / "papers.jsonl"
    if not path.exists():
        return []
    out: list[PaperRecord] = []
    for line in path.read_text(encoding="utf-8").splitlines()[-limit:]:
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
            out.append(PaperRecord(**d))
        except Exception as exc:  # noqa: BLE001
            log.warning("papers.jsonl bad line: %r", exc)
    return out


def known_dedup_keys(sub_name: str) -> set[str]:
    """全量已推送 dedup_key 集合（用于跨 run 去重）."""
    return {p.dedup_key for p in load_papers(sub_name, limit=10_000)}


# ---------------- digests.md ----------------

def append_digest(
    sub_name: str,
    target_date: str,
    hero_sentence: str,
    bullets: list[str],
    note: str = "",
) -> None:
    """累积速览：每个 target_date 一段 markdown."""
    path = sub_dir(sub_name) / "digests.md"
    block = [f"## {target_date}", ""]
    if hero_sentence:
        block.append(f"**{hero_sentence}**")
        block.append("")
    for b in bullets:
        block.append(f"- {b}")
    if note:
        block.append("")
        block.append(f"> {note}")
    block.append("")
    block.append("")
    with path.open("a", encoding="utf-8") as f:
        f.write("\n".join(block))


def recent_digest_lines(sub_name: str, days: int = 7) -> str:
    """读最近 N 天的 digest 段落，给 deep_interpret 做上下文输入."""
    path = sub_dir(sub_name) / "digests.md"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")[-4000:]
