"""ft-027: chain_extract_interpret_render 编排测试。

不真跑 docling / LLM；用 monkeypatch 把三阶段函数替成 stub，验证：
- 三阶段都成功 → result 含 stages.{extract,interpret,render}
- 任一阶段抛 → job 标 failed，error 写明哪一步
"""
from __future__ import annotations

import pytest

from apps.api import ingest as ingest_mod
from apps.api import jobs as jobs_mod


@pytest.fixture(autouse=True)
def _reset_jobs():
    yield
    from apps.core import scheduler
    scheduler.shutdown_scheduler(wait=True)
    jobs_mod.reset_for_tests()


def test_chain_all_stages_succeed(monkeypatch):
    monkeypatch.setattr(ingest_mod, "_run_extract",
                        lambda aid, p: {"arxiv_id": aid, "counts": {"sections": 5}})
    monkeypatch.setattr(ingest_mod, "_run_interpret",
                        lambda aid, p: {"arxiv_id": aid, "counts": {"claims": 3}})
    monkeypatch.setattr(ingest_mod, "_run_render",
                        lambda aid, fmt="excalidraw": {
                            "arxiv_id": aid, "fmt": fmt, "artifact_id": "a1",
                            "path": "/x/y.excalidraw"})

    info = ingest_mod.chain_extract_interpret_render(
        "2401.99999", "/tmp/x.pdf", inline=True,
    )
    assert info.status == "succeeded", info.error
    assert info.result["stages"]["extract"]["counts"]["sections"] == 5
    assert info.result["stages"]["interpret"]["counts"]["claims"] == 3
    assert info.result["stages"]["render"]["fmt"] == "excalidraw"


def test_chain_extract_failure_short_circuits(monkeypatch):
    def boom(*a, **kw):
        raise RuntimeError("docling exploded")
    monkeypatch.setattr(ingest_mod, "_run_extract", boom)
    interpret_called = {"v": False}
    def _ip(*a, **kw):
        interpret_called["v"] = True
        return {}
    monkeypatch.setattr(ingest_mod, "_run_interpret", _ip)

    info = ingest_mod.chain_extract_interpret_render(
        "2401.99999", "/tmp/x.pdf", inline=True,
    )
    assert info.status == "failed"
    assert "extract failed" in info.error
    assert interpret_called["v"] is False


def test_chain_interpret_failure_skips_render(monkeypatch):
    monkeypatch.setattr(ingest_mod, "_run_extract",
                        lambda aid, p: {"arxiv_id": aid, "counts": {}})
    def boom(*a, **kw):
        raise ValueError("no API key")
    monkeypatch.setattr(ingest_mod, "_run_interpret", boom)
    render_called = {"v": False}
    def _rd(*a, **kw):
        render_called["v"] = True
        return {}
    monkeypatch.setattr(ingest_mod, "_run_render", _rd)

    info = ingest_mod.chain_extract_interpret_render(
        "2401.99999", "/tmp/x.pdf", inline=True,
    )
    assert info.status == "failed"
    assert "interpret failed" in info.error
    assert render_called["v"] is False


def test_chain_render_failure(monkeypatch):
    monkeypatch.setattr(ingest_mod, "_run_extract",
                        lambda aid, p: {"counts": {}})
    monkeypatch.setattr(ingest_mod, "_run_interpret",
                        lambda aid, p: {"counts": {}})
    def boom(*a, **kw):
        raise RuntimeError("no graph")
    monkeypatch.setattr(ingest_mod, "_run_render", boom)

    info = ingest_mod.chain_extract_interpret_render(
        "2401.99999", "/tmp/x.pdf", inline=True,
    )
    assert info.status == "failed"
    assert "render failed" in info.error
