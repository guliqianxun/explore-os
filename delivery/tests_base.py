"""Tests for ft-016 DeliveryAdapter abstraction."""
from __future__ import annotations

import pytest

import delivery  # noqa: F401  trigger registration
from delivery.base import (
    Digest,
    DeliveryAdapter,
    DeliveryResult,
    DeliveryTarget,
    REGISTRY,
    get,
    register,
)


def test_registry_has_three_adapters():
    assert "email" in REGISTRY
    assert "feishu" in REGISTRY
    assert "wechat_subscription" in REGISTRY


def test_get_known_returns_adapter():
    a = get("email")
    assert hasattr(a, "deliver")
    assert hasattr(a, "key")
    assert a.key == "email"


def test_get_unknown_raises():
    with pytest.raises(KeyError):
        get("snail-mail")


def test_feishu_stub_returns_not_implemented():
    a = get("feishu")
    res = a.deliver(Digest(subject="x"), DeliveryTarget(channel="feishu"))
    assert res.success is False
    assert "not implemented" in res.detail.lower()


def test_wechat_stub_returns_not_implemented():
    a = get("wechat_subscription")
    res = a.deliver(Digest(subject="x"),
                     DeliveryTarget(channel="wechat_subscription"))
    assert res.success is False
    assert "not implemented" in res.detail.lower()


def test_register_custom_adapter():
    class FakeAdapter:
        key = "fake-test"

        def deliver(self, digest, target):
            return DeliveryResult(success=True, detail="fake ok")

    register(FakeAdapter())
    assert "fake-test" in REGISTRY
    res = get("fake-test").deliver(Digest(subject="x"),
                                     DeliveryTarget(channel="fake-test"))
    assert res.success
    # cleanup
    del REGISTRY["fake-test"]
