---
review_id: review-A-services
review_group: A
sprint: iter-019
status: completed
created_at: 2026-04-29
reviewer: subagent
---

# Review A — services / LLM 服务层

## 1. 范围确认

审计文件清单（行数）：

**新解读层 `apps/interpret/`（704 行业务 + 525 行测试）**
- `apps/interpret/base.py` 50 / `catalog.py` 88 / `interpreter.py` 250 / `llm_client.py` 57 / `models.py` 51 / `persist.py` 90 / `prompts.py` 65
- 测试：`tests_catalog.py` / `tests_interpreter.py` / `tests_llm_client.py` / `tests_persist.py`

**新抽取层 `apps/extract/`（1023 行业务 + 717 行测试）**
- `base.py` 80 / `extractor.py` 136 / `caption_extractor.py` 328 / `figure_extractor.py` 194 / `section_extractor.py` 170 / `models.py` 115
- `extractors/docling_ext.py`（具体实现，未读全文，已知是 docling 包装）

**ft-033 胶水**
- `apps/papers/brief_generator.py` 228 — 复用老 pipeline
- `apps/papers/signals.py` 69 — pre_save 桥接 paper FK

**顶级 legacy `interpret/`（1346 行业务 + 1268 行测试）**
- LLM 业务：`llm.py` 118 / `interpretation.py` 132 / `deep_interpret.py` 129 / `tldr.py` 51 / `narrative.py` 82 / `figure_picker.py` 160 / `figure_classifier.py` 105 / `ranker.py` 150 / `rewriter.py` 75 / `embedding.py` 91
- 抽取层 thin re-export wrapper（已迁移）：`caption_extractor.py` 14 / `figure_extractor.py` 18 / `pdf_chunker.py` 17

合计：约 5440 行（含测试），LLM 调用点 7 处（顶级 6 处 + apps/interpret 1 处）。

不读：`extractors/docling_ext.py`（CLAUDE.md 明确禁触；归 B 组 extract 范围）；`tests_docling_ext.py` 同理。



## 2. 耦合 hotspot（最多 15 条）

每条标注：严重度（1=critical / 2=major / 3=minor） + 改造工作量（h/d） + 阻塞 ft-034。

