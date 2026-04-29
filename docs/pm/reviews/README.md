---
pm_id: reviews-readme
pm_type: index
purpose: code review 报告归档与命名规范
updated_at: 2026-04-29
---

# `docs/pm/reviews/` — 代码 review 报告归档

iter-019 重构 sprint 的 review phase 产出。**修复 agent 直接读这里的 .md 报告**作为改造依据。

## 命名规范

```
review-{group}-{topic}.md
```

| group | topic | 范围 |
|---|---|---|
| A | services | LLM 服务层耦合（顶级 `interpret/` legacy + `apps/interpret/` + `apps/papers/brief_generator.py` + `apps/extract/`） |
| B | api | DRF 契约层（`apps/api/*` views/serializers/urls/ingest/jobs） |
| C | pipeline | orchestrator + 调度（`sources/` 抓取 + `apps/api/ingest.py` + `apps/api/jobs.py` + management commands） |
| D | frontend | frontend api/types/hooks 契约（`frontend/src/api/*` + `types/*` + 各 page hook 散点） |
| E | electron | Electron + sidecar + DATA_DIR 路径（`electron/src/*` + `sidecar_entry.py` + 路径胶水） |
| F | dead-code | 死码 / 重复 / 测试覆盖空洞（全仓） |

## 报告 frontmatter

每份 review 报告须含：

```yaml
---
review_id: review-A-services
review_group: A
sprint: iter-019
status: completed
created_at: 2026-04-29
reviewer: subagent
---
```

## 报告结构（建议章节）

1. **范围确认** — 实际审过哪些文件 / 行数
2. **耦合 hotspot** — 按严重度排序，每条带文件:行号
3. **重复实现 / 新旧并存** — 顶级 legacy vs `apps/*` 重复点
4. **死代码** — superseded 模块、未引用 export
5. **解耦改造提议** — 每条带改造前后对照 + 估算工作量
6. **风险标注** — 改动可能破坏的依赖
7. **不在范围 / 移交其它 group** — 越界发现交还 PM

## 修复 agent 的入口

修复 agent 派发时，dispatch 指明读哪份 review 报告 + 哪些 hotspot 必修。
**报告里的提议不是命令**——PM（人 + 主会话）拿全部 6 份做交叉决策后才下修复 dispatch。
