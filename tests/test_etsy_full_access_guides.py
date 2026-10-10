from scripts.build_etsy_full_access_guides import LOCALES, access_url, output_path


def test_etsy_full_access_guides_cover_all_supported_languages() -> None:
    assert set(LOCALES) == {"ja", "en", "es", "de"}
    for lang in LOCALES:
        assert access_url(lang) == (
            "https://chart.nanami-astro.com/redeem/western-full"
            f"?lang={lang}&provider=etsy"
        )
        assert output_path(lang).name.endswith(f"_{lang.upper()}.pdf")


def test_paid_full_guides_do_not_name_museum_or_claim_acg_is_included() -> None:
    for copy in LOCALES.values():
        visible_copy = " ".join(
            str(value) if not isinstance(value, list) else " ".join(value)
            for value in copy.values()
        )
        assert "Museum" not in visible_copy
        assert "ACG" in visible_copy
        assert "31" in visible_copy
        assert "12" in visible_copy
