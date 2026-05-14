from __future__ import annotations

import hashlib
import io
import os
import re
import secrets
import subprocess
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml
from fastapi import Body, FastAPI, Form, Header, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from services import pg_store, stores_mail_sync
from services.api_calc import calc_combined_api, calc_shichu_api, calc_transit_api, calc_western_api
from services.api_demo import build_demo_response, build_demo_shichu_svg, build_demo_svg
from services.birth_time import extract_birth_time_notice, resolve_birth_time_accuracy
from services.chart_svg import build_horoscope_svg_from_yaml, has_asteroid_svg_data
from services.api_yaml import build_handoff_yaml
from services.location import PREFECTURE_OPTIONS
from services.light_yaml import (
    build_base_astrology_yaml,
    build_light_astrology_yaml,
    build_natal_asteroids_yaml,
    build_transit_astrology_yaml,
)
from services.post_chart import build_post_chart
from services.shichu_chart import (
    build_shichusuimei_svg_from_yaml,
    is_shichusuimei_png_renderer_available,
    render_shichusuimei_png_from_svg,
)
from services.transit_yaml import build_transit_only_yaml
from services.yaml_exporter import (
    build_31days_transit_addon_yaml,
    build_asteroid_addon_yaml,
    build_product_yaml,
    build_shichu_fortune_cycles_addon_yaml,
)

app = FastAPI(title="nanami-products")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


def _resolve_asset_version() -> str:
    version = os.getenv("ASSET_VERSION", "").strip()
    if version:
        return version
    revision = os.getenv("K_REVISION", "").strip()
    if revision:
        return revision
    try:
        repo_root = Path(__file__).resolve().parent
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
        git_sha = result.stdout.strip()
        if git_sha:
            return git_sha
    except Exception:
        pass
    return "app-1.0.0"


ASSET_VERSION = _resolve_asset_version()


def _asset_url(path: str) -> str:
    clean_path = path.lstrip("/")
    return f"/static/{clean_path}?v={ASSET_VERSION}"


templates.env.globals.update(asset_version=ASSET_VERSION, asset_url=_asset_url)


