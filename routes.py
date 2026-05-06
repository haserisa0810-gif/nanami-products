from __future__ import annotations

import hashlib
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import Body, FastAPI, Form, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from services import pg_store, stores_mail_sync
from services.api_calc import calc_combined_api, calc_shichu_api, calc_transit_api, calc_western_api
from services.location import PREFECTURE_OPTIONS
from services.transit_yaml import build_transit_only_yaml
from services.yaml_exporter import build_product_yaml

app = FastAPI(title="nanami-products")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

API_CREDIT_COSTS = {
    "western": 1,
    "shichu": 1,
    "transit": 1,
    "combined": 3,
}
API_RATE_LIMIT_WINDOWS = {
    "minute": 60,
    "day": 86400,
}
API_DEMO_REQUIRED_FIELDS = {
    "western": ["birth_date", "birth_place"],
    "shichu": ["birth_date", "birth_place"],
    "transit": ["birth_date", "birth_place", "target_date"],
    "combined": ["birth_date", "birth_place", "target_date"],
}
API_KEY_PRODUCT_TYPES = {"api_key", "api_key_trial", "api_key_standard", "api_credits"}


PRODUCT_CONFIG = {
    "western_basic": {
        "label": "ホロスコープ基本版",
        "description": "西洋占星術の出生図データを生成します。小惑星・四柱推命・日替わり境界の選択項目は表示しません。",
        "features": [
            "西洋占星術の出生図データ",
            "小惑星オプションなし",
            "四柱推命なし",
            "トランジットなし",
        ],
        "include_asteroids": False,
        "include_shichusuimei": False,
        "include_transit": False,
    },
    "western_full": {
        "label": "ホロスコープFULL版",
        "description": "小惑星とトランジット（1ヶ月）をセットで含めます。購入者側での選択は不要です。",
        "features": [
            "西洋占星術の出生図データ",
            "小惑星込み",
            "トランジット（1ヶ月）込み",
            "四柱推命なし",
        ],
        "include_asteroids": True,
        "include_shichusuimei": False,
        "include_transit": True,
    },
    "shichu": {
        "label": "四柱推命版",
        "description": "四柱推命データを生成します。日替わり境界は、購入者が23時または1時から選択できます。",
        "features": [
            "四柱推命データ",
            "日替わり境界を選択可能",
            "標準選択は1時（丑の刻）",
            "小惑星・トランジットなし",
        ],
        "include_asteroids": False,
        "include_shichusuimei": True,
        "include_transit": False,
    },
    "transit_yaml": {
        "label": "トランジットYAML版",
        "description": "歴史イベント・特定日時・特定場所の、その瞬間の天体配置だけをYAML化します。",
        "features": [
            "出生情報なし",
            "イベント日時・場所の天体配置",
            "Julian / Gregorian 暦選択",
            "月相・主要アスペクト込み",
        ],
        "include_asteroids": False,
        "include_shichusuimei": False,
        "include_transit": True,
    },
}


def _product_type_from_request(request: Request) -> str:
    product_type = request.query_params.get("type", "western_basic").strip()
    if product_type not in PRODUCT_CONFIG:
        product_type = "western_basic"
    return product_type


def _product_context(product_type: str) -> dict:
    config = PRODUCT_CONFIG.get(product_type, PRODUCT_CONFIG["western_basic"])
    return {"product_type": product_type, "product": config}


def _buyer_template(prefix: str, product_type: str) -> str:
    if product_type not in PRODUCT_CONFIG:
        product_type = "western_basic"
    return f"{prefix}_{product_type}.html"


def _truthy(value: str | None) -> bool:
    return str(value).strip().lower() in {"1", "true", "on", "yes", "23"}


def _normalize_stores_order_no(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def _product_label(product_type: str | None) -> str:
    if product_type == "api_key_trial":
        return "お試しAPIクレジット"
    if product_type == "api_key_standard":
        return "APIクレジット"
    if product_type in API_KEY_PRODUCT_TYPES:
        return "APIキー"
    if product_type and product_type in PRODUCT_CONFIG:
        return PRODUCT_CONFIG[product_type]["label"]
    return "購入商品"


def _env_int(name: str, default: int) -> int:
    try:
        return max(0, int(os.getenv(name, str(default))))
    except ValueError:
        return default


def _api_key_issue_credits(product_type: str | None = None) -> int:
    fallback = _env_int("API_KEY_ISSUE_CREDITS", 20)
    if product_type == "api_key_trial":
        return _env_int("API_KEY_ISSUE_CREDITS_TRIAL", 5)
    if product_type == "api_key_standard":
        return _env_int("API_KEY_ISSUE_CREDITS_STANDARD", 20)
    return fallback


def _parse_optional_float(value: str, field_name: str) -> float | None:
    raw = value.strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"{field_name}は数値で入力してください。") from exc


def _validate_lat_lon(lat: float, lon: float) -> None:
    if not (-90 <= lat <= 90):
        raise ValueError("緯度は -90 から 90 の範囲で入力してください。")
    if not (-180 <= lon <= 180):
        raise ValueError("経度は -180 から 180 の範囲で入力してください。")


def _build_birth_location(
    *,
    prefecture: str,
    birth_place_kind: str,
    birth_place_overseas: str,
    birth_lat: str,
    birth_lng: str,
    birth_timezone: str,
) -> dict[str, object]:
    kind = birth_place_kind.strip().lower() or "domestic"
    if kind == "overseas":
        place = birth_place_overseas.strip()
        if not place:
            raise ValueError("海外出生の場合は出生地名を入力してください。")
        tz_name = birth_timezone.strip()
        if not tz_name:
            raise ValueError("海外出生の場合はタイムゾーンを入力してください。")
        try:
            tz = ZoneInfo(tz_name)
        except Exception as exc:
            raise ValueError("タイムゾーンが正しくありません。例: America/New_York") from exc
        lat = _parse_optional_float(birth_lat, "緯度")
        lon = _parse_optional_float(birth_lng, "経度")
        if lat is None or lon is None:
            raise ValueError("海外出生の場合は緯度・経度を入力してください。")
        _validate_lat_lon(lat, lon)
        return {
            "kind": "overseas",
            "birth_place": place,
            "prefecture": place,
            "lat": lat,
            "lng": lon,
            "tz_name": tz_name,
            "tz": tz,
        }

    pref_name = prefecture.strip()
    if not pref_name:
        raise ValueError("出生都道府県を選択してください。")
    return {
        "kind": "domestic",
        "birth_place": pref_name,
        "prefecture": pref_name,
        "lat": None,
        "lng": None,
        "tz_name": "Asia/Tokyo",
        "tz": ZoneInfo("Asia/Tokyo"),
    }


