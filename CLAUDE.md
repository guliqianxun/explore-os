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

## 开发节奏

- **立项/架构类讨论先头脑风暴对齐方案，再落文档/代码**。不要在方案未拍板前开始 Write 脚手架。用户说"一起头脑风暴""先讨论"时，给选项化问题等拍板。
- **参考项目要独立判断**。用户给的参考项目 ≠ 要求复用；识别真正值得借鉴的那一个点，不要把对方整套能力栈都抄过来。