@app.middleware("http")
async def _asset_cache_control_middleware(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static/") and request.url.path.endswith((".css", ".js")):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response
    content_type = response.headers.get("content-type", "")
    if content_type.startswith("text/html"):
        response.headers["Cache-Control"] = "no-store, max-age=0, must-revalidate"
    return response

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
    "western_asteroids_addon": {
        "label": "ホロスコープ：小惑星追加",
        "description": "基本版購入後に、小惑星データだけを追加するためのYAMLを生成します。",
        "features": [
            "Ceres / Pallas / Juno / Vesta / Chiron / Lilith / Vertex",
            "基本版ホロスコープに追加して使う部品データ",
            "トランジットなし",
            "四柱推命なし",
        ],
        "include_asteroids": True,
        "include_shichusuimei": False,
        "include_transit": False,
        "addon_type": "western_asteroids",
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

PRODUCT_SLUGS = {
    "western_basic": "western-basic",
    "western_full": "western-full",
    "western_asteroids_addon": "western-asteroids-addon",
    "shichu": "shichu",
    "transit_yaml": "transit-yaml",
}
PRODUCT_TYPES_BY_SLUG = {slug: product_type for product_type, slug in PRODUCT_SLUGS.items()}
CHART_EXPIRES_DAYS = 90
OVERSEAS_TIMEZONE_OPTIONS = [
    {"value": "America/New_York", "label": "アメリカ東部（New York など）"},
    {"value": "America/Chicago", "label": "アメリカ中部（Chicago など）"},
    {"value": "America/Denver", "label": "アメリカ山岳部（Denver など）"},
    {"value": "America/Los_Angeles", "label": "アメリカ西部（Los Angeles など）"},
    {"value": "America/Honolulu", "label": "ハワイ（Honolulu）"},
    {"value": "Europe/London", "label": "イギリス（London）"},
    {"value": "Europe/Paris", "label": "フランス・中央ヨーロッパ（Paris など）"},
    {"value": "Europe/Berlin", "label": "ドイツ（Berlin）"},
    {"value": "Europe/Rome", "label": "イタリア（Rome）"},
    {"value": "Asia/Seoul", "label": "韓国（Seoul）"},
    {"value": "Asia/Shanghai", "label": "中国（Shanghai）"},
    {"value": "Asia/Taipei", "label": "台湾（Taipei）"},
    {"value": "Asia/Hong_Kong", "label": "香港（Hong Kong）"},
    {"value": "Asia/Bangkok", "label": "タイ（Bangkok）"},
    {"value": "Asia/Singapore", "label": "シンガポール（Singapore）"},
    {"value": "Australia/Sydney", "label": "オーストラリア東部（Sydney）"},
]


def _product_type_from_request(request: Request) -> str:
    product_type = request.query_params.get("type", "western_basic").strip()
    if product_type not in PRODUCT_CONFIG:
        product_type = "western_basic"
    return product_type


def _product_type_from_slug(product_slug: str | None) -> str:
    if not product_slug:
        return "western_basic"
    return PRODUCT_TYPES_BY_SLUG.get(product_slug.strip(), "western_basic")


def _start_url(product_type: str) -> str:
    return f"/start/{PRODUCT_SLUGS.get(product_type, PRODUCT_SLUGS['western_basic'])}"


def _redeem_url(product_type: str) -> str:
    return f"/redeem/{PRODUCT_SLUGS.get(product_type, PRODUCT_SLUGS['western_basic'])}"


def _product_context(product_type: str) -> dict:
    config = PRODUCT_CONFIG.get(product_type, PRODUCT_CONFIG["western_basic"])
    return {
        "product_type": product_type,
        "product": config,
        "start_url": _start_url(product_type),
        "redeem_url": _redeem_url(product_type),
    }


def _chart_expires_at() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=CHART_EXPIRES_DAYS)


def _build_chart_artifacts(
    *,
    yaml_text: str,
    doc: dict,
    product_type: str,
) -> dict[str, str | None]:
    share_yaml_text = yaml_text
    horoscope_svg = None
    shichusuimei_svg = None
    if product_type == "western_full":
        try:
            share_yaml_text = build_light_astrology_yaml(yaml_text, doc=doc)
        except Exception:
            share_yaml_text = yaml_text
    if product_type in {"western_basic", "western_full"}:
        try:
            horoscope_svg = build_horoscope_svg_from_yaml(yaml_text, doc=doc)
        except Exception:
            horoscope_svg = None
    if product_type == "shichu":
        try:
            shichusuimei_svg = build_shichusuimei_svg_from_yaml(yaml_text, doc=doc)
        except Exception:
            shichusuimei_svg = None
    return {
        "share_yaml_text": share_yaml_text,
        "horoscope_svg": horoscope_svg,
        "shichusuimei_svg": shichusuimei_svg,
    }


def _buyer_template(prefix: str, product_type: str) -> str:
    if product_type not in PRODUCT_CONFIG:
        product_type = "western_basic"
    if product_type == "western_asteroids_addon":
        return f"{prefix}_western_basic.html"
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
    addon_labels = {
        "western_asteroids_addon": "ホロスコープ：小惑星追加",
        "western_31days_transit_addon": "ホロスコープ：31日トランジット追加",
        "shichu_fortune_cycles_addon": "四柱推命：大運・流年追加",
    }
    if product_type in addon_labels:
        return addon_labels[str(product_type)]
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
        if prefecture.strip():
            raise ValueError("海外出生の場合は、出生都道府県を未選択にしてください。")
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
    if birth_place_overseas.strip() or birth_timezone.strip():
        raise ValueError("国内出生の場合は、海外出生地名とタイムゾーン欄を空にしてください。")
    lat = _parse_optional_float(birth_lat, "緯度")
    lon = _parse_optional_float(birth_lng, "経度")
    if (lat is None) != (lon is None):
        raise ValueError("緯度・経度を指定する場合は、両方入力してください。")
    if lat is not None and lon is not None:
        _validate_lat_lon(lat, lon)
    return {
        "kind": "domestic",
        "birth_place": pref_name,
        "prefecture": pref_name,
        "lat": lat,
        "lng": lon,
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


def _sync_stores_orders_for_lookup() -> dict[str, object] | None:
    if not _truthy(os.getenv("STORES_MAIL_SYNC_ON_SUBMIT", "1")):
        return None
    try:
        submit_limit = int(os.getenv("STORES_MAIL_SYNC_SUBMIT_LIMIT", "100"))
    except ValueError:
        submit_limit = 100
    return stores_mail_sync.sync(limit=submit_limit)


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


@app.post("/internal/redemptions/lookup")
def internal_lookup_redemption(request: Request, payload: dict[str, object] = Body(default={})):
    error = _admin_access_error(request)
    if error:
        return error

    order_code_clean = _normalize_stores_order_no(str(payload.get("order_code") or ""))
    if not order_code_clean:
        return _api_error("INVALID_INPUT", "order_code is required", 400)
    if not re.fullmatch(r"\d{10}", order_code_clean):
        return _api_error("INVALID_INPUT", "order_code must be 10 digits", 400)

    try:
        sync_result = None
        status, order_row = stores_mail_sync.verify_order_no(order_code_clean)
        if status == "not_found":
            sync_result = _sync_stores_orders_for_lookup()
            status, order_row = stores_mail_sync.verify_order_no(order_code_clean)
        redemption = pg_store.get_redemption_by_order_code(order_code_clean)
        reset_override = pg_store.get_redemption_reset_by_order_code(order_code_clean)
        charts = pg_store.list_charts_by_order_code(order_code_clean)
    except Exception as exc:
        return _api_error("REDEMPTION_LOOKUP_FAILED", str(exc), 500)

    return JSONResponse(
        jsonable_encoder({
            "ok": True,
            "order_code": order_code_clean,
            "order_status": status,
            "stores_order": order_row,
            "redemption": redemption,
            "reset_override": reset_override,
            "charts": charts,
            "sync_result": sync_result,
            "can_redeem_after_reset": status in {"ok", "already_used"},
        })
    )


@app.post("/internal/redemptions/reset")
def internal_reset_redemption(request: Request, payload: dict[str, object] = Body(default={})):
    error = _admin_access_error(request)
    if error:
        return error

    order_code_clean = _normalize_stores_order_no(str(payload.get("order_code") or ""))
    if not order_code_clean:
        return _api_error("INVALID_INPUT", "order_code is required", 400)
    if not re.fullmatch(r"\d{10}", order_code_clean):
        return _api_error("INVALID_INPUT", "order_code must be 10 digits", 400)
    if str(payload.get("confirm") or "").strip() != order_code_clean:
        return _api_error("CONFIRMATION_REQUIRED", "confirm must match order_code", 400)

    try:
        sync_result = None
        status, order_row = stores_mail_sync.verify_order_no(order_code_clean)
        if status == "not_found":
            sync_result = _sync_stores_orders_for_lookup()
            status, order_row = stores_mail_sync.verify_order_no(order_code_clean)
    except Exception as exc:
        return _api_error("ORDER_LOOKUP_FAILED", str(exc), 500)
    if status == "not_found":
        return _api_error("ORDER_NOT_FOUND", "order_code was not found", 404)
    if status == "cancelled":
        return _api_error("ORDER_CANCELLED", "cancelled order cannot be reset for redemption", 409)

    try:
        result = pg_store.reset_redemption_by_order_code(order_code_clean)
        new_status, _new_order_row = stores_mail_sync.verify_order_no(order_code_clean)
    except Exception as exc:
        return _api_error("REDEMPTION_RESET_FAILED", str(exc), 500)

    return JSONResponse(
        jsonable_encoder({
            "ok": True,
            "order_code": order_code_clean,
            "previous_order_status": status,
            "order_status": new_status,
            "stores_order": order_row,
            "sync_result": sync_result,
            **result,
        })
    )


def _cleanup_grace_days(payload: dict[str, object]) -> int:
    value = payload.get("grace_days", 0)
    try:
        return max(0, min(365, int(value or 0)))
    except (TypeError, ValueError):
        raise ValueError("grace_days must be an integer between 0 and 365")


@app.post("/internal/charts/expired/summary")
def internal_expired_charts_summary(request: Request, payload: dict[str, object] = Body(default={})):
    error = _admin_access_error(request)
    if error:
        return error
    try:
        grace_days = _cleanup_grace_days(payload)
        summary = pg_store.expired_charts_summary(grace_days=grace_days)
    except ValueError as exc:
        return _api_error("INVALID_INPUT", str(exc), 400)
    except Exception as exc:
        return _api_error("EXPIRED_CHARTS_SUMMARY_FAILED", str(exc), 500)
    return JSONResponse(jsonable_encoder({"ok": True, "grace_days": grace_days, **summary}))


@app.post("/internal/charts/expired/cleanup")
def internal_cleanup_expired_charts(request: Request, payload: dict[str, object] = Body(default={})):
    error = _admin_access_error(request)
    if error:
        return error
    if str(payload.get("confirm") or "").strip() != "DELETE_EXPIRED_CHARTS":
        return _api_error("CONFIRMATION_REQUIRED", "confirm must be DELETE_EXPIRED_CHARTS", 400)
    try:
        grace_days = _cleanup_grace_days(payload)
        before = pg_store.expired_charts_summary(grace_days=grace_days)
        result = pg_store.delete_expired_charts(grace_days=grace_days)
        after = pg_store.expired_charts_summary(grace_days=grace_days)
    except ValueError as exc:
        return _api_error("INVALID_INPUT", str(exc), 400)
    except Exception as exc:
        return _api_error("EXPIRED_CHARTS_CLEANUP_FAILED", str(exc), 500)
    return JSONResponse(
        jsonable_encoder(
            {
                "ok": True,
                "grace_days": grace_days,
                "before": before,
                **result,
                "after": after,
            }
        )
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


def _demo_response(request: Request, endpoint: str, payload: dict[str, object]) -> JSONResponse:
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

    return JSONResponse(build_demo_response(endpoint, payload, base_url=_public_base_url(request)))


def _handle_calc_api(
    *,
    request: Request,
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

    internal_chart_yaml = body.pop("_internal_chart_yaml_text", None)
    if internal_chart_yaml and (
        isinstance(body.get("chart"), dict) or isinstance(body.get("shichusuimei_chart"), dict)
    ):
        try:
            chart_id = pg_store.save_api_chart_snapshot(
                api_key_id=api_key_id,
                endpoint=endpoint,
                yaml_text=str(internal_chart_yaml),
            )
            base_url = _public_base_url(request)
            if isinstance(body.get("chart"), dict):
                body["chart"].update(
                    {
                        "svg_available": True,
                        "chart_id": chart_id,
                        "svg_url": f"{base_url}/api/western/natal/{chart_id}/chart.svg",
                    }
                )
            if isinstance(body.get("shichusuimei_chart"), dict):
                png_available = is_shichusuimei_png_renderer_available()
                body["shichusuimei_chart"].update(
                    {
                        "svg_available": True,
                        "png_available": png_available,
                        "chart_id": chart_id,
                        "svg_url": f"{base_url}/api/shichusuimei/{chart_id}/chart.svg",
                        "png_url": f"{base_url}/api/shichusuimei/{chart_id}/chart.png" if png_available else None,
                    }
                )
            body["handoff_yaml"] = build_handoff_yaml(
                {key: value for key, value in body.items() if key not in {"ok", "handoff_yaml"}}
            )
        except Exception as exc:
            pg_store.update_api_usage(
                usage_id=usage_id,
                credits_used=0,
                status="error",
                error_code="API_CHART_SNAPSHOT_FAILED",
            )
            return _api_error("API_CHART_SNAPSHOT_FAILED", f"chart snapshot creation failed: {exc}", 500)

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


def _authenticate_api_key_for_read(api_key: str | None) -> tuple[dict | None, JSONResponse | None]:
    if not api_key:
        return None, _api_error("MISSING_API_KEY", "X-API-Key header is required", 401)
    try:
        key_row = pg_store.get_api_key_for_auth(api_key)
    except Exception as exc:
        return None, _api_error("API_AUTH_UNAVAILABLE", f"API authentication failed: {exc}", 500)
    if not key_row:
        return None, _api_error("INVALID_API_KEY", "API key is invalid", 401)
    if key_row.get("status") != "active":
        return None, _api_error("API_KEY_INACTIVE", "API key is not active", 403)
    return key_row, None


def _api_chart_snapshot(chart_id: str, x_api_key: str | None) -> tuple[dict | None, JSONResponse | None]:
    if not re.fullmatch(r"ch_[A-Za-z0-9_-]{10,80}", chart_id):
        return None, _api_error("INVALID_CHART_ID", "chart_id is invalid", 400)
    key_row, error_response = _authenticate_api_key_for_read(x_api_key)
    if error_response:
        return None, error_response
    try:
        snapshot = pg_store.get_api_chart_snapshot(chart_id=chart_id, api_key_id=int(key_row["id"]))
    except Exception as exc:
        return None, _api_error("API_CHART_UNAVAILABLE", f"chart lookup failed: {exc}", 500)
    if not snapshot:
        return None, _api_error("CHART_NOT_FOUND", "chart was not found for this API key", 404)
    return snapshot, None


def _api_chart_svg_response(chart_id: str, x_api_key: str | None) -> PlainTextResponse | JSONResponse:
    snapshot, error_response = _api_chart_snapshot(chart_id, x_api_key)
    if error_response:
        return error_response
    svg = build_horoscope_svg_from_yaml(snapshot["yaml_text"], compact=True)
    if not svg:
        return _api_error("CHART_SVG_UNAVAILABLE", "SVG is not available for this chart", 404)
    return PlainTextResponse(svg, media_type="image/svg+xml; charset=utf-8")


def _api_shichusuimei_svg_response(chart_id: str, x_api_key: str | None) -> PlainTextResponse | JSONResponse:
    snapshot, error_response = _api_chart_snapshot(chart_id, x_api_key)
    if error_response:
        return error_response
    svg = build_shichusuimei_svg_from_yaml(snapshot["yaml_text"], compact=True)
    if not svg:
        return _api_error("SHICHUSUIMEI_CHART_SVG_UNAVAILABLE", "SVG is not available for this chart", 404)
    return PlainTextResponse(svg, media_type="image/svg+xml; charset=utf-8")


def _api_shichusuimei_png_response(chart_id: str, x_api_key: str | None) -> Response | JSONResponse:
    snapshot, error_response = _api_chart_snapshot(chart_id, x_api_key)
    if error_response:
        return error_response
    svg = build_shichusuimei_svg_from_yaml(snapshot["yaml_text"], compact=True)
    if not svg:
        return _api_error("SHICHUSUIMEI_CHART_SVG_UNAVAILABLE", "SVG is not available for this chart", 404)
    png = render_shichusuimei_png_from_svg(svg)
    if png is None:
        return _api_error(
            "PNG_RENDERER_UNAVAILABLE",
            "PNG rendering is not configured on this server",
            501,
        )
    return Response(content=png, media_type="image/png")


@app.get("/api/western/natal/{chart_id}/chart.svg")
def api_western_natal_chart_svg(
    chart_id: str,
    x_api_key: str | None = Header(None, alias="X-API-Key"),
):
    return _api_chart_svg_response(chart_id, x_api_key)


@app.get("/api/charts/{chart_id}.svg")
def api_chart_svg_alias(
    chart_id: str,
    x_api_key: str | None = Header(None, alias="X-API-Key"),
):
    return _api_chart_svg_response(chart_id, x_api_key)


@app.get("/api/shichusuimei/{chart_id}/chart.svg")
def api_shichusuimei_chart_svg(
    chart_id: str,
    x_api_key: str | None = Header(None, alias="X-API-Key"),
):
    return _api_shichusuimei_svg_response(chart_id, x_api_key)


@app.get("/api/shichusuimei/{chart_id}/chart.png")
def api_shichusuimei_chart_png(
    chart_id: str,
    x_api_key: str | None = Header(None, alias="X-API-Key"),
):
    return _api_shichusuimei_png_response(chart_id, x_api_key)


@app.get("/api/charts/{chart_id}/shichusuimei.svg")
def api_shichusuimei_chart_svg_alias(
    chart_id: str,
    x_api_key: str | None = Header(None, alias="X-API-Key"),
):
    return _api_shichusuimei_svg_response(chart_id, x_api_key)


@app.post("/api/demo/western")
def api_demo_western(request: Request, payload: dict[str, object] = Body(...)):
    return _demo_response(request, "western", payload)


@app.post("/api/demo/shichu")
def api_demo_shichu(request: Request, payload: dict[str, object] = Body(...)):
    return _demo_response(request, "shichu", payload)


@app.post("/api/demo/transit")
def api_demo_transit(request: Request, payload: dict[str, object] = Body(...)):
    return _demo_response(request, "transit", payload)


@app.post("/api/demo/combined")
def api_demo_combined(request: Request, payload: dict[str, object] = Body(...)):
    return _demo_response(request, "combined", payload)


@app.get("/api/demo/charts/{chart_id}.svg")
def api_demo_chart_svg(chart_id: str):
    svg = build_demo_svg(chart_id)
    if not svg:
        return _api_error("CHART_NOT_FOUND", "demo chart was not found", 404)
    return PlainTextResponse(svg, media_type="image/svg+xml; charset=utf-8")


@app.get("/api/demo/shichusuimei/{chart_id}/chart.svg")
def api_demo_shichusuimei_chart_svg(chart_id: str):
    svg = build_demo_shichu_svg(chart_id)
    if not svg:
        return _api_error("CHART_NOT_FOUND", "demo shichusuimei chart was not found", 404)
    return PlainTextResponse(svg, media_type="image/svg+xml; charset=utf-8")


@app.post("/api/calc/western")
def api_calc_western(
    request: Request,
    payload: dict[str, object] = Body(...),
    x_api_key: str | None = Header(None, alias="X-API-Key"),
):
    return _handle_calc_api(
        request=request,
        endpoint="western",
        payload=payload,
        api_key=x_api_key,
        calc_func=calc_western_api,
    )


@app.post("/api/calc/shichu")
def api_calc_shichu(
    request: Request,
    payload: dict[str, object] = Body(...),
    x_api_key: str | None = Header(None, alias="X-API-Key"),
):
    return _handle_calc_api(
        request=request,
        endpoint="shichu",
        payload=payload,
        api_key=x_api_key,
        calc_func=calc_shichu_api,
    )


@app.post("/api/calc/transit")
def api_calc_transit(
    request: Request,
    payload: dict[str, object] = Body(...),
    x_api_key: str | None = Header(None, alias="X-API-Key"),
):
    return _handle_calc_api(
        request=request,
        endpoint="transit",
        payload=payload,
        api_key=x_api_key,
        calc_func=calc_transit_api,
    )


@app.post("/api/calc/combined")
def api_calc_combined(
    request: Request,
    payload: dict[str, object] = Body(...),
    x_api_key: str | None = Header(None, alias="X-API-Key"),
):
    return _handle_calc_api(
        request=request,
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
    if "type" in request.query_params:
        return RedirectResponse(_start_url(product_type), status_code=301)
    return templates.TemplateResponse(
        _buyer_template("start", product_type),
        {"request": request, **_product_context(product_type)},
    )


@app.get("/start/{product_slug}")
def start_by_slug(request: Request, product_slug: str):
    product_type = _product_type_from_slug(product_slug)
    return templates.TemplateResponse(
        _buyer_template("start", product_type),
        {"request": request, **_product_context(product_type)},
    )


@app.get("/redeem", response_class=HTMLResponse)
@app.get("/redeem/{product_slug}", response_class=HTMLResponse)
def redeem_get(request: Request, product_slug: str | None = None):
    product_type = _product_type_from_slug(product_slug) if product_slug else _product_type_from_request(request)
    if not product_slug and "type" in request.query_params and "order" not in request.query_params:
        return RedirectResponse(_redeem_url(product_type), status_code=301)
    order_code = request.query_params.get("order", "").strip()
    return templates.TemplateResponse(
        _buyer_template("redeem", product_type),
        {
            "request": request,
            "prefectures": PREFECTURE_OPTIONS,
            "timezone_options": OVERSEAS_TIMEZONE_OPTIONS,
            "error": None,
            "form": {"order_code": order_code} if order_code else None,
            **_product_context(product_type),
        },
    )


@app.post("/redeem", response_class=HTMLResponse)
@app.post("/redeem/{product_slug}", response_class=HTMLResponse)
def redeem_post(
    request: Request,
    product_slug: str | None = None,
    order_code: str = Form(...),
    buyer_name: str = Form(""),
    email: str = Form(""),
    birth_date: str = Form(""),
    birth_time: str = Form(""),
    birth_time_accuracy: str = Form("auto"),
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
    if product_slug:
        product_type = _product_type_from_slug(product_slug)
    else:
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
                "timezone_options": OVERSEAS_TIMEZONE_OPTIONS,
                "error": msg,
                "form": {
                    "order_code": order_code,
                    "buyer_name": buyer_name,
                    "email": email,
                    "birth_date": birth_date,
                    "birth_time": birth_time,
                    "birth_time_accuracy": birth_time_accuracy,
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
        artifacts = _build_chart_artifacts(yaml_text=yaml_text, doc=doc, product_type=product_type)
        expires_at = _chart_expires_at()
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
                    **artifacts,
                    expires_at=expires_at,
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
                    **artifacts,
                    expires_at=expires_at,
                )
        except Exception as e:
            return _form_err(f"保存に失敗しました: {e}", status=500)

        if not ok:
            return _form_err(f"この注文番号（{order_code_clean}）はすでに使用済みです。別の注文番号をご確認ください。", status=409)

        return RedirectResponse(f"/chart/{token}", status_code=303)

    if not birth_date.strip():
        return _form_err("生年月日を入力してください。")

    try:
        birth_time_info = resolve_birth_time_accuracy(
            selected_accuracy=birth_time_accuracy,
            birth_time=birth_time,
        )
    except Exception as e:
        return _form_err(str(e))

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
        common_product_args = {
            "title": buyer_name.strip() or None,
            "birth_date": birth_date.strip(),
            "birth_time": birth_time_info["calculation_time"],
            "prefecture": prefecture.strip(),
            "birth_place_label": birth_place_label,
            "birth_lat": birth_lat_value if isinstance(birth_lat_value, float) else None,
            "birth_lng": birth_lng_value if isinstance(birth_lng_value, float) else None,
            "tz_name": birth_tz_name,
            "gender": gender.strip() or "unknown",
            "birth_time_accuracy": birth_time_info["accuracy"],
            "birth_time_range": birth_time_info["range"],
            "birth_time_note": birth_time_info["note"],
        }
        if product_type == "western_asteroids_addon":
            yaml_text, prompt_text, doc = build_asteroid_addon_yaml(**common_product_args)
        else:
            yaml_text, prompt_text, doc = build_product_yaml(
                **common_product_args,
                include_asteroids=include_asteroids,
                include_shichusuimei=include_shichusuimei,
                include_transit=include_transit,
                day_change_at_23=day_change_at_23_bool,
            )
    except Exception as e:
        return _form_err(str(e))

    token = secrets.token_urlsafe(18)
    chart_options = {**doc.get("product", {}).get("options", {}), "product_type": product_type}
    artifacts = _build_chart_artifacts(yaml_text=yaml_text, doc=doc, product_type=product_type)
    expires_at = _chart_expires_at()
    try:
        if status == "reusable":
            pg_store.save_chart(
                token=token,
                order_code=order_code_clean,
                buyer_name=buyer_name.strip() or None,
                birth_date=birth_date.strip(),
                birth_time=birth_time_info["birth_time"] or birth_time_info["calculation_time"],
                birth_place=birth_place_label,
                options={**chart_options, "reusable_order": True},
                yaml_text=yaml_text,
                prompt_text=prompt_text,
                **artifacts,
                expires_at=expires_at,
            )
            ok = True
        else:
            ok = pg_store.redeem_and_save(
                order_code=order_code_clean,
                email=email.strip() or None,
                buyer_name=buyer_name.strip() or None,
                token=token,
                birth_date=birth_date.strip(),
                birth_time=birth_time_info["birth_time"] or birth_time_info["calculation_time"],
                birth_place=birth_place_label,
                options=chart_options,
                yaml_text=yaml_text,
                prompt_text=prompt_text,
                **artifacts,
                expires_at=expires_at,
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
    response = PlainTextResponse(chart["yaml_text"], media_type="text/yaml; charset=utf-8")
    _apply_public_chart_headers(response, chart, max_age=86400)
    return response


@app.get("/chart/{token}/natal.yaml", response_class=PlainTextResponse)
def chart_natal_yaml(token: str):
    chart = _load_chart_or_404(token)
    response = PlainTextResponse(build_base_astrology_yaml(chart["yaml_text"]), media_type="text/yaml; charset=utf-8")
    response.headers["Content-Disposition"] = 'attachment; filename="nanami-natal.yaml"'
    _apply_public_chart_headers(response, chart, max_age=86400)
    return response


@app.get("/chart/{token}/natal-asteroids.yaml", response_class=PlainTextResponse)
def chart_natal_asteroids_yaml(token: str):
    chart = _load_chart_or_404(token)
    response = PlainTextResponse(build_natal_asteroids_yaml(chart["yaml_text"]), media_type="text/yaml; charset=utf-8")
    response.headers["Content-Disposition"] = 'attachment; filename="nanami-natal-asteroids.yaml"'
    _apply_public_chart_headers(response, chart, max_age=86400)
    return response


@app.get("/chart/{token}/transit.yaml", response_class=PlainTextResponse)
def chart_transit_yaml(token: str):
    chart = _load_chart_or_404(token)
    response = PlainTextResponse(build_transit_astrology_yaml(chart["yaml_text"]), media_type="text/yaml; charset=utf-8")
    response.headers["Content-Disposition"] = 'attachment; filename="nanami-transit.yaml"'
    _apply_public_chart_headers(response, chart, max_age=86400)
    return response


@app.get("/chart/{token}/horoscope.svg")
def chart_horoscope_svg(token: str):
    chart = _load_chart_or_404(token)
    svg = chart.get("horoscope_svg")
    if not svg:
        raise HTTPException(status_code=404, detail="horoscope svg not found")
    response = Response(content=svg, media_type="image/svg+xml; charset=utf-8")
    response.headers["Content-Disposition"] = 'attachment; filename="nanami-horoscope.svg"'
    _apply_public_chart_headers(response, chart, max_age=86400)
    return response


@app.get("/chart/{token}/shichusuimei.svg")
def chart_shichusuimei_svg(token: str):
    chart = _load_chart_or_404(token)
    svg = chart.get("shichusuimei_svg")
    if not svg:
        raise HTTPException(status_code=404, detail="shichusuimei svg not found")
    response = Response(content=svg, media_type="image/svg+xml; charset=utf-8")
    response.headers["Content-Disposition"] = 'attachment; filename="nanami-shichusuimei.svg"'
    _apply_public_chart_headers(response, chart, max_age=86400)
    return response


@app.get("/chart/{token}/download.zip")
def chart_download_zip(token: str):
    chart = _load_chart_or_404(token)
    options = chart.get("options") or {}
    product_type = _chart_product_type(options)
    share_yaml_text = _chart_share_yaml_text(chart)
    ai_paste_text = _chart_ai_paste_text(chart, share_yaml_text)
    detail_yaml = share_yaml_text
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("full.yaml", chart["yaml_text"])
        zf.writestr("detail.yaml", detail_yaml)
        zf.writestr("ai_paste.txt", ai_paste_text)
        if product_type == "western_full":
            zf.writestr("natal.yaml", build_base_astrology_yaml(chart["yaml_text"]))
            zf.writestr("natal-asteroids.yaml", build_natal_asteroids_yaml(chart["yaml_text"]))
            zf.writestr("transit.yaml", build_transit_astrology_yaml(chart["yaml_text"]))
        elif product_type == "western_basic":
            zf.writestr("natal.yaml", build_base_astrology_yaml(chart["yaml_text"]))
        if chart.get("horoscope_svg"):
            zf.writestr("horoscope.svg", chart["horoscope_svg"])
        if chart.get("shichusuimei_svg"):
            zf.writestr("shichusuimei.svg", chart["shichusuimei_svg"])
        zf.writestr("prompt.txt", chart["prompt_text"])
        zf.writestr("README.txt", _chart_zip_readme(chart))
    response = Response(content=buffer.getvalue(), media_type="application/zip")
    response.headers["Content-Disposition"] = f'attachment; filename="{_chart_zip_filename(token)}"'
    _apply_public_chart_headers(response, chart, max_age=86400)
    return response


@app.get("/chart/{token}/prompt.txt", response_class=PlainTextResponse)
def chart_prompt(token: str):
    chart = _load_chart_or_404(token)
    response = PlainTextResponse(chart["prompt_text"], media_type="text/plain; charset=utf-8")
    _apply_public_chart_headers(response, chart, max_age=86400)
    return response


@app.get("/chart/{token}", response_class=HTMLResponse)
def chart_page(request: Request, token: str):
    chart = _load_chart_or_404(token)
    options = chart.get("options") or {}
    product_type = _chart_product_type(options)
    is_transit_yaml = product_type == "transit_yaml"
    has_yaml_mode_selector = product_type == "western_full"
    horoscope_svg = chart.get("horoscope_svg") if product_type in {"western_basic", "western_full"} else None
    shichusuimei_svg = chart.get("shichusuimei_svg") if product_type == "shichu" else None
    has_asteroids = False
    birth_time_notice = {"show": False}
    share_yaml_text = _chart_share_yaml_text(chart)
    chart_doc = None
    if has_yaml_mode_selector or not is_transit_yaml:
        try:
            loaded_doc = yaml.safe_load(chart["yaml_text"]) or {}
            chart_doc = loaded_doc if isinstance(loaded_doc, dict) else {}
        except Exception:
            chart_doc = None
    if horoscope_svg:
        try:
            has_asteroids = has_asteroid_svg_data(chart["yaml_text"], doc=chart_doc)
        except Exception:
            has_asteroids = False
    if not is_transit_yaml:
        try:
            birth_time_notice = extract_birth_time_notice(chart["yaml_text"], doc=chart_doc)
        except Exception:
            birth_time_notice = {"show": False}
    expires_at = _chart_expiry(chart)
    expires_label = _chart_expiry_label(expires_at)
    base_url = _public_base_url(request)
    response = templates.TemplateResponse(
        "chart_page.html",
        {
            "request": request,
            "token": token,
            "chart": chart,
            "is_transit_yaml": is_transit_yaml,
            "has_yaml_mode_selector": has_yaml_mode_selector,
            "horoscope_svg": horoscope_svg,
            "shichusuimei_svg": shichusuimei_svg,
            "has_asteroid_svg_data": has_asteroids,
            "birth_time_notice": birth_time_notice,
            "share_yaml_text": share_yaml_text,
            "chart_url": f"{base_url}/chart/{token}",
            "yaml_url": f"{base_url}/chart/{token}.yaml",
            "natal_yaml_url": f"{base_url}/chart/{token}/natal.yaml",
            "natal_asteroids_yaml_url": f"{base_url}/chart/{token}/natal-asteroids.yaml",
            "transit_yaml_url": f"{base_url}/chart/{token}/transit.yaml",
            "horoscope_svg_url": f"{base_url}/chart/{token}/horoscope.svg",
            "shichusuimei_svg_url": f"{base_url}/chart/{token}/shichusuimei.svg",
            "download_zip_url": f"{base_url}/chart/{token}/download.zip",
            "prompt_url": f"{base_url}/chart/{token}/prompt.txt",
            "expires_at": expires_at,
            "expires_label": expires_label,
        },
    )
    _apply_public_chart_headers(response, chart, max_age=300)
    return response


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


@app.get("/admin/post-chart/new", response_class=HTMLResponse)
def post_chart_new(request: Request):
    now = datetime.now(ZoneInfo("Asia/Tokyo"))
    return templates.TemplateResponse(
        "post_chart_form.html",
        {
            "request": request,
            "prefectures": PREFECTURE_OPTIONS,
            "default_date": now.strftime("%Y-%m-%d"),
            "default_time": now.strftime("%H:%M"),
            "form": None,
        },
    )


@app.post("/admin/post-chart/generate", response_class=HTMLResponse)
def post_chart_generate(
    request: Request,
    title: str = Form(""),
    chart_date: str = Form(...),
    chart_time: str = Form(""),
    prefecture: str = Form("東京都"),
):
    form = {
        "title": title,
        "chart_date": chart_date,
        "chart_time": chart_time,
        "prefecture": prefecture,
    }
    try:
        result = build_post_chart(
            title=title,
            chart_date=chart_date.strip(),
            chart_time=chart_time.strip() or None,
            prefecture=prefecture.strip(),
        )
    except Exception as e:
        return templates.TemplateResponse(
            "post_chart_form.html",
            {
                "request": request,
                "prefectures": PREFECTURE_OPTIONS,
                "default_date": chart_date,
                "default_time": chart_time,
                "form": form,
                "error": str(e),
            },
            status_code=400,
        )
    return templates.TemplateResponse(
        "post_chart_result.html",
        {"request": request, "result": result},
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

    if include_shichusuimei and not include_asteroids and not include_transit:
        admin_product_type = "shichu"
    elif include_transit or include_asteroids:
        admin_product_type = "western_full"
    else:
        admin_product_type = "western_basic"
    chart_options = {**doc.get("product", {}).get("options", {}), "product_type": admin_product_type}
    artifacts = _build_chart_artifacts(yaml_text=yaml_text, doc=doc, product_type=admin_product_type)
    expires_at = _chart_expires_at()

    try:
        pg_store.save_chart(
            token=token,
            order_code=None,
            buyer_name=title.strip() or None,
            birth_date=birth_date.strip(),
            birth_time=birth_time.strip() or None,
            birth_place=prefecture.strip(),
            options=chart_options,
            yaml_text=yaml_text,
            prompt_text=prompt_text,
            **artifacts,
            expires_at=expires_at,
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


ADDON_FORM_OPTIONS = [
    {"value": "western_asteroids_addon", "label": "小惑星追加"},
    {"value": "western_31days_transit_addon", "label": "31日トランジット追加"},
    {"value": "shichu_fortune_cycles_addon", "label": "四柱推命 大運・流年追加"},
]


def _addon_form_response(
    request: Request,
    *,
    form: dict[str, str] | None = None,
    result_yaml: str = "",
    transit_result_url: str = "",
    transit_download_url: str = "",
    transit_expires_label: str = "",
    error: str | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    return templates.TemplateResponse(
        "addon_form.html",
        {
            "request": request,
            "addon_options": ADDON_FORM_OPTIONS,
            "form": form or {"addon_type": "western_asteroids_addon", "order_code": "", "base_yaml": ""},
            "result_yaml": result_yaml,
            "transit_result_url": transit_result_url,
            "transit_download_url": transit_download_url,
            "transit_expires_label": transit_expires_label,
            "error": error,
            "addon_form_action": "/addon/generate" if request.url.path.startswith("/addon/") else "/admin/addon/generate",
        },
        status_code=status_code,
    )


def _load_addon_base_yaml(base_yaml: str) -> dict:
    raw_yaml = base_yaml.strip()
    fenced = re.search(r"```(?:yaml|yml)?\s*(.*?)```", raw_yaml, flags=re.I | re.S)
    if fenced:
        raw_yaml = fenced.group(1).strip()
    else:
        version_match = re.search(r"(?m)^version\s*:", raw_yaml)
        if version_match:
            raw_yaml = raw_yaml[version_match.start():].strip()
    try:
        doc = yaml.safe_load(raw_yaml) or {}
    except yaml.YAMLError as exc:
        raise ValueError(
            "YAMLとして読み込めません。"
            "プロンプト文ではなく、version: から始まるYAML本文だけを貼り付けてください。"
        ) from exc
    if not isinstance(doc, dict):
        raise ValueError("YAMLの最上位はオブジェクト形式である必要があります。")
    return doc


def _float_or_none(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _addon_args_from_base_doc(doc: dict) -> dict[str, object]:
    input_block = doc.get("input") or {}
    if not isinstance(input_block, dict):
        raise ValueError("YAML内の input 情報が不正です。")

    birth_date = str(input_block.get("birth_date") or "").strip()
    if not birth_date:
        raise ValueError("YAML内に input.birth_date がありません。")

    calculation_time = str(input_block.get("calculation_time") or "").strip()
    birth_time_value = input_block.get("birth_time")
    birth_time = calculation_time or (str(birth_time_value).strip() if birth_time_value else None)
    if birth_time in {"unknown", "approximate", "morning", "afternoon", "night"}:
        birth_time = calculation_time or None

    birth_place = str(input_block.get("birth_place") or input_block.get("prefecture") or "").strip()
    lat = _float_or_none(input_block.get("birth_lat"))
    lng = _float_or_none(input_block.get("birth_lng"))
    prefecture = str(input_block.get("prefecture") or "").strip()
    birth_place_kind = str(input_block.get("birth_place_kind") or "").strip()
    if birth_place_kind == "overseas":
        prefecture = ""
    if not prefecture and (lat is None or lng is None):
        raise ValueError("海外出生または都道府県なしのYAMLでは input.birth_lat / input.birth_lng が必要です。")

    birth_time_block = doc.get("birth_time") or {}
    if not isinstance(birth_time_block, dict):
        birth_time_block = {}

    return {
        "title": input_block.get("title"),
        "birth_date": birth_date,
        "birth_time": birth_time,
        "prefecture": prefecture,
        "birth_place_label": birth_place or None,
        "birth_lat": lat,
        "birth_lng": lng,
        "tz_name": str(input_block.get("timezone") or "Asia/Tokyo"),
        "gender": str(input_block.get("gender") or "unknown"),
        "birth_time_accuracy": str(input_block.get("birth_time_accuracy") or birth_time_block.get("accuracy") or "auto"),
        "birth_time_range": input_block.get("birth_time_range") if isinstance(input_block.get("birth_time_range"), dict) else None,
        "birth_time_note": str(input_block.get("birth_time_note") or birth_time_block.get("note") or "") or None,
    }


def _validate_addon_base_doc(doc: dict, addon_type: str) -> None:
    systems = doc.get("systems") or {}
    if not isinstance(systems, dict):
        raise ValueError("YAML内の systems 情報が不正です。")
    western = systems.get("western") or {}
    shichu = systems.get("shichusuimei") or {}

    if addon_type in {"western_asteroids_addon", "western_31days_transit_addon"}:
        if not isinstance(western, dict) or not isinstance(western.get("natal"), dict):
            raise ValueError("western addon には western の基本版YAMLが必要です。")
        return

    if addon_type == "shichu_fortune_cycles_addon":
        if not isinstance(shichu, dict) or not isinstance(shichu.get("normalized_data"), dict):
            raise ValueError("shichu addon には shichusuimei の基本版YAMLが必要です。")
        return

    raise ValueError("未対応のaddon種別です。")


def _build_addon_yaml_from_base(doc: dict, addon_type: str) -> str:
    _validate_addon_base_doc(doc, addon_type)
    args = _addon_args_from_base_doc(doc)
    if addon_type == "western_asteroids_addon":
        yaml_text, _prompt_text, _addon_doc = build_asteroid_addon_yaml(**args)
        return yaml_text
    if addon_type == "western_31days_transit_addon":
        yaml_text, _prompt_text, _addon_doc = build_31days_transit_addon_yaml(**args)
        return yaml_text

    shichu = ((doc.get("systems") or {}).get("shichusuimei") or {})
    assumptions = ((shichu.get("input") or {}).get("assumptions") or {})
    args["day_change_at_23"] = bool(assumptions.get("day_change_at_23"))
    yaml_text, _prompt_text, _addon_doc = build_shichu_fortune_cycles_addon_yaml(**args)
    return yaml_text


def _transit_addon_expires_at() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=32)


def _redeem_and_save_transit_addon_or_raise(order_code: str, addon_type: str, yaml_text: str) -> tuple[str, datetime]:
    if not os.environ.get("DATABASE_URL"):
        raise ValueError("注文番号照合用のDATABASE_URLが未設定です。管理者に連絡してください。")
    order_code_clean = _normalize_stores_order_no(order_code)
    if not order_code_clean:
        raise ValueError("STORESオーダー番号を入力してください。")
    if not re.fullmatch(r"\d{10}", order_code_clean):
        raise ValueError("STORESオーダー番号は10桁の数字で入力してください。")

    last_exc: Exception | None = None
    for _ in range(3):
        token = secrets.token_urlsafe(24)
        expires_at = _transit_addon_expires_at()
        try:
            status, order_row = pg_store.redeem_addon_order_and_save_transit_link(
                order_code=order_code_clean,
                addon_type=addon_type,
                token=token,
                yaml_text=yaml_text,
                expires_at=expires_at,
            )
            if status == "not_found" and _truthy(os.getenv("STORES_MAIL_SYNC_ON_SUBMIT", "1")):
                _sync_stores_orders_for_lookup()
                status, order_row = pg_store.redeem_addon_order_and_save_transit_link(
                    order_code=order_code_clean,
                    addon_type=addon_type,
                    token=token,
                    yaml_text=yaml_text,
                    expires_at=expires_at,
                )
        except Exception as exc:
            last_exc = exc
            continue

        if status == "ok":
            return token, expires_at
        if status == "not_found":
            raise ValueError(f"注文番号（{order_code_clean}）が見つかりません。STORESの購入確認メールに記載の番号を確認してください。")
        if status == "already_used":
            raise ValueError(f"この注文番号（{order_code_clean}）は、この追加部品ですでに使用済みです。")
        if status == "cancelled":
            raise ValueError(f"この注文番号（{order_code_clean}）はキャンセル扱いのため使用できません。")
        if status == "product_mismatch":
            purchased_type = (order_row or {}).get("product_type")
            raise ValueError(
                f"この注文番号は{_product_label(purchased_type)}用です。"
                f"{_product_label(addon_type)}の生成には使用できません。"
            )
        raise ValueError("注文番号を確認できませんでした。時間をおいて再度お試しください。")

    raise ValueError(f"トランジットデータの一時保存に失敗しました: {last_exc}")


def _redeem_addon_order_or_raise(order_code: str, addon_type: str) -> str:
    order_code_clean = _normalize_stores_order_no(order_code)
    if not order_code_clean:
        raise ValueError("STORESオーダー番号を入力してください。")
    if not re.fullmatch(r"\d{10}", order_code_clean):
        raise ValueError("STORESオーダー番号は10桁の数字で入力してください。")
    if not os.environ.get("DATABASE_URL"):
        raise ValueError("注文番号照合用のDATABASE_URLが未設定です。管理者に連絡してください。")

    try:
        status, order_row = pg_store.redeem_addon_order(order_code=order_code_clean, addon_type=addon_type)
        if status == "not_found" and _truthy(os.getenv("STORES_MAIL_SYNC_ON_SUBMIT", "1")):
            _sync_stores_orders_for_lookup()
            status, order_row = pg_store.redeem_addon_order(order_code=order_code_clean, addon_type=addon_type)
    except Exception as exc:
        raise ValueError(f"注文番号の照合に失敗しました: {exc}") from exc

    if status == "ok":
        return order_code_clean
    if status == "not_found":
        raise ValueError(f"注文番号（{order_code_clean}）が見つかりません。STORESの購入確認メールに記載の番号を確認してください。")
    if status == "already_used":
        raise ValueError(f"この注文番号（{order_code_clean}）は、この追加部品ですでに使用済みです。")
    if status == "cancelled":
        raise ValueError(f"この注文番号（{order_code_clean}）はキャンセル扱いのため使用できません。")
    if status == "product_mismatch":
        purchased_type = (order_row or {}).get("product_type")
        raise ValueError(
            f"この注文番号は{_product_label(purchased_type)}用です。"
            f"{_product_label(addon_type)}の生成には使用できません。"
        )
    raise ValueError("注文番号を確認できませんでした。時間をおいて再度お試しください。")


@app.get("/admin/addon/new", response_class=HTMLResponse)
def addon_new(request: Request):
    return _addon_form_response(request)


@app.get("/addon/new", response_class=HTMLResponse)
def public_addon_new(request: Request):
    return _addon_form_response(request)


@app.post("/admin/addon/generate", response_class=HTMLResponse)
@app.post("/addon/generate", response_class=HTMLResponse)
def addon_generate(
    request: Request,
    addon_type: str = Form("western_asteroids_addon"),
    order_code: str = Form(""),
    base_yaml: str = Form(""),
):
    form = {"addon_type": addon_type, "order_code": order_code, "base_yaml": base_yaml}
    if addon_type not in {item["value"] for item in ADDON_FORM_OPTIONS}:
        return _addon_form_response(request, form=form, error="addon種別が不正です。", status_code=400)
    if not base_yaml.strip():
        return _addon_form_response(request, form=form, error="基本版YAMLを貼り付けてください。", status_code=400)
    try:
        doc = _load_addon_base_yaml(base_yaml)
        result_yaml = _build_addon_yaml_from_base(doc, addon_type)
        if addon_type == "western_31days_transit_addon":
            token, expires_at = _redeem_and_save_transit_addon_or_raise(order_code, addon_type, result_yaml)
            base_url = _public_base_url(request)
            result_url = f"{base_url}/addon/transit/{token}"
            return _addon_form_response(
                request,
                form=form,
                transit_result_url=result_url,
                transit_download_url=f"{result_url}.yaml",
                transit_expires_label=_chart_expiry_label(expires_at),
            )
        _redeem_addon_order_or_raise(order_code, addon_type)
    except Exception as exc:
        return _addon_form_response(request, form=form, error=str(exc), status_code=400)
    return _addon_form_response(request, form=form, result_yaml=result_yaml)


def _load_transit_addon_link(token: str) -> tuple[dict | None, bool]:
    if not re.fullmatch(r"[A-Za-z0-9_-]{20,120}", token):
        raise HTTPException(status_code=404, detail="transit addon not found")
    link = pg_store.get_transit_addon_link(token)
    if not link:
        raise HTTPException(status_code=404, detail="transit addon not found")
    expires_at = _chart_expiry(link)
    expired = bool(expires_at and datetime.now(timezone.utc) >= expires_at)
    return link, expired


@app.get("/addon/transit/{token}.yaml", response_class=PlainTextResponse)
@app.get("/admin/addon/transit/{token}.yaml", response_class=PlainTextResponse)
def transit_addon_yaml(token: str):
    link, expired = _load_transit_addon_link(token)
    if expired:
        return PlainTextResponse("このトランジットデータの有効期限は終了しました。\n", status_code=410)
    response = PlainTextResponse(str((link or {}).get("yaml_text") or ""), media_type="text/yaml; charset=utf-8")
    response.headers["Content-Disposition"] = 'attachment; filename="nanami-transit-addon.yaml"'
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


@app.get("/addon/transit/{token}", response_class=HTMLResponse)
@app.get("/admin/addon/transit/{token}", response_class=HTMLResponse)
def transit_addon_page(request: Request, token: str):
    link, expired = _load_transit_addon_link(token)
    expires_at = _chart_expiry(link or {})
    return templates.TemplateResponse(
        "transit_addon_page.html",
        {
            "request": request,
            "expired": expired,
            "yaml_text": "" if expired else str((link or {}).get("yaml_text") or ""),
            "expires_label": _chart_expiry_label(expires_at),
            "download_url": f"/addon/transit/{token}.yaml",
        },
        status_code=410 if expired else 200,
    )


# ─── 共通ヘルパー ────────────────────────────────────────────────

def _chart_product_type(options: dict) -> str | None:
    product_type = options.get("product_type") if isinstance(options, dict) else None
    if product_type:
        return str(product_type)
    if not isinstance(options, dict):
        return None
    if options.get("shichusuimei") and not options.get("western_natal"):
        return "shichu"
    if options.get("transit") or options.get("asteroids"):
        return "western_full"
    if options.get("western_natal"):
        return "western_basic"
    return None


def _chart_expiry(chart: dict) -> datetime | None:
    expires_at = chart.get("expires_at")
    if isinstance(expires_at, datetime):
        return expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=timezone.utc)
    if isinstance(expires_at, str) and expires_at.strip():
        try:
            parsed = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    created_at = chart.get("created_at")
    if isinstance(created_at, datetime):
        base = created_at if created_at.tzinfo else created_at.replace(tzinfo=timezone.utc)
        return base + timedelta(days=CHART_EXPIRES_DAYS)
    if isinstance(created_at, str) and created_at.strip():
        try:
            parsed = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            base = parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
            return base + timedelta(days=CHART_EXPIRES_DAYS)
        except ValueError:
            return None
    return None


def _chart_expiry_label(expires_at: datetime | None) -> str:
    if not expires_at:
        return "発行から90日間"
    dt = expires_at.astimezone(ZoneInfo("Asia/Tokyo"))
    return f"{dt.year}年{dt.month}月{dt.day}日 {dt.hour:02d}:{dt.minute:02d}まで"


def _chart_zip_filename(token: str) -> str:
    safe_token = re.sub(r"[^A-Za-z0-9_-]", "", token)[:32] or "data"
    return f"nanami_chart_{safe_token}.zip"


def _chart_share_yaml_text(chart: dict) -> str:
    share_yaml_text = chart.get("share_yaml_text") or chart["yaml_text"]
    options = chart.get("options") or {}
    if _chart_product_type(options) == "western_full" and not chart.get("share_yaml_text"):
        try:
            return build_light_astrology_yaml(chart["yaml_text"])
        except Exception:
            return chart["yaml_text"]
    return share_yaml_text


def _chart_ai_paste_text(chart: dict, share_yaml_text: str | None = None) -> str:
    prompt_text = str(chart.get("prompt_text") or "").rstrip()
    yaml_text = share_yaml_text or chart.get("share_yaml_text") or chart.get("yaml_text") or ""
    parts = [prompt_text, "", "---", "", "以下がYAMLデータです。", "", "```yaml", str(yaml_text), "```"]
    return "\n".join(parts).rstrip() + "\n"


def _chart_zip_readme(chart: dict) -> str:
    expires_label = _chart_expiry_label(_chart_expiry(chart))
    return f"""nanami-products 鑑定データ保存用ZIP

このZIPは鑑定データを手元に保存するためのファイルです。
共有URLの有効期限は発行から90日間です。このデータページは {expires_label} に開けなくなります。

AIに渡す場合:
- ai_paste.txt: AIに渡す推奨ファイルです。軽量版なので、迷ったらまずこれを使ってください。
- natal-asteroids.yaml: 小惑星データを含む場合に、追加で詳しく読ませたいときに添付します。
- transit.yaml: トランジット詳細を追加したい場合に添付します。
- prompt.txt: AIへの読み方の指示文です。この内容は ai_paste.txt にも含まれています。

保存・確認用:
- full.yaml: 保存・検証用の完全版データです。細かく確認したい場合に使います。
- detail.yaml: AIに渡しやすい軽量版YAMLです。ai_paste.txt の元データに近い内容です。
- natal.yaml: ネイタル基本データです。出生図だけを確認したい場合に使います。

図の確認:
- horoscope.svg が入っている場合は、ホロスコープ図として確認できます。
- shichusuimei.svg が入っている場合は、四柱推命の命式図として確認できます。

注意:
- YAML内の天体位置・ハウス・アスペクトなどは計算済みデータです。
- AIに依頼するときは、生年月日から再計算せず、このYAMLを根拠に解釈するよう伝えてください。
"""


def _apply_public_chart_headers(response: Response, chart: dict, *, max_age: int) -> None:
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    expires_at = _chart_expiry(chart)
    if expires_at:
        seconds_left = int((expires_at - datetime.now(timezone.utc)).total_seconds())
        if seconds_left <= 0:
            response.headers["Cache-Control"] = "no-store"
            return
        max_age = max(0, min(max_age, seconds_left))
    response.headers["Cache-Control"] = f"public, max-age={max_age}"


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
    expires_at = _chart_expiry(chart)
    if expires_at and datetime.now(timezone.utc) >= expires_at:
        raise HTTPException(status_code=410, detail="chart expired")
    return chart
