"""Admin approval policy and rollback tests; real DB concurrency is separate."""
import copy
import os
from unittest.mock import MagicMock, patch

os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/test")
from fastapi.testclient import TestClient
import pytest
import routes
from services import order_review, order_holds, stores_mail_sync as sync, pg_store
from services.purchase_mail_items import analyze_purchase_items


ITEM = {"line_item_key": "NP-WF:1", "sku": "NP-WF", "product_type": "western_full", "quantity": 2}
REVIEW = {"status": "held", "review_version": 3, "reason": "purchase_details_conflict",
          "candidate": {"purchase_evidence": True, "payment_status": "paid", "hold_reason": None, "items": [ITEM]}}


@pytest.mark.parametrize("provider", ["stores", "payhip", "etsy"])
@pytest.mark.parametrize("sku,verified", [("NP-WF", True), ("NP-SFULL", False)])
def test_parser_evidence_survives_candidate_storage(provider, sku, verified):
    parsed = analyze_purchase_items(provider, "Purchase", f"Product: [{sku}]")
    assert isinstance(parsed["purchase_evidence"], list)
    con = MagicMock()
    order_holds.save_candidate(con, {**parsed, "provider": provider,
        "stores_order_no": "Fixture", "payment_status": "paid"})
    candidate = con.cursor.return_value.__enter__.return_value.execute.call_args.args[1][0].adapted
    assert candidate["purchase_evidence"] is verified
    if verified:
        assert order_review.validate_candidate(candidate) == parsed["line_items"]
    else:
        with pytest.raises(order_review.ReviewError, match="PURCHASE_EVIDENCE_REQUIRED"):
            order_review.validate_candidate(candidate)


@pytest.mark.parametrize("evidence", [None, False, [], "true", 1, [None], [""]])
def test_malformed_evidence_cannot_enable_approval(evidence):
    con = MagicMock()
    order_holds.save_candidate(con, {"provider": "payhip", "stores_order_no": "Fixture",
        "purchase_evidence": evidence, "payment_status": "paid", "line_items": [ITEM]})
    candidate = con.cursor.return_value.__enter__.return_value.execute.call_args.args[1][0].adapted
    assert candidate["purchase_evidence"] is False


@pytest.mark.parametrize("provider", ["stores", "payhip", "etsy"])
def test_admin_can_add_only_confirmed_missing_units_atomically(provider):
    con = MagicMock()
    cur = con.cursor.return_value.__enter__.return_value
    cur.fetchall.return_value = []
    saved = [{"line_item_key": "NP-WF:1", "sku": "NP-WF", "product_type": "western_full", "unit_index": 1,
              "status": "redeemed"}]
    with patch.object(order_review, "load_locked_review", return_value=(copy.deepcopy(REVIEW), saved)), patch.object(
        sync, "_upsert_order_entitlements") as grant, patch.object(order_holds, "resolve_hold") as resolve:
        result = order_review.approve(con, provider=provider, order_code="Fixture", expected_version=3)
    assert result["ok"] and not result["already_approved"]
    grant.assert_called_once()
    assert grant.call_args.args[1]["line_items"] == [ITEM]
    resolve.assert_called_once_with(con, provider=provider, order_code="Fixture", approved_version=3)
    con.commit.assert_called_once()
    con.rollback.assert_not_called()


@pytest.mark.parametrize("mutation,expected", [
    ("stale", "REVIEW_CHANGED"), ("unknown", "INVALID_REVIEW_ITEMS"),
    ("unpaid", "PURCHASE_EVIDENCE_REQUIRED"), ("no_evidence", "PURCHASE_EVIDENCE_REQUIRED"),
    ("zero", "INVALID_REVIEW_ITEMS"), ("bool_quantity", "INVALID_REVIEW_ITEMS"),
    ("duplicate", "INVALID_REVIEW_ITEMS"), ("changed_existing", "EXISTING_RIGHTS_CONFLICT"),
    ("removed_existing", "EXISTING_RIGHTS_CONFLICT"), ("issued", "ISSUED_CHARTS_CONFLICT"),
])
def test_invalid_or_changed_purchase_cannot_be_approved(mutation, expected):
    con = MagicMock()
    review, saved = copy.deepcopy(REVIEW), []
    con.cursor.return_value.__enter__.return_value.fetchall.return_value = []
    if mutation == "stale": review["review_version"] = 4
    if mutation == "unknown": review["candidate"]["items"][0]["sku"] = "NP-SFULL"
    if mutation == "unpaid": review["candidate"]["payment_status"] = "ordered"
    if mutation == "no_evidence": review["candidate"]["purchase_evidence"] = False
    if mutation == "zero": review["candidate"]["items"][0]["quantity"] = 0
    if mutation == "bool_quantity": review["candidate"]["items"][0]["quantity"] = True
    if mutation == "duplicate": review["candidate"]["items"].append(copy.deepcopy(ITEM))
    if mutation in {"changed_existing", "removed_existing"}:
        saved = [{"line_item_key": "NP-WF:1", "unit_index": 3 if mutation == "removed_existing" else 1,
                  "sku": "NP-WB" if mutation == "changed_existing" else "NP-WF", "product_type": "western_full"}]
    if mutation == "issued":
        con.cursor.return_value.__enter__.return_value.fetchall.return_value = [{"product_type": "western_full", "quantity": 3}]
    with patch.object(order_review, "load_locked_review", return_value=(review, saved)), patch.object(
        sync, "_upsert_order_entitlements") as grant, patch.object(order_holds, "resolve_hold") as resolve:
        with pytest.raises(order_review.ReviewError) as error:
            order_review.approve(con, provider="payhip", order_code="Fixture", expected_version=3)
    assert error.value.code == expected
    grant.assert_not_called()
    resolve.assert_not_called()
    con.commit.assert_not_called()
    con.rollback.assert_called_once()