| # | hotspot | 严重 | 工作量 | 阻塞 ft-034 |
|---|---|---|---|---|
| H1 | 两套 LLM 客户端互依赖：`apps/interpret/llm_client.py:12` 直接 `from interpret.llm import LLMError, chat, extract_json` — 新代码 import 顶级 legacy。`apps/interpret/interpreter.py:13` 也只为 `LLMError` import 老模块。说明 ft-020 当时把 chat 实现留在老地方做了一层薄封装，未真正搬迁 | 1 | 1 d | yes |
| H2 | `apps/papers/brief_generator.py:191-192` 函数体内惰性 `from interpret.deep_interpret import deep_interpret_rich` / `from interpret.interpretation import skim_interpret` — ft-033 同日落地的脏胶水，把"复用"做成了 apps→legacy 反向依赖 | 1 | 1 d | yes |
| H3 | prompt 模板散点：6 个老模块各自定义 SYSTEM 字符串（`tldr.py:14` `interpretation.py:54` `deep_interpret.py:26` `narrative.py:20` `rewriter.py:18` `figure_picker.py:91` `figure_classifier.py:22`）+ 1 个新模块（`apps/interpret/prompts.py`）。无注册表、无 versioning、prompt 改动散落多文件 | 2 | 1 d | yes |
| H4 | LLM 调用 7 处全部 try/except 内联 + log.warning 后吞错（`interpretation.py:96` `tldr.py:49` `narrative.py:80` `deep_interpret.py:86` `rewriter.py:69` `figure_picker.py:158` `apps/interpret/interpreter.py:219`）：每处自定义降级策略（None / 空 dataclass / 空 SourceQuery）。无统一错误模型 | 2 | 1 d | yes |
| H5 | JSON 解析两套：`interpret/llm.py:101 extract_json`（围栏 + 大括号兜底）vs `apps/interpret/llm_client.py:43-57 chat_json`（`response_format=json_object` + 退回 extract_json）。`apps/interpret` 路径优先，但仍依赖老 extract_json 兜底 | 2 | 4 h | partial |
| H6 | `interpret/deep_interpret.py:13 from django.conf import settings` + `figure_picker.py:19` + `figure_classifier.py:11` + `embedding.py:8`：legacy LLM 模块都直读 `settings.LLM_*` 取 model 名/key — model 选取分散在 5 处，没有 model registry | 2 | 4 h | yes |
| H7 | `apps/papers/brief_generator.py:55,69-73,96-97,126` 一个文件 5 次惰性 import（`apps.extract.section_extractor`、`apps.extract.models`、`apps.extract.caption_extractor`），全部为了"组装老 pipeline 期望的 dataclass"。等于在 paper 层重做了一遍 chunk_pdf 的归桶 | 2 | 6 h | yes |
| H8 | 副作用混杂：`apps/interpret/interpreter.py:43-55 get_paper_markdown` 在 interpreter 内部直接调 `apps.extract.extractors.docling_ext._convert`（私有下划线接口）触发 PDF 解析。解读层调抽取层私有 API + 触发 docling | 1 | 4 h | yes |
| H9 | `apps/interpret/persist.py:31-33` 先 delete 再 update_or_create — 不是真正幂等；多次 persist 期间窗口内 ClaimEvidence/CounterSignal 行为空。事务包了但仍是 "delete + insert" 模式 | 3 | 2 h | no |
| H10 | `apps/papers/signals.py:48-56` pre_save 自动补 paper FK 跨越 `apps.extract.models.{Citation,Equation,Figure,Section,Table}` 与 `apps.interpret.models.Claim` 6 类。任何新增 material 表都需修这里。隐式耦合 | 2 | 2 h | no |
| H11 | `interpret/ranker.py:108 from .embedding import EmbeddingError, cosine, embed` — ranker 是订阅推送链 only，但既不在 apps 也不属抽取/解读三段中台，定位不清；新代码无 import（仅 `subscriptions/management/commands/run_subscription.py:37` 用）→ legacy 专属 | 3 | 2 h | no |
| H12 | `interpret/figure_classifier.py:12` `from .figure_extractor import Figure, figures_root` — figure_classifier 调老 figure_extractor 的 Figure dataclass，老 figure_extractor 是 thin re-export → 间接绕回 `apps.extract.figure_extractor.Figure`。一条圈：apps.extract → interpret thin wrapper ← interpret.figure_classifier | 2 | 4 h | partial |
| H13 | `apps/interpret/interpreter.py:34 MARKDOWN_CHAR_BUDGET = 30_000` + `apps/papers/brief_generator.py:_TLDR_MAX_LEN=80` + `interpret/deep_interpret.py:113 captions[:8]` + `interpret/figure_picker.py:140 figures[:15]` — token 预算/截断阈值散落 4 个文件，无中心配置 | 3 | 2 h | no |
| H14 | `interpret/llm.py:37 max_tokens=512` 默认值过低，每个调用方独立覆盖（tldr=200 / skim=600 / deep=900 / narrative=400 / rewriter=300 / figure_picker=80）— 默认值脱离实际，靠每处调用方记住覆盖。temperature 同问题（默认 0.3，6 处覆盖） | 3 | 2 h | no |
| H15 | `interpret/embedding.py:13-15 EMBEDDING_MODEL = "text-embedding-v3"` 硬编码 + `EMBEDDING_DIM=1024` 硬编码。不读 settings；切 provider 必改源码。与 `interpret/llm.py` 设计风格不一致 | 3 | 2 h | no |



## 3. 新旧并存清单（顶级 interpret/ vs apps/interpret/）

