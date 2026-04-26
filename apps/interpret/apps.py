from django.apps import AppConfig


class InterpretConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.interpret"
    # 关键：避开与 legacy `interpret` app 的 label 冲突
    label = "interpret_v2"
