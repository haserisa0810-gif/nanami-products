from __future__ import annotations

import re
from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader

from routes import I18N


@pytest.mark.parametrize("template_name", ["redeem_shichu.html", "redeem_western_basic.html"])
@pytest.mark.parametrize("label", ["北海道", "Hokkaido"])
def test_redeem_prefecture_uses_label_and_submits_value(template_name: str, label: str) -> None:
    templates_dir = Path(__file__).resolve().parents[1] / "templates"
    template = Environment(loader=FileSystemLoader(templates_dir)).get_template(template_name)
    html = template.render(
        lang="ja",
        lang_urls={"ja": "", "en": "", "es": "", "de": ""},
        asset_url=lambda path: path,
        prefectures=[{"value": "北海道", "label": label}],
        form={"prefecture": "北海道"},
        product={"label": ""},
        product_type="western_basic",
        t=I18N["ja"],
    )

    assert re.search(rf'<option value="北海道"\s+selected>{label}</option>', html)
    assert "{'value':" not in html