| 顶级 `interpret/` 模块 | 状态 | 谁在 import？ | 是否死码 |
|---|---|---|---|
| `interpret/llm.py` (118 行) | **活跃** — 唯一真正的 HTTP chat client | `interpret/{interpretation,deep_interpret,tldr,narrative,rewriter,figure_picker,figure_classifier}.py` + `apps/interpret/llm_client.py:12` + `apps/interpret/interpreter.py:13` | 否 |
| `interpret/interpretation.py` (132 行) | 活跃 — `skim_interpret` + `DeepOut` | `apps/papers/brief_generator.py:192`、`subscriptions/.../run_subscription.py:34`、`delivery/base.py:13`、`delivery/adapters/email.py:30` | 否 |
| `interpret/deep_interpret.py` (129 行) | 活跃 — `deep_interpret_rich` | `apps/papers/brief_generator.py:191`、`subscriptions/.../run_subscription.py:27` | 否 |
| `interpret/tldr.py` (51 行) | **疑似死码** | grep 全仓只有自身 + 测试 import；`run_subscription.py` 也没 import | **是** |
| `interpret/narrative.py` (82 行) | 活跃 — 邮件 hero/bullets | `delivery/base.py:14`、`delivery/adapters/email.py:31`、`run_subscription.py:35` | 否 |
| `interpret/rewriter.py` (75 行) | 活跃 — interest → query | `run_subscription.py:38` | 否 |
| `interpret/figure_picker.py` (160 行) | 活跃 | `run_subscription.py:29` | 否 |
| `interpret/figure_classifier.py` (105 行) | **疑似死码** | grep 全仓只有自身 + 测试；`run_subscription.py` 没 import | **是** |
| `interpret/ranker.py` (150 行) | 活跃 | `run_subscription.py:37` | 否 |
| `interpret/embedding.py` (91 行) | 活跃（被 ranker 调） | `interpret/ranker.py:16` | 否 |
| `interpret/caption_extractor.py` (14 行) | thin re-export wrapper | dsp-001 注："本 sprint 完成后可在 ft-020 中清理"——ft-020 已 done 但未清 | **是（wrapper）** |
| `interpret/figure_extractor.py` (18 行) | thin re-export wrapper | `interpret/figure_classifier.py:12` 还在引用（H12）| **半死** |
| `interpret/pdf_chunker.py` (17 行) | thin re-export wrapper | `interpret/deep_interpret.py:18 from interpret.pdf_chunker import PaperChunks` | 否（仍被 deep_interpret import）|

**结论**：legacy `interpret/` 还活着的真业务（非 wrapper）共 8 个模块（llm + 7 个 LLM 能力），订阅链（`subscriptions/.../run_subscription.py`）和邮件链（`delivery/`）都直 import 顶级。`apps/interpret/` 仅承载 ft-020 的 L1+L2 claim 抽取一条新路径，并且其 LLM 客户端反过来依赖顶级 `interpret/llm.py`。

**死码 / 可清候选**：`tldr.py`（无引用方）、`figure_classifier.py`（无引用方）、3 个 thin re-export wrapper（caption_extractor / figure_extractor / pdf_chunker）。其中 figure_extractor wrapper 还被 figure_classifier 间接锁住，需先决定 figure_classifier 去留。



## 4. prompt / LLM 调用分布统计

### 4.1 prompt 模板散点

8 个 SYSTEM/SUFFIX 字符串，分布 7 个文件，0 个集中注册表：

| 模板 | 文件:行 | 用途 | LLM 能力名（ft-034 视角） |
|---|---|---|---|
| `REWRITE_SYSTEM` | `interpret/rewriter.py:18` | interests → arxiv/hf 查询 | **rewriter** |
| `SKIM_SYSTEM_SUFFIX` | `interpret/interpretation.py:54` | abstract 翻译+关键词 | **interpret_skim** |
| `DEEP_SYSTEM_SUFFIX` | `interpret/deep_interpret.py:26` | method/innovation/limit/for_you | **interpret_deep** |
| `TLDR_SYSTEM` | `interpret/tldr.py:14` | 60 字 summary + keywords | （死码，无 ft-034 对应）|
| `NARRATIVE_SYSTEM_SUFFIX` | `interpret/narrative.py:20` | 跨篇 hero/bullets | **brief_generate**（邮件版）|
| `LLM_PICK_SYSTEM` | `interpret/figure_picker.py:91` | 选 architecture 图（caption only）| 兜底，非 5 大能力 |
| `CLASSIFY_SYSTEM` | `interpret/figure_classifier.py:22` | 多模态图分类 | （死码）|
| `L1_SYSTEM` / `L2_SYSTEM` | `apps/interpret/prompts.py:4,27` | claim/counter_signal 抽取 | **interpret_extract**（apps 层）|

