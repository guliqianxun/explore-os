"""Tests for ft-013 caption_extractor.

Caption 抽取依赖真实 PDF 解析；这里测的是正则与引用归并辅助函数。
真实 PDF 解析路径在实战测试覆盖。
"""
from __future__ import annotations

from interpret import caption_extractor as ce
from interpret.caption_extractor import Caption, _attach_references


def _cap(kind: str, num: int) -> Caption:
    return Caption(
        arxiv_id="x", kind=kind, number=num,
        text=f"{kind.title()} {num}: stub", page=1,
        bbox_caption=(0, 0, 1, 1), bbox_image=(0, 0, 1, 1),
    )


def test_caption_label_format():
    assert _cap("figure", 1).label == "Fig. 1"
    assert _cap("table", 3).label == "Tab. 3"


def test_attach_references_picks_text_around_citation():
    captions = [_cap("figure", 1), _cap("table", 2)]
    blocks = [
        (1, "We illustrate the pipeline as shown in Figure 1, where the encoder ..."),
        (2, "The model achieves 95% accuracy as listed in Table 2 below."),
        (3, "Other unrelated content about Section 5."),
    ]
    _attach_references(captions, blocks)
    by_label = {c.label: c for c in captions}
    assert any("Figure 1" in r for r in by_label["Fig. 1"].references)
    assert any("Table 2" in r for r in by_label["Tab. 2"].references)


def test_attach_references_skips_caption_lines():
    captions = [_cap("figure", 1)]
    blocks = [
        (1, "Figure 1: Overview of the framework."),    # caption 自己
        (2, "We refer to Figure 1 for details."),       # 真引用
    ]
    _attach_references(captions, blocks)
    refs = captions[0].references
    assert len(refs) == 1
    assert "We refer to" in refs[0]


def test_caption_prefix_re_variants():
    cases = [
        ("Figure 1: Overview", True),
        ("Fig. 3: Results", True),
        ("Fig 7: items", True),
        ("Table 2: numbers", True),
        ("Tab. 5: ...", True),
        ("Section 3: Methodology", False),
        ("As shown in Figure 1, ...", False),
    ]
    for text, expected in cases:
        m = ce.CAPTION_PREFIX_RE.match(text)
        assert (m is not None) == expected, f"failed: {text}"
