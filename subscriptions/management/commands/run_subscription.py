"""MVP pipeline: 加载订阅 → rewriter → fetch → TL;DR → render → send.

用法：
  uv run python manage.py run_subscription video-generation-daily \\
      --yaml subscriptions.yaml [--dry-run] [--no-llm] [--limit-per-source 10]
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from delivery.email_renderer import RenderedItem, render_html
from delivery.email_sender import send as send_email
from interpret.ranker import rank
from interpret.rewriter import RewriteInput, rewrite
from interpret.tldr import summarize
from sources import fetchers  # noqa: F401  触发 registry 注册
from sources.base import REGISTRY, SourceQuery
from subscriptions.loader import find, load

log = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "运行一条订阅：fetch → tldr → email（端到端）"
    requires_system_checks: list = []

    def add_arguments(self, parser) -> None:
        parser.add_argument("name", help="订阅 name")
        parser.add_argument("--yaml", default="subscriptions.yaml",
                            help="订阅 YAML 路径")
        parser.add_argument("--dry-run", action="store_true",
                            help="不发邮件，仅打印 HTML 和 plain")
        parser.add_argument("--no-llm", action="store_true",
                            help="跳过 rewriter + TL;DR（直接用 interests 当查询）")
        parser.add_argument("--limit-per-source", type=int, default=None,
                            help="覆盖每个 source 的 limit")
        parser.add_argument("--since-days", type=int, default=None,
                            help="覆盖 source.params.since_days")

    def handle(self, *args, **opts) -> None:
        yaml_path = Path(opts["yaml"])
        if not yaml_path.exists():
            raise CommandError(f"YAML not found: {yaml_path}")

        subs = load(yaml_path)
        sub = find(subs, opts["name"])
        if sub is None:
            raise CommandError(f"subscription not found: {opts['name']}")
        if not sub.enabled:
            self.stdout.write(self.style.WARNING(f"subscription disabled: {sub.name}"))
            return

        # ---- 1. rewriter ----
        if opts["no_llm"]:
            query = SourceQuery(
                keywords=sub.interests,
                hf_keywords=sub.interests,
            )
            self.stdout.write("  [rewriter] skipped (--no-llm)")
        else:
            self.stdout.write("  [rewriter] calling LLM...")
            query = rewrite(RewriteInput(interests=sub.interests, exclude=sub.exclude))
            self.stdout.write(f"  [rewriter] arxiv_query={query.arxiv_query!r}")
            self.stdout.write(f"  [rewriter] hf_keywords={query.hf_keywords!r}")

        # ---- 2. fetch ----
        all_items = []
        dedup_sources: dict[str, list[str]] = defaultdict(list)
        for spec in sub.sources:
            if spec.key not in REGISTRY:
                self.stderr.write(self.style.ERROR(f"  [{spec.key}] unknown, skip"))
                continue
            fetcher = REGISTRY[spec.key]
            q = _apply_params(query, spec.key, spec.params)
            since_days = opts["since_days"] or spec.params.get("since_days", 7)
            since = datetime.now(timezone.utc) - timedelta(days=since_days)
            limit = opts["limit_per_source"] or spec.params.get("limit", 20)
            try:
                items = fetcher.fetch(q, since=since, limit=limit)
            except Exception as exc:  # noqa: BLE001
                self.stderr.write(self.style.ERROR(f"  [{spec.key}] raised: {exc!r}"))
                continue
            self.stdout.write(self.style.SUCCESS(
                f"  [{spec.key}] got {len(items)} items"
            ))
            for it in items:
                dedup_sources[it.dedup_key].append(spec.key)
                all_items.append(it)

        # ---- 3. 去重（同 dedup_key 保留第一个）+ 上限 ----
        max_items = sub.deliveries[0].max_items if sub.deliveries else 15
        seen: set[str] = set()
        unique: list = []
        for it in all_items:
            if it.dedup_key in seen:
                continue
            seen.add(it.dedup_key)
            unique.append(it)
        unique = unique[:max_items]
        self.stdout.write(f"  [dedup] {len(all_items)} -> {len(unique)} after dedup+limit")

        # ---- 3.5. rerank (ft-008) ----
        if opts["no_llm"]:
            self.stdout.write("  [ranker] skipped (--no-llm)")
        else:
            scored = rank(unique, interests=sub.interests, dedup_sources=dedup_sources)
            unique = [s.item for s in scored]
            deep_n = sum(1 for s in scored if s.tier == "deep")
            self.stdout.write(
                f"  [ranker] {len(scored)} items scored; "
                f"deep={deep_n} skim={len(scored) - deep_n}"
            )
            for s in scored[:5]:
                self.stdout.write(
                    f"    [{s.tier:4s}] total={s.total:.2f} "
                    f"rel={s.relevance:.2f} hot={s.hotness:.2f}  {s.item.title[:70]}"
                )

        # ---- 4. TL;DR ----
        rendered: list[RenderedItem] = []
        llm_calls = 0
        for it in unique:
            tldr_obj = None
            if not opts["no_llm"]:
                tldr_obj = summarize(it)
                if tldr_obj:
                    llm_calls += 1
            rendered.append(RenderedItem(
                item=it,
                tldr=tldr_obj,
                dup_sources=sorted(set(dedup_sources.get(it.dedup_key, []))),
            ))
        self.stdout.write(f"  [tldr] {llm_calls} LLM summaries generated")

        # ---- 5. render ----
        groups: dict[str, list[RenderedItem]] = defaultdict(list)
        for ri in rendered:
            groups[ri.item.group].append(ri)

        date_str = datetime.now().strftime("%Y-%m-%d")
        subject = f"[explore-os] {sub.name} · {date_str}"
        run_summary = (
            f"订阅 {sub.name} · {len(unique)} 篇新内容 · "
            f"来源: {', '.join(s.key for s in sub.sources)} · "
            f"{'LLM 已解读 ' + str(llm_calls) + ' 条' if llm_calls else '未调 LLM'}"
        )
        html_body, plain_body = render_html(subject, dict(groups), run_summary)

        # ---- 6. send ----
        if opts["dry_run"]:
            self.stdout.write(self.style.WARNING("\n--- DRY RUN: plain body ---"))
            self.stdout.write(plain_body)
            self.stdout.write(self.style.WARNING(
                f"\n--- HTML body ({len(html_body)} chars) not shown ---"
            ))
            return

        if not sub.deliveries:
            raise CommandError("no deliveries configured for this subscription")

        for d in sub.deliveries:
            if d.channel != "email":
                self.stderr.write(f"  [channel={d.channel}] not supported in MVP, skip")
                continue
            to = d.to or settings.EMAIL_TO_DEFAULT
            if not to:
                raise CommandError("no recipient (set delivery.to or EMAIL_TO_DEFAULT)")
            ok = send_email(subject, html_body, plain_body, to=to)
            marker = self.style.SUCCESS("OK") if ok else self.style.ERROR("FAIL")
            self.stdout.write(f"  [email -> {to}] {marker}")


def _apply_params(query: SourceQuery, source_key: str, params: dict) -> SourceQuery:
    """把订阅 source.params 按源注入到 query。"""
    cats = params.get("categories")
    if source_key == "arxiv" and cats:
        return SourceQuery(
            keywords=query.keywords,
            arxiv_query=query.arxiv_query,
            arxiv_categories=list(cats),
            hf_keywords=query.hf_keywords,
            raw=query.raw,
        )
    return query
