# explore-os

订阅驱动的信息检索推送助手。定位、里程碑与 Features 见 `docs/pm/ROADMAP.md`。

## 技术栈与环境

- **后端**：Django (Python) + uv 管理依赖
- **前端**：React + Vite（**MVP 阶段不做**，后端 + DB 跑通为先）
- **数据库**：由 docker compose 起（具体选型见 ROADMAP / ft 文档；MVP 倾向 Postgres）
- **部署**：docker compose
- **本地测试工具**：Navicat（看库）、Postman（打接口）

## MVP 开发边界

- 不写前端。所有能力以 Django management command（CLI）+ REST API 暴露，便于 Postman 手测。
- 订阅配置 MVP 阶段可先用 YAML，但数据模型（订阅状态、推送历史、解读缓存、成本账本）从一开始就落 DB，不走 SQLite 临时方案——既然有 Postgres + docker compose，直接用。
- 调度 MVP 外部 cron 触发 CLI / HTTP，不内置 scheduler。

## 参考项目

- `E:/codes/xingsuo` — 仅**方法论**参考其 `query_rewriter`（兴趣拆解思路）。**不做代码移植**，不作依赖。未来可能作为一个 source 插件接入。

## 设计原则：工具 vs LLM 的边界

```
确定性产出 → 工具化（代码 + 规则 + 缓存）
需要语义理解 / 动态编排 → LLM
LLM 是「填补 / 扩充」边界的，不是「替代规则」的
```

具体到本项目：
- 信源抓取、字段规范化、dedup_key 计算、章节正则归桶、caption 抽取、bbox 渲染、SMTP 投递、记忆线读写 → **工具**
- 兴趣 → 查询翻译、论文摘要、跨篇 narrative、深度解读、未命中规则时的图选取兜底 → **LLM**

错位的代价：把 caption 文本（确定信号）丢给视觉模型重新猜测——这是 ft-012 的根因，
ft-013 用 caption_extractor + figure_picker 校正回来。

## 产品定位

explore-os 是独立工具（OpenClaw-like），目前借助 Claude Code 协助开发，
**Python 代码本身就是产品**，不是临时脚手架。架构演进路径：
1. 完善 skill 边界（每个能力一个清晰接口）
2. 引入跨 run 记忆线（已在 ft-013 落地）
3. **拆三段中台**：抽取器（确定性 material）→ 解读器（L1+L2）→ 渲染器（Excalidraw 图谱）（v0.6/0.7/0.8 ✅）
4. orchestrator 从固定 pipeline → 可分支 agent
5. **打包为 Electron 桌面 app**（v0.9–v1.2，弃 Tauri），Django 作为 Python sidecar，DB 切 SQLite

## 长期形态约束（2026-04-25 锁定 / 2026-04-26 修订）

- **长期形态是 Electron 桌面 app**，不是云端 SaaS。新功能避免引入仅云端可用的依赖耦合（hardcoded SMTP、必需的远程数据库、外部 cron 假设等都要可拔）。
- **数据层避免 PG-only 特性**，为未来 SQLite 切换留口：
  - jsonb → 用 Django `JSONField`（ORM 已抽象）
  - 禁用 `ArrayField`、PG `tsvector`、PG-only 的 `ON CONFLICT` 写法（走 ORM `update_or_create`）
  - migrations 不要写 raw PG SQL
- **同库不同前缀**而非 schema：跨段表用 `extract_*` / `interpret_*` / `render_*` 前缀区分，SQLite 友好
- **路径假设**：所有持久化路径走 `EXPLORE_OS_DATA_DIR`（v0.9 ft-022 引入），禁止 hardcoded `BASE_DIR/'media'`，frozen exe 中 `BASE_DIR` 不可写
- **图谱渲染统一走 Excalidraw**（v0.8 ft-021 锁定），不留 tldraw / drawio renderer

## 桌面端栈（2026-04-26 锁定）

