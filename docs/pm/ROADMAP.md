---
pm_id: roadmap
pm_type: roadmap
project: explore-os
version: v1.2-plan
updated_at: 2026-04-29
---

# explore-os Roadmap

## 项目定位

**订阅驱动的信息检索推送助手**。围绕用户声明的「兴趣」，按调度或主动请求完成：
Interest Rewrite → 多源抓取 → 去重过滤 → LLM 解读 → 分组渲染 → 多渠道推送。

信源可插拔，推送渠道可插拔。xingsuo 未来可作为一个 source 插件接入，**现阶段不复用其代码**，仅在 rewriter 思路上参考。

## 技术栈

Django + uv / **SQLite**（桌面 app 长期形态，2026-04-28 弃 PG）/ React + Vite + TS + Tailwind + shadcn/ui / Electron + PyInstaller。详见 `/CLAUDE.md`。

## 目标用户

- **P0 自用**：先跑通个人论文/工具日报流程。
- **P1 产品化**：多用户订阅。数据模型从 day 1 带 `user_id` 维度，MVP 实现先单用户。

## 核心设计约束

1. **Sources / Channels / Renderers 三解耦**，均为接口化插件。
2. **分组渲染**：订阅可挂多个来源；论文组 / 代码组 / 模型组等在推送里分区展示。MVP 虽只有论文组，渲染器从一开始按分组设计。
3. **状态全部落 SQLite**（订阅、推送历史、解读缓存、成本账本）。同库不同前缀（`extract_*` / `interpret_*` / `render_*` / `papers_*` / `papers_user_*`），桌面 app 单文件 DB 不依赖外部服务。~~原计划用 Postgres + docker compose，2026-04-28 决策切 SQLite~~
4. **成本受控**：每日预算上限，分档解读，命中缓存不重算。

## 里程碑

