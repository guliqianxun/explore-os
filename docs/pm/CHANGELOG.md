# Changelog

## [Unreleased]

### 2026-05-04 (双层架构设计) — ft-041 记忆/编排双层设计 🆕

**设计落盘**：
- Formal spec: `docs/design/explore-os-formal-spec.md` (v0.2 — 观点状态机 + 活跃度 + 记忆/编排双层)
- 架构图: `docs/design/explore-os-architecture.md`（软件框架图 + 双层架构图）
- Feature doc: `docs/pm/features/ft-041.md`
- Iteration: `docs/pm/iterations/iter-023.md`
- Dispatch: `docs/pm/communications/dsp-015.md`
- PM tooling: `scripts/pm_index.py` + `templates/` 目录
- 核心原子从 paper 改为 viewpoint (claim)，五态观点状态机 unseen→exposed→confirmed→linked→internalized
- 废弃 per-topic 状态机，替换为连续活跃度 $A$ + 固化度 $C$
- 系统不再叫 Hermes——**整个系统就是 explore-os**，记忆层 + 编排层是 core

### 2026-05-01 (iter-022) — ft-039 Primary 卡重塑 + ft-040 Brief 双语 + ingest 链路完善

**ft-039 Primary 卡 A+B+E + pdfplumber fast figures（done）**

- 新文件 `apps/extract/figure_pdfplumber.py`：pdfplumber 找 image-heavy 页 → union
  bbox + 16pt padding → page.crop().to_image(150 DPI) → 落 `media/figures-fast/<id>/`，
  最多 3 张。与 docling figures（`media/figures/`）解耦。
- 新文件 `apps/papers/pdf_auto.py::ensure_figures_fast_async`：detail GET 时
  fire-and-forget；`_FAST_INFLIGHT` set 守门去重。
- 新 API `GET /api/papers/<id>/figure-fast/<seq>.png` (`FigureFastView`)。
- 新组件 `frontend/src/components/BriefSummary.tsx`：react-markdown 渲染
  method_summary，左红右蓝双列展示创新点 / 局限。
- 新组件 `frontend/src/components/ClaimsPreview.tsx`：默认折叠，点开懒加载
  detail，渲染 Top 3 claims（含 claim_type / page）。
- list DTO 扩字段 `method_summary_zh` / `limitations` —— BriefSummary 直读 list，
  无需懒加载 detail。
- PaperCard / HeroPaperCard：去 MetaCards，挂 BriefSummary + ClaimsPreview；
  图源切 `figure-fast/1.png`，onError 隐藏整图区。

**ft-040 Brief 双语 + ingest 链路完善（done）**

双语 LLM：
- 新文件 `apps/llm/lang_detect.py`：CJK 启发式（含汉字 → zh，否则 → en）。
- 新文件 `apps/llm/prompts/skim_en.py` / `deep_en.py`：英文 prompt，与中文版
  同 JSON 输出 schema。
- `skim_interpret.py` / `deep_interpret.py`：
  - 自动 detect_paper_lang，选 prompt 变体；`SkimOut.lang` / `DeepOut.lang`。
  - **Perspective 双语**：英文 paper 用 `[Perspective]` + `PRESETS_EN`，
    中文用 `【视角】` + `PRESETS`。否则中文标签会让 LLM 拐回中文输出。
  - deep user 消息的 section header 也按 lang 双语。
- `brief_generate.py` / `brief_generator.py` / `subscription_persist.py`：
  `BriefData.lang` 透传 + 写 `PaperBrief.lang`。
- Migration `0008_paperbrief_lang`：加 `lang` 字段。
- list DTO 暴露 `brief_lang`；`_serialize_brief` 也加 `lang`。
- `BriefSummary.tsx`：`briefLang` prop + UI ≠ brief.lang 时方法概要标题旁
  显示 EN/中 小 badge。
- 字段重命名（`abstract_zh` → 中性）**不做**——内容反映 paper 语言，命名将就。

ingest 链路完善：
- `apps/api/ingest.py::_backfill_abstract_from_sections`：extract 阶段后从
  第一段 Section.raw_text 头部 ~2000 字回填 `Paper.abstract`（订阅链路有，
  ingest 漏了，导致 brief view 看不到 abstract）。
