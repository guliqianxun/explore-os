"""ft-022: tests for apps.core.paths."""
from __future__ import annotations

import importlib
from pathlib import Path

import pytest


def _reload_paths(monkeypatch, data_root: Path):
    monkeypatch.setenv("EXPLORE_OS_DATA_DIR", str(data_root))
    # 确保副作用以新 env 生效
    monkeypatch.delenv("HF_HOME", raising=False)
    monkeypatch.delenv("TRANSFORMERS_CACHE", raising=False)
    import apps.core.paths as m
    importlib.reload(m)
    return m


def test_data_dir_uses_env(monkeypatch, tmp_path):
    m = _reload_paths(monkeypatch, tmp_path)
    assert m.data_dir() == tmp_path
    assert tmp_path.exists()


def test_subdirs_under_data_dir(monkeypatch, tmp_path):
    m = _reload_paths(monkeypatch, tmp_path)
    assert m.media_dir() == tmp_path / "media"
    assert m.papers_dir() == tmp_path / "media" / "papers"
    assert m.figures_dir("2401.12345") == tmp_path / "media" / "figures" / "2401.12345"
    assert m.equations_dir("2401.12345") == tmp_path / "media" / "equations" / "2401.12345"
    assert m.render_dir("2401.12345") == tmp_path / "media" / "render" / "2401.12345"
    assert m.memory_dir() == tmp_path / "media" / "memory"
    assert m.cache_dir() == tmp_path / "cache"
    assert m.outbox_dir() == tmp_path / "outbox"
    assert m.pdf_legacy_dir() == tmp_path / "media" / "pdf"


def test_dirs_exist_after_call(monkeypatch, tmp_path):
    m = _reload_paths(monkeypatch, tmp_path)
    p = m.figures_dir("foo")
    assert p.is_dir()
    p2 = m.outbox_dir()
    assert p2.is_dir()


def test_hf_env_set_on_import(monkeypatch, tmp_path):
    m = _reload_paths(monkeypatch, tmp_path)
    import os
    expected = tmp_path / "cache" / "huggingface"
    assert os.environ["HF_HOME"] == str(expected)
    assert os.environ["TRANSFORMERS_CACHE"] == str(expected / "transformers")
    assert m  # silence unused


def test_user_hf_home_not_overridden(monkeypatch, tmp_path):
    monkeypatch.setenv("HF_HOME", "/user/explicit/hf")
    monkeypatch.setenv("EXPLORE_OS_DATA_DIR", str(tmp_path))
    import apps.core.paths as m
    importlib.reload(m)
    import os
    assert os.environ["HF_HOME"] == "/user/explicit/hf"
    assert m


@pytest.fixture(autouse=True)
def _restore_paths_module():
    yield
    # 复位（用全新 env 一次 reload，避免污染其他测试）
    import apps.core.paths as m
    importlib.reload(m)