def test_repeated_approval_is_idempotent():
    con = MagicMock()
    review = {**REVIEW, "status": "resolved", "approved_version": 3}
    with patch.object(order_review, "load_locked_review", return_value=(review, [])), patch.object(
        sync, "_upsert_order_entitlements") as grant, patch.object(order_holds, "resolve_hold") as resolve:
        assert order_review.approve(con, provider="payhip", order_code="Fixture", expected_version=3)["already_approved"]
    grant.assert_not_called()
    resolve.assert_not_called()


@pytest.mark.parametrize("failure_at", ["grant", "resolve", "commit"])
def test_approval_failures_roll_back_rights_and_hold_together(failure_at):
    con = MagicMock()
    con.cursor.return_value.__enter__.return_value.fetchall.return_value = []
    if failure_at == "commit": con.commit.side_effect = RuntimeError("fixture")
    with patch.object(order_review, "load_locked_review", return_value=(copy.deepcopy(REVIEW), [])), patch.object(
        sync, "_upsert_order_entitlements", side_effect=RuntimeError("fixture") if failure_at == "grant" else None
    ), patch.object(order_holds, "resolve_hold", side_effect=RuntimeError("fixture") if failure_at == "resolve" else None):
        with pytest.raises(RuntimeError):
            order_review.approve(con, provider="payhip", order_code="Fixture", expected_version=3)
    con.rollback.assert_called_once()


def test_held_redemption_blocks_both_existing_units_and_legacy_fallback():
    cur = MagicMock()
    cur.fetchone.side_effect = [{"entitlement_table": None, "marketplace_table": "orders", "hold_table": "holds"}, {"held": 1}]
    assert pg_store._claim_order_entitlement(cur, order_code="Fixture", provider="payhip",
                                             product_type="western_full", chart_token="T") == (True, None)
    assert not any("UPDATE" in call.args[0] for call in cur.execute.call_args_list)


def test_approval_requires_admin_token_before_database_access():
    with patch.dict(os.environ, {"API_KEY_ADMIN_TOKEN": "FixtureAdmin"}), patch.object(sync, "_get_conn") as connect:
        response = TestClient(routes.app).post("/internal/orders/holds/payhip/Fixture/approve",
                                               json={"confirm_order_code": "Fixture", "review_version": 3})
    assert response.status_code == 401
    connect.assert_not_called()


@pytest.mark.parametrize("payload,status", [
    ({"confirm_order_code": "Different", "review_version": 3}, 400),
    ({"confirm_order_code": "Fixture", "review_version": "3"}, 400),
    ({"confirm_order_code": "Fixture", "review_version": True}, 400),
])
def test_approval_requires_explicit_matching_order_confirmation(payload, status):
    with patch.dict(os.environ, {"API_KEY_ADMIN_TOKEN": "FixtureAdmin"}), patch.object(sync, "_get_conn") as connect:
        response = TestClient(routes.app).post("/internal/orders/holds/payhip/Fixture/approve", json=payload,
                                               headers={"X-Admin-Token": "FixtureAdmin"})
    assert response.status_code == status
    connect.assert_not_called()


def test_api_returns_conflict_without_private_exception_or_customer_data():
    con = MagicMock()
    with patch.dict(os.environ, {"API_KEY_ADMIN_TOKEN": "FixtureAdmin"}), patch.object(sync, "_get_conn", return_value=con), patch.object(
        order_review, "approve", side_effect=order_review.ReviewError("REVIEW_CHANGED")):
        response = TestClient(routes.app).post("/internal/orders/holds/payhip/Fixture/approve",
            json={"confirm_order_code": "Fixture", "review_version": 3}, headers={"X-Admin-Token": "FixtureAdmin"})
    assert response.status_code == 409
    con.close.assert_called_once()


def test_previously_processed_source_notification_cannot_reopen_approved_hold():
    con = MagicMock()
    row = {"provider": "payhip", "stores_order_no": "Fixture", "hold_reason": "unknown_product_code",
           "raw_message_id": "fixture-source"}
    with patch.object(order_holds, "remember_notice", return_value=False), patch.object(
        order_holds, "record_hold") as record, patch.object(order_holds, "save_candidate") as save, patch.object(
        sync, "_upsert_order_entitlements") as grant:
        assert sync._upsert_order(con, row) is False
    record.assert_not_called()
    save.assert_not_called()
    grant.assert_not_called()


def test_replay_fingerprint_includes_purchase_changes_and_never_saves_source_id():
    con = MagicMock()
    cur = con.cursor.return_value.__enter__.return_value
    row = {"provider": "payhip", "stores_order_no": "Fixture", "raw_message_id": "private-message-id",
           "line_items": [copy.deepcopy(ITEM)], "buyer_reference": "private@example.invalid"}
    order_holds.remember_notice(con, row)
    first = cur.execute.call_args.args[1]
    order_holds.remember_notice(con, row)
    assert cur.execute.call_args.args[1] == first
    row["line_items"][0]["quantity"] = 3
    order_holds.remember_notice(con, row)
    assert cur.execute.call_args.args[1] != first
    assert len(first[2]) == 64
    assert "private" not in str(cur.execute.call_args_list)


def test_source_id_missing_does_not_skip_new_evidence():
    con = MagicMock()
    assert order_holds.remember_notice(con, {"raw_message_id": None}) is True
    con.cursor.assert_not_called()
