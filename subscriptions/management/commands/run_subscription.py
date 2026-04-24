"""MVP pipeline: 加载订阅 → rewriter → fetch → rerank → skim/deep → narrative → render → send.

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

from delivery.email_renderer import RenderedDeep, RenderedSkim, render_html
from delivery.email_sender import send as send_email
from interpret.interpretation import deep_interpret, skim_interpret
from interpret.narrative import build_narrative
from interpret.ranker import rank
from interpret.rewriter import RewriteInput, rewrite
from sources import fetchers  # noqa: F401  触发 registry 注册
from sources.base import REGISTRY, SourceQuery
from subscriptions.loader import find, load

log = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "运行一条订阅：fetch → rerank → skim/deep → narrative → email"
    requires_system_checks: list = []

    def add_arguments(self, parser) -> None:
        parser.add_argument("name", help="订阅 name")
        parser.add_argument("--yaml", default="subscriptions.yaml",
                            help="订阅 YAML 路径")
        parser.add_argument("--dry-run", action="store_true",
                            help="不发邮件，仅打印 plain body")
        parser.add_argument("--no-llm", action="store_true",
                            help="跳过 rewriter + rerank + skim + narrative")
        parser.add_argument("--limit-per-source", type=int, default=None)
        parser.add_argument("--since-days", type=int, default=None)
        parser.add_argument("--no-narrative", action="store_true",
                            help="跳过 Daily Narrative 生成")

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
            query = SourceQuery(keywords=sub.interests, hf_keywords=sub.interests)
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
            self.stdout.write(self.style.SUCCESS(f"  [{spec.key}] got {len(items)} items"))
            for it in items:
                dedup_sources[it.dedup_key].append(spec.key)
                all_items.append(it)

        # ---- 3. dedup + max_items ----
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

        # ---- 4. rerank (ft-008) ----
        if opts["no_llm"]:
            scored_items = unique                   # 原顺序
            deep_items = unique[:1] if unique else []
            skim_items = unique[1:]
            self.stdout.write("  [ranker] skipped (--no-llm): take first as deep")
        else:
            scored = rank(unique, interests=sub.interests, dedup_sources=dedup_sources)
            scored_items = [s.item for s in scored]
            deep_items = [s.item for s in scored if s.tier == "deep"]
            skim_items = [s.item for s in scored if s.tier == "skim"]
            self.stdout.write(
                f"  [ranker] scored={len(scored)} deep={len(deep_items)} "
                f"skim={len(skim_items)}"
            )
            for s in scored[:5]:
                self.stdout.write(
                    f"    [{s.tier:4s}] total={s.total:.2f} "
                    f"rel={s.relevance:.2f} hot={s.hotness:.2f}  {s.item.title[:70]}"
                )

        # ---- 5. skim interpret (for all; narrative needs it too) ----
        skim_out_by_id: dict[str, object] = {}
        if not opts["no_llm"]:
            for it in scored_items:
                out = skim_interpret(it, sub.perspective)
                if out is not None:
                    skim_out_by_id[it.dedup_key] = out
            self.stdout.write(f"  [skim] {len(skim_out_by_id)}/{len(scored_items)} ok")

        # ---- 6. deep interpret (iter-002: passthrough abstract + 占位) ----
        deep_out_by_id = {
            it.dedup_key: deep_interpret(it, sub.perspective) for it in deep_items
        }

        # ---- 7. narrative ----
        narrative = None
        if not opts["no_llm"] and not opts["no_narrative"]:
            # 索引从 1 起，按 scored_items 顺序（deep 在前）
            entries = [
                (i + 1, it, skim_out_by_id.get(it.dedup_key))
                for i, it in enumerate(scored_items)
            ]
            narrative = build_narrative(entries, sub.perspective)
            if narrative:
                self.stdout.write(f"  [narrative] hero: {narrative.hero_sentence[:60]}…")
            else:
                self.stdout.write("  [narrative] failed (降级不显示)")

        # ---- 8. render ----
        # 索引：deep 先从 1 编，然后 skim 接续
        deeps: list[RenderedDeep] = []
        skims: list[RenderedSkim] = []
        idx = 1
        for it in deep_items:
            deeps.append(RenderedDeep(
                item=it,
                deep=deep_out_by_id[it.dedup_key],
                dup_sources=sorted(set(dedup_sources.get(it.dedup_key, []))),
                index=idx,
            ))
            idx += 1
        for it in skim_items:
            skims.append(RenderedSkim(
                item=it,
                skim=skim_out_by_id.get(it.dedup_key),  # type: ignore[arg-type]
                dup_sources=sorted(set(dedup_sources.get(it.dedup_key, []))),
                index=idx,
            ))
            idx += 1

        date_str = datetime.now().strftime("%Y-%m-%d")
        subject = f"[explore-os] {sub.name} · {date_str}"
        persp_label = (
            sub.perspective.custom
            or sub.perspective.preset
            or "neutral"
        )
        run_summary = (
            f"{sub.name} · {len(deeps)} 精读 + {len(skims)} 略读 · "
            f"来源 {', '.join(s.key for s in sub.sources)} · 视角 {persp_label}"
        )
        html_body, plain_body = render_html(
            subject=subject,
            narrative=narrative,
            deeps=deeps,
            skims=skims,
            run_summary=run_summary,
        )

        # ---- 9. send ----
        if opts["dry_run"]:
            self.stdout.write(self.style.WARNING("\n--- DRY RUN: plain body ---"))
            self.stdout.write(plain_body)
            self.stdout.write(self.style.WARNING(
                f"\n--- HTML body ({len(html_body)} chars) not shown ---"
            ))
            return

        if not sub.deliveries:
            raise CommandError("no deliveries configured")
        for d in sub.deliveries:
            if d.channel != "email":
                self.stderr.write(f"  [channel={d.channel}] skip (MVP)")
                continue
            to = d.to or settings.EMAIL_TO_DEFAULT
            if not to:
                raise CommandError("no recipient (set delivery.to or EMAIL_TO_DEFAULT)")
            ok = send_email(subject, html_body, plain_body, to=to)
            mark = self.style.SUCCESS("OK") if ok else self.style.ERROR("FAIL")
            self.stdout.write(f"  [email -> {to}] {mark}")


def _apply_params(query: SourceQuery, source_key: str, params: dict) -> SourceQuery:
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
