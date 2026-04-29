---
pm_id: phase-2-decision
pm_type: decision
sprint: iter-019
status: locked
created_at: 2026-04-29
inputs:
  - review-A-services
  - review-B-api
  - review-C-pipeline
  - review-D-frontend
  - review-E-electron
  - review-F-dead-code
---

# iter-019 Phase 2 — PM 整合决策

6 份并行 review 共定位 ~90 个 hotspot / 死码 / DTO drift / 路径假设问题。
本决策把跨组重叠收敛为一份**单一真相**修复清单，并最终拍板 ft-034 范围。

---

## 1. 跨组 hotspot 收口

多组独立指出同一根因的 hotspot — 合并为单条修复，避免重复工作 / 修复冲突。

| 收口编号 | 涉及组 | 根因 | 单条修复方向 |
|---|---|---|---|
| **X1 LLM 客户端两套互依赖** | A H1 ⇄ C H3 ⇄ F C 类 | `apps/interpret/llm_client.py:12` + `apps/interpret/interpreter.py:13` 反向 import 顶级 `interpret/llm.py`；新解读层名义独立实则寄生 legacy | 把 chat/extract_json/LLMError 提取到 `apps/llm/`（新 app），两套客户端都改 import 它；legacy `interpret/llm.py` 保留 thin re-export 一周观察期再删 |
| **X2 brief_generator 反向胶水** | A H2/H7 ⇄ B 链路重写 ⇄ D 数据流 | `apps/papers/brief_generator.py:191-192` 函数体内惰性 import 老 `interpret.deep_interpret` / `interpret.interpretation`；为组装老 dataclass 5 次 import `apps.extract.*` | 把 skim_interpret / deep_interpret_rich 真搬迁到新 `apps/llm/services/` 接口；brief_generator 只调新接口，不再 import 顶级 |
| **X3 BASE_DIR 写盘 hardcoded** | C H10 ⇄ E H1 ⇄ F | `extract_paper.py:32` / `interpret_paper.py:32` / `figure_extractor.py:40` / `render_graph` 文案，全部 hardcoded `BASE_DIR/'media'/...`；frozen exe 里 `_MEIPASS` 不可写 | 全数走 `apps.core.paths.media_root()` / `figures_dir()`；ft-022 已立法但有 4 处漏网 |
| **X4 DTO drift（JobStatus / Equation）** | B D5 ⇄ D D2/D1 | backend `JobStatus` 5 个值（pending/running/done/failed/cancelled）vs frontend type 4 个值（queued/running/done/failed），命名 + 数量双错；EquationDTO 漏 `paper_arxiv_id/eq_label/bbox` | 新增 `apps/api/serializers/jobs.py` + `equations.py` 真 serializer；frontend `types/paper-job.ts` / `paper-material.ts` 严格对齐 |
| **X5 views.py 单文件 859 行** | B H1 ⇄ D H1（papers.ts 352 行） | 22 个 view class 5 个职能簇混在一文件；`papers.ts` 17 个裸函数 1 个文件 | backend 拆 `apps/api/views/{papers,materials,claims,jobs,subscriptions}.py`；frontend 拆 `api/papers/{core,material,claim,brief}.ts` |
| **X6 prompt + model 选取分散** | A H3/H6/H14 | 7 处 SYSTEM 字符串散落 + 5 处 `settings.LLM_*` 直读 + temperature/max_tokens 6 处独立覆盖 | `apps/llm/prompts/`（注册表 + version）+ `apps/llm/models.py`（model registry，每能力一个 named profile） |
| **X7 解读调抽取私有 API** | A H8 | `apps/interpret/interpreter.py:43-55` 直接 `apps.extract.extractors.docling_ext._convert`（私有下划线） | extract 暴露 `get_paper_markdown(paper_id)` public API；解读层只调这个 |
| **X8 subscriptions.yaml 静态读** | E H3 | `subscriptions_views.py:35` + `brief_generator.py:32` 静态路径假设 → frozen 后用户改不到 _MEIPASS asar | 走 `apps.core.paths.user_config_dir() / 'subscriptions.yaml'`，启动时 seed 默认值到 DATA_DIR |

---