@app.on_event("startup")
def startup() -> None:
    # Cloud Run の起動ヘルスチェックをDB接続待ちで落とさないため、
    # 起動時DB初期化は行わない。DBテーブルは /internal/init-db で手動初期化する。
    import logging
    logging.info("nanami-products startup: skip DB init for fast Cloud Run boot")


@app.post("/internal/init-db")
def internal_init_db(request: Request):
    expected = os.getenv("STORES_MAIL_SYNC_TOKEN", "").strip()
    if expected:
        auth = request.headers.get("Authorization", "")
        token = auth.removeprefix("Bearer ").strip()
        if token != expected:
            raise HTTPException(status_code=401, detail="unauthorized")
    if not os.environ.get("DATABASE_URL"):
        raise HTTPException(status_code=500, detail="DATABASE_URL が未設定です")
    pg_store.init_db()
    stores_mail_sync.ensure_table()
    return {"ok": True, "message": "DB initialized"}


def _admin_token_from_env() -> str:
    return (
        os.getenv("API_KEY_ADMIN_TOKEN", "").strip()
        or os.getenv("STORES_MAIL_SYNC_TOKEN", "").strip()
    )


def _admin_test_site_path() -> str:
    configured = os.getenv("ADMIN_TEST_SITE_PATH", "").strip()
    if configured:
        path = configured if configured.startswith("/") else f"/{configured}"
        return path.rstrip("/") or "/admin/test-site"

    token = _admin_token_from_env()
    if token:
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()[:20]
        return f"/admin/{digest}/test-site"

    return "/admin/test-site"


ADMIN_TEST_SITE_PATH = _admin_test_site_path()


def _is_local_request(request: Request) -> bool:
    host = request.client.host if request.client else ""
    return host in {"127.0.0.1", "::1", "localhost"}


def _admin_access_error(request: Request) -> JSONResponse | None:
    expected = _admin_token_from_env()
    if expected:
        token = request.headers.get("X-Admin-Token", "").strip()
        if token != expected:
            return _api_error("UNAUTHORIZED", "X-Admin-Token is invalid", 401)
    elif not _is_local_request(request):
        return _api_error("UNAUTHORIZED", "API key admin access requires an admin token", 401)
    return None


@app.post("/internal/api-keys")
def internal_create_api_key(request: Request, payload: dict[str, object] = Body(default={})):
    error = _admin_access_error(request)
    if error:
        return error

    label = str(payload.get("label") or "test-site").strip() or "test-site"
    status = str(payload.get("status") or "active").strip().lower()
    if status not in {"active", "inactive"}:
        return _api_error("INVALID_INPUT", "status must be active or inactive", 400)
    try:
        credits = int(payload.get("credits") or 100)
    except (TypeError, ValueError):
        return _api_error("INVALID_INPUT", "credits must be an integer", 400)
    if credits < 0:
        return _api_error("INVALID_INPUT", "credits must be 0 or greater", 400)

    try:
        row = pg_store.create_api_key(label=label, credits=credits, status=status)
    except Exception as exc:
        return _api_error("API_KEY_CREATE_FAILED", str(exc), 500)

    return JSONResponse(
        {
            "ok": True,
            "api_key": row["api_key"],
            "api_key_record": {
                "id": row["id"],
                "key_prefix": row["key_prefix"],
                "label": row["label"],
                "status": row["status"],
                "credits_remaining": row["credits_remaining"],
                "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
            },
        }
    )


@app.post("/internal/api-keys/lookup")
def internal_lookup_api_key(request: Request, payload: dict[str, object] = Body(default={})):
    error = _admin_access_error(request)
    if error:
        return error

    order_code_clean = _normalize_stores_order_no(str(payload.get("order_code") or ""))
    if not order_code_clean:
        return _api_error("INVALID_INPUT", "order_code is required", 400)
    if not re.fullmatch(r"\d{10}", order_code_clean):
        return _api_error("INVALID_INPUT", "order_code must be 10 digits", 400)

    row = pg_store.get_api_key_by_order_code(order_code_clean)
    if not row:
        return _api_error("API_KEY_NOT_FOUND", "api key was not found for this order_code", 404)
    return JSONResponse({"ok": True, "found": True, "api_key_record": row})


