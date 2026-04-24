# Changelog

## [Unreleased]

### 2026-04-24 (later)
- Django 骨架 + docker compose + uv 初始化。
- `sources/base.py` 定义 SourceFetcher 接口契约。
- **ft-003 完成**：ArxivFetcher 实现 + 10 tests（worktree 并行开发，merge 回 main）。
- **ft-004 完成**：HFPapersFetcher 实现 + 11 tests（worktree 并行开发，merge 回 main）。
- 整套 21 tests 全部通过；跨源 dedup_key 对齐（两源对同一 arxiv paper 产出相同 key）。

### 2026-04-24
- 立项头脑风暴，方向聚焦 MVP：订阅驱动的论文日报。
- 锁定技术栈：Django + uv / Postgres / docker compose / React+Vite（MVP 不做）/ Navicat + Postman 测试。
- 确定 MVP 信源：**arXiv + HF Papers**；GitHub / HF Models 推到 v0.2。
- Rewriter MVP 做最简 LLM 翻译版；v0.3 按 source 定制。
- xingsuo **不做代码复用**，仅 rewriter 思路参考；未来作为一个 source 插件接入。
- 落地文档：ROADMAP / ft-001~ft-007 / iter-001 / CLAUDE.md。
