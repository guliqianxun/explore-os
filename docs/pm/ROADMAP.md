---
pm_id: roadmap
pm_type: roadmap
project: explore-os
version: v0.2-plan
updated_at: 2026-04-24
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
| **v0.5 (M3.7)** | 渠道与源扩展（原 v0.2 内容延后） | HF Models / GitHub / 飞书 / HTTP 触发 | 2026-07 |
| **v1.0 (M4)** | 产品化基线 | 多用户 / Web 配置面板（React+Vite）/ 用量计费骨架 | 2026-09 |
| **v1.x (M5+)** | 扩展方向 | xingsuo 作为 source / 商业动态信源 / 公众号知乎半自动发文 | 待评估 |

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
- [ft-012](features/ft-012.md) — 图表提取 + LLM 分类 + 多模态解读 ✅

## 当前迭代

- [iter-001](iterations/iter-001.md) — MVP Sprint 1（ft-002/003/004/006/007 已完成；ft-001/005 DB 落库延后）
- [iter-002](iterations/iter-002.md) — Sprint 2：注意力分层（ft-008/009/010）✅
- [iter-003](iterations/iter-003.md) — Sprint 3：精读深度化（ft-011/012）✅

## 未决议题

1. **rewriter 的调用粒度**：全局一次还是按 source 一次？MVP 先全局一次，v0.3 按源定制。
2. **Django 项目布局**：单 app 还是按领域切 app（subscriptions / sources / delivery）？倾向后者。
3. **xingsuo 集成形态**：真要接时再定（HTTP / package / 共享数据层），现阶段不设计。
4. **调度**：MVP 外部 cron。v0.2 决定是否内置 Celery beat / Django-Q。