@app.post("/internal/api-keys/reissue")
def internal_reissue_api_key(request: Request, payload: dict[str, object] = Body(default={})):
    error = _admin_access_error(request)
    if error:
        return error

    order_code_clean = _normalize_stores_order_no(str(payload.get("order_code") or ""))
    if not order_code_clean:
        return _api_error("INVALID_INPUT", "order_code is required", 400)
    if not re.fullmatch(r"\d{10}", order_code_clean):
        return _api_error("INVALID_INPUT", "order_code must be 10 digits", 400)

    label = str(payload.get("label") or "").strip() or None
    owner_email = str(payload.get("email") or "").strip() or None
    credits_value = payload.get("credits")
    credits = None
    if credits_value not in (None, ""):
        try:
            credits = max(0, int(credits_value))
        except (TypeError, ValueError):
            return _api_error("INVALID_INPUT", "credits must be an integer", 400)

    current = pg_store.get_api_key_by_order_code(order_code_clean)
    if current:
        try:
            result = pg_store.reissue_api_key(
                order_code=order_code_clean,
                credits=credits,
                owner_email=owner_email or current.get("owner_email"),
                label=label or current.get("label"),
            )
        except Exception as exc:
            return _api_error("API_KEY_REISSUE_FAILED", str(exc), 500)
        return JSONResponse(
            {
                "ok": True,
                "reissued": True,
                "old_api_key_record": result["old_record"],
                "api_key": result["api_key"],
                "api_key_record": result["record"],
            }
        )

    try:
        status, order_row = stores_mail_sync.verify_order_no(order_code_clean)
        if status == "not_found" and _truthy(os.getenv("STORES_MAIL_SYNC_ON_SUBMIT", "1")):
            try:
                submit_limit = int(os.getenv("STORES_MAIL_SYNC_SUBMIT_LIMIT", "100"))
            except ValueError:
                submit_limit = 100
            stores_mail_sync.sync(limit=submit_limit)
            status, order_row = stores_mail_sync.verify_order_no(order_code_clean)
    except Exception as exc:
        return _api_error("ORDER_LOOKUP_FAILED", str(exc), 500)

    if status == "not_found":
        return _api_error("ORDER_NOT_FOUND", "order_code was not found", 404)
    if status == "cancelled":
        return _api_error("ORDER_CANCELLED", "this order cannot be used", 409)
    if status == "already_used":
        return _api_error("ORDER_ALREADY_USED", "this order was used for chart issuance", 409)

    purchased_type = (order_row or {}).get("product_type")
    if purchased_type and purchased_type not in API_KEY_PRODUCT_TYPES:
        return _api_error("INVALID_ORDER_TYPE", "this order is not an API key product", 409)
    if not purchased_type and status != "reusable":
        return _api_error("INVALID_ORDER_TYPE", "unable to determine API key product type", 409)

    issue_credits = credits if credits is not None else _api_key_issue_credits(str(purchased_type) if purchased_type else None)
    try:
        result = pg_store.create_api_key(
            label=label or f"reissue_{order_code_clean}",
            credits=issue_credits,
            status="active",
            owner_email=owner_email or None,
            order_code=order_code_clean if status != "reusable" else None,
        )
    except Exception as exc:
        return _api_error("API_KEY_CREATE_FAILED", str(exc), 500)

    return JSONResponse(
        {
            "ok": True,
            "reissued": False,
            "api_key": result["api_key"],
            "api_key_record": {
                "id": result["id"],
                "key_prefix": result["key_prefix"],
                "label": result["label"],
                "status": result["status"],
                "credits_remaining": result["credits_remaining"],
                "order_code": result["order_code"],
                "created_at": result["created_at"].isoformat() if result.get("created_at") else None,
            },
        }
    )


@app.get("/healthz")
def healthz():
    return {"ok": True, "service": "nanami-products"}


# ─── 計算結果API ────────────────────────────────────────────────


def _api_error(code: str, message: str, status_code: int) -> JSONResponse:
    return JSONResponse(
        {"ok": False, "error": {"code": code, "message": message}},
        status_code=status_code,
    )


def _api_rate_limits(endpoint: str) -> list[tuple[str, int, int, str | None]]:
    limits: list[tuple[str, int, int, str | None]] = [
        (
            "per_minute",
            API_RATE_LIMIT_WINDOWS["minute"],
            _env_int("API_RATE_LIMIT_PER_MINUTE", 10),
            None,
        ),
        (
            "per_day",
            API_RATE_LIMIT_WINDOWS["day"],
            _env_int("API_RATE_LIMIT_PER_DAY", 200),
            None,
        ),
    ]
    if endpoint == "combined":
        limits.extend(
            [
                (
                    "combined_per_minute",
                    API_RATE_LIMIT_WINDOWS["minute"],
                    _env_int("API_RATE_LIMIT_COMBINED_PER_MINUTE", 3),
                    "combined",
                ),
                (
                    "combined_per_day",
                    API_RATE_LIMIT_WINDOWS["day"],
                    _env_int("API_RATE_LIMIT_COMBINED_PER_DAY", 50),
                    "combined",
                ),
            ]
        )
    return limits


def _check_api_rate_limit(*, api_key_id: int, endpoint: str) -> tuple[bool, str | None, int | None]:
    for label, seconds, limit, endpoint_filter in _api_rate_limits(endpoint):
        if limit <= 0:
            continue
        used = pg_store.count_api_usage_since(
            api_key_id=api_key_id,
            seconds=seconds,
            endpoint=endpoint_filter,
        )
        if used >= limit:
            return False, label, limit
    return True, None, None


def _demo_response(endpoint: str, payload: dict[str, object]) -> JSONResponse:
    missing = [
        field
        for field in API_DEMO_REQUIRED_FIELDS[endpoint]
        if payload.get(field) in (None, "") or not str(payload.get(field)).strip()
    ]
    if missing:
        return _api_error(
            "INVALID_INPUT",
            f"Required fields are missing: {', '.join(missing)}",
            400,
        )

    response = {
        "ok": True,
        "meta": {
            "api_version": "1.0",
            "engine": "nanami-products",
            "endpoint": endpoint,
            "mode": "demo",
            "mock": True,
        },
        "input": payload,
        "raw_data": {
            "western": {
                "natal": {
                    "bodies": {
                        "Sun": {"sign_ja": "山羊座", "degree": 10.5, "house": 10},
                        "Moon": {"sign_ja": "牡牛座", "degree": 2.1, "house": 2},
                    },
                    "houses": {"1": {"sign_ja": "牡羊座", "degree": 0}},
                    "aspects": [{"body1": "Sun", "aspect": "trine", "body2": "Moon", "orb": 1.2}],
                }
            } if endpoint in {"western", "combined"} else None,
            "shichu": {
                "summary": {"day_master": "庚", "sample": True}
            } if endpoint in {"shichu", "combined"} else None,
            "transit": {
                "days": [{"date": str(payload.get("target_date") or "2026-05-01"), "active_aspects": []}]
            } if endpoint in {"transit", "combined"} else None,
        },
        "interpreted_tags": {
            "western": [],
            "shichu": [],
            "transit": [],
            "integration": [],
        },
        "writing_hints": {
            "key_concepts": ["demo"],
        },
        "handoff_yaml": f"mock: true\nendpoint: {endpoint}\n",
    }
    return JSONResponse(response)


