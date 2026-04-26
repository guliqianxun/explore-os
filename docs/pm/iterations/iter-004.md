---
pm_id: iter-004
pm_type: iteration
title: Sprint 4 — 三段中台：抽取层落地
milestone: v0.6
status: in_progress
start_at: 2026-04-25
end_at: 2026-05-09
---

# iter-004 Sprint 4：三段中台 · 抽取层落地

## 战略上下文

2026-04-25 决策：**商业化暂缓**，重心从「多渠道推送」转向「**论文理解中台**」三段拆分。
本 sprint 的任务是把第一段（抽取器）干净分离出来，给 ft-020/021 铺路。
长期形态确定为**单机 app（Tauri 优先 / Electron 兜底）**，所以本 sprint 也启动 packaging 调研（ft-022）。

## 目标

| # | Feature | 优先级 | 状态 | 备注 |
|---|---|---|---|---|
| 1 | ft-019 抽取器素材索引层 | P0 | done | 接口契约 + 启发式 baseline |
| 2 | ft-022 单机 app packaging 调研 | P1 | done | 文档已交付 |
| 3 | ft-015 Docling 学术 PDF 解析升级 | P0 | in_progress | ft-019 启发式 baseline 实战不可用，启动 Docling 替换 |

ft-020 / ft-021 **不在本 sprint 范围**，等 ft-015 合并后再开 iter-005。

## Scope

- ft-019：建 `apps/extract/` Django app，搬迁 pdf_chunker / caption_extractor / figure_extractor，落 5 张 `extract_*` 表，CLI `extract_paper` 跑通 ✅
- ft-022：调研文档 `docs/architecture/packaging.md`，覆盖 Tauri / Electron / SQLite 切换 / 调度器 / 风险 ✅
- ft-015：用 Docling 替换启发式 extractor 实现（DoclingExtractor + 5 类 material 映射 + 删除 equation/citation 启发式 + section/caption/figure 三 façade 改写）

## Out of Scope

- ❌ claim 抽取（→ iter-005 / ft-020）
- ❌ 实际 packaging 实施（→ v1.0）
- ❌ ft-017 飞书 / ft-018 微信渠道（降级为可选，按需推进）
- ❌ ft-015 pdffigures2/Nougat（v1.x 候选）

## 关键设计决策（已 lock）

1. **同库不同前缀**：所有表用 `extract_*` / `interpret_*` / `render_*` 前缀，**不用 PG schema**（兼容 SQLite 切换）
2. **抽取器纯确定性**：不产 claim，不做语义。claim 留给解读器
3. **citation MVP**：仅存 bibkey + 标题 + 年份；arXiv id / DOI 反解延后
4. **数据层避免 PG-only**：`JSONField` 抽象 jsonb；禁用 `ArrayField` / `tsvector` 等 PG 专属

## 工作流分配

| 工作流 | 职责 | Dispatch |
|---|---|---|
| backend-extract | ft-019 抽取层重构 + 五类 model + CLI | dsp-001 ✅ |
| research | ft-022 单机 app packaging 决策文档 | dsp-002 ✅ |
| backend-extract | ft-015 DoclingExtractor + façade 改写 + 删除启发式 | dsp-003 |

## 验收

- `python manage.py extract_paper 2401.12345` 写入五类 material 到库（幂等）
- 既有 `run_subscription` 流程不破（解读器临时直读 `extract_*` 表）
- `docs/architecture/packaging.md` 完成，给出 Tauri 失败决策点清单
- 全量测试绿；新增测试覆盖搬迁后的 caption_extractor / pdf_chunker / figure_extractor

## 风险

- 搬迁过程 import 路径大量变更：用 `git mv` 保留 blame，最后统一改 import
- 抽取层引入新 app 需要 migrate；CI 数据库须重建一遍验证
- packaging 调研容易越界改代码：dispatch 明文禁止改 `apps/*`，只允许写 `docs/architecture/`

## 里程碑

- **W1**: ft-019 models + 搬迁 + 测试
- **W1**: ft-022 调研文档（并行）
- **W2**: ft-019 端到端 + 既有流程兼容 + merge
- **W2**: ft-022 文档评审 + 风险清单 sign-off

## 每日进展

_(按日追加)_