## 2. 必修 / 顺手 / 延后

按修复优先级与 ft-034 阻塞关系分级。

### P0（ft-034 必做，~6 工作日）

| ID | 来源 | 内容 | 工作量 |
|---|---|---|---|
| **P0-1** | X1 + A H1 | 新建 `apps/llm/` app（client + error model）+ 切两套客户端 | 1 d |
| **P0-2** | X6 + A H3/H6/H14 | `apps/llm/prompts/` 注册表 + `apps/llm/models.py` registry + 默认 budget 配置中心 | 1 d |
| **P0-3** | X2 + A H2/H7 | brief_generator 反向胶水切断；skim/deep/extract 服务化到 `apps/llm/services/` | 1.5 d |
| **P0-4** | X7 + A H8 | extract 暴露 `get_paper_markdown()` public API；私有调用清零 | 0.5 d |
| **P0-5** | X3 + C H10 + E H1 | BASE_DIR 4 处漏网 → `paths.*` 化 | 0.5 d |
| **P0-6** | X4 + B D5/D D2 | JobStatus + Equation serializer 真化；frontend type 同步 | 0.5 d |
| **P0-7** | X5 + B H1 | `apps/api/views/` package 拆分（5 sub-modules） | 1 d |

### P1（顺手清，~2 工作日，可放本 sprint 也可推 v1.3）

| ID | 来源 | 内容 |
|---|---|---|
| **P1-1** | F A 类 | 6 个 0 字节 stub（`interpret/{admin,models,tests}.py` + `sources/{admin,models,tests}.py`）删 |
| **P1-2** | A 表 + F A 类 | 顶级 `interpret/{tldr,figure_classifier}.py` 死码删除（grep 全仓 0 引用） |
| **P1-3** | A 表 + F A 类 | 3 thin wrapper（`interpret/{caption_extractor,figure_extractor,pdf_chunker}.py`）删；H12 圈断 |
| **P1-4** | C 4 commands | 4 management commands grep 全仓 `call_command` 0 处 → 标 deprecated 或删 |
| **P1-5** | D | frontend `claims.ts` 9 行空壳 0 引用 → 删 |
| **P1-6** | D H1 | `papers.ts` 拆为 4 个 sub-module（与 X5 配套） |

### P2（延后到 v1.3+ 或不做）

| ID | 来源 | 决议 |
|---|---|---|
| **P2-1** | F §6 phase 3.3 | **老 email pipeline `subscriptions/run_subscription.py` (436 行) 是否弃** → **本 sprint 不动**；推到 v1.4 chat 分级落地后回头评估（届时已知 brief 链能否完全替代邮件链） |
| **P2-2** | C APScheduler | lazy start / 无 atexit / cron 未兑现 → v1.5 打包阶段一起做（电池/sleep/系统休眠都要考虑） |
| **P2-3** | D bundle 单 chunk 636KB | manualChunks → v1.5 打包阶段做 |
| **P2-4** | D statusMachine.ts 84 行手抄 | backend 暴露 `/api/state-machines/` 后再生成 → v1.3+ |
| **P2-5** | A H9 / H11 / H13 / H15 | 持久化幂等 + ranker 定位 + 截断阈值散落 + embedding 硬编码 → 不阻塞 ft-034，v1.3 顺手 |
| **P2-6** | F C 类 | embedding/narrative/figure_picker/rewriter 是否清 → 与 P2-1 绑定决策 |

### P3（永不做）

- ❌ 重写测试框架
- ❌ 全量测试覆盖率到 100%
- ❌ user_event 检索/点击日志表（4/29 PM lock）

---

## 3. ft-034 真实范围

替代 index.json 草图。**ft-034 = LLM 中台层 + 跨段解耦的最小集**，工作量 ~6 d。

### 3.1 必做 7 条（= P0-1 ~ P0-7）

见上表。

### 3.2 不做（明示）

- ❌ chat agent / function call / MCP server（v1.4+）
- ❌ user_profile 蒸馏（ft-035，v1.4+）
- ❌ FTS5 / Library 视图（ft-030，v1.3）
- ❌ APScheduler 改造（v1.5）
- ❌ 老 email pipeline 弃用（v1.4 决策）