def _handle_calc_api(
    *,
    endpoint: str,
    payload: dict[str, object],
    api_key: str | None,
    calc_func,
) -> JSONResponse:
    credits_required = API_CREDIT_COSTS[endpoint]

    if not api_key:
        try:
            pg_store.log_api_usage(
                api_key_id=None,
                endpoint=endpoint,
                credits_used=0,
                status="rejected",
                error_code="MISSING_API_KEY",
            )
        except Exception:
            pass
        return _api_error("MISSING_API_KEY", "X-API-Key header is required", 401)

    try:
        key_row = pg_store.get_api_key_for_auth(api_key)
    except Exception as exc:
        return _api_error("API_AUTH_UNAVAILABLE", f"API authentication failed: {exc}", 500)

    if not key_row:
        try:
            pg_store.log_api_usage(
                api_key_id=None,
                endpoint=endpoint,
                credits_used=0,
                status="rejected",
                error_code="INVALID_API_KEY",
            )
        except Exception:
            pass
        return _api_error("INVALID_API_KEY", "API key is invalid", 401)

    api_key_id = int(key_row["id"])
    if key_row.get("status") != "active":
        pg_store.log_api_usage(
            api_key_id=api_key_id,
            endpoint=endpoint,
            credits_used=0,
            status="rejected",
            error_code="API_KEY_INACTIVE",
        )
        return _api_error("API_KEY_INACTIVE", "API key is not active", 403)

    try:
        rate_allowed, rate_label, rate_limit = _check_api_rate_limit(api_key_id=api_key_id, endpoint=endpoint)
    except Exception as exc:
        return _api_error("API_RATE_LIMIT_UNAVAILABLE", f"API rate limit check failed: {exc}", 500)
    if not rate_allowed:
        pg_store.log_api_usage(
            api_key_id=api_key_id,
            endpoint=endpoint,
            credits_used=0,
            status="rejected",
            error_code=f"RATE_LIMIT_{rate_label}".upper(),
        )
        return _api_error(
            "RATE_LIMIT_EXCEEDED",
            f"API rate limit exceeded ({rate_label}: {rate_limit})",
            429,
        )

    credits_remaining = int(key_row.get("credits_remaining") or 0)
    if credits_remaining < credits_required:
        pg_store.log_api_usage(
            api_key_id=api_key_id,
            endpoint=endpoint,
            credits_used=0,
            status="rejected",
            error_code="INSUFFICIENT_CREDITS",
        )
        return _api_error("INSUFFICIENT_CREDITS", "Not enough credits remaining", 402)

    try:
        usage_id = pg_store.log_api_usage(
            api_key_id=api_key_id,
            endpoint=endpoint,
            credits_used=0,
            status="accepted",
            error_code=None,
        )
    except Exception as exc:
        return _api_error("API_USAGE_LOG_UNAVAILABLE", f"API usage logging failed: {exc}", 500)

    body, status_code = calc_func(payload)
    if status_code < 200 or status_code >= 300 or not body.get("ok"):
        error = body.get("error") if isinstance(body, dict) else None
        error_code = error.get("code") if isinstance(error, dict) else "API_ERROR"
        pg_store.update_api_usage(
            usage_id=usage_id,
            credits_used=0,
            status="error",
            error_code=str(error_code),
        )
        return JSONResponse(body, status_code=status_code)

    consumed = pg_store.consume_api_credits(api_key_id=api_key_id, credits=credits_required)
    if not consumed:
        pg_store.update_api_usage(
            usage_id=usage_id,
            credits_used=0,
            status="rejected",
            error_code="INSUFFICIENT_CREDITS",
        )
        return _api_error("INSUFFICIENT_CREDITS", "Not enough credits remaining", 402)

    pg_store.update_api_usage(
        usage_id=usage_id,
        credits_used=credits_required,
        status="success",
        error_code=None,
    )
    return JSONResponse(body, status_code=status_code)


@app.post("/api/demo/western")
def api_demo_western(payload: dict[str, object] = Body(...)):
    return _demo_response("western", payload)


@app.post("/api/demo/shichu")
def api_demo_shichu(payload: dict[str, object] = Body(...)):
    return _demo_response("shichu", payload)


@app.post("/api/demo/transit")
def api_demo_transit(payload: dict[str, object] = Body(...)):
    return _demo_response("transit", payload)


@app.post("/api/demo/combined")
def api_demo_combined(payload: dict[str, object] = Body(...)):
    return _demo_response("combined", payload)


@app.post("/api/calc/western")
def api_calc_western(
    payload: dict[str, object] = Body(...),
    x_api_key: str | None = Header(None, alias="X-API-Key"),
):
    return _handle_calc_api(
        endpoint="western",
        payload=payload,
        api_key=x_api_key,
        calc_func=calc_western_api,
    )


@app.post("/api/calc/shichu")
def api_calc_shichu(
    payload: dict[str, object] = Body(...),
    x_api_key: str | None = Header(None, alias="X-API-Key"),
):
    return _handle_calc_api(
        endpoint="shichu",
        payload=payload,
        api_key=x_api_key,
        calc_func=calc_shichu_api,
    )


@app.post("/api/calc/transit")
def api_calc_transit(
    payload: dict[str, object] = Body(...),
    x_api_key: str | None = Header(None, alias="X-API-Key"),
):
    return _handle_calc_api(
        endpoint="transit",
        payload=payload,
        api_key=x_api_key,
        calc_func=calc_transit_api,
    )


