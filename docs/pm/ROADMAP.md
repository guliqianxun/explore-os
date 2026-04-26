---
pm_id: roadmap
pm_type: roadmap
project: explore-os
version: v0.6-plan
updated_at: 2026-04-25
---

# explore-os Roadmap

## 项目定位

**订阅驱动的信息检索推送助手**。围绕用户声明的「兴趣」，按调度或主动请求完成：
Interest Rewrite → 多源抓取 → 去重过滤 → LLM 解读 → 分组渲染 → 多渠道推送。

信源可插拔，推送渠道可插拔。xingsuo 未来可作为一个 source 插件接入，**现阶段不复用其代码**，仅在 rewriter 思路上参考。

## 技术栈

Django + uv / Postgres / docker compose / React+Vite（MVP 不做）/ Navicat + Postman 测试。详见 `/CLAUDE.md`。

## 目标用户

- **P0 自用**：先跑通个人论文/工具日报流程。
- **P1 产品化**：多用户订阅。数据模型从 day 1 带 `user_id` 维度，MVP 实现先单用户。

## 核心设计约束

1. **Sources / Channels / Renderers 三解耦**，均为接口化插件。
2. **分组渲染**：订阅可挂多个来源；论文组 / 代码组 / 模型组等在推送里分区展示。MVP 虽只有论文组，渲染器从一开始按分组设计。
3. **状态全部落 Postgres**（订阅、推送历史、解读缓存、成本账本），不走 SQLite 过渡。
4. **成本受控**：每日预算上限，分档解读，命中缓存不重算。

## 里程碑

| 版本 | 目标 | 关键特性 | 预期 |
|------|------|----------|------|
| **v0.1 MVP (M1)** | 自用论文日报端到端 | arXiv + HF Papers / 最简 rewriter / TL;DR / 邮件 / Django CLI | 2026-05 |
| **v0.2 (M2)** | 注意力分层 | 综合分 rerank / 精读+略读分档 / 视角注入 / Daily Narrative | 2026-05 |
| **v0.3 (M3)** | 精读深度化 | arXiv PDF 拉取 / 图表提取+分类+多模态解读 / 精读档框架图 | 2026-05/06 |
| **v0.4 (M3.5)** | 时间线与回溯 | HF 历史回填 / Postgres 落库 / 月报+半年报 / 热度信号多源 | 2026-06/07 |
| **v0.5 (M4)** | DeliveryAdapter（多渠道**降级为可选**） | DeliveryAdapter 抽象 ✅ / 飞书 / 微信订阅号（按需） | 2026-05 |
| **v0.6 (M5)** | **抽取器素材索引层**（三段中台主线） | 五类 material（section/figure/table/equation/citation）/ 同库前缀 `extract_*` / 稳定 material_id | 2026-05/06 |
| **v0.7 (M6)** | **解读器 L1+L2** | claim 抽取 + evidence 映射（L1）/ 论文内反向信号扫描（L2）/ 强制 cite material_id | 2026-06/07 |
| **v0.8 (M7)** | **索引层闭环（图谱可视化 freeze）** | PaperGraphModel / `.excalidraw` / SVG 已落地，**实测可读性不及 HTML**；交互式可视化推迟到 Electron HTML 视图 | 2026-04/05 ✅ |
| **v0.9 (M8)** | **Electron 基础设施 + DRF API** | C1/C3/C5/C9 单机化清理 / EXPLORE_OS_DATA_DIR / DRF 包装 CLI / APScheduler in-process | 2026-05 |
| **v1.0 (M9)** | **Electron shell + Python sidecar** | electron-builder / PyInstaller Django / HTTP localhost / 端口与进程管理 | 2026-05 |
| **v1.1 (M10)** | **前端 MVP 4 页** | Vite+React+TS+Tailwind+shadcn/ui+Excalidraw 嵌入 / 论文列表 / 精读视图 / 订阅配置 / 抓取触发 | 2026-05/06 |
| **v1.2 (M11)** | **自动更新 + CUDA/CPU 双轨** | electron-updater / 双 PyInstaller spec（CUDA bundle 自用 + CPU bundle 分发接口）/ 不签名（自用阶段） | 2026-06 |
| **v1.x (M12+)** | 扩展方向 | 代码签名 / 公开分发 / xingsuo 作为 source / GitHub + HF Models 信源 / 跨篇图谱 | 待评估 |

## Features 索引