- chain 末尾 `jobs.enqueue(_run_brief, ...)` 起独立 brief job（`ingest-brief:<id>`），
  不阻塞主链路；LLM 失败 swallow，不影响 chain 三阶段 succeeded。
- 新 mgmt 命令 `backfill_briefs.py`：一次性给 extract 跑过但 brief 空的 paper
  补 brief。`--apply` / `--limit` / `--paper <id>` 三参数。
- 实测：4/4 老 paper（GraphCast / 006a5f88 / d4b846bd / d648e78e）全产出英文
  brief，含 abstract / method / 3-4 个创新点 / 3 个局限。

杂项修复：
- `useJobPolling.ts`：getJob 拿到 404（sidecar 重启丢 in-memory `_JOBS`）→
  本地 job 标 terminal `done`。修复"3 个灰点永远不动"的卡住症状。
- `apps/api/views/papers.py::_serialize_brief`：补暴露 `lang` 字段。

**验收**：pytest 391 passed / electron tsc 0 / frontend tsc 0 / Electron prod
实测通过（GraphCast 等 4 篇均产出英文 brief，UI 切换语言正常）。

---

### 2026-05-01 — iter-021 done：ft-031 / ft-031.5 / ft-037 / ft-038 一体落地

**ft-031 桌面通知 + brief 三段分桶（done）**

- Electron `Notification` IPC（`explore:notify`）+ 浏览器 `window.Notification`
  fallback。新文件 `frontend/src/lib/notify.ts` 抽象。
- `useJobPolling` 提到 App 顶层；`run-sub:*` 边沿 `done` 时 fire-and-forget
  notify + invalidate 未决数。`notifiedRef` Set 防重发。
- `PaperListPage` 速读区按 `created_at` 三段分桶（今日/本周/更早，更早默认折叠）。
  后端 `PaperListItemSerializer` 加 `created_at`（不改 schema）。
- NavBar Papers 旁挂未决数 badge（>=100 → "99+"）。
- 通知点击 → `navigate("/?status=new")`。

**ft-031.5 detail 页 PDF 自动下载 + 订阅 paper 详情 404 修复**

- 放宽 PaperDetailView 404：Paper 行存在但 materials 空也返回 detail。
  根因订阅 paper 不走 extract/interpret 链路。
- 新文件 `apps/papers/pdf_auto.py::ensure_pdf_async`：detail GET fire-and-forget
  拉 arXiv PDF 到 `papers_dir`，写回 `paper.pdf_path`。`_INFLIGHT` set 去重。

**ft-037 PC 便携版 + 数据目录用户可配（done）**

- electron-builder Win `[nsis, portable]` 并存；Mac `[dmg, zip]`。
- 新文件 `electron/src/dataDir.ts`：四级优先级 `user_override > env >
  PORTABLE_EXECUTABLE_DIR/data > 平台默认`。
- `launcher.json` 与 sidecar `user_config.json` 解耦（避免鸡生蛋）。
- 3 个新 IPC：`get-data-dir-info` / `set-data-dir-override` / `pick-directory`。
- Settings 页"数据目录"卡 + "重启生效"提示。
- 不做：手机版 / 自动迁移 / 热切目录 / 代码签名。

**ft-038 i18n 双语 + Settings 页发布前清理（done）**

- 装 i18next + react-i18next + browser-languagedetector。
- `frontend/src/i18n/{index.ts, locales/{zh,en}.json}` 按 namespace 组织。
- 翻译覆盖：NavBar / 通知 / 今日要览 / 订阅页+卡 / 导入页+拖拽 / Verdict 三键 /
  状态过滤栏 / 3 标签卡 + ▸ 显示中文翻译 toggle / Settings 全局。
- **Settings 页重写**：砍 SourceBadge / footer / 大部分 hint。三大组：
  通用（语言切换 — 立即生效 + localStorage）/ LLM / 数据目录。
- 不翻译：LLM 生成内容、Subscription Editor 大表单、Reading Station 内容区。
- 主 chunk 658→719kB（+61KB i18next 运行时）— 接受。

