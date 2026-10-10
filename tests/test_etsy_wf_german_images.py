from pathlib import Path

import pytest
from PIL import Image

from scripts.build_etsy_wf_german_images import build, render_planner_pages


def test_german_listing_image_builder_requires_real_planner_pages(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="German planner pages"):
        build(tmp_path / "missing", tmp_path / "output")


def test_german_planner_page_renderer_requires_source_pdf(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="German planner PDF"):
        render_planner_pages(tmp_path / "missing.pdf", tmp_path / "pages")


def test_german_listing_image_builder_writes_seven_marketing_images(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    for page in (4, 7, 10, 11, 14):
        Image.new("RGB", (1240, 1754), "white").save(source / f"page-{page:03d}.jpg")

    outputs = build(source, tmp_path / "output")

    assert len(outputs) == 7
    assert len({path.name for path in outputs}) == 7
    for path in outputs:
        assert path.exists()
        with Image.open(path) as image:
            assert image.mode == "RGB"
            assert image.size in {(1600, 1270), (2000, 2000)}
