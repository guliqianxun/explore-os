# Changelog

## [Unreleased]

### 2026-04-25 (latest) — iter-003 Sprint 3 完成
- **ft-011** arXiv PDF 拉取 + pymupdf4llm 章节切分（intro/method/experiments/conclusion，
  按桶字符上限截断）；本地缓存 + JSON 缓存。
- **ft-012** 图表提取 + 多模态分类 + 多模态深度解读：
  - figure_extractor: pymupdf 抽图 + sha1 去重 + 上限 15 张 + 临近 caption 抓取
  - figure_classifier: qwen-vl-plus 7 类标签（architecture/result_figure/...），timeout 120s
  - deep_interpret_rich: method 文本 + 架构图（若有）+ qwen3.6-plus 产出
    method_summary / key_innovation / limitations / for_you 四段，timeout 180s
  - email_sender: 支持 inline_images CID 内嵌 PNG/JPEG
- 全量 80 tests 通过。
- 实战 video-generation-daily / researcher 视角：
  Top-1 UniT 论文，PDF 拉到 15 图，深度解读输出"视觉锚定+双向互重建"等
  3 条精准创新点 + 3 条限制 + 个性化建议。邮件投递 OK。

### 2026-04-25 (later) — iter-002 Sprint 2 完成
- **ft-008** 综合分 rerank：embedding (text-embedding-v3) 余弦相关性 + HF upvotes 热度，
  权重 0.3/0.7；自适应分档（≥0.75 为 deep，保底 1，上限 3）。
- **ft-009** 分档渲染 + 视角注入：
  - interpret/interpretation.py：skim（LLM 一句话 + 关键词，视角前缀）
    + deep（iter-002 仅透传 abstract + 占位符）
  - 4 个内置视角 preset（researcher / engineer / pm / student），custom 优先
  - email_renderer 重写：narrative 块 + 精读卡 + 略读卡 + 索引编号
- **ft-010** Daily Narrative：LLM 读全部 skim 产 hero_sentence + bullets + note_for_you，
  失败降级不渲染。
- 实战：video-generation-daily + `perspective.preset=researcher`，
  9 篇 → 1 精读 + 8 略读，narrative 精准聚类 4 个主题并点名阅读建议，
  邮件发 Gmail OK。
- 全量 55 tests 通过。

### 2026-04-25
- **Phase B 打通**：ft-002（rewriter）+ ft-006（TL;DR）+ ft-007（email+CLI）一次性实现。
- 新增模块：`interpret/llm.py` `rewriter.py` `tldr.py` / `delivery/email_renderer.py` `email_sender.py` /
  `subscriptions/loader.py` + `run_subscription` management command。
- LLM 走阿里百炼 DashScope OpenAI 兼容端点，文本 `deepseek-v4-flash`、多模态预留 `qwen3.6-plus`。
- Email 走企业微信邮箱 SSL 465（非 Gmail TLS 587），`settings.py` 加 `EMAIL_USE_SSL` 字段。
- **实战验证**："video generation" 订阅：rewriter 产出布尔查询，arXiv + HF 共 9 条 TL;DR，
  真实发到 Gmail 收件箱 OK。
- MVP 阶段状态仍在内存，未走 DB（ft-001 / ft-005 完整版留待下一步）。

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
