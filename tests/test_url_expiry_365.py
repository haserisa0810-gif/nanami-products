from datetime import datetime, timedelta, timezone
import io
from pathlib import Path
from unittest.mock import Mock, patch
import zipfile

from fastapi import HTTPException
import pytest
import yaml

import routes
from services import mcp_chart_service, pg_store, planner_delivery
from services.chart_policy import CHART_EXPIRES_DAYS
from services.site_locales import CHART_EXTRA_UI
from tests.test_chart_download_zip import _download_request
from tests.test_light_yaml_transit_summary import _full_doc
from tests.test_planner_delivery import BIRTH, FIXTURE, _planner_request

ISSUED = datetime(2026, 1, 1, tzinfo=timezone.utc)
TOKEN = "syntheticexpiry365token"


class Clock(datetime):
    instant = ISSUED

    @classmethod
    def now(cls, tz=None):
        return cls.instant.astimezone(tz) if tz else cls.instant.replace(tzinfo=None)


@pytest.mark.parametrize("expiry", [None, ISSUED + timedelta(days=90), ISSUED + timedelta(days=500)])
@pytest.mark.parametrize("as_string", [False, True])
def test_web_mcp_share_policy_and_preserve_explicit_deadlines(expiry, as_string):
    chart = {"created_at": ISSUED.isoformat() if as_string else ISSUED,
             "expires_at": expiry.isoformat() if as_string and expiry else expiry}
    expected = expiry or ISSUED + timedelta(days=365)
    assert CHART_EXPIRES_DAYS == routes.CHART_EXPIRES_DAYS == mcp_chart_service.CHART_EXPIRES_DAYS == 365
    assert routes._chart_expiry(chart) == mcp_chart_service.chart_expiry(chart) == expected
    chart["options"] = {"expires_policy": "no_expiry"}
    assert routes._chart_expiry(chart) is mcp_chart_service.chart_expiry(chart) is None


def test_new_chart_and_addon_expire_at_365_days():
    Clock.instant = ISSUED
    with patch.object(routes, "datetime", Clock):
        assert routes._chart_expires_at() == routes._transit_addon_expires_at() == ISSUED + timedelta(days=365)


@pytest.mark.parametrize("seconds_before, expected", [(1, 200), (0, 410), (-1, 410)])
def test_chart_and_addon_stop_at_exact_expiry(seconds_before, expected):
    Clock.instant = ISSUED + timedelta(days=365, seconds=-seconds_before)
    chart = {"created_at": ISSUED.isoformat(), "yaml_text": "synthetic: true"}
    with patch.object(routes, "datetime", Clock), patch.object(pg_store, "get_chart", return_value=chart), patch.object(pg_store, "get_transit_addon_link", return_value=chart):
        if expected == 200:
            assert routes._load_chart_or_404(TOKEN) == chart
        else:
            with pytest.raises(HTTPException) as error:
                routes._load_chart_or_404(TOKEN)
            assert error.value.status_code == 410
        assert routes.transit_addon_yaml(TOKEN).status_code == expected


@pytest.mark.parametrize("no_expiry", [False, True])
def test_store_default_uses_365_only_for_ordinary_urls(no_expiry):
    cursor = Mock()
    with patch.object(pg_store, "_chart_columns", return_value={"expires_at"}):
        pg_store._insert_chart(cursor, token=TOKEN, order_code=None, buyer_name=None,
            birth_date="2000-01-01", birth_time=None, birth_place=None,
            options={"expires_policy": "no_expiry"} if no_expiry else {},
            yaml_text="synthetic: true", prompt_text="", share_yaml_text=None,
            horoscope_svg=None, shichusuimei_svg=None, expires_at=None)
    sql, values = cursor.execute.call_args.args
    assert ("INTERVAL '365 days'" in sql) is (not no_expiry)
    assert "90 days" not in sql and values[-1] is None


@pytest.mark.parametrize("lang", ["ja", "en", "es", "de"])
@pytest.mark.parametrize("no_expiry", [False, True])
def test_zip_deadline_copy_matches_policy_in_all_languages(lang, no_expiry):
    chart = {"options": {"product_type": "western_basic", "order_provider": "etsy",
                         "product_locale": lang, **({"expires_policy": "no_expiry"} if no_expiry else {})},
             "created_at": ISSUED, "yaml_text": yaml.safe_dump(_full_doc()), "prompt_text": ""}
    request = _download_request(TOKEN)
    request.scope["query_string"] = f"lang={lang}".encode()
    with patch.object(routes, "_load_chart_or_404", return_value=chart):
        response = routes.chart_download_zip(request, TOKEN)
    with zipfile.ZipFile(io.BytesIO(response.body)) as archive:
        readme = archive.read("README.txt").decode()
        url_copy = archive.read("CHART-PAGE-URL.txt").decode()
    assert "90" not in readme
    assert ("365" in readme) is (not no_expiry)
    if no_expiry:
        expected = {"ja": "有効期限はありません", "en": "does not expire", "es": "no caduca", "de": "läuft nicht ab"}[lang]
        assert expected in readme and expected in url_copy