观察：每个 SYSTEM 都内联自定 JSON schema 描述（`{"abstract_zh": ...}` / `{"claims": [...]}`），结构 schema 与 prompt 文本耦合 → ft-034 想"集中到注册表"必须把 schema 抽出来。

### 4.2 LLM 调用分布

`chat()` 直接调用 7 处：

| 文件:行 | 模型 | temp | max_tokens | response_format | timeout |
|---|---|---|---|---|---|
| `interpret/rewriter.py:54` | 默认 (LLM_MODEL_TEXT) | 0.2 | 300 | 无 | 30 (默认) |
| `interpret/interpretation.py:82` | 默认 | 0.2 | 600 | 无 | 30 |
| `interpret/deep_interpret.py:75` | settings.LLM_MODEL_TEXT | 0.3 | 900 | 无 | 60 |
| `interpret/tldr.py:35` | 默认 | 0.3 | 200 | 无 | 30 |
| `interpret/narrative.py:65` | 默认 | 0.4 | 400 | 无 | 30 |
| `interpret/figure_picker.py:142` | settings.LLM_MODEL_TEXT | 0.1 | 80 | 无 | 30 |
| `interpret/figure_classifier.py:75` | LLM_MODEL_VISION_CLASSIFIER \|\| LLM_MODEL_MULTIMODAL | 0.1 | 80 | 无 | 120 |
| `apps/interpret/llm_client.py:34` (chat_json 包装，被 interpreter.py 调 2 次) | 默认 | 0.2 | 2048 | json_object | 60 |

观察：
- 仅 1 个调用点用 `response_format=json_object`（apps 层），其余 6 个全靠 `extract_json` 文本兜底
- `LLM_MODEL_TEXT` 显式传 3 处，其余 4 处依赖 `chat()` 内部默认（`interpret/llm.py:46`）
- 多模态调用单独走 `interpret/figure_classifier.py:42`（`LLM_MODEL_VISION_CLASSIFIER`），与文本路径混用同一 `chat()`
- timeout 30/60/120 三档拆得不严谨

`embedding.embed()` 调用 1 处（`interpret/ranker.py:108`），独立模型 `text-embedding-v3` 硬编码。



## 5. 解耦改造提议（最多 10 条）

按 ft-034 必经度排序。每条标注：阻塞 ft-034（yes/partial/no） + 工作量。