| 版本 | 目标 | 关键特性 | 预期 |
|------|------|----------|------|
| **v0.1 MVP (M1)** | 自用论文日报端到端 | arXiv + HF Papers / 最简 rewriter / TL;DR / 邮件 / Django CLI | 2026-05 |
| **v0.2 (M2)** | 注意力分层 | 综合分 rerank / 精读+略读分档 / 视角注入 / Daily Narrative | 2026-05 |
| **v0.3 (M3)** | 精读深度化 | arXiv PDF 拉取 / 图表提取+分类+多模态解读 / 精读档框架图 | 2026-05/06 |
| **v0.4 (M3.5)** | 时间线与回溯 | HF 历史回填 / DB 落库（PG → 后切 SQLite）/ 月报+半年报 / 热度信号多源 | 2026-06/07 |
| **v0.5 (M4)** | DeliveryAdapter（多渠道**降级为可选**） | DeliveryAdapter 抽象 ✅ / 飞书 / 微信订阅号（按需） | 2026-05 |
| **v0.6 (M5)** | **抽取器素材索引层**（三段中台主线） | 五类 material（section/figure/table/equation/citation）/ 同库前缀 `extract_*` / 稳定 material_id | 2026-05/06 |
| **v0.7 (M6)** | **解读器 L1+L2** | claim 抽取 + evidence 映射（L1）/ 论文内反向信号扫描（L2）/ 强制 cite material_id | 2026-06/07 |
| **v0.8 (M7)** | **索引层闭环（图谱可视化 freeze）** | PaperGraphModel / `.excalidraw` / SVG 已落地，**实测可读性不及 HTML**；交互式可视化推迟到 Electron HTML 视图 | 2026-04/05 ✅ |
| **v0.9 (M8)** | **Electron 基础设施 + DRF API** | C1/C3/C5/C9 单机化清理 / EXPLORE_OS_DATA_DIR / DRF 包装 CLI / APScheduler in-process | 2026-05 |
| **v1.0 (M9)** | **Electron shell + Python sidecar** | electron-builder / PyInstaller Django / HTTP localhost / 端口与进程管理 | 2026-05 |
| **v1.1 (M10)** | **前端 MVP + Editorial 重设计** | 4 页 → 编辑/杂志重设计 → Subscription 表单化 + Ingest（PDF/arxiv/URL）| 2026-05/06 ✅ ft-024/026/027 |
| **v1.2 (M11)** | **用户层（A 进 B 出）+ 重构收尾** | Paper-centric schema ✅ / Inbox verdict ✅ / Reading Station ✅ / Brief 内容层 ✅ / **代码 review + 解耦重构（iter-019）+ ft-034 services 接口规整** | 2026-05 |
| **v1.3 (M12)** | **Library + FTS5 + Zotero export + PC 便携版** | ft-030（FTS5 收编 typeahead/Library/backlink 单引擎）+ Zotero `.bib + pdf` 导出 + ft-037（portable + data_dir 用户可配）| 2026-05/06 |
| **v1.4 (M13)** | **chat 分级 + user_profile 蒸馏** | α 蒸馏层（ft-035）/ 按记忆层分级 chat（fresh / sustained / archived）/ with-memory 是系统第一逻辑 | 2026-06/07 |
| **v1.5 (M14)** | **分发：自动更新 + CUDA/CPU 双轨** | electron-updater / 双 PyInstaller spec / 不签名（自用阶段）| 2026-07/08 |
| **v1.x (M15+)** | 扩展方向 | 代码签名 / 公开分发 / xingsuo 作为 source / GitHub + HF Models 信源 | 待评估 |

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
- [ft-026](features/ft-026.md) — 前端编辑/杂志重设计（Editorial）+ CORS 修复 ✅
- [ft-027](features/ft-027.md) — Subscription 表单化 + RunPage → Ingest（PDF/arxiv/URL）
- [ft-028](features/ft-028.md) — Paper-centric schema + user_* 层 + Inbox verdict UI ✅
- [ft-029](features/ft-029.md) — Reading Station：3 栏 + pdf.js 内嵌 + ClaimCard 引文展开 + notes/tag/backlink
- [ft-030](features/ft-030.md) — Library + FTS5 全文搜索 + Zotero export
- [ft-031](features/ft-031.md) — 桌面通知 + brief 未决分组
- [ft-032](features/ft-032.md) — ClaimCard 用户修订层（user_claim_edit override）
- [ft-033](features/ft-033.md) — Brief 内容处理层（PaperBrief：abstract_zh / keywords / tldr / for_you 复用老邮件 pipeline）✅
- [ft-034](features/ft-034.md) — services 接口规整：apps/llm 中台层 + 跨段解耦 7 条 P0 ✅
- [ft-036](features/ft-036.md) — First-user trial polish：HashRouter fix + 墙报式卡 + paper.keywords + 订阅桥 + 外链 ✅

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
- [iter-010](iterations/iter-010.md) — Sprint 10：编辑/杂志重设计（ft-026 ✅）
- [iter-011](iterations/iter-011.md) — Sprint 11：Subscription 表单化 + Ingest（ft-027 ✅）
- [iter-012](iterations/iter-012.md) — Sprint 12：Paper-centric schema + Inbox verdict（ft-028 ✅）
- [iter-013](iterations/iter-013.md) — Sprint 13：Reading Station + ClaimCard 引文展开（ft-029）
- [iter-014](iterations/iter-014.md) — Sprint 14：Library + FTS5 + Zotero export（ft-030）
- [iter-015](iterations/iter-015.md) — Sprint 15：桌面通知 + brief 未决分组（ft-031，已被 iter-021 承接）
- [iter-016](iterations/iter-016.md) — Sprint 16：自动更新 + CUDA/CPU 双轨（ft-025）
- [iter-017](iterations/iter-017.md) — Sprint 17：ClaimCard 用户修订层（ft-032，紧跟 ft-029 实测后启动）
- [iter-018](iterations/iter-018.md) — Sprint 18：Brief 内容处理层（ft-033，复用老邮件 pipeline）✅
- [iter-019](iterations/iter-019.md) — Sprint 19：代码 review + 解耦重构（v1.2 收尾，6 组并行 review → 修复 → ft-034）✅
- [iter-020](iterations/iter-020.md) — Sprint 20：First-user trial polish（ft-036 ✅）
- [iter-021](iterations/iter-021.md) — Sprint 21：桌面通知 + brief 未决分组（ft-031）

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

## 两条路：解读 vs 解压（2026-04-29 lock）

ft-033 落地后明确：项目内 LLM 调用走两条独立路径，**用户体验上是漏斗，架构上互不阻塞**。

| 维度 | **信息解压**（ft-019/020 抽取层） | **解读**（ft-033 brief 层） |
|---|---|---|
| 数据来源 | docling parse PDF | 复用解压层 abstract + sections + figures |
| LLM 调用风格 | 多次结构化（claim 逐条 + evidence 逐条） | 一锅端（skim_interpret + deep_interpret_rich） |
| 产出颗粒度 | material_id / claim_id / evidence_id（细） | paper 级整体叙事（粗） |
| DB 层 | `extract_*` + `interpret_*` 表 | `papers_brief` 表 |
| 服务于 | PaperDetail ClaimCard 引文展开 / 跳 PDF 锚点 / 跨引联动 / 图谱 | BriefView list 卡片 / SpeedReadView 顶置块 |
| 用户场景 | "这个 claim 的证据是什么" | "这篇值不值得花时间读" |

