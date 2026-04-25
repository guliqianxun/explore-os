"""ft-014 端到端 pipeline:
yaml → rewriter → fetch → target_date 过滤 → memory 跨 run 去重
→ rerank → 全部 items 拉 PDF + 抽 caption + 渲 framework/qualitative/table 图
→ 略读 LLM 翻译中文 abstract
→ 精读 LLM 深度解读
→ narrative → 写 memory → render → send.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

import delivery  # noqa: F401  触发各 adapter 注册到 registry
from delivery.base import (
    Digest,
    DeliveryTarget,
    RenderedDeep,
    RenderedSkim,
    get as get_adapter,
)
from interpret.caption_extractor import Caption, extract_captions
from interpret.deep_interpret import deep_interpret_rich
from interpret.figure_extractor import figures_root
from interpret.figure_picker import (
    pick_architecture,
    pick_qualitative,
    pick_table,
)
from interpret.interpretation import DEEP_PLACEHOLDER, DeepOut, SkimOut, deep_interpret, skim_interpret
from interpret.narrative import Narrative, build_narrative
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
    help = "运行一条订阅：fetch → rerank → skim/deep（含图）→ narrative → email"
    requires_system_checks: list = []

    def add_arguments(self, parser) -> None:
        parser.add_argument("name")
        parser.add_argument("--yaml", default="subscriptions.yaml")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--no-llm", action="store_true")
        parser.add_argument("--no-narrative", action="store_true")
        parser.add_argument("--no-deep", action="store_true",
                            help="精读跳过 PDF+caption+deep；用占位")
        parser.add_argument("--no-figures", action="store_true",
                            help="所有 items 都不拉 PDF / 不渲染图")
        parser.add_argument("--target-date",
                            help="目标日期 YYYY-MM-DD（默认昨日 Asia/Shanghai）")
        parser.add_argument("--limit-per-source", type=int, default=None)
        parser.add_argument("--ignore-memory", action="store_true")

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

        # ---- 2. fetch + 严格 target_date 过滤 ----
        all_items: list[Item] = []
        dedup_sources: dict[str, list[str]] = defaultdict(list)
        for spec in sub.sources:
            if spec.key not in REGISTRY:
                self.stderr.write(self.style.ERROR(f"  [{spec.key}] unknown, skip"))
                continue
            fetcher = REGISTRY[spec.key]
            q = _apply_params(query, spec.key, spec.params)
            limit = opts["limit_per_source"] or spec.params.get("limit", 30)
            try:
                items = fetcher.fetch(q, since=since_utc, limit=limit)
            except Exception as exc:  # noqa: BLE001
                self.stderr.write(self.style.ERROR(f"  [{spec.key}] raised: {exc!r}"))
                continue
            # HF dailypapers 收录日 ≠ arxiv submittedDate，常错位 1-2 天 → 加容差
            tol = timedelta(days=1) if spec.key.startswith("hf") else timedelta(0)
            local_since = since_utc - tol
            local_until = until_utc + tol
            kept = []
            for it in items:
                if it.published_at is None:
                    continue
                pub = it.published_at
                if pub.tzinfo is None:
                    pub = pub.replace(tzinfo=timezone.utc)
                if local_since <= pub < local_until:
                    kept.append(it)
            tol_label = f" (±{tol.days}d tolerance)" if tol.days else ""
            self.stdout.write(self.style.SUCCESS(
                f"  [{spec.key}] raw={len(items)} in_window={len(kept)}{tol_label}"
            ))
            for it in kept:
                dedup_sources[it.dedup_key].append(spec.key)
                all_items.append(it)

        # ---- 3. dedup（同 run + memory）+ max_items ----
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

        # ---- 5. PDF + captions + 三类图渲染（全部 items）----
        # 收集到 pdf_artifacts: dedup_key → (chunks, captions, deep_out_with_figures)
        # deep_out 在略读阶段只用 figure_path / qualitative_path / table_path 字段；
        # 精读阶段会进一步填 method_summary 等
        deep_out_by_id: dict[str, DeepOut] = {}
        chunks_by_id = {}
        captions_by_id: dict[str, list[Caption]] = {}
        inline_images: dict[str, Path] = {}

        if not opts["no_figures"]:
            for it in scored_items:
                arxiv_id = arxiv_id_of(it)
                if not arxiv_id:
                    deep_out_by_id[it.dedup_key] = DeepOut(
                        abstract=it.abstract or "", placeholder=DEEP_PLACEHOLDER,
                    )
                    continue
                pdf_path = fetch_pdf(it)
                if not pdf_path:
                    deep_out_by_id[it.dedup_key] = DeepOut(
                        abstract=it.abstract or "", placeholder=DEEP_PLACEHOLDER,
                    )
                    continue
                chunks = chunk_pdf(arxiv_id, pdf_path)
                captions = extract_captions(arxiv_id, pdf_path)
                chunks_by_id[it.dedup_key] = chunks
                captions_by_id[it.dedup_key] = captions

                arch = pick_architecture(captions, llm_fallback=False)
                qual = pick_qualitative(captions, skip=arch)
                tbl = pick_table(captions)
                self.stdout.write(
                    f"  [figs/{arxiv_id}] sec={len(chunks.sections) if chunks else 0} "
                    f"caps={len(captions)} arch={arch.label if arch else '-'} "
                    f"qual={qual.label if qual else '-'} "
                    f"tbl={tbl.label if tbl else '-'}"
                )

                d = DeepOut(abstract=it.abstract or "", placeholder=DEEP_PLACEHOLDER)
                fig_dir = figures_root() / arxiv_id
                fig_dir.mkdir(parents=True, exist_ok=True)
                # CID 加 arxiv_id 前缀避免跨论文 cid 冲突
                arxiv_cid = arxiv_id.replace("/", "_").replace(":", "_")
                if arch:
                    name = f"{arxiv_cid}__arch_{arch.kind}{arch.number}.png"
                    fp = fig_dir / name
                    if render_bbox_to_png(pdf_path, arch.page, arch.bbox_image, fp):
                        d.figure_path = name
                        d.figure_caption = arch.text
                        inline_images[name] = fp
                if qual:
                    name = f"{arxiv_cid}__qual_{qual.kind}{qual.number}.png"
                    fp = fig_dir / name
                    if render_bbox_to_png(pdf_path, qual.page, qual.bbox_image, fp):
                        d.qualitative_path = name
                        d.qualitative_caption = qual.text
                        inline_images[name] = fp
                if tbl:
                    name = f"{arxiv_cid}__tbl_{tbl.kind}{tbl.number}.png"
                    fp = fig_dir / name
                    if render_bbox_to_png(pdf_path, tbl.page, tbl.bbox_image, fp):
                        d.table_path = name
                        d.table_caption = tbl.text
                        inline_images[name] = fp
                deep_out_by_id[it.dedup_key] = d
        else:
            for it in scored_items:
                deep_out_by_id[it.dedup_key] = DeepOut(
                    abstract=it.abstract or "", placeholder=DEEP_PLACEHOLDER,
                )

        # ---- 6. skim interpret (中文 abstract) ----
        skim_out_by_id: dict[str, SkimOut] = {}
        if not opts["no_llm"]:
            for it in scored_items:
                so = skim_interpret(it, sub.perspective)
                if so is not None:
                    skim_out_by_id[it.dedup_key] = so
            self.stdout.write(f"  [skim] {len(skim_out_by_id)}/{len(scored_items)} ok")

        # ---- 7. deep interpret (only for deep tier) ----
        memory_papers = (
            [] if opts["ignore_memory"] else load_papers(sub.name, limit=40)
        )
        for it in deep_items:
            if opts["no_llm"] or opts["no_deep"]:
                continue
            chunks = chunks_by_id.get(it.dedup_key)
            captions = captions_by_id.get(it.dedup_key, [])
            deep_struct = deep_interpret_rich(
                item=it, chunks=chunks, captions=captions,
                memory_papers=memory_papers, perspective=sub.perspective,
            )
            # 把结构化字段 merge 进已有 DeepOut（保留图路径）
            existing = deep_out_by_id[it.dedup_key]
            existing.method_summary = deep_struct.method_summary
            existing.key_innovation = deep_struct.key_innovation
            existing.limitations = deep_struct.limitations
            existing.for_you = deep_struct.for_you

        # ---- 8. narrative ----
        narrative: Narrative | None = None
        if not opts["no_llm"] and not opts["no_narrative"]:
            entries = [
                (i + 1, it, skim_out_by_id.get(it.dedup_key))
                for i, it in enumerate(scored_items)
            ]
            narrative = build_narrative(entries, sub.perspective)
            if narrative:
                self.stdout.write(f"  [narrative] hero: {narrative.hero_sentence[:60]}…")

        # ---- 9. render ----
        deeps: list[RenderedDeep] = []
        skims: list[RenderedSkim] = []
        idx = 1
        for it in deep_items:
            deeps.append(RenderedDeep(
                item=it, deep=deep_out_by_id[it.dedup_key],
                skim=skim_out_by_id.get(it.dedup_key),
                dup_sources=sorted(set(dedup_sources.get(it.dedup_key, []))),
                index=idx,
            ))
            idx += 1
        for it in skim_items:
            skims.append(RenderedSkim(
                item=it, skim=skim_out_by_id.get(it.dedup_key),
                deep=deep_out_by_id.get(it.dedup_key),
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

        # ---- Build channel-neutral Digest ----
        digest = Digest(
            subject=subject,
            run_summary=run_summary,
            narrative=narrative,
            deeps=deeps,
            skims=skims,
            inline_images=inline_images,
        )

        # ---- 10. dispatch to all configured channels via DeliveryAdapter ----
        if opts["dry_run"]:
            from delivery.adapters.email import render_html as _email_render
            _, plain_body = _email_render(digest)
            self.stdout.write(self.style.WARNING("\n--- DRY RUN: plain body ---"))
            self.stdout.write(plain_body)
            self.stdout.write(self.style.WARNING(
                f"\n--- {len(inline_images)} inline images would attach ---"
            ))
            self._write_memory(sub.name, target_date, scored, scored_items,
                               skim_out_by_id, narrative, dry_run=True)
            return

        if not sub.deliveries:
            raise CommandError("no deliveries configured")
        sent_ok = False
        for d in sub.deliveries:
            try:
                adapter = get_adapter(d.channel)
            except KeyError as exc:
                self.stderr.write(self.style.ERROR(f"  [{d.channel}] {exc}"))
                continue
            target = DeliveryTarget(channel=d.channel, to=d.to or "")
            result = adapter.deliver(digest, target)
            mark = (self.style.SUCCESS("OK") if result.success
                    else self.style.ERROR("FAIL"))
            self.stdout.write(f"  [{d.channel}] {mark} {result.detail}")
            sent_ok = sent_ok or result.success

        if sent_ok:
            self._write_memory(sub.name, target_date, scored, scored_items,
                               skim_out_by_id, narrative, dry_run=False)

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
                abstract_zh=(getattr(so, "abstract_zh", "") or ""),
                keywords=list(getattr(so, "keywords", []) or []),
            ))
        append_papers(name, recs)

        if narrative:
            append_digest(
                name, target_date.isoformat(),
                narrative.hero_sentence, narrative.bullets, narrative.note_for_you,
            )
        self.stdout.write(self.style.SUCCESS(
            f"  [memory] wrote run + {len(recs)} papers + digest -> {sub_dir(name)}"
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
    return (datetime.now(SHANGHAI) - timedelta(days=1)).date()


def _date_window(target: date) -> tuple[datetime, datetime]:
    start_local = datetime.combine(target, time.min, tzinfo=SHANGHAI)
    end_local = datetime.combine(target + timedelta(days=1), time.min, tzinfo=SHANGHAI)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)
