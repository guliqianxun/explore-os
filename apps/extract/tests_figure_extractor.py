"""Tests for ft-019 figure_extractor (搬迁自 interpret/figure_extractor).

真实 PDF 解析路径走实战测试；这里只测 dataclass / save_load index 往返。
"""
from __future__ import annotations

from apps.extract import figure_extractor as fe
from apps.extract.figure_extractor import Figure


def test_figure_dataclass_defaults():
    f = Figure(arxiv_id="x", page=1, index=0, path="p01_i00.png")
    assert f.caption == ""
    assert f.kind == ""
    assert f.confidence == 0.0


def test_figure_save_and_load_index(tmp_path, monkeypatch):
    monkeypatch.setattr(fe, "figures_root", lambda: tmp_path)
    figs = [
        Figure(arxiv_id="2401.00001", page=1, index=0, path="p01_i00.png", caption="Fig 1"),
        Figure(arxiv_id="2401.00001", page=2, index=1, path="p02_i01.png"),
    ]
    path = fe.save_index("2401.00001", figs)
    assert path.exists()
    loaded = fe.load_index("2401.00001")
    assert len(loaded) == 2
    assert loaded[0].path == "p01_i00.png"


def test_load_index_missing_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(fe, "figures_root", lambda: tmp_path)
    assert fe.load_index("missing-arxiv") == []
