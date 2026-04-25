"""ft-017 (stub): 飞书 DeliveryAdapter.

未实施。预期实现：
- target.to = 飞书自定义机器人 webhook URL，或飞书应用接收人 open_id
- Digest → 飞书富文本卡片（支持图、links、callout block）
- 图先调 https://open.feishu.cn/open-apis/im/v1/images?image_type=message 上传
  得到 image_key，再嵌入卡片
- POST 到 webhook 或 https://open.feishu.cn/open-apis/im/v1/messages

关键 API：
- 自定义机器人 Webhook（最简）: 卡片 JSON 直发
- 应用机器人: 需 app_id / app_secret + tenant_access_token

精读卡 ↔ 飞书卡片元素映射：
- 标题 → header.title
- abstract_zh → 段落 text element
- 框图/效果图/表 → image element (image_key)
- 方法摘要/创新/局限 → 段落
- 视角解读 → callout block
"""
from __future__ import annotations

from dataclasses import dataclass

from delivery.base import (
    Digest,
    DeliveryAdapter,
    DeliveryResult,
    DeliveryTarget,
    register,
)


@dataclass(slots=True)
class FeishuAdapter:
    key: str = "feishu"

    def deliver(self, digest: Digest, target: DeliveryTarget) -> DeliveryResult:
        return DeliveryResult(
            success=False,
            detail="feishu adapter not implemented (ft-017 planned)",
            metadata={"todo": True},
        )


register(FeishuAdapter())
