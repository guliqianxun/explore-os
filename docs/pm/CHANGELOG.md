# Changelog

## [Unreleased]

### 2026-04-25 (latest+4) — ft-016 DeliveryAdapter 抽象层
- **方向调整**：工具核心 = 内容生产；推送渠道作为可插拔 adapter。
  后续主推 微信订阅号 + 飞书 + 邮件 三渠道并存。
- delivery/base.py 定义 Digest / DeliveryTarget / DeliveryResult /
  DeliveryAdapter Protocol + REGISTRY（同 SourceFetcher 模式）。
- delivery/adapters/email.py: 现有 email 投递迁入，实现 EmailAdapter。
- delivery/adapters/feishu.py: stub（ft-017 planned）。
- delivery/adapters/wechat_subscription.py: stub（ft-018 planned）。
- run_subscription 改为通过 REGISTRY 路由 d.channel → adapter.deliver()，
  原 SMTP 直调代码删除。
- delivery/email_renderer.py / email_sender.py 保留为 thin wrapper 重导出。
- 12 new tests（base 6 + email_adapter 6）；全量 118 passing。
- ROADMAP v0.5 重新定位为"多渠道"；GitHub/HF Models/月报推到 v0.6+。

### 2026-04-25 (latest+3) — 4 个 bug 修 + ft-015 调研记录
- **picker**: Fig 1 优先 + 关键词加持。CS 论文 Fig 1 ≈ teaser/architecture
  默认胜出；只在 Fig 1 caption 明显是定性结果时跳过走关键词。
- **HF ±1d 容差**: HF dailypapers 收录日 ≠ arxiv 提交日；hf_* 源放宽
  到 [target-1, target+2)。in_window 从 0 → 2。
- **CID 跨论文唯一**（关键修）: inline_images key 用 {arxiv_id}__name 命名，
  消除 3 篇论文共用同 cid 导致的"图反复应用"。
- **bbox 多策略**:
  - kind=table 优先 page.find_tables() 取最近表格 bbox
  - figure ink 候选空时 → text-blocks 聚合兜底
  - 渲染后空白检测（color_topusage > 99.9% 视为空白丢弃）
  - 实战 8/9 命中（89%）
- **ft-015 planned**: 启发式覆盖率达天花板 ~85-95%，记录 pdffigures2 / Nougat
  候选作为升级路径，等数据决定何时启动。

### 2026-04-25 (latest+2) — ft-014 略读升级 + 精读多图多表
- 用户反馈：原"精读 + abstract + 占位"实际是想要的略读形态——整体抬一档。
- **略读卡**（每篇都有）：标题 + 作者 + **中文翻译 abstract** +
  折叠英文原文 + framework PNG + qualitative PNG + 关键词
- **精读卡**（Top-N）：略读 + 方法摘要 / 关键创新 / 局限 / 视角解读 + 表 PNG
- `figure_picker` 扩展 `pick_qualitative` / `pick_table`
- `SkimOut.one_liner → abstract_zh`（删 one_liner，旧 memory 字段保留兼容）
- `DeepOut` 加 qualitative_path/caption + table_path/caption
- pipeline：所有 items 都拉 PDF + 抽 caption + 渲三类图
- 邮件 inline_images 每篇至多 3 张
- 全量 105 tests passing。

### 2026-04-25 (latest+1) — ft-013 重设计（替代 ft-012 多模态路径）
- **设计原则升级**：CLAUDE.md 加"工具 vs LLM 边界"段——确定性产出工具化，
  LLM 仅用于语义理解/动态编排。ft-012 的多模态图分类被识别为错位（caption
  文本是确定信号，应规则匹配，不应送视觉模型猜）。
- **caption_extractor**: pymupdf 抽 "Figure N: ..." caption + bbox + 正文引用上下文。
- **figure_picker**: 关键词规则（framework/overview/architecture/pipeline）+ figure 1
  兜底；可选文本 LLM 兜底（不喂图）。
- **pdf_renderer**: page.get_pixmap(clip=bbox) 渲染指定区域 PNG，替代抽矢量碎片。
- **memory**: media/memory/<sub_name>/ 三件套（runs.jsonl / papers.jsonl /
  digests.md），跨 run 去重 + 给 deep_interpret 提供"近期相关论文"上下文。
- **deep_interpret 改造**: 纯文本 LLM；输入加 captions + 引用上下文 + memory；
  输出引用 [Fig. N] 锚点。
- **target-date 时间窗**: 默认昨日（Asia/Shanghai），按 published_at 严格过滤。
- **多模态保留代码但默认关闭**：--multimodal-figures 显式开启。
- ft-012 status = superseded。

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
