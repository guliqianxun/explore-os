---
pm_id: iter-003
pm_type: iteration
title: Sprint 3 — 精读深度化（PDF + 图表 + 多模态）
milestone: v0.3
status: done
start_at: 2026-05-06
end_at: 2026-05-20
---

# iter-003 Sprint 3：精读深度化

## 目标
**让精读档真正有"精读"价值**——拉 PDF、提取图、挑框架图、用多模态 LLM 解读方法章节。
只对 Top-N 精读档执行（1–3 篇/天），成本可控。

## 前置依赖
iter-002 ft-008 / ft-009 已跑通（tier=deep 分档机制可用）

## Scope
- ft-011 arXiv PDF 拉取 + pymupdf4llm 章节拆分（method / exp / conclusion）
- ft-012 图像提取 + LLM 分类（architecture / result / ablation / …）+ 图索引 + qwen3.6-plus 多模态解读

## Out of Scope
- 历史数据回填 / 月半年回溯 → iter-004
- DB 持久化 → 仍延后（figures/papers 落盘即可）

## 关键设计决策
- 图像分类 **每张图都过 LLM**（用户要求），不走 Fig 1 启发式
- 图像按类型建索引（SQLite kv 或 JSON），为未来"本月所有 architecture 图"类需求铺路
- 多模态调用只对精读篇；预算上限走订阅级 `LLM_DAILY_BUDGET_CNY` 守门
- PDF 存 `media/papers/`，图 存 `media/figures/<arxiv_id>/`，全 gitignore

## 验收
1. 精读篇能拉到 PDF 并切出章节 JSON
2. 能提取 ≥3 张图，至少 1 张判为 `architecture`
3. 邮件精读块渲染内嵌图（CID attach）
4. 深度解读输出 4 段：method_summary / key_innovation / limitations / for_you
5. 视角切换对 for_you 段落措辞有可见影响
6. 单日总成本（LLM 含多模态）≤ 10 元
7. 所有 mock 测试通过；真实 PDF 测试脚本单独跑

## 里程碑
- **W1**: ft-011 PDF 拉取 + 章节拆分 + 缓存
- **W2**: ft-012 图像提取 + 分类 + 多模态解读 + 邮件内嵌 + 实战

## 风险
- pymupdf4llm 对非标准排版 PDF（双栏 / 图片密集）可能失败：降级 pymupdf
- 多模态成本波动大：每次运行前 dry-run 打印预估成本，超阈值需确认
- PDF 文件大：30MB cap，超则降级到"仅章节文本 + 无图"
- 内嵌 CID 图在部分邮件客户端（尤其手机 Gmail）渲染不稳：优先 base64 data-uri，再 CID 兜底