**用户旅程漏斗**：

```
brief 列表（解读）→ 速读模式（解读 + 解压并列）→ Reading Station（解压主导 + PDF 求证）
"读不读"           "怎么个流程"                     "证据在哪"
```

**不硬合并的理由**：LLM 调用风格相反（narrative vs structured）；失败可分离；缓存策略不同；用户编辑层不同（ft-032 改 claim / brief 改 perspective）。

**接合点**（已存在 / 可加强）：
- 已存在：`deep_interpret_rich` 的 prompt 让 LLM 在 method_summary 里写 `[Fig. 1]` 锚点
- 已存在：BriefSection + ClaimCard 速读 + figure gallery 在 SpeedReadView 同页共存
- v1.3+ 候选：`key_innovation` bullets 挂 claim_id；brief `[Fig. N]` 锚点点击跳 figure；ReadingStation SpeedCardPane 露 brief 入口

## Chat 分级 + with-memory 第一逻辑（2026-04-29 lock，落地 v1.4）

未来 chat agent 的边界：

- **Chat with single PDF won't do** — ChatPDF / SciSpace 红海，与 ClaimCard 结构化范式冲突
- **Chat with my memory will do** — 跨库的 user-aware assistant，竞品做不到（无本地全库 + 用户行为）
- **with-memory 是系统第一逻辑** — 每次 chat 启动第一步永远是检索本地记忆库 + 注入 user_profile，不是直接调用外部 LLM 通用知识

**分级（按记忆层 — 方向乙）**：

| 层 | 范围 | 触发条件 |
|---|---|---|
| **L1 fresh** | 最近 N 天 / N 篇 paper + 当前 brief | 用户日常追新 |
| **L2 sustained** | user_profile 蒸馏出的稳定偏好 | 跨周 / 跨月话题 |
| **L3 archived** | 全库 + 时间维度 + tag/backlink 网络 | 回溯式提问（"我对 X 的看法演变"）|

**当前阶段（v1.2/v1.3）只保操作历史种子**——既有 `papers_user_*`（status / tag / comment / backlink）+ `papers_brief.for_you`。不新增 user_event 检索日志表（4/29 PM lock）。具体 chat UI / 蒸馏算法 / tool schema 都推到 v1.4，届时再设计。

## Out of Scope / Won't Do（2026-04-28 竞品分析后锁定）

经过竞品象限分析（A1 订阅推送 / A2 探索式检索 / A3 引文图谱 / B1 archival / B2 PDF 标注 / B3 chat / B4 双链 / B5 综述生成），识别出与已有强势竞品高度重叠且**复制无价值**的方向，正式从 backlog 排除：

| 不做 | 替代方案 | 排除理由 |
|---|---|---|
| **引文图谱可视化** | Connected Papers / ResearchRabbit / Litmaps（免费）| 竞品成熟，且与 explore-os "深读单篇 + 沉淀" 主线无协同 |
| **PDF 高亮 / margin note 标注** | readest（一键导出逃生口）/ Hypothesis | 与 ft-028 锁定的"对照型 viewer"范式冲突；标注层走 user_comment / user_tag / user_backlink 挂 paper |
| **Chat with PDF** | ChatPDF / SciSpace Copilot / Humata | 红海；与 ClaimCard 结构化范式冲突（信息密度高于 chat） |
| **文献 archival / citation 库** | **Zotero**（一键导出 .bib + pdf 是逃生口） | 不重造 Zotero 的同步 / collections / citation style 体系 |
| **通用知识管理双链 / wiki-link 语法** | Obsidian / Logseq | ft-029 backlink 仅做 paper 颗粒度，不引入 `[[wiki]]` 语法（claim 级 backlink 也延后/不做）|
| **沉淀库内自然语言问答** | Elicit（外部）/ 等 ft-030 FTS5 实测 | v1.3+ 观望，先看 FTS5 是否够用 |
| **跨设备云同步** | （v2.x 再说）| 桌面单机自用优先，不引入云依赖 |

**保留但延后**：
- ft-017 飞书 / ft-018 微信订阅号 IM Adapter — 状态 deferred 维持，"不在电脑前"场景的兜底。

## 未决议题

1. **rewriter 的调用粒度**：全局一次还是按 source 一次？MVP 先全局一次，v0.3 按源定制。
2. **xingsuo 集成形态**：真要接时再定（HTTP / package / 共享数据层），现阶段不设计。
3. **调度**：MVP 外部 cron。桌面端切换到 in-process scheduler（APScheduler 候选），v1.0 packaging 时定。
4. **解读器 L2 的开放批判边界**：当前严格禁止引用论文外 prior work，仅扫描论文内反向信号；待 L1+L2 跑稳后重审。