| # | 提议 | 工作量 | 阻塞 ft-034 |
|---|---|---|---|
| P1 | **建立 `apps/services/llm/` 单一 LLM 中台层**：把 `interpret/llm.py` 的 `chat / extract_json / build_image_content / LLMResult / LLMError` 物理搬到 `apps/services/llm/client.py`，老 `interpret/llm.py` 改成 `from apps.services.llm.client import *` 一行 wrapper（或直接删，逐处改 import）。同时把 `apps/interpret/llm_client.py:chat_json` 也合并进去。这是 H1 / H4 的根因解 | 1 d | yes |
| P2 | **建 prompt 注册表 `apps/services/llm/prompts/`**：每个 LLM 能力一个文件（`rewriter.py` / `skim.py` / `deep.py` / `narrative.py` / `interpret_extract.py`），导出 `Prompt(name, system, user_template, response_schema, default_params)` 对象。废弃散点 SYSTEM 字符串。配合 P1 让 `chat()` 接受 Prompt 对象 | 1 d | yes |
| P3 | **5 个 LLM 能力规整 service registry**：在 `apps/services/llm/registry.py` 暴露 `rewriter / interpret_skim / interpret_deep / interpret_extract（L1+L2）/ brief_generate` 5 个 callable。每个签名稳定（`(input_dataclass) -> output_dataclass`），输入/输出 dataclass 由 `apps.services.llm.schemas` 集中。这是 ft-034 的核心交付物 | 2 d | yes |
| P4 | **brief_generator 反向依赖切断**：`apps/papers/brief_generator.py:191-192` 改为 `from apps.services.llm.registry import interpret_skim, interpret_deep`（统一新接口）。删除 5 处 `from apps.extract.*` 惰性 import，把 chunks/captions 组装下沉到 service 内部（让 service 自己读 extract 表） | 6 h | yes |
| P5 | **interpreter 切断对 docling 私有 API 的直调**：`apps/interpret/interpreter.py:43-55` 的 `get_paper_markdown` 不应直接 `from apps.extract.extractors.docling_ext import _convert`。提议在 `apps/extract/extractor.py` 加 public `get_markdown(arxiv_id)` 入口（带缓存），interpreter 层调 public API。同时把 `MARKDOWN_CHAR_BUDGET` 移到 prompt 配置中 | 4 h | yes |
| P6 | **删除死码**：`interpret/tldr.py`（51 行）、`interpret/figure_classifier.py`（105 行）、`interpret/tests_tldr*.py` 类 / `tests_figure_classifier.py`。先确认 `figure_classifier` 真的没被任何 management command 用，再删（grep 已确认无业务 import）| 1 h | no |
| P7 | **清理 thin re-export wrapper**：在 P4 把 brief_generator 的 import 改完后，`interpret/caption_extractor.py` / `figure_extractor.py` / `pdf_chunker.py` 三个 wrapper 可删；同时 `interpret/deep_interpret.py:18 from interpret.pdf_chunker import PaperChunks` 改为 `from apps.extract.section_extractor import PaperChunks`（或在 P3 service 化时一并消失） | 2 h | partial |
| P8 | **错误模型统一**：每个 service callable 返回 `Result[T, LLMServiceError]` 或 raise `LLMServiceError(stage, cause)`，由调用方决定降级。废弃 7 处内联 try/except + `return None / 空 dataclass` 模式。caller 拿到错误后能知道是哪个 stage 失败（rewriter/skim/deep/extract）| 6 h | yes |
| P9 | **model 选取集中到 registry**：`interpret/llm.py:46` 的 `model = model or settings.LLM_MODEL_TEXT or settings.LLM_MODEL` fallback 链 + `figure_classifier.py:42` 的 `LLM_MODEL_VISION_CLASSIFIER` 都搬到 `apps/services/llm/models.py`。每个能力通过 `model_role: text / vision / embedding` 选 model，不再让 service 直读 settings | 4 h | partial |
| P10 | **persist 真幂等改造（H9）**：把 `apps/interpret/persist.py:31-33` 的 "delete + insert" 改成 diff-based update（按 (claim_id, material_id) 主键集合做 add/update/del 三集），避免事务窗口内 evidence 表为空。低优先，可放到 ft-034 之后 | 3 h | no |

**ft-034 必做**：P1-P5 + P8-P9（合计约 6 d）。P6/P7 可顺便清理但不阻塞。P10 单独排期。



## 6. ft-034 必经路径

ft-034 目标："把 5 个 LLM 能力（rewriter / extract / interpret_skim / interpret_deep / brief_generate）规整成稳定 schema 接口，集中到注册表"。

**必经路径（按依赖序）**：

