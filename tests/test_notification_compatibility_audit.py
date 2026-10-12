"""Release checks, including regressions for the two notification defects."""
import os
from unittest.mock import patch

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/test")
import routes
from services import stores_mail_sync as sync
from test_product_catalog import EXISTING


@pytest.mark.parametrize("code,product_type", EXISTING.items())
@pytest.mark.parametrize("provider", ["stores", "etsy", "payhip"])
def test_registered_code_still_authorizes_only_its_saved_product(code, product_type, provider):
    row = {"provider": provider, "stores_order_no": "9123456789", "sku": code,
           "product_type": product_type, "payment_status": "paid"}
    with patch.object(sync, "verify_order_entitlement", return_value=("ok", row)):
        status, _, error, http_status = routes._check_order_for_redeem(
            order_id="9123456789", provider=provider, product_type=product_type)
    assert status == "ok" and error is None and http_status == 200
    other = "western_basic" if product_type != "western_basic" else "western_full"
    with patch.object(sync, "verify_order_entitlement", return_value=("ok", row)):
        result = routes._check_order_for_redeem(
            order_id="9123456789", provider=provider, product_type=other)
    assert result[0] == "product_mismatch" and result[3] == 409


@pytest.mark.parametrize("code", ["NP-WB", "NP-WF", "NP-AA", "NP-TA"])
def test_payhip_known_selection_remains_consistent_with_saved_purchase(code):
    expected = routes.PAYHIP_PRODUCTS[code]["product_type"]
    metadata, error = routes._payhip_metadata_from_form(
        payhip_email="fixture@example.invalid", payhip_product_code=code,
        payhip_order_id="FixtureOrder", expected_product_type=expected)
    assert error is None and metadata["selected_product_type"] == expected
    row = {"provider": "payhip", "stores_order_no": "FixtureOrder",
           "product_type": expected, "payment_status": "paid", "sku": code}
    assert routes._check_payhip_order_row_for_redeem(
        order_id="FixtureOrder", order_row=row, product_type=expected)[3] == 200


def test_guidance_codes_do_not_grant_extra_purchases():
    # Synthetic counterexample, not copied customer mail. The actual 3 notices
    # with multiple unlabeled codes still need an independent purchase oracle.
    body = ("Order ID: FixtureOrder\nProduct: [NP-WF] Full\nQuantity: 1\n"
            "Other products available:\n[NP-WB] Core\n[NP-AA] Add-on\n[NP-TA] Add-on")
    items = sync._parse_payhip_mail("You've Sold An Item!", body, None, None, "contact@payhip.com")["line_items"]
    assert [item["sku"] for item in items] == ["NP-WF"]


def test_unknown_payhip_form_code_is_rejected_at_input():
    _, error = routes._payhip_metadata_from_form(
        payhip_email="fixture@example.invalid", payhip_product_code="NP-SFULL",
        payhip_order_id="FixtureOrder", expected_product_type="western_full")
    assert error is not None
