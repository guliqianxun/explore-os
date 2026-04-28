from pathlib import Path

import environ

# ft-022: 触发 apps.core.paths 副作用（HF_HOME / TRANSFORMERS_CACHE 重定向），
# 必须在任何可能 import docling 的代码之前。也提供 data_dir() 供下面 DATA_DIR 复用。
from apps.core.paths import data_dir as _data_dir

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
)
environ.Env.read_env(BASE_DIR / ".env")

# ft-022: 数据根目录（环境变量 EXPLORE_OS_DATA_DIR 优先，否则跨平台默认）
DATA_DIR = _data_dir()
MEDIA_ROOT = DATA_DIR / "media"
MEDIA_URL = "media/"

SECRET_KEY = env("DJANGO_SECRET_KEY", default="dev-insecure-change-me")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",  # ft-026: cross-origin (5173 → sidecar) for dev + Electron loadFile
    # Local apps
    "apps.core",
    "apps.api",
    "subscriptions",
    "sources",
    "interpret",
    "delivery",
    "apps.extract",
    "apps.interpret",
    "apps.render",
    "apps.papers",
]

MIDDLEWARE = [
    # ft-026: CORS middleware must be at the very top to set headers before
    # CommonMiddleware can short-circuit responses.
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default=f"sqlite:///{DATA_DIR / 'explore_os.sqlite3'}",
    ),
}

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Shanghai"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ft-026: single-machine app — allow any origin so Vite dev (5173) and
# Electron loadFile (file://) can hit the sidecar without preflight pain.
CORS_ALLOW_ALL_ORIGINS = True

# ---- LLM ----
LLM_API_BASE = env("LLM_API_BASE", default="https://api.openai.com/v1")
LLM_API_KEY = env("LLM_API_KEY", default="")
LLM_MODEL = env("LLM_MODEL", default="gpt-4o-mini")
LLM_MODEL_TEXT = env("LLM_MODEL_TEXT", default=LLM_MODEL)
LLM_MODEL_MULTIMODAL = env("LLM_MODEL_MULTIMODAL", default="")
LLM_MODEL_VISION_CLASSIFIER = env("LLM_MODEL_VISION_CLASSIFIER", default=LLM_MODEL_MULTIMODAL)
LLM_DAILY_BUDGET_CNY = env.float("LLM_DAILY_BUDGET_CNY", default=30.0)

# ---- Email ----
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_USE_SSL = env.bool("EMAIL_USE_SSL", default=False)
DEFAULT_FROM_EMAIL = env("EMAIL_FROM", default="explore-os@localhost")
EMAIL_TO_DEFAULT = env("EMAIL_TO_DEFAULT", default="")
