"""Tests for ft-019 caption_extractor (搬迁自 interpret/caption_extractor)."""
from __future__ import annotations

from apps.extract import caption_extractor as ce
from apps.extract.caption_extractor import Caption, _attach_references


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
    ]
    _attach_references(captions, blocks)
    by_label = {c.label: c for c in captions}
    assert any("Figure 1" in r for r in by_label["Fig. 1"].references)
    assert any("Table 2" in r for r in by_label["Tab. 2"].references)


def test_attach_references_skips_caption_lines():
    captions = [_cap("figure", 1)]
    blocks = [
        (1, "Figure 1: Overview of the framework."),
        (2, "We refer to Figure 1 for details."),
    ]
    _attach_references(captions, blocks)
    refs = captions[0].references
    assert len(refs) == 1
    assert "We refer to" in refs[0]


def test_caption_prefix_re_variants():
    cases = [
        ("Figure 1: Overview", True),
        ("Fig. 3: Results", True),
        ("Table 2: numbers", True),
        ("Section 3: Methodology", False),
        ("As shown in Figure 1, ...", False),
    ]
    for text, expected in cases:
        assert (ce.CAPTION_PREFIX_RE.match(text) is not None) == expected, text