1. **P1 LLM 中台层**（1 d）— 没有这一步，`apps/interpret/llm_client.py` 仍依赖顶级 `interpret/llm.py`，注册表无法摆脱新旧混用。**先做**。
2. **P9 model 选取集中**（4 h）— 与 P1 同 sprint，让 chat() 不再吃 settings 直引用。
3. **P2 prompt 注册表**（1 d）— 8 个散点 SYSTEM/SUFFIX 集中。schema 与 prompt 文本耦合的问题在这里解开（每个 Prompt 带 response_schema）。
4. **P5 docling public API**（4 h）— 让 interpret_extract 能力（apps/interpret 现 L1+L2）能放进注册表而不绕私有下划线接口。
5. **P3 service registry**（2 d）— 5 个能力 callable 暴露。规整后每个能力签名 = `(input_dc, params) -> output_dc | raise LLMServiceError`。
6. **P8 错误模型**（6 h）— 与 P3 同步落地，否则注册表里每个 callable 错误处理风格不一致。
7. **P4 brief_generator 反向依赖切断**（6 h）— ft-033 胶水现状是 ft-034 验收的 acid test：能否通过新注册表跑 brief 生成且不 import 顶级 `interpret/`。

**ft-034 不必做（但建议顺手）**：P6（删死码）、P7（清 wrapper）、P10（persist 幂等）。

**预估总工时**：6 个工作日（P1+P9+P2+P5+P3+P8+P4）。已含与 B 组（extract）协作 P5（在 `apps/extract/extractor.py` 加 public `get_markdown`）。

**风险**：
- ft-033 today 才落，user 实测路径上的 `deep_interpret_rich`／`skim_interpret` 任何接口微调都需要回归（参考 ROADMAP §解读 vs 解压）。建议 P4 落地时保留老入口 1-2 周做 A/B。
- `subscriptions/management/commands/run_subscription.py` 一次性 import 8 个 `interpret.*` 模块，是订阅推送链与新注册表的最大兼容面；本 review 划归 D/E 组（订阅/邮件）但 ft-034 改造 P3 时需向 D 组同步新接口。



## 7. 不在范围 / 移交其它 group

| 文件/问题 | 移交 group | 说明 |
|---|---|---|
| `apps/extract/extractors/docling_ext.py` | **B 组（extract）** | CLAUDE.md 锁：派发文档 forbid。但 P5（加 public `get_markdown`）需 B 组配合 |
| `apps/extract/caption_extractor.py` / `figure_extractor.py` / `section_extractor.py` 内部实现 | **B 组（extract）** | 本 review 仅看 import 链与契约（`base.py` ExtractResult），不审实现细节 |
| `apps/papers/models.py` PaperBrief schema | **C 组（user_layer / DB）** | brief_generator 只用 update_or_create 写表，schema 演进归 C |
| `apps/papers/signals.py` 跨表 pre_save 桥接 | **C 组** | 涉及 6 个 model + UserPaperStatus 触发器，本 review 仅指出 H10 副作用混杂位置 |
| `subscriptions/management/commands/run_subscription.py` | **D 组（subscription/scheduler）** | 一次性 import 8 个老 `interpret.*`，是 ft-034 注册表落地时最大改造面，但本身归 D |
| `delivery/base.py` / `delivery/adapters/email.py` | **E 组（delivery/UI）** | 直 import `interpret.interpretation` / `interpret.narrative`，需 E 组同步切新注册表 |
| `interpret/embedding.py` + `ranker.py` | **D 组** | embedding 是订阅推送 ranker 链专属，与 ft-034 5 大 LLM 能力不直接相关。但 H15 指出 model 硬编码问题，可放到 ft-034 后专项 |
| `apps/interpret/migrations/` / `apps/extract/migrations/` | **C 组** | DB schema |
| `apps/render/graph.py` 对 `apps.interpret.models / apps.extract.models` 的引用 | **F 组（render）** | 本 review 仅记录耦合点：`apps/render/graph.py:33-34,108`、`tests_graph.py:12-13` |

**本 review 范围内疑虑但暂未深查**：
- `apps/interpret/tests_interpreter.py` 271 行 — 长度可疑，是否过度 mock 了 `chat_json`？未审测试设计，建议 ft-034 重写注册表时把测试夹具一并移到 `apps/services/llm/tests/`
- `apps/interpret/management/commands/interpret_paper.py` — 仅看到 import 链，未审 CLI 参数与 ft-034 是否一致