**iter-021 验收**：pytest 391 / tsc 0 / Electron prod 实测全通过。

---

### 2026-04-29 (续) — ft-033 落地 + 5 次用户实测调优 + 解读 vs 解压两条路 lock

**ft-033 Brief 内容处理层完成（done，同日立项 + 同日落地）**：

主体（commit 4f2c010）：
- `Paper.abstract` TextField + 0005 migration + 0006 backfill 从 docling Section
- `PaperBrief` OneToOne 表（papers_brief）：abstract_zh / keywords / method_summary_zh / key_innovation / limitations / for_you / tldr_zh / perspective_used / model_used / generated_at
- `apps/papers/brief_generator.py` 复用 `interpret/interpretation.py` 老 pipeline
- 2 endpoints：`GET/POST /api/papers/<id>/brief/` + `/brief/regenerate/`（同步阻塞 + 502 兜底）
- DTO list 加 `tldr_zh / keywords / has_brief / abstract_en`；detail nested `brief`
- 17 例 brief 测试 → pytest 332 passed
- Frontend：types 扩 + HeroPaperCard/PaperCard keywords prop + BriefSection 组件 + SpeedReadView 顶置接通

5 轮用户实测调优：
1. **D10 fix** (commit d007890)：`_build_item` fallback 从 Section 实时拉。根因 0006 backfill 仅 migrate 跑一次 + ingest 链不写 paper.abstract → 新 paper 跑不出 brief
2. **D11 enhance** (commit 13491fe)：接通 `deep_interpret_rich` 替代占位 `deep_interpret`。新增 `_build_chunks` / `_build_captions` / `_classify_bucket_from_path` 把 docling Section 表归桶（intro/method/experiments/conclusion）；BriefSection 加英文 abstract 折叠按钮。实测 GHQNYSJY 产出 abstract_zh 918 字 + method_summary 744 字 + key_innovation 2 + limitations 2 + for_you 258
3. **D12 list 信息密度** (commit 5a91c97)：list DTO 加 `abstract_zh` 短字段；BriefView lead 优先级改 `abstract_zh > tldr_zh > abstract_en`；HeroPaperCard line-clamp-4 → 6
4. **D13 list 卡片自动撑高 + 英文展开** (commit 78156e1)：HeroPaperCard / PaperCard 去 line-clamp + 加 `abstractEn` prop + `▸ Show original abstract` 折叠按钮（与 BriefSection 同款）；图文 grid 280px → 220px / 120px → 100px
5. **D14 图文比例 fr 自适应** (commit c253f9f)：grid 固定 px 改 fr。HeroPaperCard `1fr_220px` → `2fr_1fr`（图占 33%）；PaperCard `1fr_100px` → `3fr_1fr`（图占 25%）

**4/29 PM lock：解读 vs 解压两条路漏斗架构**：
- ROADMAP 加 §"两条路：解读 vs 解压" 战略段
- 信息解压（ft-019/020）= material_id / claim_id 细粒度结构化；解读（ft-033）= paper 级整体叙事
- 用户旅程漏斗：brief 列表 → 速读模式 → Reading Station + PDF（信息密度递增）
- 不硬合并理由：LLM 调用风格相反（narrative vs structured）/ 失败可分离 / 缓存策略不同 / 用户编辑层独立（ft-032 vs brief perspective）
- 接合点 v1.3+ 候选：`key_innovation` 挂 claim_id；brief `[Fig. N]` 锚点点击跳 figure；ReadingStation SpeedCardPane 露 brief 入口

**最终基线**：
- pytest 332 passed（315 baseline + 17 brief）
- frontend tsc strict 0 error
- 主 chunk 636 KB（vs ft-029 631KB +4KB BriefSection）

**已知遗留 / follow-up**：
- 新 ingest 默认不自动跑 brief（避 LLM 失控）；要"自动"加 `--auto-brief` flag
- TJCU4BAE 老 paper（ft-029 commit daaf73f 之前抽的）raw_text 全空，brief 跑不出，需 reingest
- brief 内 `[Fig. N]` 锚点未做可点击跳转
- ReadingStation SpeedCardPane 没露 brief 入口

### 2026-04-29 — ft-029 落地 + 用户实测反馈 + 毛玻璃 + 邮件双组 + ft-033 立项

