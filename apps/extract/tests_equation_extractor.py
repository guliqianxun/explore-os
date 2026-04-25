"""Tests for ft-019 equation_extractor."""
from __future__ import annotations

from apps.extract.equation_extractor import EQ_NUMBERED_RE, MATH_HINT_RE, Equation


def test_eq_numbered_re_matches():
    m = EQ_NUMBERED_RE.match("y = Wx + b (3)")
    assert m is not None
    assert m.group("num") == "3"


def test_eq_numbered_re_rejects_plain_caption():
    # 一行有数字括号但不是方程：依靠 MATH_HINT_RE 过滤
    line = "see reference (12)"
    m = EQ_NUMBERED_RE.match(line)
    assert m is not None  # 正则本身能匹配
    assert MATH_HINT_RE.search(m.group("body")) is None  # 但被数学算子启发挡掉


def test_math_hint_re_detects_operators():
    assert MATH_HINT_RE.search("y = x")
    assert MATH_HINT_RE.search("L_total = L_a + L_b")
    assert MATH_HINT_RE.search("argmax x")


def test_extract_equations_missing_pdf(tmp_path):
    from apps.extract.equation_extractor import extract_equations
    assert extract_equations("x", tmp_path / "no.pdf") == []


def test_equation_dataclass():
    eq = Equation(
        arxiv_id="x", page=1, eq_label="3",
        bbox=(0, 0, 1, 1), text="y = Wx + b (3)",
    )
    assert eq.inline_or_display == "display"
