"""ft-033 brief 内容处理层 tests.

覆盖：
  - ``_compose_tldr`` 句末截断
  - ``_resolve_perspective`` fallback researcher
  - ``generate_brief`` happy（mock skim/deep_interpret）
  - ``regenerate=False`` 已存在不重跑
  - ``regenerate=True`` 覆盖
  - list DTO 含 tldr_zh / keywords / has_brief / abstract_en
  - detail DTO nested brief（None / 含值）
  - GET / POST regenerate endpoint
  - regenerate LLM 失败 → 502
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from rest_framework.test import APIClient

from apps.extract.models import Section
from apps.papers.models import Paper, PaperBrief


@pytest.fixture(autouse=True)
def _shutdown_scheduler_after():
    yield
    from apps.api import jobs
    from apps.core import scheduler
    scheduler.shutdown_scheduler(wait=True)
    jobs.reset_for_tests()


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def paper(db):
    p = Paper.objects.create(
        arxiv_id="2401.99001",
        title="Self-Rewarding LMs",
        abstract="We propose a novel self-rewarding framework that ...",
    )
    Section.objects.create(
        material_id=f"{p.arxiv_id}:section:1",
        paper_arxiv_id=p.arxiv_id, seq=1, path="Abstract", level=1,
        raw_text="We propose a novel self-rewarding framework that ...",
    )
    return p


# ---------------- pure helpers ----------------

def test_compose_tldr_句末截断():
    from apps.papers.brief_generator import _compose_tldr

    text = "本文提出了一种自奖励的语言模型框架。我们在 AlpacaEval 2.0 上达到 SOTA。"
    out = _compose_tldr(text, max_len=30)
    assert out.endswith("。")
    assert "自奖励" in out
    assert "AlpacaEval" not in out  # 第二句被截掉


def test_compose_tldr_短文本原样返回():
    from apps.papers.brief_generator import _compose_tldr

    assert _compose_tldr("短句", max_len=80) == "短句"


def test_compose_tldr_无句末符号_用_ellipsis():
    from apps.papers.brief_generator import _compose_tldr

    text = "abcdefghij" * 20  # 200 chars no separator
    out = _compose_tldr(text, max_len=50)
    assert out.endswith("…")
    assert len(out) == 51  # 50 + ellipsis


def test_resolve_perspective_无_yaml_fallback_researcher(settings, tmp_path):
    from apps.papers.brief_generator import _resolve_perspective

    settings.SUBSCRIPTIONS_YAML = str(tmp_path / "missing.yaml")
    persp = _resolve_perspective()
    assert persp.preset == "researcher"
    assert persp.custom == ""


def test_resolve_perspective_读出第一个_active(settings, tmp_path):
    from apps.papers.brief_generator import _resolve_perspective

    p = tmp_path / "subs.yaml"
    p.write_text(
        "subscriptions:\n"
        "  - name: a\n"
        "    enabled: false\n"
        "    perspective:\n"
        "      preset: pm\n"
        "  - name: b\n"
        "    enabled: true\n"
        "    perspective:\n"
        "      preset: engineer\n",
        encoding="utf-8",
    )
    settings.SUBSCRIPTIONS_YAML = str(p)
    persp = _resolve_perspective()
    assert persp.preset == "engineer"


# ---------------- generate_brief ----------------

def _mock_skim(monkeypatch, abstract_zh="一种自奖励的 LM 框架。", keywords=None):
    keywords = keywords or ["self-rewarding", "DPO", "alignment"]
    fake = SimpleNamespace(
        abstract_zh=abstract_zh, keywords=keywords, usage={"total": 100},
    )
    monkeypatch.setattr(
        "interpret.interpretation.skim_interpret",
        lambda item, persp: fake,
    )


def _mock_deep(monkeypatch):
    fake = SimpleNamespace(
        abstract="...",
        placeholder="...",
        method_summary="方法 X",
        key_innovation=["创新 1", "创新 2"],
        limitations=["限制 1"],
        for_you="给你的视角看法",
        figure_path="", figure_caption="",
        qualitative_path="", qualitative_caption="",
        table_path="", table_caption="",
    )
    monkeypatch.setattr(
        "interpret.deep_interpret.deep_interpret_rich",
        lambda item, chunks, captions, mem, persp: fake,
    )


def test_generate_brief_happy(paper, monkeypatch):
    _mock_skim(monkeypatch)
    _mock_deep(monkeypatch)
    from apps.papers.brief_generator import generate_brief

    brief = generate_brief(paper)
    assert brief.abstract_zh.startswith("一种自奖励")
    assert brief.keywords == ["self-rewarding", "DPO", "alignment"]
    assert brief.method_summary_zh == "方法 X"
    assert brief.for_you == "给你的视角看法"
    assert brief.tldr_zh.endswith("。")
    assert brief.perspective_used == "researcher"  # fallback


def test_generate_brief_skip_existing(paper, monkeypatch):
    _mock_skim(monkeypatch, abstract_zh="第一次生成")
    _mock_deep(monkeypatch)
    from apps.papers.brief_generator import generate_brief

    first = generate_brief(paper)
    first_at = first.generated_at

    # 改 mock，但不 regenerate ：应跳过
    _mock_skim(monkeypatch, abstract_zh="第二次（不应被采用）")
    second = generate_brief(paper, regenerate=False)
    assert second.abstract_zh == "第一次生成"
    assert second.generated_at == first_at


def test_generate_brief_regenerate_覆盖(paper, monkeypatch):
    _mock_skim(monkeypatch, abstract_zh="V1")
    _mock_deep(monkeypatch)
    from apps.papers.brief_generator import generate_brief

    generate_brief(paper)
    _mock_skim(monkeypatch, abstract_zh="V2")
    second = generate_brief(paper, regenerate=True)
    assert second.abstract_zh == "V2"
    assert PaperBrief.objects.filter(paper=paper).count() == 1  # 仍 OneToOne


def test_generate_brief_skim_失败_仍落空行(paper, monkeypatch):
    monkeypatch.setattr(
        "interpret.interpretation.skim_interpret",
        lambda item, persp: None,
    )
    _mock_deep(monkeypatch)
    from apps.papers.brief_generator import generate_brief

    brief = generate_brief(paper)
    assert brief.abstract_zh == ""
    assert brief.keywords == []
    # tldr 走 paper.abstract 头部
    assert "self-rewarding" in brief.tldr_zh.lower() or brief.tldr_zh != ""


# ---------------- DTO ----------------

def test_list_dto_含_brief_短字段(client, paper, monkeypatch):
    _mock_skim(monkeypatch, abstract_zh="一句中文摘要")
    _mock_deep(monkeypatch)
    from apps.papers.brief_generator import generate_brief

    generate_brief(paper)
    r = client.get("/api/papers/")
    assert r.status_code == 200
    found = next(it for it in r.json() if it["arxiv_id"] == paper.arxiv_id)
    assert found["has_brief"] is True
    assert found["tldr_zh"] != ""
    assert isinstance(found["keywords"], list)
    assert found["abstract_en"].startswith("We propose")


def test_list_dto_无_brief_空字段(client, paper):
    r = client.get("/api/papers/")
    found = next(it for it in r.json() if it["arxiv_id"] == paper.arxiv_id)
    assert found["has_brief"] is False
    assert found["tldr_zh"] == ""
    assert found["keywords"] == []


def test_detail_dto_brief_nested(client, paper, monkeypatch):
    _mock_skim(monkeypatch)
    _mock_deep(monkeypatch)
    from apps.papers.brief_generator import generate_brief

    generate_brief(paper)
    r = client.get(f"/api/papers/{paper.arxiv_id}/")
    assert r.status_code == 200
    body = r.json()
    assert body["abstract"].startswith("We propose")
    assert body["brief"] is not None
    assert body["brief"]["abstract_zh"].startswith("一种自奖励")
    assert body["brief"]["for_you"] == "给你的视角看法"
    assert body["brief"]["perspective_used"] == "researcher"


def test_detail_dto_brief_null_when_absent(client, paper):
    r = client.get(f"/api/papers/{paper.arxiv_id}/")
    body = r.json()
    assert body["brief"] is None


# ---------------- endpoints ----------------

def test_get_brief_404_when_absent(client, paper):
    r = client.get(f"/api/papers/{paper.arxiv_id}/brief/")
    assert r.status_code == 404


def test_post_regenerate_happy(client, paper, monkeypatch):
    _mock_skim(monkeypatch, abstract_zh="生成结果")
    _mock_deep(monkeypatch)
    r = client.post(f"/api/papers/{paper.arxiv_id}/brief/regenerate/")
    assert r.status_code == 200
    body = r.json()
    assert body["abstract_zh"] == "生成结果"
    assert PaperBrief.objects.filter(paper=paper).exists()


def test_post_regenerate_502_on_pipeline_error(client, paper, monkeypatch):
    def boom(*a, **kw):
        raise RuntimeError("LLM down")

    monkeypatch.setattr("interpret.interpretation.skim_interpret", boom)
    monkeypatch.setattr("interpret.deep_interpret.deep_interpret_rich", boom)
    r = client.post(f"/api/papers/{paper.arxiv_id}/brief/regenerate/")
    assert r.status_code == 502
    assert "generation failed" in r.json()["detail"]


def test_get_brief_after_generate(client, paper, monkeypatch):
    _mock_skim(monkeypatch)
    _mock_deep(monkeypatch)
    client.post(f"/api/papers/{paper.arxiv_id}/brief/regenerate/")
    r = client.get(f"/api/papers/{paper.arxiv_id}/brief/")
    assert r.status_code == 200
    assert r.json()["abstract_zh"].startswith("一种自奖励")