**ft-029 全套落地（dsp-013 + dsp-014）**：
- backend rpt-013：Paper.pdf_path + 0004 migration + paths.resolve_pdf_path() + PaperPdfView GET/HEAD + DTO has_pdf/pdf_url + evidences nested 已有；pytest 315 passed (+9)
- frontend rpt-014：6 phases 全套（3 栏响应式 + ClaimCard 三态 + PdfViewer 联动 + NotesPane + ActionBar 状态机 + StatusPill 双入口）；tsc 0 error；主 chunk 627KB ↓7KB（vs ft-028 基线，因 lazy split）
- frontend agent socket 中断后主会话接手收尾（rpt-014 由主会话写，不影响成果）

**用户视觉实测反馈（4/29 浏览器/Electron 实测）**：

1. **毛玻璃弹窗（macOS Big Sur 风）已落地**：
   - `ui/dialog.tsx` Overlay `bg-black/30 backdrop-blur-md` + Content `bg-[var(--bg)]/85 backdrop-blur-xl border-white/15 shadow-2xl`
   - `reading/StatusPill.tsx` 浮层同款
   - 全局只这两处 floating（已 grep 确认无其它 Sheet/Popover 浮层）

2. **Today's brief 邮件版双组（拍板 macOS 风 + b 按 status + A 默认两组并列）**：
   - types/paper.ts StatusFilter 加 'brief'
   - StatusFilterBar 最左加 [Brief] chip；默认 filter 改 'brief'
   - 切到 brief 调 status=all 数据 → 前端按 status 切组：
     - 主要论文 = status in [reading, queued]，HeroPaperCard + PaperCard 大版面
     - 速读 = status=new，新建 SkimCard 紧凑单行
     - read_*/archived 在 brief 隐藏（切对应 chip 可看）
   - 新增 BriefView 内部组件 + SectionHeader（"主要论文 (N)"/"速读 (N)" 分隔条）
   - 新增 SkimCard.tsx
   - 主 chunk 627KB → 631KB (+3.4KB)

3. **Brief 内容处理需求 → ft-033 立项**：
   - 用户反馈"论文内容也应该和老邮件一样，各种翻译、缩略，完全相同的内容处理方案"
   - 4/29 调查根因：`apps/papers/Paper` 只有 title/arxiv_id/doi/pdf_path/created_at，**没有 abstract / tldr / abstract_zh 字段**；老邮件 pipeline (`interpret/interpretation.py` 的 `skim_interpret + deep_interpret`) 完全没接到新 ingest 链
   - 立项 ft-033 Brief 内容处理层：复用老 pipeline + 新增 PaperBrief OneToOne 表 (abstract_zh / keywords / tldr_zh / for_you / method_summary 等) + 2 endpoints + ~2.5 天
   - 决策：默认手动触发避 LLM 失控；perspective 从 active subscription yaml 读 fallback researcher；ingest 链同步加 abstract 字段
   - iter-018 立项

### 2026-04-28 (晚) — 竞品分析 + ft-029 增强 + ft-032 立项 + ROADMAP § Out of Scope

**PM 竞品分析**（B 象限地图：A1 推送 / A2 检索 / A3 引文图谱 / B1 archival / B2 PDF 标注 / B3 chat / B4 双链 / B5 综述）：
- 强差异化 = 该做：A→B 单一闭环、claim/figure 颗粒度沉淀、本地单机数据自有、结构化速读卡片
- 弱差异化 = 砍 / 借 / 延后：引文图谱（→ Connected Papers）、PDF 高亮（→ readest）、Chat with PDF（红海+范式冲突）、archival 库（→ Zotero）、wiki-link 双链（→ Obsidian）

**4 个 PM 决策点拍板**：
- Q1 wiki-link：不做，仅 paper 颗粒度 backlink
- Q2 沉淀库 NL 问答：不做，先看 ft-030 FTS5
- Q3 Daily Narrative：维持 ft-010 现状
- Q4 飞书 / 微信 IM Adapter：保留 deferred（"不在电脑前"兜底）

