---
pm_id: iter-006
pm_type: iteration
title: Sprint 6 — 渲染层（图谱抽象 + Excalidraw renderer）
milestone: v0.8
status: done
start_at: 2026-04-26
end_at: 2026-04-26
---

# iter-006 Sprint 6：渲染层

## 战略上下文

iter-004 抽取层 + iter-005 解读器 L1+L2 已闭环。本 sprint 完成三段中台的最后一段——**渲染层**。
然后转向 Electron 桌面化（v0.9–v1.2，预计 5 周）。

**2026-04-26 决策锁定**：
- 弃 tldraw / drawio，唯一 renderer 走 Excalidraw（+ SVG fallback）
- 桌面端**直上 Electron**（Tauri 弃用，理由：CLI 已通；Electron sidecar 模式社区最成熟）
- 自用阶段不签名

## 目标

| # | Feature | 优先级 | 状态 | 备注 |
|---|---|---|---|---|
| 1 | ft-021 图谱抽象层 + Excalidraw renderer + SVG fallback | P0 | in_progress | 主线 |

## Scope

- 新建 `apps/render/` Django app（label="render"，db_table 前缀 `render_*`）
- `PaperGraphModel` 抽象层（claim/figure/table/citation 节点 + supports/contradicts/cites/illustrates 边）
- `ExcalidrawRenderer` 输出 `.excalidraw` JSON
- `SvgRenderer` 输出兜底 `.svg`
- CLI：`python manage.py render_graph <arxiv_id>`
- counter_signal 不作为独立节点，作为 contradicts 边的注解

## Out of Scope

- ❌ 自动布局（dagre / elkjs，留 v1.x）
- ❌ tldraw / drawio renderer（永久弃用）
- ❌ 跨篇图谱
- ❌ 应用内编辑器嵌入（→ ft-024 前端 MVP）

## 关键设计决策（已 lock）

1. Excalidraw 作为唯一 renderer（drop tldraw / drawio）
2. counter_signal 简化为「contradicts」边注解，不做独立节点
3. 节点限定 4 类：claim / figure / table / citation；equation / section 不入图
4. 简单分层布局（claim 一行、evidence 一行、citation 一行），用户自己拖
5. SVG fallback 作为非 Excalidraw 场景兜底
6. 同库前缀 `render_*` + 全 JSONField

## 工作流分配

| 工作流 | 职责 | Dispatch |
|---|---|---|
| backend-render | ft-021 图谱抽象层 + Excalidraw / SVG 双 renderer | dsp-005 |

## 验收

- `render_graph leworldmodel` 产出 `media/render/leworldmodel/graph.excalidraw`，excalidraw.com 拖入显示正常
- 节点：claim 10 + figure ~5（被 cite 的）+ citation ~5（被 cite 的）
- 边色：supports 蓝 / illustrates 绿 / contradicts 红 / cites 灰
- ConvNeXt V2 同样跑通
- `--format svg` fallback 也通
- 全量 pytest 绿（不少于 184 + 新测试）
- ruff 通过

## 风险

- Excalidraw JSON schema 边界细节多（`boundElements` / `containerId` / `groupIds`）：参考官方 schema，先做 minimal viable JSON 再补特性
- 图片嵌入 `files` 字段是 base64 data URI：注意编码 + 大小（19 张 figure base64 后总 JSON 可能 >5MB，excalidraw 加载偶有卡顿）
- 节点 ID 设计：用 `claim:1` / `figure:3` 简写做 graph 内部 ID；Excalidraw 自身 ID 用 nanoid

## 里程碑

- W1 D1: models + migrations + Renderer Protocol + PaperGraphModel
- W1 D2-3: ExcalidrawRenderer 主体 + base64 image 嵌入 + 边样式
- W1 D4: SVG fallback + CLI + 测试
- W1 D5: 实战 leworldmodel + convnextv2 + 收尾

## 每日进展

_(按日追加)_