### 3.3 验收

- `pytest -q` ≥ 315 passed（基线不退）
- `tsc -b` 0 error
- `npm run build` 主 chunk 不退
- 调用图：`apps/papers/brief_generator.py` 不再 import 顶级 `interpret.*`
- 调用图：`apps/interpret/llm_client.py` 不再 import 顶级 `interpret.llm`
- grep `BASE_DIR / 'media'` 全仓 0 处
- brief 视图 + Reading Station 视觉无回归（用户实测）

---

## 4. Phase 3 修复分组（按文件冲突避免，非按 review 组）

避免 worktree 冲突 — 多组同改一文件必须串行 / 同 agent 内做。

| 组 | 主要文件 | 包含 P0 任务 | Agent | 工作量 |
|---|---|---|---|---|
| **F1 LLM 中台层** | 新建 `apps/llm/`（client / error / prompts / models / services）+ legacy `interpret/llm.py` 改 thin wrapper | P0-1 / P0-2 | agent-1 | 2 d |
| **F2 services 解耦 + brief_generator** | `apps/papers/brief_generator.py` + `apps/papers/signals.py` + `apps/extract/extractor.py`（暴露 get_paper_markdown）+ `apps/interpret/interpreter.py` | P0-3 / P0-4 | agent-2（依赖 F1） | 2 d |
| **F3 API 层 + DTO drift** | `apps/api/views.py` 拆包 + 新 serializers/{jobs,equations}.py + frontend `api/papers/*.ts` 拆 + `types/paper-*.ts` 对齐 | P0-6 / P0-7 / P1-6 | agent-3 | 1.5 d |
| **F4 路径 + 死码清理** | `extract_paper.py` / `interpret_paper.py` / `figure_extractor.py` / `render_graph`(文案) + 死码删除 | P0-5 / P1-1~5 | agent-4（独立可并行） | 1 d |

**派发顺序**：F1 → (F2 ∥ F3 ∥ F4)。F1 提供 `apps/llm/` 接口契约，是 F2 的依赖；F3/F4 与 F1/F2 文件不重叠可并行。

---

## 5. 派发约束（继承 CLAUDE.md 9 条）

- **worktree 隔离**：`Agent(isolation="worktree")`，派发前 `git -C <worktree> reset --hard main`
- **白名单写死**：每个 agent prompt 指定可改文件 + 严禁触碰 `docs/pm/`
- **测试文件错开**：`apps/llm/tests_*.py` / `apps/api/tests_views_*.py` 命名分散，pyproject `python_files` 已通配
- **subagent 沙箱禁 git write**：commit 由主会话代理
- **合并顺序**：F1 → 跑全测 → F2 + F3 + F4 顺序 merge，每次 merge 后跑 pytest

---

## 6. 风险

- **legacy `interpret/llm.py` 留 thin wrapper 一周观察期**：F1 不强删，避免老 email pipeline 在 P2-1 决策前断链
- **brief_generator 已是 4/29 today 落地（ft-033）**：F2 改动须保持 brief 视觉 + 字段不变；用户实测必须复跑
- **DTO drift 修复触发 frontend 重新 fetch**：JobStatus 改名（queued → pending）需后端兼容老值过渡期 1 个 sprint，或前端 mapping 层
- **6 个 0 字节 stub 删除**：可能某些 Django app config 仍 import `models` — 删前先 grep `from .models` / `from .admin`

---

## 7. 时间线

| 日 | 内容 |
|---|---|
| 4/29 | Phase 2 lock（本文档）+ ft-034 spec + dispatch 文件起草 |
| 4/30 | F1 派发 + 完成 + merge |
| 5/1 | F2 / F3 / F4 并行派发 |
| 5/4–5/6 | 三组完成 + 顺序 merge |
| 5/7–5/8 | 集成测试 + 用户实测 brief / Reading Station |
| 5/9 | iter-019 关闭，启动 v1.3 iter-020（ft-030） |

---

## 8. 决策签字

- **PM** ：主会话（4/29）
- **用户**：4/29 confirmed via "continue" — Phase 2 自动推进
- **后续可改决议**：P2-1（老 email 链是否弃）— v1.4 chat 分级落地后再投票
