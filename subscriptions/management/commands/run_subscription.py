"""端到端 pipeline (ft-013):
yaml → rewriter → fetch → 按 target_date 过滤 → memory 跨 run 去重
→ rerank → skim → caption + bbox-render 图 → text-only deep_interpret
→ narrative → 写 memory → render → send.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from delivery.email_renderer import RenderedDeep, RenderedSkim, render_html
from delivery.email_sender import send as send_email
from interpret.caption_extractor import extract_captions
from interpret.deep_interpret import deep_interpret_rich
from interpret.figure_classifier import classify_figures, pick_architecture_figure
from interpret.figure_extractor import extract_figures, figures_root, save_index
from interpret.figure_picker import pick_architecture
from interpret.interpretation import DEEP_PLACEHOLDER, DeepOut, deep_interpret, skim_interpret
from interpret.narrative import build_narrative
from interpret.pdf_chunker import chunk_pdf
from interpret.ranker import rank
from interpret.rewriter import RewriteInput, rewrite
from sources import fetchers  # noqa: F401  触发 registry 注册
from sources.base import Item, REGISTRY, SourceQuery
from sources.pdf_fetcher import arxiv_id_of, fetch_pdf
from sources.pdf_renderer import render_bbox_to_png
from subscriptions.loader import find, load
from subscriptions.memory import (
    PaperRecord,
    RunRecord,
    append_digest,
    append_papers,
    append_run,
    known_dedup_keys,
    load_papers,
    sub_dir,
)

log = logging.getLogger(__name__)

SHANGHAI = timezone(timedelta(hours=8))


class Command(BaseCommand):
    help = "运行一条订阅：fetch → rerank → skim/deep → narrative → email"
    requires_system_checks: list = []

    def add_arguments(self, parser) -> None:
        parser.add_argument("name")
        parser.add_argument("--yaml", default="subscriptions.yaml")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--no-llm", action="store_true",
                            help="跳过 rewriter+rerank+skim+narrative+deep")
        parser.add_argument("--no-narrative", action="store_true")
        parser.add_argument("--no-deep", action="store_true",
                            help="跳过精读 PDF+caption+deep；用 ft-009 占位")
        parser.add_argument("--multimodal-figures", action="store_true",
                            help="(legacy) 启用多模态图分类（ft-012）；默认关闭")
        parser.add_argument("--target-date",
                            help="目标日期 YYYY-MM-DD（默认昨日 Asia/Shanghai）")
        parser.add_argument("--limit-per-source", type=int, default=None)
        parser.add_argument("--ignore-memory", action="store_true",
                            help="跳过 memory 跨 run 去重")

    def handle(self, *args, **opts) -> None:
        yaml_path = Path(opts["yaml"])
        if not yaml_path.exists():
            raise CommandError(f"YAML not found: {yaml_path}")
        subs = load(yaml_path)
        sub = find(subs, opts["name"])
        if sub is None:
            raise CommandError(f"subscription not found: {opts['name']}")
        if not sub.enabled:
            self.stdout.write(self.style.WARNING(f"disabled: {sub.name}"))
            return

        target_date = _parse_target_date(opts["target_date"])
        since_utc, until_utc = _date_window(target_date)
        self.stdout.write(self.style.NOTICE(
            f"[target] date={target_date.isoformat()} "
            f"window=[{since_utc.isoformat()} .. {until_utc.isoformat()}]"
        ))

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
        all_items: list[Item] = []
        dedup_sources: dict[str, list[str]] = defaultdict(list)
        for spec in sub.sources:
            if spec.key not in REGISTRY:
                self.stderr.write(self.style.ERROR(f"  [{spec.key}] unknown, skip"))
                continue
            fetcher = REGISTRY[spec.key]
            q = _apply_params(query, spec.key, spec.params)
            limit = opts["limit_per_source"] or spec.params.get("limit", 30)
            # 拉宽窗口（since 起点向后扩 1 天容错），后再按 target_date 严格过滤
            try:
                items = fetcher.fetch(q, since=since_utc, limit=limit)
            except Exception as exc:  # noqa: BLE001
                self.stderr.write(self.style.ERROR(f"  [{spec.key}] raised: {exc!r}"))
                continue
            kept: list[Item] = []
            for it in items:
                if it.published_at is None:
                    continue
                pub = it.published_at
                if pub.tzinfo is None:
                    pub = pub.replace(tzinfo=timezone.utc)
                if since_utc <= pub < until_utc:
                    kept.append(it)
            self.stdout.write(self.style.SUCCESS(
                f"  [{spec.key}] raw={len(items)} in_window={len(kept)}"
            ))
            for it in kept:
                dedup_sources[it.dedup_key].append(spec.key)
                all_items.append(it)

        # ---- 3. dedup（同 run 内 + 跨 run memory）+ max_items ----
        max_items = sub.deliveries[0].max_items if sub.deliveries else 15
        run_seen: set[str] = set()
        deduped: list[Item] = []
        for it in all_items:
            if it.dedup_key in run_seen:
                continue
            run_seen.add(it.dedup_key)
            deduped.append(it)
        if not opts["ignore_memory"]:
            past = known_dedup_keys(sub.name)
            before = len(deduped)
            deduped = [it for it in deduped if it.dedup_key not in past]
            if before - len(deduped):
                self.stdout.write(
                    f"  [memory] skipped {before - len(deduped)} already-pushed"
                )
        deduped = deduped[:max_items]
        self.stdout.write(
            f"  [dedup] {len(all_items)} -> {len(deduped)} (run+memory+limit)"
        )
        if not deduped:
            self.stdout.write(self.style.WARNING("no items, exit early"))
            return

        # ---- 4. rerank ----
        if opts["no_llm"]:
            scored_items = deduped
            deep_items = deduped[:1]
            skim_items = deduped[1:]
            scored = []
        else:
            scored = rank(deduped, interests=sub.interests, dedup_sources=dedup_sources)
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
                    f"rel={s.relevance:.2f} hot={s.hotness:.2f}  "
                    f"{s.item.title[:64]}"
                )

        # ---- 5. skim interpret ----
        skim_out_by_id: dict[str, object] = {}
        if not opts["no_llm"]:
            for it in scored_items:
                so = skim_interpret(it, sub.perspective)
                if so is not None:
                    skim_out_by_id[it.dedup_key] = so
            self.stdout.write(f"  [skim] {len(skim_out_by_id)}/{len(scored_items)} ok")

        # ---- 6. deep (caption + memory + text LLM, no multimodal) ----
        memory_papers = (
            [] if opts["ignore_memory"] else load_papers(sub.name, limit=40)
        )
        deep_out_by_id: dict[str, DeepOut] = {}
        inline_images: dict[str, Path] = {}
        for it in deep_items:
            if opts["no_llm"] or opts["no_deep"]:
                deep_out_by_id[it.dedup_key] = deep_interpret(it, sub.perspective)
                continue
            arxiv_id = arxiv_id_of(it)
            pdf_path = fetch_pdf(it) if arxiv_id else None
            chunks = chunk_pdf(arxiv_id, pdf_path) if (arxiv_id and pdf_path) else None
            captions = extract_captions(arxiv_id, pdf_path) if (arxiv_id and pdf_path) else []
            arch_caption = pick_architecture(captions, llm_fallback=False)

            if opts["multimodal_figures"]:
                # legacy ft-012 path
                figs = (extract_figures(arxiv_id, pdf_path)
                        if arxiv_id and pdf_path else [])
                if figs:
                    figs = classify_figures(arxiv_id, figs)
                    save_index(arxiv_id, figs)
                    arch_fig = pick_architecture_figure(figs)
                else:
                    arch_fig = None
                self.stdout.write(
                    f"  [deep/{arxiv_id}] [legacy MM] sections="
                    f"{len(chunks.sections) if chunks else 0} figs={len(figs)} "
                    f"arch={arch_fig.path if arch_fig else '-'}"
                )
            else:
                arch_fig = None

            self.stdout.write(
                f"  [deep/{arxiv_id}] sections={len(chunks.sections) if chunks else 0} "
                f"captions={len(captions)} arch={arch_caption.label if arch_caption else '-'}"
            )

            out = deep_interpret_rich(
                item=it,
                chunks=chunks,
                captions=captions,
                memory_papers=memory_papers,
                perspective=sub.perspective,
            )
            # 渲染架构图为 PNG（用 caption bbox 推断的图区域）
            if arch_caption and arxiv_id and pdf_path:
                fig_dir = figures_root() / arxiv_id
                fig_dir.mkdir(parents=True, exist_ok=True)
                fig_name = f"arch_{arch_caption.kind}{arch_caption.number}.png"
                fig_path = fig_dir / fig_name
                ok = render_bbox_to_png(
                    pdf_path, arch_caption.page,
                    arch_caption.bbox_image, fig_path,
                )
                if ok:
                    out.figure_path = fig_name
                    out.figure_caption = arch_caption.text
                    inline_images[fig_name] = fig_path
                    self.stdout.write(f"    [render] {fig_name} OK")
                else:
                    self.stdout.write(f"    [render] failed; no inline image")
            deep_out_by_id[it.dedup_key] = out

        # ---- 7. narrative ----
        narrative = None
        if not opts["no_llm"] and not opts["no_narrative"]:
            entries = [
                (i + 1, it, skim_out_by_id.get(it.dedup_key))
                for i, it in enumerate(scored_items)
            ]
            narrative = build_narrative(entries, sub.perspective)
            if narrative:
                self.stdout.write(f"  [narrative] hero: {narrative.hero_sentence[:60]}…")
            else:
                self.stdout.write("  [narrative] failed (skip render)")

        # ---- 8. render ----
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

        date_str = target_date.isoformat()
        subject = f"[explore-os] {sub.name} · {date_str}"
        persp_label = (
            sub.perspective.custom or sub.perspective.preset or "neutral"
        )
        run_summary = (
            f"{sub.name} · {date_str} · {len(deeps)} 精读 + {len(skims)} 略读 · "
            f"来源 {', '.join(s.key for s in sub.sources)} · 视角 {persp_label}"
        )
        html_body, plain_body = render_html(
            subject=subject, narrative=narrative,
            deeps=deeps, skims=skims, run_summary=run_summary,
        )

        # ---- 9. send ----
        if opts["dry_run"]:
            self.stdout.write(self.style.WARNING("\n--- DRY RUN: plain body ---"))
            self.stdout.write(plain_body)
            self.stdout.write(self.style.WARNING(
                f"\n--- HTML body ({len(html_body)} chars) not shown ---"
            ))
            self._write_memory(sub.name, target_date, scored, scored_items,
                               skim_out_by_id, narrative, dry_run=True)
            return

        if not sub.deliveries:
            raise CommandError("no deliveries configured")
        sent_ok = False
        for d in sub.deliveries:
            if d.channel != "email":
                self.stderr.write(f"  [channel={d.channel}] skip (MVP)")
                continue
            to = d.to or settings.EMAIL_TO_DEFAULT
            if not to:
                raise CommandError("no recipient")
            ok = send_email(subject, html_body, plain_body, to=to,
                            inline_images=inline_images or None)
            mark = self.style.SUCCESS("OK") if ok else self.style.ERROR("FAIL")
            self.stdout.write(f"  [email -> {to}] {mark}")
            sent_ok = sent_ok or ok

        # ---- 10. write memory ----
        if sent_ok:
            self._write_memory(sub.name, target_date, scored, scored_items,
                               skim_out_by_id, narrative, dry_run=False)

    # ------ memory writeback ------

    def _write_memory(self, name, target_date: date, scored, scored_items,
                       skim_out_by_id, narrative, dry_run: bool) -> None:
        now = datetime.now(timezone.utc).isoformat()
        deep_n = sum(1 for s in scored if s.tier == "deep") if scored else 0
        skim_n = (len(scored) - deep_n) if scored else 0

        rec = RunRecord(
            target_date=target_date.isoformat(),
            started_at=now,
            item_count=len(scored_items),
            deep_count=deep_n,
            skim_count=skim_n,
            sources=[],
            notes="dry-run" if dry_run else "",
        )
        append_run(name, rec)

        recs: list[PaperRecord] = []
        score_by_id = {s.item.dedup_key: s for s in (scored or [])}
        for it in scored_items:
            so = skim_out_by_id.get(it.dedup_key)
            s = score_by_id.get(it.dedup_key)
            recs.append(PaperRecord(
                dedup_key=it.dedup_key,
                title=it.title,
                authors=list(it.authors),
                url=it.url,
                source_key=it.source_key,
                pushed_at=now,
                target_date=target_date.isoformat(),
                score=(s.total if s else 0.0),
                tier=(s.tier if s else "skim"),
                one_liner=(getattr(so, "one_liner", "") or ""),
                keywords=list(getattr(so, "keywords", []) or []),
            ))
        append_papers(name, recs)

        if narrative:
            append_digest(
                name, target_date.isoformat(),
                narrative.hero_sentence, narrative.bullets, narrative.note_for_you,
            )
        self.stdout.write(self.style.SUCCESS(
            f"  [memory] wrote run + {len(recs)} papers + digest "
            f"to {sub_dir(name)}"
        ))


def _apply_params(query: SourceQuery, source_key: str, params: dict) -> SourceQuery:
    cats = params.get("categories")
    if source_key == "arxiv" and cats:
        return SourceQuery(
            keywords=query.keywords, arxiv_query=query.arxiv_query,
            arxiv_categories=list(cats), hf_keywords=query.hf_keywords,
            raw=query.raw,
        )
    return query


def _parse_target_date(s: str | None) -> date:
    if s:
        return datetime.strptime(s, "%Y-%m-%d").date()
    yesterday = (datetime.now(SHANGHAI) - timedelta(days=1)).date()
    return yesterday


def _date_window(target: date) -> tuple[datetime, datetime]:
    start_local = datetime.combine(target, time.min, tzinfo=SHANGHAI)
    end_local = datetime.combine(target + timedelta(days=1), time.min, tzinfo=SHANGHAI)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)