**ROADMAP 更新**：
- 里程碑表 v1.2 重定义为"用户层（A 进 B 出）"，自动更新顺延 v1.3
- 新增 § "Out of Scope / Won't Do"：引文图谱 / PDF 标注 / Chat / archival 库 / wiki-link / NL 问答 / 云同步
- updated_at 2026-04-25 → 2026-04-28；version v0.6-plan → v1.2-plan
- Features 索引补 ft-028 ~ ft-032；当前迭代补 iter-012 ~ iter-017

**ft-029 spec 增量**（PM review 后追加 D1/D2/D5/D8 + Out of Scope 收紧）：
- D1 NotesPane 响应式宽度（min 280 / max 420，窄屏 < 1100px 折抽屉），不写死 320px
- D2 **ClaimCard 三态**：collapsed / expanded with evidence / editing
  - **引文展开附原文**：claim → `evidences[]` → material_id → fan-out 5 类（section / figure / table / equation / citation 不同模板）
  - 无 schema 改动；`PaperDetailSerializer` 加 `evidences` nested 即可
  - editing 态移交 ft-032，本 ft 仅 placeholder
- D5 底部 action bar 纯文字无图标 + **状态机驱动**：reading 显示 4 键 / read_kept|dropped 仅 [Archive][Reopen] / archived 仅 [Reopen]
- D8 顶部 status pill 双入口：`[reading ▾]` 下拉直接改 5 态（与底部 bar 冗余但好用）
- Out of Scope 加 claim 编辑（→ ft-032）/ wiki-link / Chat with PDF
- frontend 工作量 5–6 → 6–7 天

**ft-032 ClaimCard 用户修订层立项**（v1.2 第五个特性，紧跟 ft-029 实测后）：
- 方案 A：覆盖层（不直改 Claim，保留 audit + re-interpret 不冲突）
- `UserClaimEdit(claim_id PK, text_override, hidden, edited_at)` 单表 OneToOne
- D7：hide 也归此表，不另起表（claim 修订动作归一）
- PATCH `/api/claims/<id>/edit/` + DELETE 还原；`text_effective` 字段注入 detail DTO
- ClaimCard 编辑态内联（textarea + 折叠 `ⓘ Original` + `[↶ revert]` + Cmd+Enter 提交）
- hidden 默认隐藏 + 顶部 `[显示已隐藏 (N)]` toggle；`✎ edited` 徽章
- 工作量 ~2.5 天（backend 0.5 + frontend 2）；可主会话直接做不必派 subagent

**iter-017 立项**（ft-032，等 ft-029 上线 + 用户实测确认编辑诉求强烈后启动）

### 2026-04-28 — v1.2 启动：ft-028 + 砍 PG + ft-029 spec 立项

**产品决策（4/28 lock）**：
- A 进 B 出 product shape：subscription brief 入口 + 论文沉淀层（status / comment(history) / tag / paper 级双链）
- Paper-centric schema：`[A-Z2-9]{8}` Zotero 风格 stable_key；arxiv_id/doi 降元数据列
- 5 态状态机 + comment append-only + 内嵌 pdf.js"对照型" + Zotero/readest 是逃生口
- **砍 Postgres**：桌面 app 单进 SQLite；psycopg / docker-compose / .env DATABASE_URL 全删

**ft-028 Paper-centric schema + user_* + Inbox verdict UI 完成（25)**：
- backend `apps/papers/`：Paper + UserPaperStatus + UserComment + UserTag + UserBacklink + STATUS_TRANSITIONS + `gen_key()` retry-3
- 9 个迁移：3 papers + 3 extract + 3 interpret；`pre_save` signal 自动 wire `paper_arxiv_id → paper_id` 让 docling 抽取链不动
- 11 DRF endpoints：POST status / GET+POST comments / PATCH comment(hidden only) / GET+POST tags / DELETE tag / GET+POST backlinks / DELETE backlink；list/detail 加 `?status=&tag=&q=` filter + `paper_key/title/status/tags/n_comments` DTO
- `<id>` 双解析：`[A-Z2-9]{8}` → Paper.key；其它 → arxiv_id（regex 不重合）
- frontend：types/paper.ts（DTO 集中）+ VerdictActions.tsx（[Skip][Queue][Read now]）+ StatusFilterBar.tsx（5 chip + counts 旁标）
- PaperList sticky filter + url 化 + 跨缓存乐观更新 + 空状态 empty-state
- 双 backend agent 接力（一个 socket 中断后续派一个收尾）+ 主会话补 2 bug（`gen_key` 字符表含 I/O / `POST tag` IntegrityError 没 transaction.atomic 隔离）
- 测试：**306 passed**（基线 262 + 44 新；走 SQLite override + 默认 SQLite 双跑都过）

