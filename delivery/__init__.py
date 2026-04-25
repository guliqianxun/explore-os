"""delivery 包：触发各 adapter 注册到 registry."""
from delivery.adapters import email as _email  # noqa: F401
from delivery.adapters import feishu as _feishu  # noqa: F401
from delivery.adapters import wechat_subscription as _wechat  # noqa: F401