@pytest.mark.parametrize("no_expiry", [False, True])
def test_planner_allows_repeated_downloads_while_valid_and_stops_at_expiry(no_expiry):
    text = FIXTURE.read_text(encoding="utf-8").replace("transit_long_term:", "transit:", 1).replace("days: 365", "days: 38", 1)
    chart = {"token": TOKEN, "created_at": ISSUED.isoformat(), "yaml_text": text,
             "options": {"product_type": "western_full", **({"expires_policy": "no_expiry"} if no_expiry else {})}}
    with patch.object(pg_store, "get_chart", return_value=chart), patch.object(routes, "datetime", Clock), patch.object(routes, "_build_personal_planner_pdf", return_value=b"%PDF-synthetic") as build:
        Clock.instant = ISSUED + timedelta(days=365, seconds=-1)
        for _ in range(2):
            assert routes.chart_planner_pdf(_planner_request(TOKEN), TOKEN).status_code == 200
        Clock.instant = ISSUED + timedelta(days=365)
        if no_expiry:
            assert routes.chart_planner_pdf(_planner_request(TOKEN), TOKEN).status_code == 200
        else:
            with pytest.raises(HTTPException) as error:
                routes.chart_planner_pdf(_planner_request(TOKEN), TOKEN)
            assert error.value.status_code == 410
        assert build.call_count == (3 if no_expiry else 2)


def test_planner_refreshes_stored_long_term_period_each_month():
    chart = {"token": TOKEN, "yaml_text": FIXTURE.read_text(encoding="utf-8")}
    with patch.object(routes, "datetime", Clock), patch.object(routes, "build_planner_yaml_from_natal_yaml", return_value="fresh: true") as refresh, patch.object(routes, "build_planner_pdf_from_yaml", return_value=b"%PDF-synthetic") as render:
        for month in (1, 2):
            Clock.instant = ISSUED.replace(month=month, day=20)
            assert routes._build_personal_planner_pdf(chart, lang="ja") == b"%PDF-synthetic"
            assert refresh.call_args.kwargs["transit_start_date"] == ISSUED.replace(month=month)
            assert refresh.call_args.kwargs["months"] == render.call_args.kwargs["months"] == 12
            assert render.call_args.kwargs["yaml_text"] == "fresh: true"


def test_birth_input_planner_also_starts_at_each_generation_month():
    doc = {"systems": {"western": {"transit": {"items": []}}}}
    with patch.object(planner_delivery, "datetime", Clock), patch.object(planner_delivery, "build_product_yaml", side_effect=lambda **kwargs: ("", "", doc)) as calculate, patch.object(planner_delivery, "build_ai_long_term_transits_yaml", return_value="fresh: true"), patch.object(planner_delivery, "build_planner_pdf_from_yaml", return_value=b"%PDF-synthetic") as render:
        for month in (1, 2):
            Clock.instant = ISSUED.replace(month=month, day=20)
            assert planner_delivery.build_planner_pdf(**BIRTH) == b"%PDF-synthetic"
            assert calculate.call_args.kwargs["transit_start_date"] == ISSUED.replace(month=month)
            assert render.call_args.kwargs["months"] == 12


def test_current_guide_sources_and_runtime_copy_do_not_reintroduce_90_days():
    root = Path(__file__).resolve().parents[1]
    files = ["routes.py", "services/site_locales.py", "templates/yaml_form.html",
             "scripts/build_etsy_full_access_guides.py", "scripts/build_etsy_wbt_guide.py",
             "scripts/build_marketplace_product_guides.py", "scripts/build_coconala_product_guides.py"]
    for name in files:
        text = (root / name).read_text(encoding="utf-8")
        for old in ("90日", "90 days", "90 días", "90 Tage"):
            assert old not in text, name
    for lang in ("ja", "en", "es", "de"):
        assert "12" in CHART_EXTRA_UI[lang]["planner_hint"]