**ft-026 follow-up（用户实测发现）**：
- **figure 排版 root-cause fix**：`docling._map_sections` 累积 `text/paragraph/list_item` 节点为 section.raw_text；views.py 相似度纳入 `s.path + s.raw_text` → 6/6 figures 全部归属（之前全沉底）
- **Electron 标题栏冲突**：原生 menu/title 与 React header 双层；改 frameless + titleBarOverlay (40px) + WebkitAppRegion drag/no-drag
- **PaperDetail 形态级 pivot**：从 markdown 重渲全文 → 速读卡片（title + abstract + ClaimCard 排序 + figure 画廊）；删 4 组件（MarkdownView/FloatingTOC/ClaimDrawer/ReadingModeToggle）+ 移 getPaperMarkdown API
- sidecar `--data-dir`：dev 模式优先 in-repo `.venv/Scripts/python.exe`，避开 uv re-sync 受限网络挂

**砍 PG**：
- pyproject.toml `psycopg[binary]` 移除；uv sync 卸 4 包
- `docker-compose.yml` 删除（PG-only 文件无其它服务）
- `.env` `DATABASE_URL=postgres://...` 注释掉，settings.py 默认 `sqlite:///<DATA_DIR>/explore_os.sqlite3` 接管
- CLAUDE.md / README.md / docs/pm/ROADMAP.md：技术栈 / MVP 心智 / 部署条目同步改 SQLite

**ft-029 Reading Station spec 立项**（v1.2 第二个特性，待派发）：
- 3 栏布局（speed-card / pdf.js / notes pane），`react-pdf` + `react-resizable-panels`
- claim:fig → 跳页 + bbox overlay 高亮；claim:sec → pdf.js textLayer 文本搜索
- NotesPane Tabs：Comments（append-only chrono）/ Tags（ChipInput 复用）/ Backlinks（`?q=` typeahead）
- 自动 status bump：detail mount 时 new/queued → reading
- 底部 action bar：`[Mark kept ✓][Mark dropped ✗][Archive]` → 修今天发现的 verdict 出口 gap
- PDF 不可用降级 2 栏；status='archived' 退回 speed 模式；可手动 toggle

### 2026-04-27 — ft-027 Subscription 表单化 + Ingest（代码完成）

- 5 subscription CRUD/run + 3 ingest endpoints (PDF upload / arxiv id / URL) + chain extract→interpret→render
- frontend SubscriptionPage 卡片+modal + ChipInput 复用 / IngestPage 三入口 + IngestProgressItem
- ruamel.yaml 替 PyYAML 保留 subscription YAML 注释
- HF_HOME 优先复用 `~/.cache/huggingface` 全局缓存避免 sidecar 首次拉 600MB docling 模型
- 用户最终 ingest 三阶段链路实测待最终确认

### 2026-04-26 — ft-026 编辑/杂志重设计 + CORS 修复

- `frontend/src/styles/tokens.css`：暖中性色板 + 衬线/无衬线/等宽字体栈 + claim_type 软色 + counter 红
- 6 新组件：HeroPaperCard / ClaimDrawer / FloatingTOC / ReadingModeToggle / lib/fonts.ts
- 10 改造：PaperList feed / PaperDetail 单栏沉浸 / PaperCard editorial / ClaimCard 抽屉宽松 / globals.css prose-paper / tailwind theme.extend / index.html web fonts / MarkdownView
- CORS：`django-cors-headers 4.9.0` + CORS_ALLOW_ALL_ORIGINS=True
- 触发用户反馈：PaperList 形态满意；SubscriptionPage YAML editor 不友好（→ ft-027）；RunPage 定位不清（→ ft-027）

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