@app.post("/api/calc/combined")
def api_calc_combined(
    payload: dict[str, object] = Body(...),
    x_api_key: str | None = Header(None, alias="X-API-Key"),
):
    return _handle_calc_api(
        endpoint="combined",
        payload=payload,
        api_key=x_api_key,
        calc_func=calc_combined_api,
    )


@app.get("/api-sandbox", response_class=HTMLResponse)
def api_sandbox(request: Request):
    return templates.TemplateResponse("api_sandbox.html", {"request": request})


@app.get("/manual/api", response_class=HTMLResponse)
def api_manual(request: Request):
    return templates.TemplateResponse("nanami_api_spec.html", {"request": request})


# ─── APIキー購入者発行フロー ───────────────────────────────────

@app.get("/api-key/start", response_class=HTMLResponse)
def api_key_start(request: Request):
    return templates.TemplateResponse(
        "api_key_start.html",
        {
            "request": request,
            "error": None,
            "form": None,
            "default_credits": _api_key_issue_credits(),
            "trial_credits": _api_key_issue_credits("api_key_trial"),
            "standard_credits": _api_key_issue_credits("api_key_standard"),
        },
    )


@app.get("/manual/api-key/start")
def api_key_start_manual_legacy():
    return RedirectResponse("/api-key/start", status_code=301)


@app.post("/api-key/redeem", response_class=HTMLResponse)
def api_key_redeem(
    request: Request,
    order_code: str = Form(...),
    email: str = Form(""),
    agree_final: str | None = Form(None),
):
    order_code_clean = _normalize_stores_order_no(order_code)
    form = {"order_code": order_code, "email": email, "agree_final": bool(agree_final)}

    def _render_error(message: str, status_code: int = 400):
        return templates.TemplateResponse(
            "api_key_start.html",
            {
                "request": request,
                "error": message,
                "form": form,
                "default_credits": _api_key_issue_credits(),
                "trial_credits": _api_key_issue_credits("api_key_trial"),
                "standard_credits": _api_key_issue_credits("api_key_standard"),
            },
            status_code=status_code,
        )

    if not order_code_clean:
        return _render_error("STORESオーダー番号を入力してください。")
    if not re.fullmatch(r"\d{10}", order_code_clean):
        return _render_error("STORESオーダー番号は10桁の数字で入力してください。")
    if not agree_final:
        return _render_error("APIキーは一度だけ表示されることを確認し、チェックを入れてください。")
    if not os.environ.get("DATABASE_URL"):
        return _render_error("DATABASE_URL が未設定のためAPIキーを発行できません。", 500)

    existing = pg_store.get_api_key_by_order_code(order_code_clean)
    if existing:
        return templates.TemplateResponse(
            "api_key_result.html",
            {
                "request": request,
                "api_key": None,
                "record": existing,
                "already_issued": True,
            },
            status_code=409,
        )

    try:
        status, order_row = stores_mail_sync.verify_order_no(order_code_clean)
        if status == "not_found" and _truthy(os.getenv("STORES_MAIL_SYNC_ON_SUBMIT", "1")):
            try:
                submit_limit = int(os.getenv("STORES_MAIL_SYNC_SUBMIT_LIMIT", "100"))
            except ValueError:
                submit_limit = 100
            stores_mail_sync.sync(limit=submit_limit)
            status, order_row = stores_mail_sync.verify_order_no(order_code_clean)
    except Exception as exc:
        return _render_error(f"注文番号の照合に失敗しました: {exc}", 500)

    if status == "not_found":
        return _render_error(
            f"注文番号（{order_code_clean}）が見つかりません。STORESの購入確認メールに記載の番号を確認してください。"
        )
    if status == "cancelled":
        return _render_error(f"この注文番号（{order_code_clean}）はキャンセル扱いのため使用できません。", 409)
    if status == "already_used":
        return _render_error(f"この注文番号（{order_code_clean}）は鑑定データ発行に使用済みです。", 409)

    purchased_type = (order_row or {}).get("product_type")
    if purchased_type and purchased_type not in API_KEY_PRODUCT_TYPES:
        return _render_error(
            f"この注文番号はAPIキー用の商品ではありません。購入商品: {_product_label(str(purchased_type))}",
            409,
        )
    if not purchased_type and status != "reusable":
        return _render_error("購入商品の判定ができません。APIキー用商品の注文番号か確認してください。", 409)

    issue_credits = _api_key_issue_credits(str(purchased_type) if purchased_type else None)
    try:
        record = pg_store.create_api_key(
            label=f"stores_{order_code_clean}",
            credits=issue_credits,
            status="active",
            owner_email=email.strip() or None,
            order_code=order_code_clean if status != "reusable" else None,
        )
    except Exception as exc:
        if "duplicate" in str(exc).lower() or "unique" in str(exc).lower():
            existing = pg_store.get_api_key_by_order_code(order_code_clean)
            return templates.TemplateResponse(
                "api_key_result.html",
                {
                    "request": request,
                    "api_key": None,
                    "record": existing,
                    "already_issued": True,
                },
                status_code=409,
            )
        return _render_error(f"APIキー発行に失敗しました: {exc}", 500)

    return templates.TemplateResponse(
        "api_key_result.html",
        {
            "request": request,
            "api_key": record["api_key"],
            "record": record,
            "already_issued": False,
        },
    )


# ─── STORESメール同期（Cloud Scheduler から POST） ───────────────

@app.post("/internal/mail-sync")
def internal_mail_sync(request: Request):
    expected = os.getenv("STORES_MAIL_SYNC_TOKEN", "").strip()
    if expected:
        auth = request.headers.get("Authorization", "")
        token = auth.removeprefix("Bearer ").strip()
        if token != expected:
            raise HTTPException(status_code=401, detail="unauthorized")

    try:
        limit = int(os.getenv("STORES_MAIL_SYNC_LIMIT", "100"))
    except ValueError:
        limit = 100

    result = stores_mail_sync.sync(limit=limit)
    print(f"[mail-sync] {result}")
    return JSONResponse(result)