- [ft-001](features/ft-001.md) — 订阅配置 schema（interests + sources + delivery）
- [ft-002](features/ft-002.md) — Interest Rewriter（最简 LLM 翻译）✅
- [ft-003](features/ft-003.md) — Source: arXiv ✅
- [ft-004](features/ft-004.md) — Source: HF Papers ✅
- [ft-005](features/ft-005.md) — 推送去重 & 运行历史
- [ft-006](features/ft-006.md) — LLM TL;DR 解读 ✅
- [ft-007](features/ft-007.md) — Email 渲染与投递 + Django CLI ✅
- [ft-008](features/ft-008.md) — 综合分 rerank + 自适应 Top-N（iter-002）
- [ft-009](features/ft-009.md) — 精读/略读分档渲染 + 视角注入（iter-002）
- [ft-010](features/ft-010.md) — Daily Narrative 跨篇合成（iter-002）
- [ft-011](features/ft-011.md) — arXiv PDF 拉取 + 章节拆分 ✅
- [ft-012](features/ft-012.md) — 图表提取 + LLM 分类 + 多模态解读（superseded by ft-013）
- [ft-013](features/ft-013.md) — caption + bbox + 记忆线 ✅
- [ft-014](features/ft-014.md) — 略读升级（中文摘要+双图）+ 精读多图多表 ✅
- [ft-015](features/ft-015.md) — 学术 PDF 解析升级（Docling-based，**ft-019 启发式 baseline 替换**）
- [ft-016](features/ft-016.md) — DeliveryAdapter 抽象层 ✅
- [ft-017](features/ft-017.md) — 飞书 DeliveryAdapter
- [ft-018](features/ft-018.md) — 微信订阅号 DeliveryAdapter（按需，非主线）
- [ft-019](features/ft-019.md) — 抽取器素材索引层（v0.6 主线）
- [ft-020](features/ft-020.md) — 解读器 L1+L2（claim→evidence + 反向信号）
- [ft-021](features/ft-021.md) — 图谱抽象层 + Excalidraw renderer + SVG fallback
- [ft-022](features/ft-022.md) — Electron 基础设施清理 + DRF API（原 packaging 调研已 done，rpt-002）
- [ft-023](features/ft-023.md) — Electron shell + Python sidecar + PyInstaller Django
- [ft-024](features/ft-024.md) — 前端 MVP 4 页（Vite+React+TS+Tailwind+shadcn/ui+Excalidraw）
- [ft-025](features/ft-025.md) — 自动更新 + CUDA/CPU 双轨打包
- [ft-026](features/ft-026.md) — 前端编辑/杂志重设计（Editorial）+ CORS 修复

## 当前迭代

- [iter-001](iterations/iter-001.md) — MVP Sprint 1（ft-002/003/004/006/007 已完成；ft-001/005 DB 落库延后）
- [iter-002](iterations/iter-002.md) — Sprint 2：注意力分层（ft-008/009/010）✅
- [iter-003](iterations/iter-003.md) — Sprint 3：精读深度化（ft-011/012）✅
- [iter-004](iterations/iter-004.md) — Sprint 4：三段中台（ft-019 + ft-022 + ft-015 ✅）
- [iter-005](iterations/iter-005.md) — Sprint 5：解读器 L1+L2 生产侧（ft-020 ✅）
- [iter-006](iterations/iter-006.md) — Sprint 6：渲染层（ft-021 ✅ freeze；图谱可视化推迟到 v1.x，索引层数据建立完成）
- [iter-007](iterations/iter-007.md) — Sprint 7：Electron 基础设施 + DRF API（ft-022 ✅）
- [iter-008](iterations/iter-008.md) — Sprint 8：Electron shell + Python sidecar（ft-023 ✅）
- [iter-009](iterations/iter-009.md) — Sprint 9：前端 MVP 4 页（ft-024 ✅）
- [iter-010](iterations/iter-010.md) — Sprint 10：编辑/杂志重设计（ft-026）

## 战略转向（2026-04-25）

商业化暂缓，重心从「多渠道推送」转向「**论文理解中台**」三段拆分：

```
内容抽取器 → 解读器 → 渲染器
（确定性素材） （L1+L2 逻辑+反向信号） （Excalidraw 图谱 + 速读卡片）
```

长期形态：**Electron 桌面 app**（2026-04-26 锁定，弃 Tauri），Django 作为 Python sidecar，DB 切到 SQLite。
v0.5 多渠道降级为可选，飞书/微信订阅号按需推进。

## 桌面端决策（2026-04-26 锁定 / 二次修订）

- **直上 Electron**：Tauri 弃用。理由：CLI 已通；Electron sidecar 模式社区最成熟；前端栈灵活
- **前端栈**：Vite + React + TypeScript + Tailwind + shadcn/ui + KaTeX（公式真渲染）+ Zustand
- **图谱可视化退到 v1.x**：v0.8 cluster cards 实测可读性不及 HTML 邮件渲染。Excalidraw 静态格式无折叠 / 无交叉跳转 / 无 KaTeX；这些 HTML 自然支持。**Excalidraw 嵌入从 ft-024 移除**
- **索引层（extract + interpret）才是基础**：5 类 material + claims + counter_signals 已实战验证产出可用，是后续视图的真正资产
- **自用阶段不签名**：跳过 Apple Dev / Windows EV cert（约省 1.5 周 + 钱）；公开分发延后到 v1.x
- **CUDA / CPU 双轨**：v1.2 ft-025 落两套 PyInstaller spec；自用走 CUDA bundle，CPU bundle 留接口待分发

## 未决议题

1. **rewriter 的调用粒度**：全局一次还是按 source 一次？MVP 先全局一次，v0.3 按源定制。
2. **xingsuo 集成形态**：真要接时再定（HTTP / package / 共享数据层），现阶段不设计。
3. **调度**：MVP 外部 cron。桌面端切换到 in-process scheduler（APScheduler 候选），v1.0 packaging 时定。
4. **解读器 L2 的开放批判边界**：当前严格禁止引用论文外 prior work，仅扫描论文内反向信号；待 L1+L2 跑稳后重审。
