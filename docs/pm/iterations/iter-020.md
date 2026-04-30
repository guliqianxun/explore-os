---
pm_id: iter-020
pm_type: iteration
title: Sprint 20 — 首位用户实测 + UX polish + 订阅闭环
milestone: v1.2
status: done
start_at: 2026-04-29
end_at: 2026-04-30
---

# iter-020 Sprint 20：First-user trial + UX polish

## 战略上下文

iter-019 收尾「v1.2 重构 + ft-034」标记 done。但**实际只在 dev 模式（Vite
HMR）跑过**，从未在 Electron prod-mode（loadFile file://）真启过——首位
用户开 .exe 看到整页空白。

同期用户提了一连串 UX 反馈：

1. blank window（首先就看不到内容）
2. 摘要太长堆视野，要"墙报式"图文绕排
3. keywords 想分作者/AI 两层
4. 订阅配置后跑完没在 feed 里看到 paper
5. 想要外链 arxiv 网页 + PDF 下载

把这些放一起做：是「**首位用户 onboarding**」的最短闭环，不是 ft-030 Library
那种 v1.3 大刀。

## 目标

| # | 内容 | 状态 |
|---|---|---|
| 1 | Electron prod-mode 真启 fix（HashRouter） | ✅ done |
| 2 | paper.keywords 字段 + PATCH endpoint + 编辑器 UI | ✅ done |
| 3 | 卡片墙报式 + 信息密度（精读 / 速度两层） | ✅ done |
| 4 | 订阅 → Paper feed 桥（legacy run_subscription 落库） | ✅ done |
| 5 | 外链 arXiv ↗ + PDF ↓ via shell.openExternal | ✅ done |
| 6 | 首位用户实测两条订阅闭环 | ✅ done（precip + video-gen 14 篇 paper） |

## 落地（按 commit）

| commit | 内容 |
|---|---|
| `8175407` | fix: BrowserRouter → HashRouter（prod-mode 真启的 blank 真因） |
| `76b1525` | feat: paper.keywords 字段 + 墙报式 card + 3-tab meta + brief_keywords DTO |
| `beaf18b` | chore: socksio 进 pyproject（dev 机 SOCKS 代理 ImportError） |
| `36b37a0` | feat: paper.keywords PATCH endpoint + KeywordsEditor 组件 + SpeedReadView 挂载 |
| `9135183` | feat: subscription_persist 桥（legacy → Paper+PaperBrief）+ run_subscription --days/--no-persist + conftest 隔离 |
| `d24562b` | feat: brief_keywords fallback + 速度卡升级（不截断 abstract，不展示 LLM 翻译版 keywords）+ 中文翻译 toggle 翻向回正 |
| `2d4c6bf` | feat: 外链 arXiv ↗ + PDF ↓ via shell.openExternal |

## 首位用户实测结果

- 配置：`subscriptions.yaml` 两条 enable（deliveries=[]）：
  - `precip-nowcasting` 降水短临预报（physics.ao-ph + cs.LG，30 天窗口）
  - `video-generation` 视频生成（cs.CV + cs.LG + cs.MM，7 天窗口）
- 跑 `run_subscription <name> --no-deep --days N`：
  - precip 2 篇（30 天窗口找到 2 个高匹配度 paper）
  - video-gen 12 篇（7 天窗口）
  - 共 14 篇落 Paper + PaperBrief，耗时 ~70s
- UI：
  - 4 篇手动置 `reading` → 主要论文区（墙报式精读卡，含 figure float + 3 tab）
  - 11 篇 `new` → 速读区（速度卡：title + chips + 原文 abstract + 中文 toggle）
  - 每张卡 arxiv ID 旁有 `arXiv ↗ / PDF ↓` 按钮
- AI Summary tab 点开能看 method_summary_zh / key_innovation / for_you
- 用户反馈："初步满意了"

## 决策 / 偏离

- **「订阅=快粗，detail=慢精」分层意图锁定**（写入
  `memory/subscription_speed_vs_precision.md`）：订阅链不强制 docling，detail
  页按需触发；任何把 docling 塞进订阅链的方案都违反意图
- **paper.keywords vs brief.keywords 双源**：作者上传 vs LLM 抽分别字段，前
  端 fallback；速度卡只显示 paper.keywords（不展示 LLM 翻译版）
- **legacy email 链留着**：subscription_persist 是「桥」不是替代；email
  pipeline 仍可用，trial 阶段 deliveries=[] 跳过即可
- **conftest.py 加 autouse fixture**：把 SUBSCRIPTIONS_YAML 默认指到
  tmp_path，防真 yaml 漏进 perspective fixture

## 验收

| 项 | 标准 | 实测 |
|---|---|---|
| pytest | ≥ 371 | 371 passed（基线持平） |
| tsc | 0 error | ✓（frontend + electron 都过） |
| build 主 chunk | ≤ 基线 +50KB | 642 KB (+5KB) |
| Electron prod-mode 启动 | 不 blank | ✓ |
| 首位用户配置 → 跑 → 看到 paper | 闭环 | ✓ |

## 下一刀（v1.3 候选）

- **detail 页 lazy docling**：detect 没 extract 数据 → enqueue extract 链 →
  完成后 Reading Station 自动可用
- **ft-030 Library + FTS5**：v1.3 第一刀（推迟）
- **ft-031 桌面通知 + brief 未决分组**
- **ft-025 自动更新 + CUDA/CPU 双轨打包**

## 风险后顾

- ✅ Electron prod-mode 实测覆盖：iter-019 的死角已补
- ✅ 订阅 yaml 不再做 perspective fixture 污染（conftest 隔离）
- 🟡 paper.keywords 现在没人自动填（订阅 paper 都空）；需要后续 ingest 时机
  补上、或 DETAIL 页编辑成为常态
- 🟡 socksio 是 dev 机配置依赖，packaged build 上没影响（PyInstaller 不读
  ALL_PROXY）—— pyproject 加上是 dev 体验稳定