# ─── 購入者フロー ────────────────────────────────────────────────

@app.get("/start")
def start(request: Request):
    product_type = _product_type_from_request(request)
    return templates.TemplateResponse(
        _buyer_template("start", product_type),
        {"request": request, **_product_context(product_type)},
    )


@app.get("/redeem", response_class=HTMLResponse)
def redeem_get(request: Request):
    product_type = _product_type_from_request(request)
    order_code = request.query_params.get("order", "").strip()
    return templates.TemplateResponse(
        _buyer_template("redeem", product_type),
        {
            "request": request,
            "prefectures": PREFECTURE_OPTIONS,
            "error": None,
            "form": {"order_code": order_code} if order_code else None,
            **_product_context(product_type),
        },
    )


@app.post("/redeem", response_class=HTMLResponse)
def redeem_post(
    request: Request,
    order_code: str = Form(...),
    buyer_name: str = Form(""),
    email: str = Form(""),
    birth_date: str = Form(""),
    birth_time: str = Form(""),
    prefecture: str = Form(""),
    birth_place_kind: str = Form("domestic"),
    birth_place_overseas: str = Form(""),
    birth_lat: str = Form(""),
    birth_lng: str = Form(""),
    birth_timezone: str = Form(""),
    gender: str = Form("unknown"),
    product_type: str = Form("western_basic"),
    day_change_at_23: str | None = Form(None),
    event_name: str = Form(""),
    event_date: str = Form(""),
    event_time: str = Form(""),
    location_name: str = Form(""),
    event_lat: str = Form(""),
    event_lng: str = Form(""),
    event_timezone: str = Form("Asia/Tokyo"),
    input_calendar: str = Form("gregorian"),
    calendar_note: str = Form(""),
    agree_final: str | None = Form(None),
):
    product_type = request.query_params.get("type", product_type).strip() or "western_basic"
    if product_type not in PRODUCT_CONFIG:
        product_type = "western_basic"
    product = PRODUCT_CONFIG[product_type]

    include_asteroids = bool(product["include_asteroids"])
    include_shichusuimei = bool(product["include_shichusuimei"])
    include_transit = bool(product.get("include_transit"))

    # 商品ごとに強制制御します。
    # western_basic / western_full では日替わり境界UIを出さず、必ず False。
    # shichu は購入者が 23時 / 1時 を選択できます。未選択時は 1時（False）を標準にします。
    day_change_at_23_bool = _truthy(day_change_at_23) if product_type == "shichu" else False

    def _form_err(msg: str, status: int = 400):
        return templates.TemplateResponse(
            _buyer_template("redeem", product_type),
            {
                "request": request,
                "prefectures": PREFECTURE_OPTIONS,
                "error": msg,
                "form": {
                    "order_code": order_code,
                    "buyer_name": buyer_name,
                    "email": email,
                    "birth_date": birth_date,
                    "birth_time": birth_time,
                    "prefecture": prefecture,
                    "birth_place_kind": birth_place_kind,
                    "birth_place_overseas": birth_place_overseas,
                    "birth_lat": birth_lat,
                    "birth_lng": birth_lng,
                    "birth_timezone": birth_timezone,
                    "gender": gender,
                    "product_type": product_type,
                    "day_change_at_23": day_change_at_23_bool,
                    "event_name": event_name,
                    "event_date": event_date,
                    "event_time": event_time,
                    "location_name": location_name,
                    "event_lat": event_lat,
                    "event_lng": event_lng,
                    "event_timezone": event_timezone,
                    "input_calendar": input_calendar,
                    "calendar_note": calendar_note,
                    "agree_final": bool(agree_final),
                },
                **_product_context(product_type),
            },
            status_code=status,
        )

    order_code_clean = _normalize_stores_order_no(order_code)
    if not order_code_clean:
        return _form_err("STORESオーダー番号を入力してください。")
    if not re.fullmatch(r"\d{10}", order_code_clean):
        return _form_err("STORESオーダー番号は10桁の数字で入力してください。")
    if not agree_final:
        return _form_err("入力後は変更できないことを確認し、チェックを入れてください。")

    if product_type == "transit_yaml":
        try:
            lat = _parse_optional_float(event_lat, "緯度")
            lng = _parse_optional_float(event_lng, "経度")
            if lat is None or lng is None:
                raise ValueError("緯度・経度を入力してください。")
            _validate_lat_lon(lat, lng)
            if not event_name.strip():
                raise ValueError("イベント名を入力してください。")
            if not event_date.strip():
                raise ValueError("日付を入力してください。")
            if not event_time.strip():
                raise ValueError("時刻を入力してください。")
            if not location_name.strip():
                raise ValueError("場所名を入力してください。")
            yaml_text, prompt_text, doc = build_transit_only_yaml(
                event_name=event_name.strip(),
                event_date=event_date.strip(),
                event_time=event_time.strip(),
                location_name=location_name.strip(),
                latitude=lat,
                longitude=lng,
                timezone_name=event_timezone.strip() or "Asia/Tokyo",
                input_calendar=input_calendar.strip() or "gregorian",
                calendar_note=calendar_note.strip() or "歴史日付は諸説あり。必要に応じて検証してください。",
            )
        except Exception as e:
            return _form_err(str(e))

        if os.environ.get("DATABASE_URL"):
            try:
                status, order_row = stores_mail_sync.verify_order_no(order_code_clean)
                if status == "not_found" and _truthy(os.getenv("STORES_MAIL_SYNC_ON_SUBMIT", "1")):
                    try:
                        submit_limit = int(os.getenv("STORES_MAIL_SYNC_SUBMIT_LIMIT", "100"))
                    except ValueError:
                        submit_limit = 100
                    stores_mail_sync.sync(limit=submit_limit)
                    status, order_row = stores_mail_sync.verify_order_no(order_code_clean)
            except Exception as e:
                return _form_err(f"注文番号の照合に失敗しました: {e}", status=500)

            if status == "not_found":
                return _form_err(f"注文番号（{order_code_clean}）が見つかりません。STORESの購入確認メールに記載の番号を確認してください。")
            if status == "already_used":
                return _form_err(f"この注文番号（{order_code_clean}）はすでに使用済みです。", status=409)
            if status == "cancelled":
                return _form_err(f"この注文番号（{order_code_clean}）はキャンセル扱いのため使用できません。", status=409)
            purchased_type = (order_row or {}).get("product_type")
            if purchased_type and purchased_type != product_type:
                return _form_err(
                    f"この注文番号は{_product_label(purchased_type)}用です。"
                    f"{_product_label(product_type)}の入力フォームでは使用できません。",
                    status=409,
                )
        else:
            status = "ok"

        token = secrets.token_urlsafe(18)
        chart_options = {**doc.get("product", {}).get("options", {}), "product_type": product_type}
        try:
            if status == "reusable":
                pg_store.save_chart(
                    token=token,
                    order_code=order_code_clean,
                    buyer_name=event_name.strip(),
                    birth_date=doc["event"]["date"],
                    birth_time=doc["event"]["time"],
                    birth_place=location_name.strip(),
                    options={**chart_options, "reusable_order": True},
                    yaml_text=yaml_text,
                    prompt_text=prompt_text,
                )
                ok = True
            else:
                ok = pg_store.redeem_and_save(
                    order_code=order_code_clean,
                    email=email.strip() or None,
                    buyer_name=event_name.strip(),
                    token=token,
                    birth_date=doc["event"]["date"],
                    birth_time=doc["event"]["time"],
                    birth_place=location_name.strip(),
                    options=chart_options,
                    yaml_text=yaml_text,
                    prompt_text=prompt_text,
                )
        except Exception as e:
            return _form_err(f"保存に失敗しました: {e}", status=500)

        if not ok:
            return _form_err(f"この注文番号（{order_code_clean}）はすでに使用済みです。別の注文番号をご確認ください。", status=409)

        return RedirectResponse(f"/chart/{token}", status_code=303)

    if not birth_date.strip():
        return _form_err("生年月日を入力してください。")

    try:
        birth_location = _build_birth_location(
            prefecture=prefecture,
            birth_place_kind=birth_place_kind,
            birth_place_overseas=birth_place_overseas,
            birth_lat=birth_lat,
            birth_lng=birth_lng,
            birth_timezone=birth_timezone,
        )
        birth_place_label = str(birth_location["birth_place"])
        birth_lat_value = birth_location["lat"]
        birth_lng_value = birth_location["lng"]
        birth_tz_name = str(birth_location["tz_name"])
    except Exception as e:
        return _form_err(str(e))

    # STORES注文番号の照合。DBがある場合のみ有効。
    if os.environ.get("DATABASE_URL"):
        try:
            status, order_row = stores_mail_sync.verify_order_no(order_code_clean)
            if status == "not_found" and _truthy(os.getenv("STORES_MAIL_SYNC_ON_SUBMIT", "1")):
                try:
                    submit_limit = int(os.getenv("STORES_MAIL_SYNC_SUBMIT_LIMIT", "100"))
                except ValueError:
                    submit_limit = 100
                stores_mail_sync.sync(limit=submit_limit)
                status, order_row = stores_mail_sync.verify_order_no(order_code_clean)
        except Exception as e:
            return _form_err(f"注文番号の照合に失敗しました: {e}", status=500)

        if status == "not_found":
            return _form_err(
                f"注文番号（{order_code_clean}）が見つかりません。"
                "STORESの購入確認メールに記載の番号を確認してください。"
            )
        if status == "already_used":
            return _form_err(f"この注文番号（{order_code_clean}）はすでに使用済みです。", status=409)
        if status == "cancelled":
            return _form_err(f"この注文番号（{order_code_clean}）はキャンセル扱いのため使用できません。", status=409)
        purchased_type = (order_row or {}).get("product_type")
        if purchased_type and purchased_type != product_type:
            return _form_err(
                f"この注文番号は{_product_label(purchased_type)}用です。"
                f"{_product_label(product_type)}の入力フォームでは使用できません。",
                status=409,
            )
    else:
        status = "ok"

    try:
        yaml_text, prompt_text, doc = build_product_yaml(
            title=buyer_name.strip() or None,
            birth_date=birth_date.strip(),
            birth_time=birth_time.strip() or None,
            prefecture=prefecture.strip(),
            birth_place_label=birth_place_label,
            birth_lat=birth_lat_value if isinstance(birth_lat_value, float) else None,
            birth_lng=birth_lng_value if isinstance(birth_lng_value, float) else None,
            tz_name=birth_tz_name,
            gender=gender.strip() or "unknown",
            include_asteroids=include_asteroids,
            include_shichusuimei=include_shichusuimei,
            include_transit=include_transit,
            day_change_at_23=day_change_at_23_bool,
        )
    except Exception as e:
        return _form_err(str(e))

    token = secrets.token_urlsafe(18)
    try:
        if status == "reusable":
            pg_store.save_chart(
                token=token,
                order_code=order_code_clean,
                buyer_name=buyer_name.strip() or None,
                birth_date=birth_date.strip(),
                birth_time=birth_time.strip() or None,
                birth_place=birth_place_label,
                options={**doc.get("product", {}).get("options", {}), "product_type": product_type, "reusable_order": True},
                yaml_text=yaml_text,
                prompt_text=prompt_text,
            )
            ok = True
        else:
            ok = pg_store.redeem_and_save(
                order_code=order_code_clean,
                email=email.strip() or None,
                buyer_name=buyer_name.strip() or None,
                token=token,
                birth_date=birth_date.strip(),
                birth_time=birth_time.strip() or None,
                birth_place=birth_place_label,
                options={**doc.get("product", {}).get("options", {}), "product_type": product_type},
                yaml_text=yaml_text,
                prompt_text=prompt_text,
            )
    except Exception as e:
        return _form_err(f"保存に失敗しました: {e}", status=500)

    if not ok:
        return _form_err(
            f"この注文番号（{order_code_clean}）はすでに使用済みです。"
            "別の注文番号をご確認ください。",
            status=409,
        )

    return RedirectResponse(f"/chart/{token}", status_code=303)


