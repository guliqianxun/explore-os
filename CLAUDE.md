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
