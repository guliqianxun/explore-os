# explore-os

订阅驱动的信息检索推送助手。详见 [`docs/pm/ROADMAP.md`](docs/pm/ROADMAP.md) 与 [`CLAUDE.md`](CLAUDE.md)。

## 本地开发

```bash
cp .env.example .env
uv sync
docker compose up -d postgres
uv run python manage.py migrate
uv run python manage.py runserver
```

## 项目结构

```
config/              # Django settings / urls / wsgi
subscriptions/       # ft-001 订阅 schema
sources/             # ft-003 / ft-004 信源 fetcher
interpret/           # ft-002 rewriter + ft-006 LLM 解读
delivery/            # ft-005 去重历史 + ft-007 渲染投递
docs/pm/             # Roadmap / Features / Iterations
```