# ─── チャートページ（ルート順に注意） ──────────────────────────────

@app.get("/chart/{token}.yaml", response_class=PlainTextResponse)
def chart_yaml(token: str):
    chart = _load_chart_or_404(token)
    return PlainTextResponse(chart["yaml_text"], media_type="text/yaml; charset=utf-8")


@app.get("/chart/{token}/prompt.txt", response_class=PlainTextResponse)
def chart_prompt(token: str):
    chart = _load_chart_or_404(token)
    return PlainTextResponse(chart["prompt_text"], media_type="text/plain; charset=utf-8")


@app.get("/chart/{token}", response_class=HTMLResponse)
def chart_page(request: Request, token: str):
    chart = _load_chart_or_404(token)
    options = chart.get("options") or {}
    is_transit_yaml = options.get("product_type") == "transit_yaml"
    base_url = _public_base_url(request)
    return templates.TemplateResponse(
        "chart_page.html",
        {
            "request": request,
            "token": token,
            "chart": chart,
            "is_transit_yaml": is_transit_yaml,
            "chart_url": f"{base_url}/chart/{token}",
            "yaml_url": f"{base_url}/chart/{token}.yaml",
            "prompt_url": f"{base_url}/chart/{token}/prompt.txt",
        },
    )


# ─── 管理者フロー ────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "admin_test_site_path": ADMIN_TEST_SITE_PATH},
    )


