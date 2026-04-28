from django.apps import AppConfig


class PapersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.papers"
    label = "papers"

    def ready(self) -> None:  # pragma: no cover - signal wiring
        # 注册 signals：现有 extract / interpret 落库代码只会写
        # ``paper_arxiv_id``；signal 在 pre_save 时自动 get_or_create 出
        # ``Paper`` 并把 ``paper_id`` 补上，避免改动既有 extractor /
        # interpreter / persist 逻辑。
        from apps.papers import signals  # noqa: F401