- **Shell**: Electron + electron-builder（Tauri 弃用，理由：CLI 已通；Electron sidecar 模式社区最成熟）
- **Sidecar**: PyInstaller-bundled Django，HTTP localhost 通信
- **前端**: Vite + React + TypeScript + Tailwind + shadcn/ui + @excalidraw/excalidraw + Zustand
- **调度器**: APScheduler in-process（不依赖系统 cron / 外部 broker）
- **签名**: 自用阶段不签（跳 Apple Dev / Win EV cert）；公开分发延后到 v1.x
- **CUDA / CPU 双轨**：v1.2 落两套 PyInstaller spec：
  - CUDA bundle（自用，~1.5GB，含 cu124 torch + docling 模型）
  - CPU bundle（分发接口，~700MB，CPU torch）
  - 单一代码库，pyproject.toml `[tool.uv.sources]` 区分 index

## 并行开发：worktree + subagent 协作规范

多 feature 并行时使用 `Agent(isolation="worktree")` 让每个 subagent 在独立分支/工作区开发，主会话负责合并。**踩过的坑 + 规则**：

1. **派发前必须先把共享基线 commit 到 main**。worktree 从当前 main HEAD 派生——基线缺失会让 subagent 一开始就找不到公共契约（接口定义、脚手架、feature 文档）而卡死。本次首轮派发时基线只在工作区未 commit，两个 agent 都从 `Initial commit` 派生，导致全量返工。
2. **派发前先预置接口契约文件**并 commit（如 `sources/base.py`）。让各 subagent 只实现自己的具体文件，不改共享契约，合并时天然无冲突。
3. **文件范围在 prompt 里写死白名单 + 黑名单**。"只能新增/修改 X/Y/Z，严禁触碰 A/B/C"。不说清会改到共享文件。
4. **测试文件命名错开**（如 `tests_<source>.py`），避免两人改同一 `tests.py`。但要在 `pyproject.toml` 的 `python_files` 里放开对应 glob。
5. **Resume 一个已有 subagent 不要用 Agent() 二次派发**——`isolation=worktree` 每次都起新 worktree；不带 isolation 则继承父 shell cwd，可能落到错误工作区。需要继续前次的 agent 用 `SendMessage` 指定 agentId。
6. **subagent 沙箱默认禁 git write**。本次 ft-003 agent 完成代码但无法 commit，由主会话代为 `git -C <worktree> add && commit`。把这步当成协议的一部分，别假设 subagent 能自己提交。
7. **合并顺序**：先 merge 一个 → 跑一次全量测试 → 再 merge 下一个。两边若都修了同一个轻量文件（如 `fetchers/__init__.py` 各自加一行 import），第二次 merge 必冲突，手动合并即可。
8. **worktree 清理**：`.claude/worktrees/` 已加入 `.gitignore`。运行结束后 worktree 可能仍被 Claude runtime lock，`git worktree remove --force` 若失败，下次 Claude Code 重启会自动释放，或 `-f -f` 强制。
9. **worktree base 漂移已知问题**：`Agent(isolation="worktree")` 偶发从过时 main 引用派生（多次实测：基线落到 `33be9ac` MVP 时期，缺所有后续 commits 的 apps/*）。**默认派发不用 isolation**，让 agent 直接在主仓写（前几次 ft-021/ft-020/ft-022 都跑通）。需要并行隔离时再用 worktree，并在派发前 `git -C <worktree> reset --hard main` 校正基线。

## 开发节奏

- **立项/架构类讨论先头脑风暴对齐方案，再落文档/代码**。不要在方案未拍板前开始 Write 脚手架。用户说"一起头脑风暴""先讨论"时，给选项化问题等拍板。
- **参考项目要独立判断**。用户给的参考项目 ≠ 要求复用；识别真正值得借鉴的那一个点，不要把对方整套能力栈都抄过来。
