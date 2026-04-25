"""ft-018 (stub): 微信订阅号 DeliveryAdapter.

未实施。预期实现：

1. **access_token**：
   POST https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential
       &appid=APPID&secret=SECRET
   每 2h 刷新；缓存到本地

2. **上传图（每张图先换 media_id）**：
   - 永久素材：POST .../material/add_material?type=image  → media_id
   - 用于图文中插图：POST .../media/uploadimg → 得到 url（仅图文用）

3. **创建图文素材（草稿）**：
   POST .../material/add_news
   body 包含 articles[]，每篇 article 含：
     - title, thumb_media_id（封面图）, content（HTML，受限白名单）, ...

4. **群发**（订阅号每天 1 次）：
   POST .../message/mass/sendall  with media_id
   或先发 preview 给指定 openid 测试

精读 / 略读 → 一篇推文：
- 标题：digest.subject
- 封面：deeps[0].deep.figure_path（最高分论文的 framework 图）
- 正文 HTML：narrative + 精读详细 + 略读列表 + 阅读原文链接
- 精读 + 略读如果太多，可拆成 multiple articles（订阅号支持单次推 1-8 篇）

HTML 受限：去掉 <details>，去掉 cid:image（必须在线 url）。
图必须先上传到微信服务器获得 cdn url，再 inline 到 HTML。

target 字段：
- target.to = "" 表示群发（默认）
- target.params: {appid, appsecret, draft_only: bool, preview_openid: str}
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
class WeChatSubscriptionAdapter:
    key: str = "wechat_subscription"

    def deliver(self, digest: Digest, target: DeliveryTarget) -> DeliveryResult:
        return DeliveryResult(
            success=False,
            detail="wechat_subscription adapter not implemented (ft-018 planned)",
            metadata={"todo": True},
        )


register(WeChatSubscriptionAdapter())
