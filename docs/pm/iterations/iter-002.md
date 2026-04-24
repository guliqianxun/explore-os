---
pm_id: iter-002
pm_type: iteration
title: Sprint 2 — 注意力分层（邮件形态改造）
milestone: v0.2
status: done
start_at: 2026-04-25
end_at: 2026-05-05
---

# iter-002 Sprint 2：注意力分层

## 目标
**把日报从"平铺论文清单"升级为"精读 + 略读 + 叙事" 三层结构。**
本迭代不涉及 PDF / 多模态 / DB，纯在现有 fetcher 输出上加 rerank + 分档 + 视角 + 跨篇合成。
精读档在本迭代只展示"原文 abstract + 占位深度解读"，iter-003 再填实。

## Scope
- ft-008 综合分 rerank（embedding relevance + HF upvote hotness，0.3/0.7 权重）+ 自适应 Top-N（阈值 0.75，保底 1，上限 3）
- ft-009 精读 / 略读分档渲染 + 视角注入（`perspective.preset` / `custom`）
- ft-010 Daily Narrative

## Out of Scope
- PDF / 图表 / 多模态 → iter-003
- 热度历史回填 / 月半年回溯 → iter-004
- DB 持久化（订阅、推送历史、成本）→ 仍延后

## 关键设计决策
- 综合分 = 0.3×relevance + 0.7×hotness（用户选择偏热度，高热带拉力）
- hotness MVP 只用 HF upvotes；跨源命中 +0.1；arXiv 无信号给 0.1 底
- 精读档不放 one_liner；略读档只放 one_liner
- 精读档"原文摘要"字段原样展示 abstract，不做 LLM 改写
- 视角作用在所有 LLM 步骤：rewriter / skim / deep / narrative

## 验收
1. video-generation-daily 订阅加 `perspective.preset=researcher`，`run_subscription` 产出邮件：
   - 顶部 Daily Narrative 2–3 句
   - 精读档 1–3 篇（综合分 ≥0.75 或保底 1）
   - 略读档其余，按分降序
2. 略读档每条只有 one_liner + keywords
3. 精读档有 abstract 原文 + 占位"深度解读（iter-003 填）"提示
4. 视角切到 `engineer` 后，相同论文的 skim/deep 措辞能看出差异（人工验）
5. 关键日志能看到每篇 paper 的 relevance / hotness / total 三分数
6. 所有 mock 测试通过（不打真 LLM）
7. 实战跑 video-generation-daily 真邮件，人工 review 邮件结构和视角效果

## 里程碑
- **W1**: ft-008 rerank + 分档（含 embedding 客户端 + ranker + 测试）
- **W2**: ft-009 分档渲染 + 视角注入 + ft-010 Daily Narrative + 实战

## 风险
- embedding 调用失败率（阿里百炼端点稳定性）：内置降级到 relevance=0.5
- 视角 prompt 调优需要多轮，预留 1 天迭代
