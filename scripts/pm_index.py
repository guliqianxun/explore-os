#!/usr/bin/env python3
"""PM Index: Build, aggregate, validate, sync for explore-os project.

Architecture:
  docs/pm/  -- PM territory (roadmap, changelog, features, iterations, communications)
    ├── ROADMAP.md
    ├── CHANGELOG.md
    ├── index.json
    ├── features/ft-*.md
    ├── iterations/iter-*.md
    └── communications/
        ├── dsp-*.md   (dispatches: PM -> executor)
        └── rpt-*.md   (reports: executor -> PM)

No external dependencies.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Force UTF-8 output on Windows
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DEFAULT_PM_ROOT = Path("docs/pm")
DEFAULT_INDEX = DEFAULT_PM_ROOT / "index.json"

DOC_GLOB = "**/*.md"
HEADING_RE = re.compile(r"^(?P<level>#{1,6})\s+(?P<title>.+?)\s*$")
FEATURE_STATUS_ORDER = ["done", "in_progress", "planned", "deferred", "superseded"]
ITER_STATUS_ORDER = ["done", "in_progress", "planned", "superseded"]


def parse_scalar(value: str):
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [p.strip().strip('"\'') for p in inner.split(",")]
    low = value.lower()
    if low in ("true", "false"):
        return low == "true"
    return value.strip('"\'')


def parse_frontmatter(text: str):
    lines = text.splitlines()
    if len(lines) < 3 or lines[0].strip() != "---":
        return {}, 0
    meta: dict = {}
    end_line = 0
    in_nested = None
    for idx in range(1, len(lines)):
        raw = lines[idx].rstrip()
        if raw.strip() == "---":
            end_line = idx + 1
            break
        if not raw or raw.lstrip().startswith("#"):
            continue
        if raw.startswith("  ") and in_nested:
            if ":" in raw:
                k, v = raw.strip().split(":", 1)
                meta[in_nested][k.strip()] = parse_scalar(v)
            continue
        in_nested = None
        if ":" not in raw:
            continue
        key, value = raw.split(":", 1)
        key = key.strip()
        vs = value.strip()
        if not vs:
            meta[key] = {}
            in_nested = key
        else:
            meta[key] = parse_scalar(value)
    return meta, end_line


def ensure_list(val):
    if isinstance(val, list):
        return val
    if isinstance(val, str) and val:
        return [v.strip() for v in val.split(",") if v.strip()]
    return []


def resolve_paths(args):
    pm_root = DEFAULT_PM_ROOT
    index_path = DEFAULT_INDEX
    if "--root" in args:
        pm_root = Path(args[args.index("--root") + 1])
        index_path = pm_root / "index.json"
    if "--index" in args:
        index_path = Path(args[args.index("--index") + 1])
    return pm_root, index_path


def parse_args_map(args):
    out = {}
    i = 0
    while i < len(args):
        if args[i].startswith("--") and i + 1 < len(args):
            out[args[i][2:]] = args[i + 1]
            i += 2
        else:
            i += 1
    return out


def load_index(index_path: Path):
    if index_path.exists():
        return json.loads(index_path.read_text(encoding="utf-8"))
    return {"project": "explore-os", "features": [], "iterations": [], "errors": []}


# ── Build ──

def cmd_build(args):
    pm_root, index_path = resolve_paths(args)

    features = []
    iterations = []
    errors = []
    seen_ids = set()

    # Scan features/
    feat_dir = pm_root / "features"
    if feat_dir.exists():
        for fp in sorted(feat_dir.glob("ft-*.md")):
            text = fp.read_text(encoding="utf-8")
            meta, _ = parse_frontmatter(text)
            fid = meta.get("pm_id", fp.stem)
            if fid in seen_ids:
                errors.append(f"Duplicate pm_id: {fid}")
                continue
            seen_ids.add(fid)
            features.append({
                "id": fid,
                "title": meta.get("title", ""),
                "status": meta.get("status", "planned"),
                "priority": meta.get("priority", ""),
                "milestone": meta.get("milestone", ""),
                "depends_on": ensure_list(meta.get("depends_on", [])),
                "blocks": ensure_list(meta.get("blocks", [])),
                "file": fp.relative_to(pm_root).as_posix(),
            })

    # Scan iterations/
    iter_dir = pm_root / "iterations"
    if iter_dir.exists():
        for fp in sorted(iter_dir.glob("iter-*.md")):
            text = fp.read_text(encoding="utf-8")
            meta, _ = parse_frontmatter(text)
            iid = meta.get("pm_id", fp.stem)
            if iid in seen_ids:
                errors.append(f"Duplicate pm_id: {iid}")
                continue
            seen_ids.add(iid)
            iterations.append({
                "id": iid,
                "title": meta.get("title", ""),
                "status": meta.get("status", "planned"),
                "milestone": meta.get("milestone", ""),
                "file": fp.relative_to(pm_root).as_posix(),
            })

    data = {
        "project": "explore-os",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "features": features,
        "iterations": iterations,
        "errors": errors,
    }
    index_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Built: {len(features)} features, {len(iterations)} iterations, {len(errors)} errors -> {index_path.as_posix()}")


# ── Aggregate ──

def cmd_aggregate(args):
    pm_root, index_path = resolve_paths(args)
    data = load_index(index_path)
    features = data.get("features", [])
    iterations = data.get("iterations", [])

    # Feature stats
    status_counts: dict[str, int] = {}
    for f in features:
        s = f.get("status", "planned")
        status_counts[s] = status_counts.get(s, 0) + 1

    total = len(features)
    done = status_counts.get("done", 0)
    wip = status_counts.get("in_progress", 0)
    planned = status_counts.get("planned", 0)
    deferred = status_counts.get("deferred", 0)
    superseded = status_counts.get("superseded", 0)

    active = done + wip
    pct = f"{int(active / total * 100)}%" if total else "0%"

    print("=" * 60)
    print(f"  explore-os PM Status Report")
    print(f"  Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC")
    print(f"=" * 60)
    print(f"\n  Features: {total} total  |  {done} done  |  {wip} in-progress")
    print(f"             {planned} planned  |  {deferred} deferred  |  {superseded} superseded")
    print(f"  Completion: {active}/{total} ({pct})")

    # Iteration stats
    if iterations:
        it_done = sum(1 for i in iterations if i.get("status") == "done")
        it_wip = sum(1 for i in iterations if i.get("status") == "in_progress")
        it_planned = sum(1 for i in iterations if i.get("status") == "planned")
        print(f"\n  Iterations: {len(iterations)} total  |  {it_done} done  |  {it_wip} in-progress  |  {it_planned} planned")

    # WIP features
    wip_features = [f for f in features if f.get("status") == "in_progress"]
    if wip_features:
        print(f"\n  -- In Progress --")
        for f in wip_features:
            print(f"  [{f['id']}] {f.get('title','')}")

    # Planned features
    planned_features = [f for f in features if f.get("status") == "planned"]
    if planned_features:
        print(f"\n  -- Planned (Next) --")
        for f in planned_features:
            print(f"  [{f['id']}] {f.get('title','')}  ({f.get('milestone','')})")

    # Deferred
    deferred_features = [f for f in features if f.get("status") == "deferred"]
    if deferred_features:
        print(f"\n  -- Deferred --")
        for f in deferred_features:
            print(f"  [{f['id']}] {f.get('title','')}")

    # Check dispatches vs reports
    comm_dir = pm_root / "communications"
    if comm_dir.exists():
        dispatches = {}
        for dp in sorted(comm_dir.glob("dsp-*.md")):
            text = dp.read_text(encoding="utf-8")
            meta, _ = parse_frontmatter(text)
            dsp_id = meta.get("pm_id", dp.stem)
            dispatches[dsp_id] = meta

        reports = {}
        for rp in sorted(comm_dir.glob("rpt-*.md")):
            text = rp.read_text(encoding="utf-8")
            meta, _ = parse_frontmatter(text)
            rpt_id = meta.get("pm_id", rp.stem)
            reports[rpt_id] = meta

        # Pending dispatches with completed reports
        stale = []
        for dsp_id, dsp in dispatches.items():
            dsp_status = dsp.get("status", "")
            feat = dsp.get("feature", "")
            # Find report referencing this dispatch
            matched_reports = [r for r in reports.values() if r.get("dispatch_ref") == dsp_id]
            if dsp_status == "pending" and matched_reports:
                for r in matched_reports:
                    if r.get("status") == "completed":
                        stale.append((dsp_id, feat, dsp.get("target", ""), r.get("pm_id", "")))

        if stale:
            print(f"\n  -- Stale Dispatches (pending but report completed) --")
            for dsp_id, feat, target, rpt_id in stale:
                print(f"  {dsp_id} ({feat}, -> {target}) completed by {rpt_id}")

    # Missing iteration files (from index.json references)
    iter_dir = pm_root / "iterations"
    if iterations and iter_dir.exists():
        existing_iters = {fp.stem for fp in iter_dir.glob("iter-*.md")}
        for it in iterations:
            if it["id"] not in existing_iters:
                print(f"\n  ! Missing iteration file: {it['id']} ({it.get('title','')})")

    print()


# ── Validate ──

def cmd_validate(args):
    pm_root, index_path = resolve_paths(args)
    data = load_index(index_path)
    features = data.get("features", [])
    errors = []
    warnings = []

    feature_ids = {f["id"] for f in features}

    # Reference integrity
    for f in features:
        for dep in ensure_list(f.get("depends_on", [])):
            if dep not in feature_ids:
                errors.append(f"[{f['id']}] depends_on missing feature: {dep}")
        for blk in ensure_list(f.get("blocks", [])):
            if blk not in feature_ids:
                errors.append(f"[{f['id']}] blocks missing feature: {blk}")

    # Dispatch-report consistency
    comm_dir = pm_root / "communications"
    if comm_dir.exists():
        for dp in sorted(comm_dir.glob("dsp-*.md")):
            text = dp.read_text(encoding="utf-8")
            meta, _ = parse_frontmatter(text)
            dsp_id = meta.get("pm_id", "")
            dsp_status = meta.get("status", "")
            feat = meta.get("feature", "")
            if dsp_status == "pending":
                if feat and feat in feature_ids:
                    feat_obj = next((f for f in features if f["id"] == feat), None)
                    if feat_obj and feat_obj.get("status") == "done":
                        warnings.append(f"Dispatch {dsp_id} is 'pending' but feature {feat} is 'done' — update dispatch status")

    # Missing iteration files check
    iter_dir = pm_root / "iterations"
    iterations = data.get("iterations", [])
    if iter_dir.exists() and iterations:
        existing_iters = {fp.stem for fp in iter_dir.glob("iter-*.md")}
        for it in iterations:
            if it["id"] not in existing_iters:
                warnings.append(f"Iteration {it['id']} ({it.get('title','')}) referenced in index but no .md file exists")

    if errors:
        print(f"[ERR] {len(errors)} error(s):")
        for e in errors:
            print(f"  {e}")
    if warnings:
        print(f"[WARN] {len(warnings)} warning(s):")
        for w in warnings:
            print(f"  {w}")
    if not errors and not warnings:
        print("All checks passed. [OK]")
        return 0
    return 1 if errors else 0


# ── Status ──

def cmd_status(args):
    pm_root, index_path = resolve_paths(args)
    data = load_index(index_path)
    features = data.get("features", [])
    iterations = data.get("iterations", [])

    done = sum(1 for f in features if f.get("status") == "done")
    wip = sum(1 for f in features if f.get("status") == "in_progress")
    planned = sum(1 for f in features if f.get("status") == "planned")
    total = len(features)
    active = done + wip
    pct = f"{int(active / total * 100)}%" if total else "0%"

    it_done = sum(1 for i in iterations if i.get("status") == "done")
    it_total = len(iterations)

    print(f"[PM] Status Report:")
    print(f"  Roadmap: v1.2 ({pct} Complete) {'[DONE]' if active == total else '[WIP]'}")
    print(f"  Iterations: {it_done}/{it_total} done")
    print(f"  Features: {done} done | {wip} in-progress | {planned} planned")

    wip_list = [f for f in features if f.get("status") == "in_progress"]
    planned_list = [f for f in features if f.get("status") == "planned"]
    if wip_list:
        ids = ", ".join(f["id"] for f in wip_list)
        print(f"  Current Focus: {ids}")
    if planned_list:
        ids_top = ", ".join(f["id"] for f in planned_list[:3])
        suffix = "..." if len(planned_list) > 3 else ""
        print(f"  Next Up: {ids_top}{suffix}")

    # Check for unlinked dispatches
    comm_dir = pm_root / "communications"
    if comm_dir.exists():
        pending_dsps = []
        for dp in sorted(comm_dir.glob("dsp-*.md")):
            meta, _ = parse_frontmatter(dp.read_text(encoding="utf-8"))
            if meta.get("status") == "pending":
                found_report = False
                for rp in comm_dir.glob("rpt-*.md"):
                    rm, _ = parse_frontmatter(rp.read_text(encoding="utf-8"))
                    if rm.get("dispatch_ref") == meta.get("pm_id") and rm.get("status") == "completed":
                        found_report = True
                        break
                if not found_report:
                    pending_dsps.append(meta.get("pm_id", ""))
                else:
                    pending_dsps.append(f"{meta.get('pm_id','')}*")
        if pending_dsps:
            print(f"  Blockers: {len(pending_dsps)} pending dispatch(es) ({', '.join(pending_dsps)}) — * has completed report")
        else:
            print(f"  Blockers: None reported.")


# ── Sync ──

def cmd_sync(args):
    pm_root, index_path = resolve_paths(args)
    data = load_index(index_path)
    features = data.get("features", [])

    roadmap_path = pm_root / "ROADMAP.md"
    if not roadmap_path.exists():
        print("ROADMAP.md not found.", file=sys.stderr)
        sys.exit(1)

    rtext = roadmap_path.read_text(encoding="utf-8")
    lines = rtext.splitlines()

    # Parse milestones from heading level-2 lines containing "M" or version
    milestones = {}
    for i, line in enumerate(lines):
        if not line.startswith("## "):
            continue
        title = line[3:].strip()
        if title in ("项目定位", "技术栈", "目标用户", "核心设计约束",
                     "Features 索引", "当前迭代", "战略转向", "桌面端决策",
                     "两条路：解读 vs 解压", "Chat 分级 + with-memory 第一逻辑",
                     "Out of Scope / Won't Do", "未决议题"):
            continue
        name = title.split("—", 1)[0].strip() if "—" in title else title.split(" ", 1)[0].strip()
        # Extract version from milestone name like "v0.1 MVP (M1)"
        ver = name.split(" ")[0] if " " in name else name
        milestones[name] = ver

    # Count features per milestone
    mil_counts: dict[str, dict] = {}
    for f in features:
        ms = f.get("milestone", "")
        if ms not in mil_counts:
            mil_counts[ms] = {"total": 0, "done": 0}
        mil_counts[ms]["total"] += 1
        if f.get("status") in ("done",):
            mil_counts[ms]["done"] += 1

    # Rebuild version overview table
    rows = []
    for name, ver in milestones.items():
        mc = mil_counts.get(ver, {"total": 0, "done": 0})
        total = mc["total"]
        done_n = mc["done"]
        pct = f"{int(done_n / total * 100)}%" if total else "--"
        status_icon = "Done" if done_n >= total > 0 else "WIP" if done_n > 0 else "Planned"
        rows.append(f"| {name} | {status_icon} | {total} | {done_n} | {pct} |")

    # Find and replace version overview table
    start = header = end = None
    for i, line in enumerate(lines):
        if line.startswith("## 版本概览"):
            start = i
        elif start is not None and header is None and line.startswith("| 版本 |"):
            header = i
        elif header is not None and i > header + 1 and not line.startswith("|"):
            end = i
            break

    table = ["| 版本 | 状态 | 计划特性数 | 已完成 | 进度 |", "|------|------|-----------|--------|------|"] + rows
    if start is None or header is None:
        suffix = ["", "## 版本概览", "", *table]
        new_text = "\n".join(lines + suffix) + ("\n" if rtext.endswith("\n") else "")
    else:
        if end is None:
            end = len(lines)
        new_text = "\n".join(lines[:header] + table + lines[end:]) + "\n"

    roadmap_path.write_text(new_text, encoding="utf-8")
    print(f"Synced ROADMAP.md version overview table with {len(rows)} milestones.")


# ── Main ──

USAGE = """pm_index.py — explore-os project management tool

Commands:
  build       Scan all PM docs and rebuild index.json
  aggregate   Unified status report (features, iterations, dispatch drift)
  validate    Cross-document consistency checks (references, stale dispatches)
  sync        Rebuild ROADMAP.md version overview table
  status      Quick status summary

Options:
  --root <path>   PM root directory (default: docs/pm)
  --index <path>  Index file path (default: docs/pm/index.json)
"""


def main(argv):
    if len(argv) < 2 or argv[1] in {"-h", "--help", "help"}:
        print(USAGE)
        return 0
    cmd = argv[1]
    args = argv[2:]
    cmds = {
        "build": cmd_build,
        "aggregate": cmd_aggregate,
        "validate": cmd_validate,
        "sync": cmd_sync,
        "status": cmd_status,
    }
    if cmd not in cmds:
        print(f"Unknown command: {cmd}\n{USAGE}", file=sys.stderr)
        return 1
    return cmds[cmd](args) or 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
