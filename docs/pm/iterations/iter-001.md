---
pm_id: iter-001
pm_type: iteration
title: MVP Sprint 1 — 端到端打通
milestone: v0.1
status: planned
start_at: 2026-04-25
end_at: 2026-05-15
---

# iter-001 MVP Sprint 1

## 目标
**一条 CLI，跑通「interests → rewriter → arXiv + HF Papers 抓取 → 去重 → TL;DR → 邮件投递」端到端链路。**
验收场景：自己的 "diffusion + flow matching" 订阅，每天早上收到一封邮件。

## Scope
- ft-001 订阅配置（YAML + DB + 最小 REST）
- ft-002 Rewriter 最简实现 + 缓存
- ft-003 arXiv fetcher
- ft-004 HF Papers fetcher
- ft-005 去重表 + 运行历史
- ft-006 TL;DR 解读 + 缓存 + 预算守门
- ft-007 HTML 邮件渲染 + SMTP 投递 + CLI + 最小 HTTP 触发

## Out of Scope
- 深度解读、飞书、HF Models、GitHub 源、embedding 相关性、Web 前端、多用户、rewriter 按源定制

## 工程里程碑
1. **W1 基础设施**：Django 项目骨架（按领域切 app：`subscriptions / sources / interpret / delivery`）/ Postgres docker compose / uv / Navicat 连通。
2. **W2 数据链路**：ft-001 + ft-003 + ft-004 + ft-005，CLI 能抓到并落库去重，不含 LLM/邮件。
3. **W3 解读与推送**：ft-002 + ft-006 + ft-007，端到端发出第一封真实邮件。

## 风险
- arXiv/HF API 稳定性，第一天先 spike。
- SMTP 凭据（Gmail/Outlook/企业邮）踩坑，预留 0.5 天。
- Rewriter prompt 质量，预留 1 天迭代。

## 验收
见 ft-007 验收 1–5，全部通过即 Sprint 关闭。