@app.get("/test-site", response_class=HTMLResponse)
def test_site_legacy():
    raise HTTPException(status_code=404, detail="not found")


@app.get(ADMIN_TEST_SITE_PATH, response_class=HTMLResponse)
def test_site(request: Request):
    return templates.TemplateResponse("test_site.html", {"request": request})


@app.get("/admin/812f0fd3577c40b5d12b/test-site", response_class=HTMLResponse)
def test_site_legacy_admin_path(request: Request):
    return templates.TemplateResponse("test_site.html", {"request": request})


@app.get("/admin/yaml/new", response_class=HTMLResponse)
def yaml_new(request: Request):
    return templates.TemplateResponse(
        "yaml_form.html",
        {"request": request, "prefectures": PREFECTURE_OPTIONS},
    )


@app.post("/admin/yaml/generate", response_class=HTMLResponse)
def yaml_generate(
    request: Request,
    title: str = Form(""),
    birth_date: str = Form(...),
    birth_time: str = Form(""),
    prefecture: str = Form(""),
    gender: str = Form("unknown"),
    include_asteroids: str | None = Form(None),
    include_shichusuimei: str | None = Form(None),
    include_transit: str | None = Form(None),
    day_change_at_23: str | None = Form(None),
):
    token = secrets.token_urlsafe(18)
    try:
        yaml_text, prompt_text, doc = build_product_yaml(
            title=title.strip() or None,
            birth_date=birth_date.strip(),
            birth_time=birth_time.strip() or None,
            prefecture=prefecture.strip(),
            gender=gender.strip() or "unknown",
            include_asteroids=bool(include_asteroids),
            include_shichusuimei=bool(include_shichusuimei),
            include_transit=bool(include_transit),
            day_change_at_23=bool(day_change_at_23),
        )
    except Exception as e:
        return templates.TemplateResponse(
            "yaml_form.html",
            {
                "request": request,
                "prefectures": PREFECTURE_OPTIONS,
                "error": str(e),
                "form": {
                    "title": title,
                    "birth_date": birth_date,
                    "birth_time": birth_time,
                    "prefecture": prefecture,
                    "gender": gender,
                },
            },
            status_code=400,
        )

    try:
        pg_store.save_chart(
            token=token,
            order_code=None,
            buyer_name=title.strip() or None,
            birth_date=birth_date.strip(),
            birth_time=birth_time.strip() or None,
            birth_place=prefecture.strip(),
            options=doc.get("product", {}).get("options", {}),
            yaml_text=yaml_text,
            prompt_text=prompt_text,
        )
    except Exception as e:
        return templates.TemplateResponse(
            "yaml_form.html",
            {
                "request": request,
                "prefectures": PREFECTURE_OPTIONS,
                "error": f"DB保存に失敗しました: {e}",
                "form": {
                    "title": title,
                    "birth_date": birth_date,
                    "birth_time": birth_time,
                    "prefecture": prefecture,
                    "gender": gender,
                },
            },
            status_code=500,
        )
    return RedirectResponse(f"/admin/yaml/result/{token}", status_code=303)


@app.get("/admin/yaml/result/{token}", response_class=HTMLResponse)
def admin_yaml_result(request: Request, token: str):
    chart = _load_chart_or_404(token)
    base_url = _public_base_url(request)
    return templates.TemplateResponse(
        "admin_result.html",
        {
            "request": request,
            "token": token,
            "chart": chart,
            "chart_url": f"{base_url}/chart/{token}",
            "yaml_url": f"{base_url}/chart/{token}.yaml",
            "prompt_url": f"{base_url}/chart/{token}/prompt.txt",
        },
    )


# ─── 共通ヘルパー ────────────────────────────────────────────────

def _public_base_url(request: Request) -> str:
    env_url = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")
    if env_url:
        return env_url
    base_url = str(request.base_url).rstrip("/")
    if base_url.startswith("http://chart.nanami-astro.com"):
        base_url = base_url.replace("http://", "https://", 1)
    return base_url


def _load_chart_or_404(token: str) -> dict:
    chart = pg_store.get_chart(token)
    if not chart:
        raise HTTPException(status_code=404, detail="chart not found")
    return chart
