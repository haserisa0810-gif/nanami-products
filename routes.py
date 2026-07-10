from __future__ import annotations

import base64
import copy
import csv
import hashlib
import io
import json
import logging
import os
import re
import secrets
import subprocess
import time
import zipfile
from html import escape as html_escape
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import yaml
from fastapi import Body, FastAPI, Form, Header, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markupsafe import Markup

from services import pg_store, stores_mail_sync
from services.api_calc import calc_combined_api, calc_shichu_api, calc_transit_api, calc_western_api
from services.api_demo import build_demo_response, build_demo_shichu_svg, build_demo_svg
from services.birth_time import extract_birth_time_notice, resolve_birth_time_accuracy
from services.chart_svg import build_horoscope_svg_from_yaml, has_asteroid_svg_data
from services.api_yaml import build_handoff_yaml
from services.location import PREFECTURE_OPTIONS, prefecture_full_name, resolve_municipality, resolve_prefecture
from services.light_yaml import (
    build_base_astrology_yaml,
    build_detail_astrology_yaml,
    build_light_astrology_yaml,
    build_natal_asteroids_yaml,
    build_transit_astrology_yaml,
)
from services.long_term_transit_yaml import build_ai_long_term_transits_yaml, build_long_term_transits_yaml, has_long_term_transits
from services.mundane_chart import build_mundane_chart_svg_from_yaml, mundane_aspect_summary_from_yaml
from services.mundane_yaml import generate_mundane_yaml
from services.mcp_chart_service import (
    ChartMcpError,
    extract_chart_id_from_url,
    get_available_sections_from_url,
    get_astrology_prompt,
    get_chart_summary_from_url,
    get_chart_yaml_from_url,
    get_download_info_from_url,
    mask_chart_id,
)
from services.note_transit import (
    NoteTransitCampaign,
    get_note_transit_campaign_by_access_key,
)
from services.post_chart import build_post_chart
from services.prompt_builder import build_prompt, ensure_transit_date_guidance
from services.shichu_chart import (
    build_shichusuimei_svg_from_yaml,
    is_shichusuimei_png_renderer_available,
    render_shichusuimei_png_from_svg,
)
from services.svg_optimize import optimize_svg
from services.transit_yaml import build_transit_only_yaml
from services.yaml_exporter import (
    build_31days_transit_addon_yaml,
    build_asteroid_addon_yaml,
    build_product_yaml,
    build_shichu_fortune_cycles_addon_yaml,
    validate_yaml_option_section_consistency,
)

app = FastAPI(title="nanami-products")
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/kaii", StaticFiles(directory="kaii", html=True), name="kaii")
templates = Jinja2Templates(directory="templates")
logger = logging.getLogger("nanami.chart")
TRANSIENT_ERROR_MARKERS = (
    "ssl connection has been closed unexpectedly",
    "server closed the connection unexpectedly",
    "connection already closed",
    "connection not open",
    "terminating connection",
    "could not receive data from server",
    "could not send data to server",
    "timeout expired",
    "too many connections",
    "connection pool exhausted",
)
USER_TRANSIENT_ERROR_MESSAGE = (
    "通信が一時的に不安定でした。少し時間をおいて再試行してください。"
    "すでに生成が完了している場合は、同じ注文番号で再送信すると生成済みページへ戻ります。"
)


def _elapsed_ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 2)


def _is_transient_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(marker in message for marker in TRANSIENT_ERROR_MARKERS)


def _public_error_message(exc: Exception, *, fallback: str = "処理に失敗しました。時間をおいて再試行してください。") -> str:
    if _is_transient_error(exc):
        return USER_TRANSIENT_ERROR_MESSAGE
    return fallback


def _mark_no_store(response: Response) -> Response:
    response.headers["Cache-Control"] = "no-store, max-age=0, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


def _raise_chart_yaml_generation_error(token: str, endpoint: str, exc: Exception) -> None:
    logger.exception(
        "chart_yaml_generation_failed token=%s endpoint=%s error=%r",
        token,
        endpoint,
        exc,
    )
    raise HTTPException(
        status_code=500,
        detail="YAMLデータの生成に失敗しました。時間をおいて再試行してください。",
    ) from exc


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
_ASSET_CONTENT_VERSIONS: dict[str, str] = {}


def _asset_url(path: str) -> str:
    clean_path = path.lstrip("/")
    version = _ASSET_CONTENT_VERSIONS.get(clean_path)
    if version is None:
        try:
            asset_path = Path(__file__).resolve().parent / "static" / clean_path
            version = hashlib.sha256(asset_path.read_bytes()).hexdigest()[:12]
        except Exception:
            version = ASSET_VERSION
        _ASSET_CONTENT_VERSIONS[clean_path] = version
    return f"/static/{clean_path}?v={version}"


templates.env.globals.update(asset_version=ASSET_VERSION, asset_url=_asset_url)


MCP_TOOL_DEFINITIONS = [
    {
        "name": "get_chart_yaml_from_url",
        "description": (
            "Chart URLからAI解釈用YAMLを取得します。ネイタル、トランジット、小惑星、"
            "四柱推命、インド占星術などのセクションを必要に応じて取得できます。"
            "URLはアクセスキーとして扱われます。期限が近い場合は保存案内を返し、"
            "期限切れの場合はYAMLを返しません。今日の占い、ホロスコープ、ネイタルチャート、"
            "トランジット、小惑星を読む依頼では、先に get_chart_summary_from_url と "
            "get_astrology_prompt を呼び、取得した鑑定ルールに沿ってこのYAMLを解釈してください。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "chart_url": {"type": "string", "description": "https://chart.nanami-astro.com/chart/{chart_id}"},
                "sections": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["natal", "transit_31days", "long_term", "asteroid", "shichu", "indian"],
                    },
                    "description": "必要なセクション。未指定なら利用可能な全YAMLを返します。",
                },
                "format": {"type": "string", "enum": ["full"], "default": "full"},
            },
            "required": ["chart_url"],
        },
    },
    {
        "name": "get_chart_summary_from_url",
        "description": (
            "Chart URLから商品種別、生成日時、有効期限、残り日数、含まれるセクション一覧を確認します。"
            "URLはアクセスキーとして扱われ、期限切れの場合は保存済みYAML利用または再購入案内を返します。"
            "今日の占い、ネイタル、トランジット、小惑星を読む前の最初の確認ツールとして使ってください。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"chart_url": {"type": "string", "description": "https://chart.nanami-astro.com/chart/{chart_id}"}},
            "required": ["chart_url"],
        },
    },
    {
        "name": "get_astrology_prompt",
        "description": (
            "nanami-products側の西洋占星術鑑定ルール・出力構成・禁止事項を返します。"
            "今日の占い、ホロスコープ、ネイタルチャート、トランジット、小惑星を使う依頼では、"
            "Chart YAMLを解釈する前に必ずこのツールで鑑定プロンプトを取得してください。"
            "MCPは鑑定本文を生成せず、AIはこのプロンプトと get_chart_yaml_from_url のYAMLだけを根拠に解釈します。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "purpose": {
                    "type": "string",
                    "enum": ["today_fortune", "monthly_flow", "natal_with_transit", "relationship", "work_activity", "long_term"],
                    "default": "today_fortune",
                    "description": "MVPでは today_fortune / natal_with_transit に対応します。",
                },
                "product_type": {
                    "type": "string",
                    "default": "western_31days_transit_addon",
                    "description": "Chart summary の product_type が分かる場合に渡してください。",
                },
            },
        },
    },
    {
        "name": "get_available_sections_from_url",
        "description": (
            "Chart URLに含まれるネイタル、トランジット、小惑星、四柱推命などの利用可能セクション一覧を返します。"
            "URLはアクセスキーとして扱われます。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"chart_url": {"type": "string", "description": "https://chart.nanami-astro.com/chart/{chart_id}"}},
            "required": ["chart_url"],
        },
    },
    {
        "name": "get_download_info_from_url",
        "description": (
            "Chart URLのYAMLダウンロードURL、ファイル名、有効期限、保存推奨メッセージを返します。"
            "期限が近い場合は保存案内を返し、期限切れの場合はYAMLを返さず再購入導線を案内します。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"chart_url": {"type": "string", "description": "https://chart.nanami-astro.com/chart/{chart_id}"}},
            "required": ["chart_url"],
        },
    },
]


def _mcp_result(request_id, result: dict) -> JSONResponse:
    return JSONResponse({"jsonrpc": "2.0", "id": request_id, "result": result})


def _mcp_error(request_id, code: int, message: str, *, data: dict | None = None) -> JSONResponse:
    error: dict[str, object] = {"code": code, "message": message}
    if data:
        error["data"] = data
    return JSONResponse({"jsonrpc": "2.0", "id": request_id, "error": error})


def _mcp_tool_content(payload: dict, *, is_error: bool = False) -> dict:
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(payload, ensure_ascii=False, indent=2, default=str),
            }
        ],
        "isError": is_error,
    }


def _call_mcp_tool(name: str, arguments: dict) -> dict:
    if not isinstance(arguments, dict):
        raise ChartMcpError("arguments は object で指定してください。", code="invalid_arguments")
    if name == "get_chart_yaml_from_url":
        sections = arguments.get("sections")
        if sections is not None and not isinstance(sections, list):
            raise ChartMcpError("sections は配列で指定してください。", code="invalid_sections")
        return get_chart_yaml_from_url(
            chart_url=str(arguments.get("chart_url") or ""),
            sections=sections,
            format=str(arguments.get("format") or "full"),
        )
    if name == "get_chart_summary_from_url":
        return get_chart_summary_from_url(chart_url=str(arguments.get("chart_url") or ""))
    if name == "get_astrology_prompt":
        return get_astrology_prompt(
            purpose=str(arguments.get("purpose") or "today_fortune"),
            product_type=str(arguments.get("product_type") or ""),
        )
    if name == "get_available_sections_from_url":
        return get_available_sections_from_url(chart_url=str(arguments.get("chart_url") or ""))
    if name == "get_download_info_from_url":
        return get_download_info_from_url(chart_url=str(arguments.get("chart_url") or ""))
    raise ChartMcpError("未知のMCPツールです。", code="unknown_tool")


@app.post("/mcp")
async def mcp_endpoint(request: Request):
    try:
        body = await request.json()
    except Exception:
        return _mcp_error(None, -32700, "Invalid JSON")
    request_id = body.get("id") if isinstance(body, dict) else None
    if not isinstance(body, dict):
        return _mcp_error(request_id, -32600, "Invalid Request")
    method = str(body.get("method") or "")
    params = body.get("params") if isinstance(body.get("params"), dict) else {}

    if method == "initialize":
        return _mcp_result(
            request_id,
            {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "nanami-products-mcp", "version": ASSET_VERSION},
                "capabilities": {"tools": {}},
            },
        )
    if method == "notifications/initialized":
        return Response(status_code=202)
    if method == "tools/list":
        return _mcp_result(request_id, {"tools": MCP_TOOL_DEFINITIONS})
    if method == "tools/call":
        name = str(params.get("name") or "")
        arguments = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
        chart_url = str(arguments.get("chart_url") or "")
        try:
            chart_id = extract_chart_id_from_url(chart_url) if chart_url else ""
            payload = _call_mcp_tool(name, arguments)
            if chart_id:
                logger.info("mcp_tool_call_ok tool=%s chart_id=%s", name, mask_chart_id(chart_id))
            return _mcp_result(request_id, _mcp_tool_content(payload))
        except ChartMcpError as exc:
            masked = ""
            try:
                masked = mask_chart_id(extract_chart_id_from_url(chart_url)) if chart_url else ""
            except Exception:
                masked = ""
            logger.info("mcp_tool_call_rejected tool=%s chart_id=%s code=%s", name, masked, exc.code)
            return _mcp_result(
                request_id,
                _mcp_tool_content(
                    {"ok": False, "error_code": exc.code, "message": str(exc)},
                    is_error=True,
                ),
            )
        except Exception:
            logger.exception("mcp_tool_call_failed tool=%s", name)
            return _mcp_result(
                request_id,
                _mcp_tool_content(
                    {"ok": False, "error_code": "internal_error", "message": "内部エラーが発生しました。時間をおいて再度お試しください。"},
                    is_error=True,
                ),
            )
    return _mcp_error(request_id, -32601, "Method not found")


@app.get("/favicon.ico")
def favicon():
    return RedirectResponse("/static/favicon.svg", status_code=307)


@app.middleware("http")
async def _asset_cache_control_middleware(request: Request, call_next):
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception as exc:
        logger.exception(
            "request_failed path=%s method=%s elapsed_ms=%s error_type=%s error=%r",
            request.url.path,
            request.method,
            _elapsed_ms(start),
            type(exc).__name__,
            exc,
        )
        raise
    elapsed_ms = _elapsed_ms(start)
    if elapsed_ms >= float(os.getenv("SLOW_REQUEST_LOG_MS", "12000")):
        logger.warning(
            "slow_request path=%s method=%s status=%s elapsed_ms=%s",
            request.url.path,
            request.method,
            response.status_code,
            elapsed_ms,
        )
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
NO_EXPIRY_CHART_POLICY = "no_expiry"
SUPPORTED_LANGS = {"ja", "en"}

I18N = {
    "ja": {
        "lang_label": "表示言語",
        "lang_ja": "日本語",
        "lang_en": "English",
        "product_labels": {
            "western_basic": "ホロスコープ基本版",
            "western_full": "ホロスコープFULL版",
            "western_asteroids_addon": "ホロスコープ：小惑星追加",
            "shichu": "四柱推命鑑定",
            "transit_yaml": "トランジットYAML版",
        },
        "product_leads": {
            "western_basic": "注文番号と出生情報を入力してください。",
            "western_full": "小惑星・トランジット（1ヶ月）を含む出生図データを作成します。<br>注文番号と出生情報を入力してください。",
            "shichu": "四柱推命に必要な情報を入力してください。<br>日替わり境界は、標準の1時（丑の刻）または23時から選択できます。",
        },
        "start_title_suffix": "鑑定データ作成",
        "start_notice_title": "登録前に必ず確認してください",
        "start_notice_items": [
            "<strong>注文番号は1回だけ使用できます。</strong>一度生成すると再生成できません。",
            "<strong>送信後の入力変更はできません。</strong>生年月日・出生時刻・出生地をよく確認してください。",
            "出生時刻が不明な場合は空欄のままで構いません（正午で計算します）。",
            "生成後に表示されるURLは、必ず保存してください。",
        ],
        "product_summary_title": "購入商品",
        "input_contents_title": "入力する内容",
        "start_transit_input_items": [
            "注文番号",
            "メールアドレス（任意）",
            "イベント名",
            "日付・時刻・タイムゾーン",
            "場所名・緯度・経度",
            "Julian / Gregorian の暦種別",
        ],
        "start_flow_title": "作成の流れ",
        "start_transit_flow_items": [
            "STORESの注文番号を入力します。",
            "イベント日時と場所を入力します。",
            "暦種別を選択します。",
            "確認チェックを入れて送信します。",
            "AI分析用のYAMLデータが表示されます。",
        ],
        "product_type_label": "商品タイプ",
        "start_button": "入力フォームへ進む",
        "start_input_hint": "注文番号と出生情報を入力してください。",
        "input_title_suffix": "鑑定データ入力",
        "shichu_input_title_suffix": "データ入力",
        "precheck": "入力前チェック",
        "precheck_strong": "送信後は同じ注文番号で再生成できません。",
        "precheck_note": "生年月日・出生時刻・出生地を確認してから送信してください。",
        "order_info": "注文情報",
        "order_provider": "購入元",
        "provider_stores": "STORES",
        "provider_gumroad": "Gumroad",
        "provider_payhip": "Payhip",
        "stores_order": "注文番号",
        "payhip_email": "購入時のメールアドレス",
        "payhip_product": "購入した商品",
        "payhip_order_id": "Order ID / Invoice Number",
        "payhip_order_id_optional": "Order ID / Invoice Number（任意）",
        "payhip_order_hint": "Payhipの購入メールに表示されているOrder IDを入力してください。",
        "required": "必須",
        "optional": "任意",
        "not_entered": "未入力",
        "order_help": "注文番号を入力してください。",
        "order_mail_hint": "STORESから届く購入完了メールに記載されている注文番号を入力してください。例：#12345678 など",
        "name": "お名前",
        "birth_info": "出生情報",
        "birth_date": "生年月日",
        "birth_date_manual_hint": "数字だけ入力すると YYYY-MM-DD 形式で表示されます。例：1990-01-01",
        "birth_date_required_error": "生年月日を入力してください。",
        "birth_date_format_error": "生年月日は YYYY-MM-DD 形式になるよう8桁の数字で入力してください。例：1990-01-01",
        "birth_date_invalid_error": "存在しない日付です。YYYY-MM-DD として解釈できる日付を入力してください。",
        "birth_date_future_error": "未来日は指定できません。",
        "birth_time_accuracy": "出生時刻の精度",
        "time_exact": "正確な時刻あり",
        "time_unknown": "不明",
        "time_morning": "午前",
        "time_afternoon": "午後",
        "time_night": "夜",
        "time_accuracy_help": "推定時刻の場合、ハウス・ASC・MCなどは参考値になります。",
        "birth_time": "出生時刻",
        "birth_time_help": "正確な出生時刻が分かる場合のみ入力してください。",
        "prefecture": "出生都道府県",
        "select_placeholder": "選択してください",
        "place_details": "出生地の詳細",
        "place_kind": "出生地区分",
        "domestic": "国内",
        "international": "海外",
        "coordinates": "緯度・経度で入力",
        "domestic_place_note": "都道府県は必須です。市区町村は任意です。対応する座標があれば市区町村を使用し、緯度・経度を入力した場合はそちらを最優先で使用します。",
        "domestic_coordinates_summary": "詳細座標を指定する（任意）",
        "domestic_coordinates_note": "緯度・経度を入力した場合は、市区町村や都道府県の代表座標より優先して使用します。",
        "overseas_place_note": "海外出生地は、国・都市に加えて緯度・経度・タイムゾーンの入力が必要です。",
        "coordinates_place_note": "出生地を緯度・経度で指定したい場合はこちらを使ってください。",
        "coordinates_range_note": "緯度は -90〜90、経度は -180〜180 の数値で入力してください。",
        "birth_place_country_city": "国・都市",
        "birth_place_city": "市区町村",
        "latitude": "緯度",
        "longitude": "経度",
        "coordinate_note": "空欄なら都道府県の代表座標を使います。市区町村単位など、より細かく指定したい場合だけ入力してください。",
        "international_coordinate_help": "You can search coordinates using Google Maps.",
        "timezone": "タイムゾーン",
        "timezone_other": "その他（手入力）",
        "timezone_custom_placeholder": "例：America/New_York",
        "timezone_help": "出生地に近い地域を選んでください。リストにない場合だけ「その他」を使います。",
        "gender": "性別",
        "gender_unknown": "指定なし",
        "gender_female": "女性",
        "gender_male": "男性",
        "gender_help": "四柱推命の大運計算に使用します。不明な場合は「指定なし」のまま送信できます。",
        "shichu_settings": "四柱推命設定",
        "day_change": "日替わり境界",
        "standard_1am": "1時（丑の刻）— 標準",
        "day_change_help": "23時切替の流派で見る場合のみ「23時」を選択してください。",
        "final_check": "最終確認",
        "final_check_hint": "送信後は、この注文番号で再生成できません。入力内容に間違いがある場合も、購入者側では変更できません。",
        "final_agree": "入力内容を確認しました。送信後に変更できないことに同意します。",
        "submit_generate": "AI鑑定データを生成する",
        "submit_confirm": "この内容でAI鑑定データを生成します。送信後は変更・再生成できません。よろしいですか？",
        "confirm_title": "最終確認",
        "confirm_lead": "作成前に入力内容を確認してください。",
        "confirm_modify": "修正する",
        "confirm_create": "この内容で作成する",
        "confirm_order": "注文番号",
        "confirm_name": "名前",
        "confirm_birth_date": "生年月日",
        "confirm_birth_time": "出生時刻",
        "confirm_birth_place_mode": "出生地入力モード",
        "confirm_birth_place": "出生地",
        "confirm_coordinates": "緯度・経度",
        "submit_loading_button": "生成中です...",
        "submit_loading_title": "鑑定データを生成しています",
        "submit_loading_desc": "通信状況や初回起動により時間がかかる場合があります。この画面のままお待ちください。",
        "chart_eyebrow": "AI鑑定データ",
        "analysis_eyebrow": "AI分析データ",
        "chart_title": "さん専用の鑑定データ",
        "chart_title_default": "あなたさん専用の鑑定データ",
        "transit_title_default": "イベント",
        "transit_title_suffix": "のトランジットYAML",
        "chart_lead": "AI鑑定用に整理された基本データです。「AIに送る」からそのまま使えます。",
        "transit_lead": "このデータをAIに貼るだけで、イベント時点の天体配置分析を始められます。<br>出生情報を使わない、トランジットのみのYAMLです。",
        "birthday": "生年月日",
        "date": "日付",
        "time": "時刻",
        "calc_time": "計算用時刻",
        "birth_time_badge": "出生時刻",
        "place": "場所",
        "birth_place": "出生地",
        "unknown": "不明",
        "page_expiry": "このページはURLを知っている人が開けます。有効期限は{expires_label}（発行から90日間）です。",
        "page_no_expiry": "このページはURLを知っている人が開けます。有効期限はありません。",
        "steps_title": "3ステップで鑑定をはじめる",
        "step1_title": "データをAIに渡す",
        "step1_desc": "下のボタンから、鑑定用データをAIへ送ります。",
        "step2_title": "そのまま送信する",
        "step2_desc": "ChatGPT / Claude / Gemini などで使えます。",
        "step3_title": "鑑定を受け取る",
        "step3_desc": "返ってきた内容に、そのまま続けて質問できます。",
        "guide_link": "初めての方はこちら（使い方）",
        "guide_desc": "初めての方は、画面を見ながら手順を確認できます。",
        "page_url": "このページのURL",
        "event_url": "このイベントデータのURL",
        "copy_label": "コピー",
        "page_url_hint": "あとで開き直したい場合や、別の端末で使いたい場合にコピーしてください。",
        "send_to_ai": "AIへ渡す",
        "send_ai_button": "AIに送る",
        "fallback_summary": "うまくいかない場合",
        "fallback_desc": "AIに直接送れない場合は、コピーまたはTXT保存をご利用ください。",
        "copy_to_use": "コピーして使う",
        "save_txt_to_use": "TXTを保存して使う",
        "yaml_only_title": "AI活用向けYAML",
        "copy_yaml_only": "選んだ版のYAMLをコピー",
        "copy_yaml_only_hint": "占いプロンプトを含まないYAMLデータです。保存や他のAIサービスでの活用に利用できます。",
        "yaml_only_title_long_term": "AI用データ",
        "copy_yaml_only_long_term": "AI用データをコピー",
        "copy_yaml_only_hint_long_term": "長期トランジットでは、ChatGPTに貼るための軽量版をコピーします。完全版はTXT保存またはZIP保存をご利用ください。",
        "yaml_only_copied": "YAMLデータだけをコピーしました。",
        "yaml_only_copied_long_term": "AI用データをコピーしました。",
        "yaml_only_copy_failed": "YAMLデータをコピーできませんでした。時間をおいて再度お試しください。",
        "helper_note": "ChatGPT / Claude / Gemini など各種AIサービスに対応",
        "full_asteroid_note": "FULL版には、小惑星を含む詳しいデータも入っています。<br>もっと深く鑑定したい時に使えます。<br>",
        "full_asteroid_link": "FULL版の小惑星データを見る",
        "transit_detail_note": "このページには、この商品に含まれるトランジットの詳しいデータが入っています。<br>もっと深く鑑定したい時に使えます。<br>",
        "transit_detail_link": "トランジット詳細データを見る",
        "chart_note": "ホロスコープ図も用意されています。鑑定を始めるだけなら見なくて大丈夫ですが、図で確認したい方はこちらから見られます。<br>",
        "view_horoscope_chart": "ホロスコープ図を見る",
        "time_accuracy_label": "出生時刻の扱い",
        "birth_time_notice_unknown_short": "出生時刻不明のため、一部データは参考値です",
        "birth_time_notice_approximate_short": "出生時刻が推定のため、一部データは参考値です",
        "time_accuracy_intro": "出生時刻が不明、または推定時刻のため、ハウス・ASC・MCなどは参考値として扱ってください。",
        "time_accuracy_variable": "出生時刻によって変わりやすいもの:",
        "time_accuracy_stable": "比較的安定して使いやすいもの:",
        "time_accuracy_items_variable": ["ハウス", "ASC（アセンダント）", "MC", "Vertex", "月の度数やサイン（一部の場合）"],
        "time_accuracy_items_stable": ["太陽・水星・金星・火星などの天体サイン", "天体同士の主要アスペクト", "エレメント", "モード", "世代天体の配置"],
        "time_accuracy_ai_note": "AIに貼る場合も、出生時刻の精度情報を一緒に渡してください。断定的なハウス解釈は避け、参考情報として扱うのがおすすめです。",
        "ai_usage_title": "AIに貼ると、こう使えます",
        "ai_usage_items": ["あなたの本質や傾向が、AIの言葉で整理されます。", "今気になるテーマをそのまま質問できます。", "仕事・恋愛・今月の注意日などを、あとから深掘りできます。"],
        "ai_usage_transit_items": ["イベント時点の天体配置が、AIの言葉で整理されます。", "歴史イベント・満月・特定日時の象徴分析に使えます。", "日付や暦の前提を明示したまま、あとから深掘りできます。"],
        "ai_usage_hint": "このページは鑑定結果を表示する場所ではなく、AIに渡すファイルを作る入口です。",
        "followup_title": "鑑定のあとに聞けること",
        "followup_items": ["「仕事の流れを詳しく知りたい」", "「恋愛面をもう少し深掘りしたい」", "「今月の注意日を教えてほしい」"],
        "followup_hint": "鑑定文のあとに、そのままAIへ続けて質問できます。",
        "download_event_yaml": "イベントYAML",
        "download_natal": "ネイタル",
        "download_natal_asteroids": "ネイタル＋小惑星",
        "download_transit": "トランジット",
        "download_long_term_transits": "長期トランジット",
        "download_yaml_data": "YAMLデータ",
        "download_horoscope_svg": "ホロスコープSVG",
        "download_shichu_svg": "命式SVG",
        "next_transit_title": "次のトランジットを作成",
        "next_transit_desc": "前回の鑑定データを引き継いで、<br>次の38日トランジットを生成できます。",
        "chart_details_summary_both": "ホロスコープ図・命式図を見る",
        "chart_details_summary_horoscope": "ホロスコープ図を見る",
        "chart_details_summary_shichu": "命式図を見る",
        "chart_details_intro": "鑑定を始めるだけなら確認しなくて大丈夫です。図で見たい方だけご利用ください。",
        "horoscope_chart_title": "ホロスコープ図",
        "horoscope_chart_desc": "このホロスコープ図は、YAMLログと同じ計算済みデータから自動描画しています。AI生成画像ではありません。",
        "horoscope_chart_time_hint": "この図は仮計算時刻を元に描画しています。ハウス・ASC・MCは参考値です。",
        "horoscope_loading": "ホロスコープ図を読み込んでいます...",
        "show_asteroids": "補助天体を表示",
        "hide_houses": "ハウスなし表示",
        "save_svg": "SVGを保存",
        "horoscope_chart_footer": "AIに貼る基本データはYAMLログです。ホロスコープ図は必要な時だけ、別資料として保存・コピーできます。",
        "shichu_chart_title": "四柱推命 命式図",
        "shichu_chart_desc": "この命式図は、YAMLログ内の計算済み四柱推命データから自動描画しています。鑑定文ではなく、計算結果の可視化です。",
        "shichu_loading": "命式図を読み込んでいます...",
        "save_shichu_svg": "命式SVGを保存",
        "save_shichu_png": "命式PNGを保存",
        "shichu_chart_footer": "AIに貼る基本データはYAMLログです。命式図は商品ページや確認用の補助資料として使えます。",
        "usage_limits": "本商品は個人利用向けのデータ商品です。ChatGPT等のAIサービスへの入力、個人範囲での利用は可能です。再配布、転載、販売、サービス組み込み等の商用利用は禁止します。商用利用・アプリ組み込み用途はAPI版をご利用ください。",
        "save_data": "データを保存したい方へ",
        "save_data_hint": "URLやZIPは、あとで使いたい方だけ保存してください。",
        "save_zip": "ZIPを保存する",
        "individual_files": "個別ファイルを見る",
        "details": "詳細データ・AI活用",
        "details_intro": "この商品で利用可能なデータを選んで、AIへの送信やコピーに使えます。",
        "full_details_title_asteroids": "利用可能なデータ種別",
        "full_details_title_transit": "利用可能なデータ種別",
        "full_details_hint_asteroids": "小惑星を含む詳細データです。もっと深く鑑定したい場合に使えます。",
        "full_details_hint_transit": "この商品に含まれるトランジット詳細データです。もっと深く鑑定したい場合に使えます。",
        "asteroid_mode_label": "小惑星つき版",
        "recommended_badge": "おすすめ",
        "asteroid_mode_desc": "小惑星や、この商品に含まれるトランジット詳細データを含む、より詳しいデータです。",
        "standard_mode_desc": "この商品で利用できる基本データです。通常のAI鑑定や保存に使えます。",
        "full_mode_label": "完全版",
        "all_details_badge": "全詳細",
        "full_mode_desc_asteroids": "小惑星と、この商品に含まれるすべてのトランジット詳細データを含む完全版です。情報量が多いため、必要な場合だけご利用ください。",
        "full_mode_desc_transit": "この商品に含まれるすべてのトランジット詳細データを含む版です。\n期間は商品の設定に基づきます（例：対象月の全期間など）。",
        "send_selected_to_ai": "選んだ版をAIに送る",
        "copy_selected": "選んだ版をコピー",
        "data_preview_label": "YAMLとプロンプトを確認する",
        "data_preview_title": "YAMLの一部",
        "data_preview_desc": "必要な場合だけ、AIに渡されるYAMLや案内文の一部を確認できます。",
        "analysis_label": "分析",
        "reading_label": "鑑定",
        "yaml_preview_label": "YAMLログの一部",
        "data_preview_note": "AIが再計算せず、このデータを根拠として解釈します。保存したい場合はファイルとして残せます。",
        "prompt_preview_title": "プロンプトの一部",
        "prompt_preview_desc": "AIへの案内文の一部です。",
        "prompt_preview_label": "プロンプトの一部",
        "yaml_direct_link": "YAML直リンク",
        "yaml_url_hint": "AIにURLとして渡す場合に使います。",
        "prompt_direct_link": "プロンプト直リンク",
        "prompt_full_title": "プロンプト全文",
        "prompt_full_hint": "AIに「どう鑑定してほしいか」を伝える文章です。",
        "copy_prompt_full": "プロンプト全文コピー",
        "yaml_full_title": "YAML全文",
        "yaml_complete_title": "完全版YAML",
        "yaml_hint_transit": "イベント時点の天体配置データです。AIにはこの計算結果を変更せず、解釈だけさせてください。",
        "yaml_hint_full": "完全版YAMLは、小惑星やこの商品に含まれる詳細データまでじっくり読みたい時に使います。",
        "yaml_hint_standard": "通常版YAMLです。AIにはこの計算結果を変更せず、解釈だけさせてください。",
        "copy_yaml_full": "YAML全文コピー",
        "copy_yaml_complete": "完全版YAMLコピー",
        "copy_next_chunk": "続きからコピー",
        "download_yaml": "YAMLを保存",
        "download_yaml_complete": "完全版YAMLをダウンロード",
        "show_yaml": "YAMLを表示",
        "hide_yaml": "YAMLを閉じる ▲",
        "transit_date_note": "歴史イベントの日付には諸説があり得ます。必要に応じて日付・暦種別の前提を確認してください。",
        "notes": "注意事項",
        "notes_items": [
            "入力後のデータ変更はできません。ご不明点やお困りのことがある場合は、お問い合わせください。",
            "AIの種類や設定によって、文章表現や鑑定の深さは変わります。",
            "YAMLは計算済みデータです。AIには「計算をやり直さず、このYAMLを根拠に解釈する」よう指示してください。",
        ],
        "copied": "コピーしました",
        "mode_full": "完全版",
        "mode_asteroids": "小惑星つき版",
        "mode_paste": "通常版",
        "full_yaml_loading": "完全版YAMLを読み込んでいます...",
        "full_yaml_load_failed": "完全版YAMLを読み込めませんでした。コピーまたはダウンロードを再度お試しください。",
        "asteroid_yaml_loading": "小惑星つき版を読み込んでいます...",
        "asteroid_yaml_load_failed": "小惑星つき版を読み込めませんでした。通常版または完全版をご利用ください。",
        "yaml_data_intro": "以下がYAMLデータです。",
        "load_on_demand": "必要時に読み込みます",
        "char_unit": "文字",
        "transit_detail_mode": "トランジット詳細版",
        "full_yaml_load_on_demand": "完全版は、使う時に読み込みます。",
        "asteroid_yaml_load_on_demand": "小惑星つき版は、使う時に読み込みます。",
        "share_text_title": "AI用テキスト",
        "share_txt_title": "AI用TXTファイル",
        "share_unavailable": "この環境では直接送れないため、下のコピーまたはTXT保存をご利用ください。",
        "share_large_unavailable": "データ量が大きいため、この環境では直接共有できない場合があります。コピー、TXT保存、またはZIP保存をご利用ください。",
        "zip_save_failed": "ZIPの保存に失敗しました。共有かコピーを試してください。",
        "zip_preparing": "ZIPを準備しています...",
        "zip_started": "ZIPの保存を開始しました。",
        "selected_copied_more": "{label}をコピーしました。必要なら「続きからコピー」で次の分を送れます。",
        "selected_copied": "{label}をコピーしました。",
        "chunk_copied": "{label} {index}/{total} をコピーしました",
        "svg_loading": "図を読み込んでいます...",
        "svg_load_failed": "図を読み込めませんでした。時間をおいて再度お試しください。",
        "png_failed_svg_copied": "PNG保存に失敗したため、SVGをコピーしました",
        "addon_title": "追加部品YAML生成",
        "addon_lead": "STORESで購入した追加部品を、AIに渡せるYAMLとして生成するフォームです。",
        "addon_usage_title": "使い方",
        "addon_usage_items": [
            "STORESの購入確認メールに記載された注文番号を入力してください。",
            "小惑星追加は、基本版の出生データを土台に生成します。",
            "トランジット追加では、基本版YAML または 90日以内の前回鑑定URLを入力してください。",
            "生成されたaddon YAMLは、基本版YAMLと一緒にAIへ渡して使います。",
            "YAML単体でも、AI鑑定用の全文コピペに追加しても使えます。",
            "貼り付けたYAMLは保存しません。",
        ],
        "addon_generate_section_title": "生成する追加部品",
        "addon_type_label": "addon種別",
        "order_code_label": "STORESオーダー番号",
        "order_code_placeholder": "例：9824333454",
        "order_code_hint": "購入確認メールの件名にある注文番号です。追加部品ごとに1回だけ使用できます。",
        "base_data_title": "基本データ入力",
        "base_data_hint_transit": "38日トランジット追加は、基本版の出生データを土台に生成します。",
        "base_data_hint_standard": "基本版YAMLの内容から出生情報を読み取り、追加部品YAMLだけを生成します。",
        "previous_chart_url_label": "90日以内の前回鑑定URL",
        "previous_chart_url_placeholder": "https://.../chart/...",
        "previous_chart_url_hint": "前回の鑑定結果ページURLから、ネイタル情報を引き継げます。",
        "base_yaml_label": "YAML貼り付け欄",
        "base_yaml_placeholder": "ここに基本版YAMLを貼り付けてください",
        "base_yaml_hint": "基本版YAMLの内容から出生情報を読み取り、addon生成に使用します。",
        "transit_period_title": "トランジット期間",
        "transit_period_hint": "38日トランジットは38日間、長期トランジットは1年間です。開始日は現在日から前後5年以内で指定できます。",
        "transit_start_date_label": "開始日",
        "transit_start_date_hint": "指定可能範囲: {min_date} 〜 {max_date}",
        "generate_button": "追加部品YAMLを生成する",
        "generated_transit_title": "38日トランジットデータを生成しました",
        "generated_transit_lead": "以下のURLから閲覧できます。",
        "transit_url_label": "閲覧URL",
        "transit_expires_hint": "有効期限: {label}",
        "transit_url_hint": "AIに詳しく読ませたい場合は、ダウンロードしたYAMLファイルを添付してください。",
        "copy_url_button": "URLをコピー",
        "open_page_button": "ページを開く",
        "download_yaml_button": "YAMLをダウンロード",
        "result_yaml_title": "生成結果YAML",
        "result_yaml_hint": "このaddon YAMLを基本版YAMLと一緒にAIへ貼り付けてください。",
        "copy_button": "コピー",
        "download_button": "ダウンロード",
        "copy_no_yaml": "コピーするYAMLがありません。",
        "copy_no_url": "コピーするURLがありません。",
        "copy_no_download": "ダウンロードするYAMLがありません。",
        "copy_done": "コピーしました。",
        "url_copied_done": "URLをコピーしました。",
        "download_started": "ダウンロードを開始しました。",
    },
    "en": {
        "lang_label": "Language",
        "lang_ja": "日本語",
        "lang_en": "English",
        "product_labels": {
            "western_basic": "Basic horoscope",
            "western_full": "Full horoscope",
            "western_asteroids_addon": "Horoscope asteroid add-on",
            "shichu": "Four Pillars data",
            "transit_yaml": "Transit YAML",
        },
        "product_leads": {
            "western_basic": "Enter your order number and birth information.",
            "western_full": "Create birth chart data including asteroids and one-month transits.<br>Enter your order number and birth information.",
            "shichu": "Enter the information needed to create Four Pillars data.<br>You can choose the day-change boundary: standard 1:00 AM or 11:00 PM.",
            "transit_yaml": "Create YAML for the planetary positions at a specific event, date, and place.<br>Birth information is not used.",
        },
        "start_title_suffix": "Create AI-readable astrology data",
        "start_notice_title": "Please check before you start",
        "start_notice_items": [
            "<strong>The order number can be used only once.</strong>After generation, it cannot be used again.",
            "<strong>You cannot change the input after submission.</strong>Please check the birth date, birth time, and place of birth carefully.",
            "If the birth time is unknown, leave it blank. Noon will be used for calculation.",
            "Please save the URL shown after generation.",
        ],
        "product_summary_title": "Selected product",
        "input_contents_title": "What to enter",
        "start_transit_input_items": [
            "Order number",
            "Email address (optional)",
            "Event name",
            "Date, time, and time zone",
            "Place name, latitude, and longitude",
            "Julian / Gregorian calendar type",
        ],
        "start_flow_title": "How it works",
        "start_transit_flow_items": [
            "Enter your STORES order number.",
            "Enter the event date, time, and place.",
            "Choose the calendar type.",
            "Check the confirmation box and submit.",
            "The AI analysis YAML data will be displayed.",
        ],
        "product_type_label": "Product type",
        "start_button": "Go to input form",
        "start_input_hint": "Enter your order number and birth information.",
        "input_title_suffix": "AI-readable astrology data input",
        "shichu_input_title_suffix": "Data input",
        "precheck": "Before you submit",
        "precheck_strong": "You cannot generate the data again with the same order number after submission.",
        "precheck_note": "Please check the birth date, birth time, and place of birth before submitting.",
        "order_info": "Order information",
        "order_provider": "Purchase provider",
        "provider_stores": "STORES",
        "provider_gumroad": "Gumroad",
        "provider_payhip": "Payhip",
        "stores_order": "Order number",
        "payhip_email": "Email address used for purchase",
        "payhip_product": "Purchased product",
        "payhip_order_id": "Order ID / Invoice Number",
        "payhip_order_id_optional": "Order ID / Invoice Number (optional)",
        "payhip_order_hint": "Enter the Order ID shown in your Payhip purchase email.",
        "required": "Required",
        "optional": "Optional",
        "not_entered": "Not entered",
        "order_help": "Enter your order number.",
        "order_mail_hint": "Enter the order number shown in the purchase completion email from STORES. Example: #12345678.",
        "name": "Name",
        "birth_info": "Birth information",
        "birth_date": "Date of birth",
        "birth_date_manual_hint": "Type digits only and it will be shown as YYYY-MM-DD. Example: 1990-01-01.",
        "birth_date_required_error": "Enter your date of birth.",
        "birth_date_format_error": "Enter 8 digits so the date can be shown as YYYY-MM-DD. Example: 1990-01-01.",
        "birth_date_invalid_error": "That date does not exist. Enter a date that can be interpreted as YYYY-MM-DD.",
        "birth_date_future_error": "Future dates are not allowed.",
        "birth_time_accuracy": "Birth time accuracy",
        "time_exact": "Exact time known",
        "time_unknown": "Unknown",
        "time_morning": "Morning",
        "time_afternoon": "Afternoon",
        "time_night": "Night",
        "time_accuracy_help": "If the time is estimated, houses, ASC, and MC should be treated as reference values.",
        "birth_time": "Birth time",
        "birth_time_help": "Enter this only if you know the exact birth time.",
        "prefecture": "Prefecture of birth",
        "select_placeholder": "Select",
        "place_details": "Details of the place of birth",
        "place_kind": "Place of birth type",
        "domestic": "Domestic",
        "international": "International",
        "coordinates": "Use latitude / longitude",
        "domestic_place_note": "Prefecture is required and city/ward is optional. If matching coordinates exist, the city/ward coordinates are used. Entered latitude and longitude are always used first.",
        "domestic_coordinates_summary": "Optional detailed coordinates",
        "domestic_coordinates_note": "If latitude and longitude are entered, they are used before city/ward or prefecture reference coordinates.",
        "overseas_place_note": "For international birth places, country/city, latitude, longitude, and time zone are required.",
        "coordinates_place_note": "Use this when you want to specify the birth place by latitude and longitude.",
        "coordinates_range_note": "Latitude should be -90 to 90, and longitude should be -180 to 180.",
        "birth_place_country_city": "Country / city",
        "birth_place_city": "City / ward",
        "latitude": "Latitude",
        "longitude": "Longitude",
        "coordinate_note": "If left blank, the prefecture's reference coordinates are used. Enter them only when you want a more specific location.",
        "international_coordinate_help": "You can search coordinates using Google Maps.",
        "timezone": "Time zone",
        "timezone_other": "Other / Manual timezone",
        "timezone_custom_placeholder": "Example: America/New_York",
        "timezone_help": "Choose the region closest to the place of birth. Use Other only if it is not listed.",
        "gender": "Gender",
        "gender_unknown": "Unspecified",
        "gender_female": "Female",
        "gender_male": "Male",
        "gender_help": "Used for Four Pillars fortune-cycle calculation. If unknown, leave it as Unspecified.",
        "shichu_settings": "Four Pillars settings",
        "day_change": "Day-change boundary",
        "standard_1am": "1:00 AM - standard",
        "day_change_help": "Choose 11:00 PM only if you use that tradition.",
        "final_check": "Final check",
        "final_check_hint": "After submission, this order number cannot be used again. The buyer cannot change the data even if the input contains a mistake.",
        "final_agree": "I have checked the input and agree that it cannot be changed after submission.",
        "submit_generate": "Generate AI-readable astrology data",
        "submit_confirm": "Generate AI-readable astrology data with this input? You cannot change or regenerate it after submission.",
        "confirm_title": "Final review",
        "confirm_lead": "Check your input before creating the data.",
        "confirm_modify": "Edit",
        "confirm_create": "Create with this data",
        "confirm_order": "Order number",
        "confirm_name": "Name",
        "confirm_birth_date": "Date of birth",
        "confirm_birth_time": "Birth time",
        "confirm_birth_place_mode": "Birth place mode",
        "confirm_birth_place": "Birth place",
        "confirm_coordinates": "Latitude / longitude",
        "submit_loading_button": "Generating...",
        "submit_loading_title": "Generating your AI-readable astrology data",
        "submit_loading_desc": "This can take a little longer on unstable networks or first startup. Please keep this screen open.",
        "chart_eyebrow": "AI-readable astrology data",
        "analysis_eyebrow": "AI analysis data",
        "chart_title": "'s AI-readable astrology data",
        "chart_title_default": "Your AI-readable astrology data",
        "transit_title_default": "Event",
        "transit_title_suffix": " transit YAML",
        "chart_lead": "This is the AI-ready core data. Tap \"Send to AI\" to use it as-is.",
        "transit_lead": "Paste this data into an AI tool to analyze the planetary positions at the event time.<br>This YAML contains transit-only data and does not use birth information.",
        "birthday": "Date of birth",
        "date": "Date",
        "time": "Time",
        "calc_time": "Calculation time",
        "birth_time_badge": "Birth time",
        "place": "Place",
        "birth_place": "Place of birth",
        "unknown": "Unknown",
        "page_expiry": "Anyone with this URL can open the page. It expires on {expires_label} (90 days after issue).",
        "page_no_expiry": "Anyone with this URL can open the page. It does not expire.",
        "steps_title": "Start in 3 steps",
        "step1_title": "Send the data to AI",
        "step1_desc": "Use the button below to send the AI-readable astrology data to an AI tool.",
        "step2_title": "Submit as-is",
        "step2_desc": "You can use it with ChatGPT, Claude, Gemini, and similar tools.",
        "step3_title": "Receive the reading",
        "step3_desc": "After receiving the response, you can ask follow-up questions in the same chat.",
        "guide_link": "First-time here? How to use it",
        "guide_desc": "First-time users can check the steps with screenshots.",
        "page_url": "URL of this page",
        "event_url": "URL of this event data",
        "copy_label": "Copy",
        "page_url_hint": "Copy this if you want to reopen the page later or use it on another device.",
        "send_to_ai": "Send to AI",
        "send_ai_button": "Send to AI",
        "fallback_summary": "If sending does not work",
        "fallback_desc": "If direct sharing does not work, copy the text or save it as a TXT file.",
        "copy_to_use": "Copy and use",
        "save_txt_to_use": "Save TXT and use",
        "yaml_only_title": "YAML for AI use",
        "copy_yaml_only": "Copy selected version YAML",
        "copy_yaml_only_hint": "YAML data without the astrology reading prompt. Use it for storage or with other AI services.",
        "yaml_only_title_long_term": "AI data",
        "copy_yaml_only_long_term": "Copy AI data",
        "copy_yaml_only_hint_long_term": "For long-term transits, this copies a lightweight version for ChatGPT. Use TXT save or ZIP save for the full version.",
        "yaml_only_copied": "YAML data only copied.",
        "yaml_only_copied_long_term": "AI data copied.",
        "yaml_only_copy_failed": "Could not copy the YAML data. Please try again later.",
        "helper_note": "Compatible with ChatGPT / Claude / Gemini and other AI services.",
        "full_asteroid_note": "The FULL version also includes detailed data such as asteroids.<br>Use it if you want a deeper reading.<br>",
        "full_asteroid_link": "View FULL asteroid data",
        "transit_detail_note": "This page also includes the detailed transit data included with this product.<br>Use it if you want a deeper reading.<br>",
        "transit_detail_link": "View detailed transit data",
        "chart_note": "A horoscope chart is also available. You do not need to view it to start the reading, but you can check it here if you want to see the chart.<br>",
        "view_horoscope_chart": "View horoscope chart",
        "time_accuracy_label": "Birth time handling",
        "birth_time_notice_unknown_short": "Because the birth time is unknown, some data should be treated as reference values.",
        "birth_time_notice_approximate_short": "Because the birth time is approximate, some data should be treated as reference values.",
        "time_accuracy_intro": "Because the birth time is unknown or estimated, houses, ASC, and MC should be treated as reference values.",
        "time_accuracy_variable": "Items that can change depending on birth time:",
        "time_accuracy_stable": "Items that are relatively stable and easier to use:",
        "time_accuracy_items_variable": ["Houses", "ASC (Ascendant)", "MC", "Vertex", "Moon degree or sign in some cases"],
        "time_accuracy_items_stable": ["Planetary signs such as Sun, Mercury, Venus, and Mars", "Major aspects between planets", "Elements", "Modes", "Generational planet placements"],
        "time_accuracy_ai_note": "When sending this to AI, include the birth time accuracy information. Avoid definitive house interpretations and treat them as reference information.",
        "ai_usage_title": "What you can do after sending it to AI",
        "ai_usage_items": ["Your traits and tendencies can be organized in AI-generated language.", "You can ask follow-up questions about what you care about now.", "You can explore topics such as work, relationships, and key dates in more detail."],
        "ai_usage_transit_items": ["The planetary positions at the event time can be organized in AI-generated language.", "You can use it for symbolic analysis of historical events, full moons, and specific dates or times.", "You can explore the topic further while keeping the date and calendar assumptions explicit."],
        "ai_usage_hint": "This page is not the reading itself. It is the entry point for creating data to send to AI.",
        "followup_title": "Follow-up questions after the reading",
        "followup_items": ["“I want to know more about my work flow.”", "“I want to explore relationships more deeply.”", "“Please tell me the key dates to pay attention to this month.”"],
        "followup_hint": "After the reading, you can continue asking questions in the same AI chat.",
        "download_event_yaml": "Event YAML",
        "download_natal": "Natal",
        "download_natal_asteroids": "Natal + asteroids",
        "download_transit": "Transit",
        "download_long_term_transits": "Long-term transits",
        "download_yaml_data": "YAML data",
        "download_horoscope_svg": "Horoscope SVG",
        "download_shichu_svg": "Four Pillars SVG",
        "next_transit_title": "Create the next transit",
        "next_transit_desc": "You can carry over the previous AI-readable astrology data<br>and generate the next 38-day transit.",
        "chart_details_summary_both": "View horoscope and Four Pillars charts",
        "chart_details_summary_horoscope": "View horoscope chart",
        "chart_details_summary_shichu": "View Four Pillars chart",
        "chart_details_intro": "You do not need to check this to start the reading. Use it only if you want to view the chart.",
        "horoscope_chart_title": "Horoscope chart",
        "horoscope_chart_desc": "This horoscope chart is automatically drawn from the same calculated data as the YAML log. It is not an AI-generated image.",
        "horoscope_chart_time_hint": "This chart is drawn using the estimated calculation time. Houses, ASC, and MC are reference values.",
        "horoscope_loading": "Loading horoscope chart...",
        "show_asteroids": "Show auxiliary bodies",
        "hide_houses": "Hide houses",
        "save_svg": "Save SVG",
        "horoscope_chart_footer": "The basic data to send to AI is the YAML log. Save or copy the horoscope chart only when you need it as a supplemental reference.",
        "shichu_chart_title": "Four Pillars chart",
        "shichu_chart_desc": "This chart is automatically drawn from the calculated Four Pillars data in the YAML log. It is a visualization of calculation results, not the reading text.",
        "shichu_loading": "Loading Four Pillars chart...",
        "save_shichu_svg": "Save Four Pillars SVG",
        "save_shichu_png": "Save Four Pillars PNG",
        "shichu_chart_footer": "The basic data to send to AI is the YAML log. Use the Four Pillars chart as supplemental material for product pages or review.",
        "usage_limits": "This product is for personal use. You may input it into AI services such as ChatGPT and use it within a personal scope. Redistribution, reposting, resale, service integration, and other commercial use are prohibited. Use the API version for commercial or app integration use.",
        "save_data": "For saving the data",
        "save_data_hint": "Save the URL or ZIP only if you want to use it later.",
        "save_zip": "Save ZIP",
        "individual_files": "View individual files",
        "details": "Detailed data and AI use",
        "details_intro": "Select data available with this product to send it to AI or copy it.",
        "full_details_title_asteroids": "Available data types",
        "full_details_title_transit": "Available data types",
        "full_details_hint_asteroids": "Detailed data with asteroids. Use it if you want a deeper reading.",
        "full_details_hint_transit": "Detailed transit data included with this product. Use it if you want a deeper reading.",
        "asteroid_mode_label": "Asteroid version",
        "recommended_badge": "Recommended",
        "asteroid_mode_desc": "Detailed data including asteroids and the transit details included with this product.",
        "standard_mode_desc": "The basic data available with this product. Use it for regular AI readings or storage.",
        "full_mode_label": "Complete version",
        "all_details_badge": "All details",
        "full_mode_desc_asteroids": "The complete version includes asteroids and all transit details included with this product. Use it only when you need the extra volume.",
        "full_mode_desc_transit": "This version includes all detailed transit data included with this product.\nThe period is based on the product settings, such as the full target month.",
        "send_selected_to_ai": "Send selected version to AI",
        "copy_selected": "Copy selected version",
        "data_preview_label": "Check YAML and prompt",
        "data_preview_title": "YAML excerpt",
        "data_preview_desc": "Inspect part of the YAML and prompt sent to AI only if needed.",
        "analysis_label": "analysis",
        "reading_label": "the reading",
        "yaml_preview_label": "YAML log excerpt",
        "data_preview_note": "AI interprets this data as the source without recalculating it. You can save it as a file if needed.",
        "prompt_preview_title": "Prompt excerpt",
        "prompt_preview_desc": "A partial view of the prompt that guides the AI.",
        "prompt_preview_label": "Prompt excerpt",
        "yaml_direct_link": "Direct YAML link",
        "yaml_url_hint": "Use this when sending the YAML as a URL to AI.",
        "prompt_direct_link": "Direct prompt link",
        "prompt_full_title": "Full prompt",
        "prompt_full_hint": "This text tells the AI how you want the reading to be written.",
        "copy_prompt_full": "Copy full prompt",
        "yaml_full_title": "Full YAML",
        "yaml_complete_title": "Complete YAML",
        "yaml_hint_transit": "This is planetary position data at the event time. Ask the AI to interpret the results without changing the calculation.",
        "yaml_hint_full": "Use the complete YAML when you want to read asteroids and the detailed data included with this product in depth.",
        "yaml_hint_standard": "This is the standard YAML. Ask the AI to interpret the results without recalculating them.",
        "copy_yaml_full": "Copy full YAML",
        "copy_yaml_complete": "Copy complete YAML",
        "copy_next_chunk": "Copy next chunk",
        "download_yaml": "Save YAML",
        "download_yaml_complete": "Download complete YAML",
        "show_yaml": "Show YAML",
        "hide_yaml": "Hide YAML ▲",
        "transit_date_note": "Historical event dates may have multiple interpretations. Check the date and calendar assumptions as needed.",
        "notes": "Notes",
        "notes_items": [
            "The data cannot be changed after submission. Please contact support if you have questions or trouble.",
            "The wording and depth of the reading may vary depending on the AI service and settings.",
            "YAML is calculated data. Tell the AI to interpret this YAML as the source instead of recalculating it.",
        ],
        "copied": "Copied",
        "mode_full": "Complete version",
        "mode_asteroids": "Asteroid version",
        "mode_paste": "Standard version",
        "full_yaml_loading": "Loading complete YAML...",
        "full_yaml_load_failed": "Could not load the complete YAML. Please try copying or downloading it again.",
        "asteroid_yaml_loading": "Loading asteroid version...",
        "asteroid_yaml_load_failed": "Could not load the asteroid version. Please use the standard or complete version.",
        "yaml_data_intro": "Here is the YAML data.",
        "load_on_demand": "Loaded when needed",
        "char_unit": "characters",
        "transit_detail_mode": "Detailed transit version",
        "full_yaml_load_on_demand": "The complete version will load when you use it.",
        "asteroid_yaml_load_on_demand": "The asteroid version will load when you use it.",
        "share_text_title": "AI text",
        "share_txt_title": "AI TXT file",
        "share_unavailable": "Direct sharing is not available in this environment. Please use copy or TXT save below.",
        "share_large_unavailable": "Because the data is large, direct sharing may not work in this environment. Please use copy, TXT save, or ZIP save instead.",
        "zip_save_failed": "Could not save the ZIP. Please try sharing or copying instead.",
        "zip_preparing": "Preparing ZIP...",
        "zip_started": "ZIP save has started.",
        "selected_copied_more": "{label} copied. Use Copy next chunk if you need to send the next part.",
        "selected_copied": "{label} copied.",
        "chunk_copied": "{label} {index}/{total} copied",
        "svg_loading": "Loading chart...",
        "svg_load_failed": "Could not load the chart. Please try again later.",
        "png_failed_svg_copied": "PNG save failed, so the SVG was copied instead.",
        "addon_title": "Add-on YAML generation",
        "addon_lead": "This form generates YAML for purchased add-ons that can be passed to AI.",
        "addon_usage_title": "How to use",
        "addon_usage_items": [
            "Enter the order number shown in the STORES purchase confirmation email.",
            "The asteroid add-on is generated on top of the basic birth data.",
            "For transit add-ons, enter either the basic YAML or a previous chart URL from the last 90 days.",
            "The generated add-on YAML is used together with the basic YAML when sending it to AI.",
            "You can use the YAML on its own or append it to a full AI-reading prompt.",
            "The pasted YAML is not saved.",
        ],
        "addon_generate_section_title": "Add-on to generate",
        "addon_type_label": "Add-on type",
        "order_code_label": "STORES order number",
        "order_code_placeholder": "Example: 9824333454",
        "order_code_hint": "This is the order number shown in the purchase confirmation email. Each add-on can be used only once.",
        "base_data_title": "Base data input",
        "base_data_hint_transit": "Transit add-ons are generated on top of the basic birth data.",
        "base_data_hint_standard": "The basic YAML is parsed to read the birth data and generate only the add-on YAML.",
        "previous_chart_url_label": "Previous chart URL within 90 days",
        "previous_chart_url_placeholder": "https://.../chart/...",
        "previous_chart_url_hint": "You can carry over natal information from the previous chart page URL.",
        "base_yaml_label": "Paste YAML here",
        "base_yaml_placeholder": "Paste the basic YAML here",
        "base_yaml_hint": "The basic YAML is used to read the birth data for add-on generation.",
        "transit_period_title": "Transit period",
        "transit_period_hint": "The 38-day transit covers 38 days, and the long-term transit covers one year. The start date can be set within five years before or after today.",
        "transit_start_date_label": "Start date",
        "transit_start_date_hint": "Available range: {min_date} to {max_date}",
        "generate_button": "Generate add-on YAML",
        "generated_transit_title": "38-day transit data generated",
        "generated_transit_lead": "You can access this page from the URL below.",
        "transit_url_label": "View URL",
        "transit_expires_hint": "Expires: {label}",
        "transit_url_hint": "If you want AI to read it in more detail, attach the downloaded YAML file.",
        "copy_url_button": "Copy URL",
        "open_page_button": "Open page",
        "download_yaml_button": "Download YAML",
        "result_yaml_title": "Generated YAML",
        "result_yaml_hint": "Paste this add-on YAML together with the basic YAML when sending it to AI.",
        "copy_button": "Copy",
        "download_button": "Download",
        "copy_no_yaml": "There is no YAML to copy.",
        "copy_no_url": "There is no URL to copy.",
        "copy_no_download": "There is no YAML to download.",
        "copy_done": "Copied.",
        "url_copied_done": "URL copied.",
        "download_started": "Download started.",
    },
}
OVERSEAS_TIMEZONE_OPTIONS = [
    {"value": "Asia/Tokyo", "label_ja": "日本（Tokyo）", "label_en": "Japan (Tokyo)"},
    {"value": "Europe/London", "label_ja": "イギリス（London）", "label_en": "United Kingdom (London)"},
    {"value": "Europe/Paris", "label_ja": "フランス・中央ヨーロッパ（Paris など）", "label_en": "France / Central Europe (Paris etc.)"},
    {"value": "Europe/Berlin", "label_ja": "ドイツ（Berlin）", "label_en": "Germany / Central Europe (Berlin etc.)"},
    {"value": "Europe/Rome", "label_ja": "イタリア（Rome）", "label_en": "Italy / Central Europe (Rome etc.)"},
    {"value": "America/New_York", "label_ja": "アメリカ東部（New York など）", "label_en": "United States Eastern (New York etc.)"},
    {"value": "America/Chicago", "label_ja": "アメリカ中部（Chicago など）", "label_en": "United States Central (Chicago etc.)"},
    {"value": "America/Denver", "label_ja": "アメリカ山岳部（Denver など）", "label_en": "United States Mountain (Denver etc.)"},
    {"value": "America/Los_Angeles", "label_ja": "アメリカ西部（Los Angeles など）", "label_en": "United States Pacific (Los Angeles etc.)"},
    {"value": "America/Honolulu", "label_ja": "ハワイ（Honolulu）", "label_en": "Hawaii (Honolulu)"},
    {"value": "Asia/Seoul", "label_ja": "韓国（Seoul）", "label_en": "South Korea (Seoul)"},
    {"value": "Asia/Shanghai", "label_ja": "中国（Shanghai）", "label_en": "China (Shanghai)"},
    {"value": "Asia/Taipei", "label_ja": "台湾（Taipei）", "label_en": "Taiwan (Taipei)"},
    {"value": "Asia/Hong_Kong", "label_ja": "香港（Hong Kong）", "label_en": "Hong Kong"},
    {"value": "Asia/Bangkok", "label_ja": "タイ（Bangkok）", "label_en": "Thailand (Bangkok)"},
    {"value": "Asia/Singapore", "label_ja": "シンガポール（Singapore）", "label_en": "Singapore"},
    {"value": "Australia/Sydney", "label_ja": "オーストラリア東部（Sydney）", "label_en": "Australia Eastern (Sydney)"},
]


def _timezone_options(lang: str) -> list[dict[str, str]]:
    label_key = "label_en" if lang == "en" else "label_ja"
    return [
        {"value": option["value"], "label": option[label_key]}
        for option in OVERSEAS_TIMEZONE_OPTIONS
    ]


def _localized_birth_time_notice(notice: dict[str, Any], lang: str) -> dict[str, Any]:
    localized = dict(notice or {"show": False})
    if not localized.get("show"):
        return localized
    accuracy = str(localized.get("accuracy") or "").lower()
    t = I18N.get(lang, I18N["ja"])
    if accuracy == "unknown":
        localized["short"] = t.get("birth_time_notice_unknown_short", localized.get("short", ""))
    elif accuracy == "approximate":
        localized["short"] = t.get("birth_time_notice_approximate_short", localized.get("short", ""))
    return localized


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


def _resolve_lang(request: Request) -> str:
    lang = request.query_params.get("lang", "").strip().lower()
    return lang if lang in SUPPORTED_LANGS else "ja"


def _lang_urls(request: Request) -> dict[str, str]:
    return {
        "ja": str(request.url.include_query_params(lang="ja")),
        "en": str(request.url.include_query_params(lang="en")),
    }


def _localized_product(product_type: str, lang: str) -> dict:
    config = PRODUCT_CONFIG.get(product_type, PRODUCT_CONFIG["western_basic"])
    localized = dict(config)
    product_i18n = I18N.get(lang, I18N["ja"])
    localized["label"] = product_i18n["product_labels"].get(product_type, config["label"])
    if lang == "en":
        english_descriptions = {
            "western_basic": "Creates core birth chart data for Western astrology. No asteroids, Four Pillars, or day-boundary options are shown.",
            "western_full": "Includes asteroids and a 38-day transit set. No selection is required from the buyer.",
            "western_asteroids_addon": "Creates the asteroid add-on YAML to use with the basic version.",
            "shichu": "Creates Four Pillars data. The day-change boundary can be set to the standard 1:00 AM or 11:00 PM.",
            "transit_yaml": "Creates YAML for the planetary positions at a specific event, date, and place. Birth information is not used.",
        }
        english_features = {
            "western_basic": [
                "Western astrology birth chart data",
                "No asteroid options",
                "No Four Pillars data",
                "No transit data",
            ],
            "western_full": [
                "Western astrology birth chart data",
                "Includes asteroids",
                "Includes 38-day transits",
                "No Four Pillars data",
            ],
            "western_asteroids_addon": [
                "Ceres / Pallas / Juno / Vesta / Chiron / Lilith / Vertex",
                "Add-on data to use with the basic horoscope",
                "No transit data",
                "No Four Pillars data",
            ],
            "shichu": [
                "Four Pillars data",
                "Selectable day-change boundary",
                "Standard 1:00 AM option",
                "No asteroid or transit data",
            ],
            "transit_yaml": [
                "Planetary positions for an event, date, and place",
                "No birth information required",
                "Julian / Gregorian calendar selection",
                "Moon phases and major aspects included",
            ],
        }
        localized["description"] = english_descriptions.get(product_type, config["description"])
        localized["features"] = english_features.get(product_type, list(config.get("features") or []))
    return localized


def _i18n_context(request: Request) -> dict:
    lang = _resolve_lang(request)
    return {
        "lang": lang,
        "t": I18N.get(lang, I18N["ja"]),
        "lang_urls": _lang_urls(request),
    }


def _product_context(product_type: str, lang: str = "ja") -> dict:
    return {
        "product_type": product_type,
        "product": _localized_product(product_type, lang),
        "start_url": _start_url(product_type),
        "redeem_url": _redeem_url(product_type),
    }


def _chart_expires_at() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=CHART_EXPIRES_DAYS)


def _chart_has_no_expiry(chart: dict) -> bool:
    options = chart.get("options") or {}
    return isinstance(options, dict) and options.get("expires_policy") == NO_EXPIRY_CHART_POLICY


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
            horoscope_svg = optimize_svg(build_horoscope_svg_from_yaml(yaml_text, doc=doc))
        except Exception:
            horoscope_svg = None
    if product_type == "shichu":
        try:
            shichusuimei_svg = optimize_svg(build_shichusuimei_svg_from_yaml(yaml_text, doc=doc))
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


ORDER_CODE_RE = re.compile(r"[A-Za-z0-9=_-]+")
ORDER_PROVIDERS = {"stores", "gumroad", "payhip"}
# Gumroad relaxed（サーバー照合なし）を許す商品。Gumroadで販売しているのは西洋2種のみで、
# provider欄の無いフォーム（四柱推命・トランジット等）が非数字コードで無検証発行になるのを防ぐ。
GUMROAD_RELAXED_PRODUCT_TYPES = {"western_basic", "western_full"}
ORDER_CHECK_POLICIES = {
    "stores": {"strict": True},
    # Temporary Gumroad relaxed mode. Set GUMROAD_ORDER_STRICT=1 to re-enable
    # server-side email/order/product tag verification after the mail format is stable.
    "gumroad": {"strict": False},
    "payhip": {"strict": True},
}
PAYHIP_PRODUCTS = {
    "NP-WB": {
        "label": "NP-WB / AI-Readable Natal Data Core Pack",
        "product_type": "western_basic",
    },
    "NP-WF": {
        "label": "NP-WF / AI-Readable Astrology Data Full Version",
        "product_type": "western_full",
    },
    "NP-AA": {
        "label": "NP-AA / AI-Readable Asteroid Data Add-on",
        "product_type": "western_asteroids_addon",
    },
    "NP-TA": {
        "label": "NP-TA / AI-Readable Transit Data Add-on",
        "product_type": "western_31days_transit_addon",
    },
}


def _normalize_stores_order_no(value: str) -> str:
    return (value or "").strip()


def _is_valid_order_code(value: str) -> bool:
    return bool(ORDER_CODE_RE.fullmatch(value))


def _resolve_order_provider(order_code: str, provider: str | None = None) -> str | None:
    explicit = (provider or "").strip().lower()
    if explicit in ORDER_PROVIDERS:
        return explicit
    if re.fullmatch(r"\d{10}", order_code or ""):
        return "stores"
    if _is_valid_order_code(order_code or "") and not re.fullmatch(r"\d{10}", order_code or ""):
        return "gumroad"
    return None


def _get_order_check_policy(provider: str | None) -> dict[str, bool]:
    if provider == "gumroad":
        return {"strict": _truthy(os.getenv("GUMROAD_ORDER_STRICT", "0"))}
    return ORDER_CHECK_POLICIES.get(provider or "", {"strict": True})


def _payhip_product_options() -> list[dict[str, str]]:
    return [
        {"code": code, "label": product["label"], "product_type": product["product_type"]}
        for code, product in PAYHIP_PRODUCTS.items()
    ]


def _normalize_payhip_email(value: str) -> str:
    return (value or "").strip().lower()


def _payhip_metadata_from_form(
    *,
    payhip_email: str,
    payhip_product_code: str,
    payhip_order_id: str,
    expected_product_type: str,
) -> tuple[dict[str, str], str | None]:
    email_clean = _normalize_payhip_email(payhip_email)
    product_code_clean = (payhip_product_code or "").strip().upper()
    optional_order_id = (payhip_order_id or "").strip()
    if email_clean and "@" not in email_clean:
        return {}, "Payhipの購入時メールアドレスを正しい形式で入力してください。"
    if not optional_order_id:
        return {}, "Payhipを選択した場合は、Order IDを入力してください。"
    if not _is_valid_order_code(optional_order_id):
        return {}, "Order IDには英数字、ハイフン、アンダースコア、イコールのみ使用できます。"
    product = PAYHIP_PRODUCTS.get(product_code_clean)
    selected_product_type = str(product["product_type"]) if product else expected_product_type
    metadata = {
        "provider": "payhip",
        "purchaser_email": email_clean,
        "selected_product_code": product_code_clean,
        "selected_product_type": selected_product_type,
        "optional_order_id": optional_order_id,
    }
    return metadata, None


def _resolve_payhip_order_from_metadata(metadata: dict[str, str]) -> tuple[str, dict | None, str | None, int]:
    email_clean = metadata.get("purchaser_email") or ""
    product_code = metadata.get("selected_product_code") or ""
    order_id = _normalize_stores_order_no(metadata.get("optional_order_id") or "")
    if not os.environ.get("DATABASE_URL"):
        return "", None, "Payhip購入履歴の照合に必要なDATABASE_URLが未設定です。", 503
    try:
        status, order_row = stores_mail_sync.verify_order_no(order_id)
        if status == "not_found" and _truthy(os.getenv("STORES_MAIL_SYNC_ON_SUBMIT", "1")):
            _sync_stores_orders_for_lookup()
            status, order_row = stores_mail_sync.verify_order_no(order_id)
    except Exception as exc:
        logger.exception(
            "payhip_order_check_failed order_id=%s email_present=%s product_code=%s error_type=%s error=%r",
            order_id,
            bool(email_clean),
            product_code,
            type(exc).__name__,
            exc,
        )
        return "", None, _public_error_message(exc, fallback="Payhip購入履歴の照合に失敗しました。時間をおいて再試行してください。"), 503
    if status == "not_found":
        return "", order_row, "Payhip購入履歴を確認できません。Order IDを確認してください。", 400
    if status == "already_used":
        return "", order_row, "このPayhip購入履歴はすでに使用済みです。", 409
    if status == "cancelled":
        return "", order_row, "このPayhip購入履歴はキャンセル扱いのため使用できません。", 409
    order_code = str((order_row or {}).get("stores_order_no") or "").strip()
    if not order_code:
        return "", order_row, "Payhip購入履歴の注文IDを確認できません。管理者に連絡してください。", 400
    return order_code, order_row, None, 200


def _check_payhip_order_row_for_redeem(
    *,
    order_id: str,
    order_row: dict | None,
    product_type: str,
    enforce_product_type: bool = True,
) -> tuple[str, dict | None, str | None, int]:
    if not order_row:
        return "not_found", None, f"注文番号（{order_id}）が見つかりません。購入確認メールに記載の番号を確認してください。", 400

    payment_status = str((order_row or {}).get("payment_status") or "").lower()
    if payment_status == "cancelled":
        return "cancelled", order_row, f"この注文番号（{order_id}）はキャンセル扱いのため使用できません。", 409

    purchased_type = order_row.get("product_type")
    if enforce_product_type and purchased_type and purchased_type != product_type:
        return (
            "product_mismatch",
            order_row,
            f"この注文番号は{_product_label(purchased_type)}用です。"
            f"{_product_label(product_type)}の入力フォームでは使用できません。",
            409,
        )
    if payment_status in {"reusable", "test", "permanent"}:
        return "reusable", order_row, None, 200
    return "ok", order_row, None, 200


def _log_order_check(
    *,
    provider: str | None,
    order_id: str,
    strict_check: bool,
    check_result: str,
    reason: str,
) -> None:
    logger.info(
        "order_check provider=%s order_id=%s strict_check=%s check_result=%s reason=%s",
        provider or "unknown",
        order_id,
        strict_check,
        check_result,
        reason,
    )


def _existing_chart_redirect(order_code: str) -> RedirectResponse | None:
    if not os.environ.get("DATABASE_URL"):
        return None
    try:
        redemption = pg_store.get_redemption_by_order_code(order_code)
        token = redemption.get("token") if redemption else None
        if not token:
            charts = pg_store.list_charts_by_order_code(order_code)
            token = charts[0].get("token") if charts else None
        if token:
            logger.info("redirect_existing_chart order_id=%s token_prefix=%s", order_code, str(token)[:8])
            return RedirectResponse(f"/chart/{token}", status_code=303)
    except Exception as exc:
        logger.exception(
            "existing_chart_lookup_failed order_id=%s error_type=%s error=%r",
            order_code,
            type(exc).__name__,
            exc,
        )
    return None


def _verify_strict_stores_order(order_id: str) -> tuple[str, dict | None]:
    status, order_row = stores_mail_sync.verify_order_no(order_id)
    if status == "not_found" and _truthy(os.getenv("STORES_MAIL_SYNC_ON_SUBMIT", "1")):
        try:
            submit_limit = int(os.getenv("STORES_MAIL_SYNC_SUBMIT_LIMIT", "100"))
        except ValueError:
            submit_limit = 100
        stores_mail_sync.sync(limit=submit_limit)
        status, order_row = stores_mail_sync.verify_order_no(order_id)
    return status, order_row


def _gumroad_product_name_from_order(order_row: dict | None) -> str:
    if not isinstance(order_row, dict):
        return ""
    candidates = [
        order_row.get("product_name"),
        order_row.get("product_title"),
        order_row.get("product"),
        order_row.get("item_name"),
        order_row.get("name"),
        order_row.get("mail_subject"),
    ]
    return "\n".join(str(value) for value in candidates if value)


def _gumroad_product_type_from_name(product_name: str) -> str | None:
    normalized = (product_name or "").upper()
    has_basic = "[NP-WB]" in normalized
    has_full = "[NP-WF]" in normalized
    if has_basic == has_full:
        return None
    if has_full:
        return "western_full"
    return "western_basic"


def _verify_gumroad_order_product(
    *,
    order_id: str,
    order_row: dict | None,
    product_type: str,
    enforce_product_type: bool,
) -> tuple[str | None, int]:
    purchased_type = _gumroad_product_type_from_name(_gumroad_product_name_from_order(order_row))
    if not purchased_type:
        _log_order_check(
            provider="gumroad",
            order_id=order_id,
            strict_check=True,
            check_result="product_tag_missing",
            reason="Gumroad product name does not contain [NP-WB] or [NP-WF]",
        )
        return "Gumroadの商品名タグを確認できません。購入商品を確認できないため、この注文番号は使用できません。", 400
    if enforce_product_type and purchased_type != product_type:
        _log_order_check(
            provider="gumroad",
            order_id=order_id,
            strict_check=True,
            check_result="product_mismatch",
            reason=f"gumroad tag product_type={purchased_type} requested={product_type}",
        )
        return (
            f"この注文番号は{_product_label(purchased_type)}用です。"
            f"{_product_label(product_type)}の入力フォームでは使用できません。",
            409,
        )
    return None, 200


def _check_order_for_redeem(
    *,
    order_id: str,
    provider: str | None,
    product_type: str,
    enforce_product_type: bool = True,
    allow_gumroad_relaxed: bool = True,
) -> tuple[str, dict | None, str | None, int]:
    policy = _get_order_check_policy(provider)
    strict_check = bool(policy["strict"])
    if provider not in ORDER_PROVIDERS:
        _log_order_check(
            provider=provider,
            order_id=order_id,
            strict_check=strict_check,
            check_result="provider_unknown",
            reason="provider could not be resolved",
        )
        return "not_found", None, f"注文番号（{order_id}）を確認できません。購入確認メールに記載の番号を確認してください。", 400

    if (
        provider == "gumroad"
        and not strict_check
        and allow_gumroad_relaxed
        and product_type in GUMROAD_RELAXED_PRODUCT_TYPES
    ):
        order_row = {
            "provider": "gumroad",
            "stores_order_no": order_id,
            "payment_status": "relaxed",
            "product_type": product_type,
        }
        _log_order_check(
            provider=provider,
            order_id=order_id,
            strict_check=False,
            check_result="accepted_relaxed",
            reason="temporary Gumroad relaxed verification; order will be recorded in redemptions/charts on save",
        )
        return "ok", order_row, None, 200

    if provider == "gumroad" and not strict_check:
        _log_order_check(
            provider=provider,
            order_id=order_id,
            strict_check=False,
            check_result="relaxed_not_allowed",
            reason="temporary Gumroad relaxed verification is disabled for this flow",
        )
        return "not_found", None, "Gumroad注文はこのフォームでは使用できません。", 400

    if not os.environ.get("DATABASE_URL"):
        _log_order_check(
            provider=provider,
            order_id=order_id,
            strict_check=True,
            check_result="skipped" if provider == "stores" else "error",
            reason="DATABASE_URL is not configured",
        )
        if provider == "gumroad":
            return "error", None, "Gumroad注文の確認に必要なDATABASE_URLが未設定です。", 503
        return "ok", None, None, 200

    try:
        status, order_row = _verify_strict_stores_order(order_id)
    except Exception as exc:
        logger.exception(
            "order_check_failed provider=%s order_id=%s product_type=%s error_type=%s error=%r",
            provider,
            order_id,
            product_type,
            type(exc).__name__,
            exc,
        )
        _log_order_check(
            provider=provider,
            order_id=order_id,
            strict_check=True,
            check_result="error",
            reason=repr(exc),
        )
        return "error", None, _public_error_message(exc, fallback="注文番号の照合に失敗しました。時間をおいて再試行してください。"), 503

    _log_order_check(
        provider=provider,
        order_id=order_id,
        strict_check=True,
        check_result=status,
        reason="stores strict check",
    )
    if status == "not_found":
        return "not_found", order_row, f"注文番号（{order_id}）が見つかりません。購入確認メールに記載の番号を確認してください。", 400
    if status == "already_used":
        return "already_used", order_row, f"この注文番号（{order_id}）はすでに使用済みです。", 409
    if status == "cancelled":
        return "cancelled", order_row, f"この注文番号（{order_id}）はキャンセル扱いのため使用できません。", 409

    row_provider = str((order_row or {}).get("provider") or "").strip().lower()
    if row_provider and row_provider != provider:
        _log_order_check(
            provider=provider,
            order_id=order_id,
            strict_check=True,
            check_result="provider_mismatch",
            reason=f"order provider={row_provider} requested={provider}",
        )
        return "not_found", order_row, f"注文番号（{order_id}）を{_provider_label(provider)}の注文として確認できません。", 400

    if provider == "gumroad":
        product_error, product_error_status = _verify_gumroad_order_product(
            order_id=order_id,
            order_row=order_row,
            product_type=product_type,
            enforce_product_type=enforce_product_type,
        )
        if product_error:
            return "product_mismatch", order_row, product_error, product_error_status
        return status, order_row, None, 200

    purchased_type = (order_row or {}).get("product_type")
    if enforce_product_type and purchased_type and purchased_type != product_type:
        return (
            "product_mismatch",
            order_row,
            f"この注文番号は{_product_label(purchased_type)}用です。"
            f"{_product_label(product_type)}の入力フォームでは使用できません。",
            409,
        )
    return status, order_row, None, 200


def _provider_label(provider: str | None) -> str:
    if provider == "payhip":
        return "Payhip"
    if provider == "gumroad":
        return "Gumroad"
    if provider == "stores":
        return "STORES"
    return "購入元"


def _product_label(product_type: str | None) -> str:
    if product_type == "api_key_trial":
        return "お試しAPIクレジット"
    if product_type == "api_key_standard":
        return "APIクレジット"
    if product_type in API_KEY_PRODUCT_TYPES:
        return "APIキー"
    addon_labels = {
        "western_asteroids_addon": "ホロスコープ：小惑星追加",
        "western_31days_transit_addon": "ホロスコープ：38日トランジット追加",
        "western_long_term_transits_addon": "ホロスコープ：長期トランジット追加",
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


def _validate_lat_lon(lat: float, lon: float) -> tuple[float, float]:
    if not (-90 <= lat <= 90):
        raise ValueError("緯度は -90 から 90 の範囲で入力してください。")
    # 経度は周期的なので、範囲外（地図クリックで世界地図が横に繰り返し表示された
    # 箇所を選んだ場合など）は弾かずに ±180 へ正規化する。範囲内の値は
    # 浮動小数の誤差を出さないようそのまま返す。
    if lon < -180.0 or lon > 180.0:
        lon = ((lon + 180.0) % 360.0 + 360.0) % 360.0 - 180.0
    return lat, lon


def _validate_birth_date(value: str, lang: str = "ja") -> str:
    raw = value.strip()
    digits = re.sub(r"\D", "", raw)
    if not digits:
        raise ValueError("Enter your date of birth." if lang == "en" else "生年月日を入力してください。")
    if len(digits) != 8:
        raise ValueError(
            "Enter 8 digits so the date can be interpreted as YYYY-MM-DD. Example: 1990-01-01"
            if lang == "en"
            else "生年月日は YYYY-MM-DD として解釈できる8桁の数字で入力してください。例: 1990-01-01"
        )
    try:
        selected = date(int(digits[0:4]), int(digits[4:6]), int(digits[6:8]))
    except ValueError as exc:
        raise ValueError(
            "That date does not exist. Enter a date that can be interpreted as YYYY-MM-DD."
            if lang == "en"
            else "存在しない日付です。YYYY-MM-DD として解釈できる日付を入力してください。"
        ) from exc
    today_jst = datetime.now(ZoneInfo("Asia/Tokyo")).date()
    if selected > today_jst:
        raise ValueError("Future dates are not allowed." if lang == "en" else "生年月日は未来日を指定できません。")
    return selected.isoformat()


def _build_birth_location(
    *,
    prefecture: str,
    birth_place_kind: str,
    birth_place_overseas: str,
    birth_place_city: str,
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
        lat, lon = _validate_lat_lon(lat, lon)
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
        lat, lon = _validate_lat_lon(lat, lon)
    city_name = birth_place_city.strip()
    place_label = f"{pref_name} {city_name}" if city_name else pref_name
    if lat is None and lon is None and city_name:
        municipality = resolve_municipality(pref_name, city_name)
        if municipality:
            _prefecture, resolved_city, lat, lon = municipality
            place_label = f"{pref_name} {resolved_city}"
    if lat is None and lon is None:
        _prefecture, lat, lon = resolve_prefecture(pref_name)
    return {
        "kind": "domestic",
        "birth_place": place_label,
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


ADMIN_BASIC_REALM = "nanami-products admin"


def _admin_basic_unauthorized(message: str = "Unauthorized") -> HTMLResponse:
    return HTMLResponse(
        message,
        status_code=401,
        headers={"WWW-Authenticate": f'Basic realm="{ADMIN_BASIC_REALM}", charset="UTF-8"'},
    )


def _admin_basic_auth_error(request: Request) -> HTMLResponse | None:
    expected_user = os.getenv("ADMIN_BASIC_USER", "").strip()
    expected_password = os.getenv("ADMIN_BASIC_PASSWORD", "")
    if not expected_user or not expected_password:
        if _is_local_request(request):
            return None
        return _admin_basic_unauthorized("Admin authentication is not configured")

    auth = request.headers.get("Authorization", "")
    scheme, _, encoded = auth.partition(" ")
    if scheme.lower() != "basic" or not encoded:
        return _admin_basic_unauthorized()
    try:
        decoded = base64.b64decode(encoded, validate=True).decode("utf-8")
    except Exception:
        return _admin_basic_unauthorized()
    username, separator, password = decoded.partition(":")
    if not separator:
        return _admin_basic_unauthorized()
    if not (
        secrets.compare_digest(username, expected_user)
        and secrets.compare_digest(password, expected_password)
    ):
        return _admin_basic_unauthorized()
    return None


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
    if not _is_valid_order_code(order_code_clean):
        return _api_error("INVALID_INPUT", "order_code contains invalid characters", 400)

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
    if not _is_valid_order_code(order_code_clean):
        return _api_error("INVALID_INPUT", "order_code contains invalid characters", 400)

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
    if not _is_valid_order_code(order_code_clean):
        return _api_error("INVALID_INPUT", "order_code contains invalid characters", 400)

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
    if not _is_valid_order_code(order_code_clean):
        return _api_error("INVALID_INPUT", "order_code contains invalid characters", 400)
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


# ─── ACG（アストロカートグラフィ） ─────────────────────────────


@app.get("/acg", response_class=HTMLResponse)
def acg_map_page(request: Request):
    """ACG 天空線マップ（マンデン＋YAML貼り付けパーソナル）。?lang=en で英語表示。"""
    return templates.TemplateResponse(
        "acg_map.html",
        {
            "request": request,
            "lang": _resolve_lang(request),
            "public_base_url": _public_base_url(request),
        },
    )


@app.get("/acg/globe-demo", response_class=HTMLResponse)
def acg_globe_demo_page(request: Request):
    """ACG 3D地球儀デモ（仕組み理解用）。"""
    return templates.TemplateResponse("acg_globe_demo.html", {"request": request})


# ─── Astro Earth（3Dアストロカートグラフィ地球儀ビューア） ──────────────
# 3D用JS/CSS（Three.js）はこの astro_earth.html にだけ読み込む。
# ACGラインは既存 /api/acg/personal を流用し、クリック地点の洞察のみ下記APIで返す。

@app.get("/astro-earth", response_class=HTMLResponse)
def astro_earth_page(request: Request):
    return templates.TemplateResponse("astro_earth.html", {"request": request})


@app.get("/api/geocode")
def api_geocode(q: str = ""):
    """地名検索（source=manual_search）。結果は内部共通形式の配列で返す。

    プロバイダ（MVP: Nominatim）は services/geocoding_service に分離。
    """
    from services.geocoding_service import GeocodingError, search

    query = (q or "").strip()
    if not query:
        return JSONResponse({"results": [], "error": "検索する地名を入力してください。"}, status_code=400)
    if len(query) < 2:
        return JSONResponse({"results": [], "error": "地名をもう少し具体的に入力してください（2文字以上）。"}, status_code=400)

    try:
        results = search(query)
    except GeocodingError:
        return JSONResponse(
            {"results": [], "error": "地名の検索に失敗しました。時間をおいて再試行してください。"},
            status_code=502,
        )
    if not results:
        return _mark_no_store(JSONResponse({"results": [], "error": "地点が見つかりませんでした。"}))
    return _mark_no_store(JSONResponse({"results": results}))


@app.post("/api/astro-earth/point")
async def astro_earth_point(request: Request):
    """出生YAML＋緯度経度から、近いACGライン・リロケーション概要・AI用YAMLを返す。

    ステートレス（保存しない・本文をログに出さない）。ACGライン全体は
    /api/acg/personal を使う想定で、ここは1地点の洞察に絞る。
    """
    from services.acg_api import AcgInputError, AcgYamlFormatError
    from services.astro_earth.earth_service import build_point_insight

    try:
        payload = await request.json()
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}

    yaml_text = payload.get("yaml_text")
    if not isinstance(yaml_text, str) or not yaml_text.strip():
        return JSONResponse({"ok": False, "error": "出生YAMLを貼り付けてください。"}, status_code=400)

    try:
        result = build_point_insight(
            natal_yaml_text=yaml_text,
            latitude=payload.get("lat"),
            longitude=payload.get("lon"),
            location_name=str(payload.get("location_name") or ""),
            source=str(payload.get("source") or "globe_click"),
        )
    except AcgYamlFormatError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=422)
    except (AcgInputError, ValueError) as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)

    return _mark_no_store(JSONResponse({"ok": True, **result}))


@app.get("/api/acg/mundane")
def acg_mundane(date: str = ""):
    """指定日のマンデン ACG 線 GeoJSON。認証なし・日付単位で全ユーザー共通。

    計算基準時刻は当該日 03:00 UTC 固定（= 日本時間の正午時点の空）。
    """
    from services.acg_api import AcgInputError, mundane_geojson

    target = date.strip() if date else datetime.now(timezone.utc).date().isoformat()
    try:
        geojson = mundane_geojson(target)
    except AcgInputError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
    return JSONResponse(
        geojson,
        headers={"Cache-Control": "public, max-age=86400"},
    )


@app.post("/api/acg/personal")
async def acg_personal(request: Request):
    """貼り付け YAML からパーソナル ACG 線 GeoJSON を返す。

    ステートレス: 貼り付け内容はサーバーに保存せず、ログにも本文を出さない。
    """
    from services.acg_api import (
        MAX_YAML_BYTES,
        AcgInputError,
        AcgYamlFormatError,
        personal_geojson,
    )

    body = await request.body()
    if len(body) > MAX_YAML_BYTES:
        return JSONResponse({"ok": False, "error": "YAML テキストが大きすぎます。"}, status_code=413)

    yaml_text = body.decode("utf-8", errors="replace")
    # 仕様は JSON ボディ {"yaml_text": "..."}。生テキスト貼り付けも受け付ける
    content_type = (request.headers.get("content-type") or "").lower()
    if "application/json" in content_type:
        try:
            parsed = json.loads(yaml_text)
            if isinstance(parsed, dict) and isinstance(parsed.get("yaml_text"), str):
                yaml_text = parsed["yaml_text"]
        except json.JSONDecodeError:
            pass

    try:
        geojson = personal_geojson(yaml_text)
    except AcgYamlFormatError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=422)
    except AcgInputError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
    return _mark_no_store(JSONResponse(geojson))


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
        logger.exception("api_key_auth_failed endpoint=%s", endpoint)
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
            logger.warning(
                "api_chart_snapshot_unavailable endpoint=%s api_key_id=%s error_type=%s error=%r",
                endpoint,
                api_key_id,
                type(exc).__name__,
                exc,
            )
            if isinstance(body.get("chart"), dict):
                body["chart"].update({"svg_available": False, "chart_id": None, "svg_url": None})
            if isinstance(body.get("shichusuimei_chart"), dict):
                body["shichusuimei_chart"].update(
                    {
                        "svg_available": False,
                        "png_available": False,
                        "chart_id": None,
                        "svg_url": None,
                        "png_url": None,
                    }
                )

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
        logger.exception("api_key_auth_failed endpoint=chart_read")
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


# ─── Astro Travel（旅行先診断 MVP） ──────────────────────────
# 既存の鑑定・ACG・マンデンとは分離した導線。出生YAML・旅行先・日程・目的から
# travel_report YAML を生成し、charts テーブル（product_type=travel）に保存する。

def _travel_default_dates() -> tuple[str, str]:
    base = datetime.now(ZoneInfo("Asia/Tokyo")).date()
    arrival = base + timedelta(days=30)
    departure = arrival + timedelta(days=3)
    return arrival.isoformat(), departure.isoformat()


def _travel_form_response(request: Request, *, form: dict | None, error: str | None, status_code: int = 200):
    from services.travel.travel_schema import TRAVEL_PURPOSES

    default_arrival, default_departure = _travel_default_dates()
    response = templates.TemplateResponse(
        "travel_form.html",
        {
            "request": request,
            "purposes": list(TRAVEL_PURPOSES.items()),
            "default_arrival": default_arrival,
            "default_departure": default_departure,
            "form": form,
            "error": error,
        },
        status_code=status_code,
    )
    return _mark_no_store(response)


@app.get("/travel", response_class=HTMLResponse)
def travel_form(request: Request):
    return _travel_form_response(request, form=None, error=None)


@app.post("/travel/generate")
def travel_generate(
    request: Request,
    natal_yaml: str = Form(""),
    purpose: str = Form(""),
    location_name: str = Form(""),
    country: str = Form(""),
    latitude: str = Form(""),
    longitude: str = Form(""),
    timezone: str = Form(""),
    arrival_date: str = Form(""),
    departure_date: str = Form(""),
):
    from services.travel.travel_generator import build_travel_report

    form_values = {
        "natal_yaml": natal_yaml,
        "purpose": purpose,
        "location_name": location_name,
        "country": country,
        "latitude": latitude,
        "longitude": longitude,
        "timezone": timezone,
        "arrival_date": arrival_date,
        "departure_date": departure_date,
    }
    try:
        result = build_travel_report(
            natal_yaml_text=natal_yaml,
            purpose_key=purpose,
            location_name=location_name,
            country=country,
            latitude=latitude,
            longitude=longitude,
            timezone_name=timezone,
            arrival_date=arrival_date,
            departure_date=departure_date,
        )
    except ValueError as exc:
        # 入力起因（日付・目的・緯度経度・YAML形式）はフォームへ差し戻す。
        return _travel_form_response(request, form=form_values, error=str(exc), status_code=400)
    except Exception as exc:  # noqa: BLE001
        logger.exception("travel_generate_failed error_type=%s", type(exc).__name__)
        return _travel_form_response(
            request,
            form=form_values,
            error=_public_error_message(exc, fallback="診断の生成に失敗しました。時間をおいて再試行してください。"),
            status_code=500,
        )

    stay = result["doc"]["input"]["stay"]
    loc = result["doc"]["input"]["location"]
    token = secrets.token_urlsafe(18)
    try:
        pg_store.save_chart(
            token=token,
            order_code=None,
            buyer_name=loc.get("name") or None,
            birth_date=stay["arrival_date"],
            birth_time=None,
            birth_place=", ".join(p for p in [loc.get("name"), loc.get("country")] if p) or None,
            options={"product_type": "travel", "app": "astro_travel"},
            yaml_text=result["yaml_text"],
            prompt_text=result["prompt_text"],
            expires_at=_chart_expires_at(),
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("travel_save_failed error_type=%s", type(exc).__name__)
        return _travel_form_response(
            request,
            form=form_values,
            error=_public_error_message(exc, fallback="診断結果の保存に失敗しました。時間をおいて再試行してください。"),
            status_code=500,
        )
    return RedirectResponse(f"/travel/result/{token}", status_code=303)


@app.get("/travel/result/{token}", response_class=HTMLResponse)
def travel_result(request: Request, token: str):
    chart = _load_chart_or_404(token, include_svgs=False)
    options = chart.get("options") or {}
    if options.get("product_type") != "travel":
        raise HTTPException(status_code=404, detail="travel result not found")
    try:
        loaded = yaml.safe_load(chart["yaml_text"]) or {}
    except Exception:
        loaded = {}
    doc = (loaded.get("travel_report") if isinstance(loaded, dict) else None) or {}
    expires_at = _chart_expiry(chart)
    expires_label = _chart_expiry_label(expires_at)
    response = templates.TemplateResponse(
        "travel_result.html",
        {
            "request": request,
            "doc": doc,
            "yaml_text": chart["yaml_text"],
            "prompt_text": chart.get("prompt_text") or "",
            "expires_label": expires_label,
        },
    )
    _apply_public_chart_headers(response, chart, max_age=300)
    return response


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
    order_provider: str = Form(""),
    email: str = Form(""),
    agree_final: str | None = Form(None),
):
    order_code_clean = _normalize_stores_order_no(order_code)
    form = {"order_code": order_code, "order_provider": order_provider, "email": email, "agree_final": bool(agree_final)}

    def _render_error(message: str, status_code: int = 400):
        return _mark_no_store(templates.TemplateResponse(
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
        ))

    if not order_code_clean:
        return _render_error("注文番号を入力してください。")
    if not _is_valid_order_code(order_code_clean):
        return _render_error("注文番号には英数字、ハイフン、アンダースコア、イコールのみ使用できます。")
    order_provider_clean = _resolve_order_provider(order_code_clean, order_provider)
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

    status, order_row, order_error, order_error_status = _check_order_for_redeem(
        order_id=order_code_clean,
        provider=order_provider_clean,
        product_type="api_key_trial",
        enforce_product_type=False,
        allow_gumroad_relaxed=False,
    )
    if order_error:
        return _render_error(order_error, order_error_status)

    purchased_type = (order_row or {}).get("product_type")
    if order_provider_clean == "stores" and purchased_type and purchased_type not in API_KEY_PRODUCT_TYPES:
        return _render_error(
            f"この注文番号はAPIキー用の商品ではありません。購入商品: {_product_label(str(purchased_type))}",
            409,
        )
    if order_provider_clean == "stores" and not purchased_type and status != "reusable":
        return _render_error("購入商品の判定ができません。APIキー用商品の注文番号か確認してください。", 409)

    issue_credits = _api_key_issue_credits(str(purchased_type) if purchased_type else None)
    try:
        record = pg_store.create_api_key(
            label=f"{order_provider_clean}_{order_code_clean}",
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
    lang = _resolve_lang(request)
    if "type" in request.query_params:
        return RedirectResponse(str(request.url.replace(path=_start_url(product_type)).include_query_params(lang=lang)), status_code=301)
    return templates.TemplateResponse(
        _buyer_template("start", product_type),
        {"request": request, **_i18n_context(request), **_product_context(product_type, lang)},
    )


@app.get("/start/{product_slug}")
def start_by_slug(request: Request, product_slug: str):
    product_type = _product_type_from_slug(product_slug)
    lang = _resolve_lang(request)
    return templates.TemplateResponse(
        _buyer_template("start", product_type),
        {"request": request, **_i18n_context(request), **_product_context(product_type, lang)},
    )


@app.get("/redeem", response_class=HTMLResponse)
@app.get("/redeem/{product_slug}", response_class=HTMLResponse)
def redeem_get(request: Request, product_slug: str | None = None):
    product_type = _product_type_from_slug(product_slug) if product_slug else _product_type_from_request(request)
    lang = _resolve_lang(request)
    if not product_slug and "type" in request.query_params and "order" not in request.query_params:
        return RedirectResponse(str(request.url.replace(path=_redeem_url(product_type)).include_query_params(lang=lang)), status_code=301)
    order_code = request.query_params.get("order", "").strip()
    return templates.TemplateResponse(
        _buyer_template("redeem", product_type),
        {
            "request": request,
            **_i18n_context(request),
            "prefectures": PREFECTURE_OPTIONS,
            "timezone_options": _timezone_options(lang),
            "error": None,
            "form": {"order_code": order_code} if order_code else None,
            "payhip_products": _payhip_product_options(),
            **_product_context(product_type, lang),
        },
    )


@app.post("/redeem", response_class=HTMLResponse)
@app.post("/redeem/{product_slug}", response_class=HTMLResponse)
def redeem_post(
    request: Request,
    product_slug: str | None = None,
    order_code: str = Form(""),
    order_provider: str = Form(""),
    payhip_email: str = Form(""),
    payhip_product_code: str = Form(""),
    payhip_order_id: str = Form(""),
    buyer_name: str = Form(""),
    email: str = Form(""),
    birth_date: str = Form(""),
    birth_time: str = Form(""),
    birth_time_accuracy: str = Form("auto"),
    prefecture: str = Form(""),
    birth_place_kind: str = Form("domestic"),
    birth_place_overseas: str = Form(""),
    birth_place_city: str = Form(""),
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
    lang = _resolve_lang(request)
    product = PRODUCT_CONFIG[product_type]

    include_asteroids = bool(product["include_asteroids"])
    include_shichusuimei = bool(product["include_shichusuimei"])
    include_transit = bool(product.get("include_transit"))

    # 商品ごとに強制制御します。
    # western_basic / western_full では日替わり境界UIを出さず、必ず False。
    # shichu は購入者が 23時 / 1時 を選択できます。未選択時は 1時（False）を標準にします。
    day_change_at_23_bool = _truthy(day_change_at_23) if product_type == "shichu" else False

    def _form_err(msg: str, status: int = 400):
        return _mark_no_store(templates.TemplateResponse(
            _buyer_template("redeem", product_type),
            {
                "request": request,
                **_i18n_context(request),
                "prefectures": PREFECTURE_OPTIONS,
                "timezone_options": _timezone_options(lang),
                "error": msg,
                "form": {
                    "order_code": order_code,
                    "order_provider": order_provider,
                    "payhip_email": payhip_email,
                    "payhip_product_code": payhip_product_code,
                    "payhip_order_id": payhip_order_id,
                    "buyer_name": buyer_name,
                    "email": email,
                    "birth_date": birth_date,
                    "birth_time": birth_time,
                    "birth_time_accuracy": birth_time_accuracy,
                    "prefecture": prefecture,
                    "birth_place_kind": birth_place_kind,
                    "birth_place_overseas": birth_place_overseas,
                    "birth_place_city": birth_place_city,
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
                **_product_context(product_type, lang),
                "payhip_products": _payhip_product_options(),
            },
            status_code=status,
        ))

    requested_provider = (order_provider or "").strip().lower()
    payhip_metadata: dict[str, str] = {}
    payhip_order_row: dict | None = None
    if requested_provider == "payhip":
        payhip_metadata, payhip_error = _payhip_metadata_from_form(
            payhip_email=payhip_email,
            payhip_product_code=payhip_product_code,
            payhip_order_id=payhip_order_id,
            expected_product_type=product_type,
        )
        if payhip_error:
            return _form_err(payhip_error)
        order_code_clean, payhip_order_row, payhip_order_error, payhip_order_error_status = _resolve_payhip_order_from_metadata(payhip_metadata)
        if payhip_order_error:
            return _form_err(payhip_order_error, status=payhip_order_error_status)
        order_provider_clean = "payhip"
    else:
        order_code_clean = _normalize_stores_order_no(order_code)
        if not order_code_clean:
            return _form_err("注文番号を入力してください。")
        if not _is_valid_order_code(order_code_clean):
            return _form_err("注文番号には英数字、ハイフン、アンダースコア、イコールのみ使用できます。")
        order_provider_clean = _resolve_order_provider(order_code_clean, order_provider)
    if not agree_final:
        return _form_err("入力後は変更できないことを確認し、チェックを入れてください。")

    if product_type == "transit_yaml":
        try:
            lat = _parse_optional_float(event_lat, "緯度")
            lng = _parse_optional_float(event_lng, "経度")
            if lat is None or lng is None:
                raise ValueError("緯度・経度を入力してください。")
            lat, lng = _validate_lat_lon(lat, lng)
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

        if order_provider_clean == "payhip":
            status, _order_row, order_error, order_error_status = _check_payhip_order_row_for_redeem(
                order_id=order_code_clean,
                order_row=payhip_order_row,
                product_type=product_type,
            )
        else:
            status, _order_row, order_error, order_error_status = _check_order_for_redeem(
                order_id=order_code_clean,
                provider=order_provider_clean,
                product_type=product_type,
            )
        if order_error:
            return _form_err(order_error, status=order_error_status)

        token = secrets.token_urlsafe(18)
        chart_options = {
            **doc.get("product", {}).get("options", {}),
            "product_type": product_type,
            "order_provider": order_provider_clean,
            "order_strict_check": _get_order_check_policy(order_provider_clean)["strict"],
            **payhip_metadata,
        }
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
                    email=payhip_metadata.get("purchaser_email") or email.strip() or None,
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
                    redemption_metadata=payhip_metadata or None,
                )
        except Exception as e:
            logger.exception(
                "chart_save_failed product_type=%s provider=%s order_id=%s error_type=%s error=%r",
                product_type,
                order_provider_clean,
                order_code_clean,
                type(e).__name__,
                e,
            )
            existing = _existing_chart_redirect(order_code_clean)
            if existing:
                return existing
            return _form_err(_public_error_message(e, fallback="保存に失敗しました。時間をおいて再試行してください。"), status=503)

        if not ok:
            existing = _existing_chart_redirect(order_code_clean)
            if existing:
                return existing
            _log_order_check(
                provider=order_provider_clean,
                order_id=order_code_clean,
                strict_check=_get_order_check_policy(order_provider_clean)["strict"],
                check_result="already_used",
                reason="redemption insert rejected duplicate order_id",
            )
            return _form_err(f"この注文番号（{order_code_clean}）はすでに使用済みです。別の注文番号をご確認ください。", status=409)

        return RedirectResponse(f"/chart/{token}", status_code=303)

    try:
        birth_date_clean = _validate_birth_date(birth_date, lang)
    except Exception as e:
        return _form_err(str(e))

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
            birth_place_city=birth_place_city,
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

    if order_provider_clean == "payhip":
        status, _order_row, order_error, order_error_status = _check_payhip_order_row_for_redeem(
            order_id=order_code_clean,
            order_row=payhip_order_row,
            product_type=product_type,
        )
    else:
        status, _order_row, order_error, order_error_status = _check_order_for_redeem(
            order_id=order_code_clean,
            provider=order_provider_clean,
            product_type=product_type,
        )
    if order_error:
        return _form_err(order_error, status=order_error_status)

    try:
        common_product_args = {
            "title": buyer_name.strip() or None,
            "birth_date": birth_date_clean,
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
    chart_options = {
        **doc.get("product", {}).get("options", {}),
        "product_type": product_type,
        "order_provider": order_provider_clean,
        "order_strict_check": _get_order_check_policy(order_provider_clean)["strict"],
        **payhip_metadata,
    }
    artifacts = _build_chart_artifacts(yaml_text=yaml_text, doc=doc, product_type=product_type)
    expires_at = _chart_expires_at()
    try:
        if status == "reusable":
            pg_store.save_chart(
                token=token,
                order_code=order_code_clean,
                buyer_name=buyer_name.strip() or None,
                birth_date=birth_date_clean,
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
                email=payhip_metadata.get("purchaser_email") or email.strip() or None,
                buyer_name=buyer_name.strip() or None,
                token=token,
                birth_date=birth_date_clean,
                birth_time=birth_time_info["birth_time"] or birth_time_info["calculation_time"],
                birth_place=birth_place_label,
                options=chart_options,
                yaml_text=yaml_text,
                prompt_text=prompt_text,
                **artifacts,
                expires_at=expires_at,
                redemption_metadata=payhip_metadata or None,
            )
    except Exception as e:
        logger.exception(
            "chart_save_failed product_type=%s provider=%s order_id=%s error_type=%s error=%r",
            product_type,
            order_provider_clean,
            order_code_clean,
            type(e).__name__,
            e,
        )
        existing = _existing_chart_redirect(order_code_clean)
        if existing:
            return existing
        return _form_err(_public_error_message(e, fallback="保存に失敗しました。時間をおいて再試行してください。"), status=503)

    if not ok:
        existing = _existing_chart_redirect(order_code_clean)
        if existing:
            return existing
        _log_order_check(
            provider=order_provider_clean,
            order_id=order_code_clean,
            strict_check=_get_order_check_policy(order_provider_clean)["strict"],
            check_result="already_used",
            reason="redemption insert rejected duplicate order_id",
        )
        return _form_err(
            f"この注文番号（{order_code_clean}）はすでに使用済みです。"
            "別の注文番号をご確認ください。",
            status=409,
        )

    chart_redirect = f"/chart/{token}"
    if lang != "ja":
        chart_redirect = f"{chart_redirect}?lang={lang}"
    return RedirectResponse(chart_redirect, status_code=303)


# ─── チャートページ（ルート順に注意） ──────────────────────────────

@app.get("/chart/{token}.yaml", response_class=PlainTextResponse)
def chart_yaml(token: str):
    chart = _load_chart_or_404(token, include_svgs=False)
    yaml_text = chart["yaml_text"]
    response = PlainTextResponse(yaml_text, media_type="text/yaml; charset=utf-8")
    _apply_public_chart_headers(response, chart, max_age=0)
    return response


@app.get("/chart/{token}/natal.yaml", response_class=PlainTextResponse)
def chart_natal_yaml(token: str):
    chart = _load_chart_or_404(token, include_svgs=False)
    try:
        yaml_text = build_base_astrology_yaml(chart["yaml_text"])
    except Exception as exc:
        _raise_chart_yaml_generation_error(token, "natal.yaml", exc)
    response = PlainTextResponse(yaml_text, media_type="text/yaml; charset=utf-8")
    response.headers["Content-Disposition"] = 'attachment; filename="nanami-natal.yaml"'
    _apply_public_chart_headers(response, chart, max_age=86400)
    return response


@app.get("/chart/{token}/natal-asteroids.yaml", response_class=PlainTextResponse)
def chart_natal_asteroids_yaml(token: str):
    chart = _load_chart_or_404(token, include_svgs=False)
    try:
        yaml_text = build_natal_asteroids_yaml(chart["yaml_text"])
    except Exception as exc:
        _raise_chart_yaml_generation_error(token, "natal-asteroids.yaml", exc)
    response = PlainTextResponse(yaml_text, media_type="text/yaml; charset=utf-8")
    response.headers["Content-Disposition"] = 'attachment; filename="nanami-natal-asteroids.yaml"'
    _apply_public_chart_headers(response, chart, max_age=86400)
    return response


@app.get("/chart/{token}/transit.yaml", response_class=PlainTextResponse)
def chart_transit_yaml(token: str):
    chart = _load_chart_or_404(token, include_svgs=False)
    try:
        yaml_text = build_transit_astrology_yaml(chart["yaml_text"])
    except Exception as exc:
        _raise_chart_yaml_generation_error(token, "transit.yaml", exc)
    response = PlainTextResponse(yaml_text, media_type="text/yaml; charset=utf-8")
    response.headers["Content-Disposition"] = 'attachment; filename="nanami-transit.yaml"'
    _apply_public_chart_headers(response, chart, max_age=0)
    return response


@app.get("/chart/{token}/long-term-transits.yaml", response_class=PlainTextResponse)
def chart_long_term_transits_yaml(token: str):
    chart = _load_chart_or_404(token, include_svgs=False)
    try:
        yaml_text = build_long_term_transits_yaml(yaml_text=chart["yaml_text"])
    except Exception as exc:
        _raise_chart_yaml_generation_error(token, "long-term-transits.yaml", exc)
    if not yaml_text:
        raise HTTPException(status_code=404, detail="long-term transits yaml not found")
    response = PlainTextResponse(yaml_text, media_type="text/yaml; charset=utf-8")
    response.headers["Content-Disposition"] = 'attachment; filename="nanami-long-term-transits.yaml"'
    _apply_public_chart_headers(response, chart, max_age=0)
    return response


@app.get("/chart/{token}/detail.yaml", response_class=PlainTextResponse)
def chart_detail_yaml(token: str):
    chart = _load_chart_or_404(token, include_svgs=False)
    try:
        yaml_text = build_detail_astrology_yaml(chart["yaml_text"])
    except Exception as exc:
        _raise_chart_yaml_generation_error(token, "detail.yaml", exc)
    response = PlainTextResponse(yaml_text, media_type="text/yaml; charset=utf-8")
    response.headers["Content-Disposition"] = 'attachment; filename="nanami-detail.yaml"'
    _apply_public_chart_headers(response, chart, max_age=0)
    return response


@app.get("/chart/{token}/horoscope.svg")
def chart_horoscope_svg(token: str):
    chart = _load_chart_or_404(token)
    svg = chart.get("horoscope_svg")
    if not svg:
        try:
            loaded_doc = yaml.safe_load(chart["yaml_text"]) or {}
            chart_doc = loaded_doc if isinstance(loaded_doc, dict) else {}
        except Exception:
            chart_doc = None
        if _chart_has_western_natal(chart, doc=chart_doc):
            try:
                svg = optimize_svg(build_horoscope_svg_from_yaml(chart["yaml_text"], doc=chart_doc))
                if svg:
                    try:
                        pg_store.update_chart_svgs(token=token, horoscope_svg=svg)
                    except Exception:
                        pass
            except Exception:
                svg = None
    if not svg:
        raise HTTPException(status_code=404, detail="horoscope svg not found")
    response = Response(content=svg, media_type="image/svg+xml; charset=utf-8")
    response.headers["Content-Disposition"] = 'attachment; filename="nanami-horoscope.svg"'
    _apply_public_chart_headers(response, chart, max_age=86400)
    return response


@app.get("/chart/{token}/shichusuimei.svg")
def chart_shichusuimei_svg(token: str):
    chart = _load_chart_or_404(token)
    svg = optimize_svg(chart.get("shichusuimei_svg"))
    if not svg:
        try:
            loaded_doc = yaml.safe_load(chart["yaml_text"]) or {}
            chart_doc = loaded_doc if isinstance(loaded_doc, dict) else {}
            svg = optimize_svg(build_shichusuimei_svg_from_yaml(chart["yaml_text"], doc=chart_doc))
            if svg:
                try:
                    pg_store.update_chart_svgs(token=token, shichusuimei_svg=svg)
                except Exception:
                    pass
        except Exception:
            svg = None
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
    try:
        loaded_doc = yaml.safe_load(chart["yaml_text"]) or {}
        chart_doc = loaded_doc if isinstance(loaded_doc, dict) else {}
    except Exception:
        chart_doc = None
    has_western_natal = _chart_has_western_natal(chart, doc=chart_doc)
    has_western_asteroids = _chart_has_western_asteroids(chart, doc=chart_doc)
    has_31day_transit = _chart_has_31day_transit(chart, doc=chart_doc)
    full_like_western = has_western_natal and has_31day_transit
    asteroid_like_western = has_western_natal and has_western_asteroids
    long_term_transits_yaml = build_long_term_transits_yaml(doc=chart_doc) if has_long_term_transits(doc=chart_doc) else None
    ai_long_term_transits_yaml = build_ai_long_term_transits_yaml(doc=chart_doc) if has_long_term_transits(doc=chart_doc) else None
    full_yaml_text = chart["yaml_text"]
    share_yaml_text = _chart_share_yaml_text(chart, doc=chart_doc)
    try:
        detail_yaml = build_detail_astrology_yaml(full_yaml_text)
    except Exception:
        detail_yaml = share_yaml_text
    ai_paste_text = _chart_ai_paste_text(chart, share_yaml_text, doc=chart_doc)
    prompt_text = _chart_prompt_text(chart, doc=chart_doc)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("full.yaml", full_yaml_text)
        zf.writestr("detail.yaml", detail_yaml)
        zf.writestr("ai_paste.txt", ai_paste_text)
        if full_like_western:
            zf.writestr("natal.yaml", build_base_astrology_yaml(chart["yaml_text"]))
            zf.writestr("natal-asteroids.yaml", build_natal_asteroids_yaml(chart["yaml_text"]))
            zf.writestr("transit.yaml", build_transit_astrology_yaml(chart["yaml_text"]))
        elif asteroid_like_western:
            zf.writestr("natal.yaml", build_base_astrology_yaml(chart["yaml_text"]))
            zf.writestr("natal-asteroids.yaml", build_natal_asteroids_yaml(chart["yaml_text"]))
        elif product_type == "western_basic" or (has_western_natal and has_long_term_transits(doc=chart_doc)):
            zf.writestr("natal.yaml", build_base_astrology_yaml(chart["yaml_text"]))
        if long_term_transits_yaml:
            zf.writestr("long-term-transits.yaml", long_term_transits_yaml)
            zf.writestr("long-term-transits-full.yaml", long_term_transits_yaml)
        if ai_long_term_transits_yaml:
            zf.writestr("long-term-transits-ai.yaml", ai_long_term_transits_yaml)
        if chart.get("horoscope_svg"):
            zf.writestr("horoscope.svg", optimize_svg(chart["horoscope_svg"]) or "")
        if chart.get("shichusuimei_svg"):
            zf.writestr("shichusuimei.svg", optimize_svg(chart["shichusuimei_svg"]) or "")
        zf.writestr("prompt.txt", prompt_text)
        zf.writestr("README.txt", _chart_zip_readme(chart))
    response = Response(content=buffer.getvalue(), media_type="application/zip")
    response.headers["Content-Disposition"] = f'attachment; filename="{_chart_zip_filename(token)}"'
    _apply_public_chart_headers(response, chart, max_age=0)
    return response


@app.get("/chart/{token}/prompt.txt", response_class=PlainTextResponse)
def chart_prompt(token: str):
    chart = _load_chart_or_404(token, include_svgs=False)
    response = PlainTextResponse(_chart_prompt_text(chart), media_type="text/plain; charset=utf-8")
    _apply_public_chart_headers(response, chart, max_age=86400)
    return response


@app.get("/chart/{token}", response_class=HTMLResponse)
def chart_page(request: Request, token: str):
    total_start = time.perf_counter()
    lang = _resolve_lang(request)
    timings: dict[str, float] = {}
    chart = None
    product_type = None
    yaml_bytes = 0
    html_bytes = 0
    try:
        step_start = time.perf_counter()
        chart = _load_chart_or_404(token, include_svgs=False)
        timings["chart_fetch_ms"] = _elapsed_ms(step_start)
        yaml_bytes = len((chart.get("yaml_text") or "").encode("utf-8"))

        step_start = time.perf_counter()
        options = chart.get("options") or {}
        product_type = _chart_product_type(options)
        is_transit_yaml = product_type == "transit_yaml"
        chart_doc = None
        if not is_transit_yaml:
            try:
                loaded_doc = yaml.safe_load(chart["yaml_text"]) or {}
                chart_doc = loaded_doc if isinstance(loaded_doc, dict) else {}
            except Exception:
                chart_doc = None
        timings["yaml_parse_ms"] = _elapsed_ms(step_start)

        step_start = time.perf_counter()
        has_31day_transit = _chart_has_31day_transit(chart, doc=chart_doc)
        has_western_natal = _chart_has_western_natal(chart, doc=chart_doc)
        has_western_asteroids = _chart_has_western_asteroids(chart, doc=chart_doc)
        has_long_term_transits_data = has_long_term_transits(doc=chart_doc)
        full_like_western = has_western_natal and has_31day_transit
        asteroid_like_western = has_western_natal and has_western_asteroids
        long_term_like_western = has_western_natal and has_long_term_transits_data
        can_continue_with_transit = full_like_western
        has_yaml_mode_selector = full_like_western or asteroid_like_western or long_term_like_western
        has_horoscope_svg = has_western_natal
        has_shichusuimei_svg = product_type == "shichu"
        timings["display判定_ms"] = _elapsed_ms(step_start)
        chart["prompt_text"] = _chart_prompt_text(chart, doc=chart_doc)

        has_asteroids = False
        step_start = time.perf_counter()
        if has_horoscope_svg:
            try:
                has_asteroids = has_asteroid_svg_data(chart["yaml_text"], doc=chart_doc)
            except Exception:
                has_asteroids = False
        # /chart 初期HTMLではSVG本体を埋め込まない。ここはSVG関連の表示可否判定だけを測る。
        timings["svg取得整形_ms"] = _elapsed_ms(step_start)

        step_start = time.perf_counter()
        birth_time_notice = {"show": False}
        if not is_transit_yaml:
            try:
                birth_time_notice = extract_birth_time_notice(chart["yaml_text"], doc=chart_doc)
                birth_time_notice = _localized_birth_time_notice(birth_time_notice, lang)
            except Exception:
                birth_time_notice = {"show": False}
        share_yaml_text = _chart_share_yaml_text(chart, doc=chart_doc)
        share_prompt_text = _chart_prompt_for_yaml_text(chart, share_yaml_text, fallback_doc=chart_doc)
        asteroid_yaml_text = None
        expires_at = _chart_expiry(chart)
        expires_label = _chart_expiry_label(expires_at)
        base_url = _public_base_url(request)
        canonical_chart_url = f"{base_url}/chart/{token}"
        chart_url = canonical_chart_url if lang == "ja" else f"{canonical_chart_url}?lang={lang}"
        next_transit_url = (
            "/addon/new"
            f"?addon_type=western_31days_transit_addon"
            f"&previous_chart_url={quote(canonical_chart_url, safe='')}"
        )
        # 星読みの暦アプリ（HOSHIYOMI_APP_URL 設定時のみ）: チャートYAML＋ホロスコープSVGを
        # ?load= で自動読み込みさせるリンク。西洋占星術チャートのときだけ出す。
        hoshiyomi_app_url = None
        app_base = os.getenv("HOSHIYOMI_APP_URL", "").strip().rstrip("/")
        if app_base and has_western_natal and not is_transit_yaml:
            hoshiyomi_app_url = f"{app_base}/?load={quote(f'{base_url}/chart/{token}.yaml', safe='')}"
            if has_horoscope_svg:
                hoshiyomi_app_url += f"&load={quote(f'{base_url}/chart/{token}/horoscope.svg', safe='')}"
        timings["zip個別ファイル準備_ms"] = _elapsed_ms(step_start)

        step_start = time.perf_counter()
        response = templates.TemplateResponse(
            "chart_page.html",
            {
                "request": request,
                **_i18n_context(request),
                "token": token,
                "chart": chart,
                "is_transit_yaml": is_transit_yaml,
                "can_continue_with_transit": can_continue_with_transit,
                "has_31day_transit": has_31day_transit,
                "has_western_asteroids": has_western_asteroids,
                "has_long_term_transits": has_long_term_transits_data,
                "has_yaml_mode_selector": has_yaml_mode_selector,
                "has_horoscope_svg": has_horoscope_svg,
                "has_shichusuimei_svg": has_shichusuimei_svg,
                "has_asteroid_svg_data": has_asteroids,
                "birth_time_notice": birth_time_notice,
                "share_yaml_text": share_yaml_text,
                "share_prompt_text": share_prompt_text,
                "asteroid_yaml_text": asteroid_yaml_text,
                "chart_url": chart_url,
                "yaml_url": f"{base_url}/chart/{token}.yaml",
                "natal_yaml_url": f"{base_url}/chart/{token}/natal.yaml",
                "natal_asteroids_yaml_url": f"{base_url}/chart/{token}/natal-asteroids.yaml",
                "transit_yaml_url": f"{base_url}/chart/{token}/transit.yaml",
                "long_term_transits_yaml_url": f"{base_url}/chart/{token}/long-term-transits.yaml",
                "detail_yaml_url": f"{base_url}/chart/{token}/detail.yaml",
                "horoscope_svg_url": f"{base_url}/chart/{token}/horoscope.svg",
                "shichusuimei_svg_url": f"{base_url}/chart/{token}/shichusuimei.svg",
                "download_zip_url": f"{base_url}/chart/{token}/download.zip",
                "prompt_url": f"{base_url}/chart/{token}/prompt.txt",
                "usage_guide_url": "https://guide.nanami-astro.com/",
                "hoshiyomi_app_url": hoshiyomi_app_url,
                "next_transit_url": next_transit_url,
                "expires_at": expires_at,
                "expires_label": expires_label,
                "chart_has_no_expiry": _chart_has_no_expiry(chart),
            },
        )
        html_bytes = len(response.body or b"")
        timings["template描画_ms"] = _elapsed_ms(step_start)

        step_start = time.perf_counter()
        _apply_public_chart_headers(response, chart, max_age=300)
        timings["headers_ms"] = _elapsed_ms(step_start)
        return response
    finally:
        timings["合計_ms"] = _elapsed_ms(total_start)
        logger.warning(
            "chart_page_perf token_prefix=%s product_type=%s yaml_bytes=%s html_bytes=%s timings=%s",
            token[:8],
            product_type,
            yaml_bytes,
            html_bytes,
            timings,
        )


# ─── 管理者フロー ────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "admin_test_site_path": ADMIN_TEST_SITE_PATH},
    )


@app.get("/type")
def type_redirect():
    return RedirectResponse("/start/western-basic", status_code=302)


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
    auth_error = _admin_basic_auth_error(request)
    if auth_error:
        return auth_error
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


POST_CHART_BULK_SAMPLE = """トヨタ自動車工業株式会社,1937-08-28,12:00,愛知県 豊田市
ハイエレコン,1982-06-08,,広島県 広島市"""


def _post_chart_bulk_context(
    request: Request,
    *,
    bulk_input: str = "",
    rows: list[dict] | None = None,
    csv_output: str = "",
) -> dict:
    return {
        "request": request,
        "bulk_input": bulk_input,
        "sample_input": POST_CHART_BULK_SAMPLE,
        "rows": rows or [],
        "csv_output": csv_output,
    }


def _resolve_bulk_birth_place(raw_place: str) -> dict[str, object]:
    place = raw_place.strip()
    if not place:
        raise ValueError("出生地を入力してください。")
    parts = place.split(maxsplit=1)
    prefecture = parts[0]
    city = parts[1] if len(parts) > 1 else ""
    if city:
        resolved = resolve_municipality(prefecture, city)
        if resolved:
            resolved_prefecture, resolved_city, lat, lng = resolved
            return {
                "prefecture": resolved_prefecture,
                "birth_place_label": place,
                "birth_lat": lat,
                "birth_lng": lng,
            }
    resolved_prefecture = prefecture_full_name(prefecture)
    resolve_prefecture(resolved_prefecture)
    return {
        "prefecture": resolved_prefecture,
        "birth_place_label": place,
        "birth_lat": None,
        "birth_lng": None,
    }


def _parse_post_chart_bulk_line(line: str, line_number: int) -> dict[str, str]:
    try:
        fields = next(csv.reader([line]))
    except csv.Error as exc:
        raise ValueError(f"CSV形式が不正です: {exc}") from exc
    if len(fields) < 4:
        raise ValueError("カンマ区切りで 名前,生年月日,出生時間,出生地 を入力してください。")
    if len(fields) > 4:
        raise ValueError("カンマが多すぎます。1行は 名前,生年月日,出生時間,出生地 の4項目です。")
    name, birth_date, birth_time, birth_place = (field.strip() for field in fields)
    if not name:
        raise ValueError("名前を入力してください。")
    try:
        datetime.strptime(birth_date, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("生年月日はYYYY-MM-DDで入力してください。") from exc
    if not birth_time:
        birth_time = "12:00"
    try:
        datetime.strptime(birth_time, "%H:%M")
    except ValueError as exc:
        raise ValueError("出生時間はHH:MMで入力してください。") from exc
    if not birth_place:
        raise ValueError("出生地を入力してください。")
    return {
        "line": line_number,
        "name": name,
        "birth_date": birth_date,
        "birth_time": birth_time,
        "birth_place": birth_place,
    }


def _post_chart_bulk_line_preview(line: str) -> dict[str, str]:
    try:
        fields = next(csv.reader([line]))
    except csv.Error:
        return {}
    if len(fields) < 4:
        return {}
    name, birth_date, birth_time, birth_place = (field.strip() for field in fields[:4])
    return {
        "name": name,
        "birth_date": birth_date,
        "birth_time": birth_time,
        "birth_place": birth_place,
    }


def _build_post_chart_bulk_csv(rows: list[dict]) -> str:
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(["line", "name", "birth_date", "birth_time", "birth_place", "url", "status", "error"])
    for row in rows:
        writer.writerow([
            row.get("line", ""),
            row.get("name", ""),
            row.get("birth_date", ""),
            row.get("birth_time", ""),
            row.get("birth_place", ""),
            row.get("url", ""),
            row.get("status", ""),
            row.get("error", ""),
        ])
    return output.getvalue()


def _issue_post_sample_chart_url(*, request: Request, item: dict[str, str]) -> str:
    place = _resolve_bulk_birth_place(item["birth_place"])
    yaml_text, prompt_text, doc = build_product_yaml(
        title=item["name"],
        birth_date=item["birth_date"],
        birth_time=item["birth_time"],
        prefecture=str(place["prefecture"]),
        birth_place_label=str(place["birth_place_label"]),
        birth_lat=place["birth_lat"],
        birth_lng=place["birth_lng"],
        gender="unknown",
        include_asteroids=False,
        include_shichusuimei=False,
        include_transit=True,
    )
    admin_product_type = "western_full"
    chart_options = {
        **doc.get("product", {}).get("options", {}),
        "product_type": admin_product_type,
        "expires_policy": NO_EXPIRY_CHART_POLICY,
        "url_purpose": "post_sample",
        "bulk_issue": True,
    }
    artifacts = _build_chart_artifacts(yaml_text=yaml_text, doc=doc, product_type=admin_product_type)
    token = secrets.token_urlsafe(18)
    pg_store.save_chart(
        token=token,
        order_code=None,
        buyer_name=item["name"],
        birth_date=item["birth_date"],
        birth_time=item["birth_time"],
        birth_place=item["birth_place"],
        options=chart_options,
        yaml_text=yaml_text,
        prompt_text=prompt_text,
        **artifacts,
        expires_at=None,
    )
    return f"{_public_base_url(request)}/chart/{token}"


@app.get("/admin/post-chart/bulk-new", response_class=HTMLResponse)
def post_chart_bulk_new(request: Request):
    auth_error = _admin_basic_auth_error(request)
    if auth_error:
        return auth_error
    return templates.TemplateResponse(
        "post_chart_bulk_form.html",
        _post_chart_bulk_context(request),
    )


@app.post("/admin/post-chart/bulk-new", response_class=HTMLResponse)
def post_chart_bulk_generate(
    request: Request,
    bulk_input: str = Form(""),
):
    auth_error = _admin_basic_auth_error(request)
    if auth_error:
        return auth_error

    rows: list[dict] = []
    for line_number, raw_line in enumerate(bulk_input.splitlines(), start=1):
        if not raw_line.strip():
            continue
        row = {
            "line": line_number,
            "name": "",
            "birth_date": "",
            "birth_time": "",
            "birth_place": "",
            "url": "",
            "status": "error",
            "error": "",
        }
        try:
            row.update(_post_chart_bulk_line_preview(raw_line))
            item = _parse_post_chart_bulk_line(raw_line, line_number)
            row.update(item)
            row["url"] = _issue_post_sample_chart_url(request=request, item=item)
            row["status"] = "ok"
        except Exception as exc:
            logger.info("post_chart_bulk_row_failed line=%s error_type=%s", line_number, type(exc).__name__)
            row["error"] = str(exc)
        rows.append(row)

    csv_output = _build_post_chart_bulk_csv(rows)
    return templates.TemplateResponse(
        "post_chart_bulk_form.html",
        _post_chart_bulk_context(request, bulk_input=bulk_input, rows=rows, csv_output=csv_output),
    )


MUNDANE_POST_STATUSES = {"draft", "published"}
MUNDANE_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,80}$")
MUNDANE_ADMIN_PREFIX = os.getenv(
    "MUNDANE_ADMIN_PREFIX",
    "/admin/7d4c2f8b91a64e0d/mundane",
).rstrip("/")


def _render_simple_markdown(markdown_text: str | None) -> Markup:
    raw = (markdown_text or "").strip()
    if not raw:
        return Markup("")

    blocks: list[str] = []
    paragraph: list[str] = []
    list_items: list[str] = []

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            blocks.append(f"<p>{'<br>'.join(html_escape(line) for line in paragraph)}</p>")
            paragraph = []

    def flush_list() -> None:
        nonlocal list_items
        if list_items:
            blocks.append("<ul>" + "".join(f"<li>{item}</li>" for item in list_items) + "</ul>")
            list_items = []

    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            flush_paragraph()
            flush_list()
            continue
        if stripped.startswith("### "):
            flush_paragraph()
            flush_list()
            blocks.append(f"<h3>{html_escape(stripped[4:].strip())}</h3>")
            continue
        if stripped.startswith("## "):
            flush_paragraph()
            flush_list()
            blocks.append(f"<h2>{html_escape(stripped[3:].strip())}</h2>")
            continue
        if stripped.startswith("# "):
            flush_paragraph()
            flush_list()
            blocks.append(f"<h2>{html_escape(stripped[2:].strip())}</h2>")
            continue
        if stripped.startswith(("- ", "* ")):
            flush_paragraph()
            list_items.append(html_escape(stripped[2:].strip()))
            continue
        flush_list()
        paragraph.append(stripped)

    flush_paragraph()
    flush_list()
    return Markup("\n".join(blocks))


def _format_datetime_local(value) -> str:
    if not value:
        return ""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value[:16]
    if isinstance(value, datetime):
        if value.tzinfo:
            value = value.astimezone(ZoneInfo("Asia/Tokyo"))
        return value.strftime("%Y-%m-%dT%H:%M")
    return ""


def _parse_mundane_published_at(value: str) -> datetime | None:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError("公開日時の形式が不正です。") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo("Asia/Tokyo"))
    return parsed


def _parse_mundane_form(
    *,
    title: str,
    slug: str,
    target_year: int,
    target_month: int,
    summary: str,
    yaml_content: str,
    body_markdown: str,
    status: str,
    published_at: str,
) -> dict:
    clean_slug = slug.strip().lower()
    clean_status = status.strip().lower() or "draft"
    clean_yaml = yaml_content.strip()
    if not title.strip():
        raise ValueError("titleを入力してください。")
    if not MUNDANE_SLUG_RE.fullmatch(clean_slug):
        raise ValueError("slugは半角小文字英数字とハイフンで入力してください。例: 2026-07")
    if not (1 <= int(target_month) <= 12):
        raise ValueError("target_monthは1〜12で入力してください。")
    if not (1900 <= int(target_year) <= 2100):
        raise ValueError("target_yearは1900〜2100で入力してください。")
    if clean_status not in MUNDANE_POST_STATUSES:
        raise ValueError("statusはdraftまたはpublishedを選んでください。")
    if not clean_yaml:
        raise ValueError("yaml_contentを入力してください。")
    try:
        yaml.safe_load(clean_yaml)
    except yaml.YAMLError as exc:
        raise ValueError(f"YAMLの形式が不正です: {exc}") from exc
    return {
        "title": title.strip(),
        "slug": clean_slug,
        "target_year": int(target_year),
        "target_month": int(target_month),
        "summary": summary.strip() or None,
        "yaml_content": clean_yaml,
        "body_markdown": body_markdown.strip() or None,
        "status": clean_status,
        "published_at": _parse_mundane_published_at(published_at),
    }


def _mundane_form_context(
    request: Request,
    *,
    form: dict | None = None,
    post: dict | None = None,
    error: str | None = None,
    saved: bool = False,
) -> dict:
    base_url = _public_base_url(request)
    now = datetime.now(ZoneInfo("Asia/Tokyo"))
    is_edit = bool(post and post.get("id"))
    if form is None and post:
        form = {
            **post,
            "published_at": _format_datetime_local(post.get("published_at")),
        }
    if form is None:
        form = {
            "title": "",
            "slug": now.strftime("%Y-%m"),
            "target_year": now.year,
            "target_month": now.month,
            "summary": "",
            "yaml_content": "",
            "body_markdown": "",
            "status": "draft",
            "published_at": _format_datetime_local(now),
        }
    public_url = f"{base_url}/mundane/{form.get('slug')}" if form.get("slug") else ""
    edit_url = f"{MUNDANE_ADMIN_PREFIX}/{post['id']}/edit" if is_edit else ""
    return {
        "request": request,
        "form": form,
        "post": post,
        "is_edit": is_edit,
        "error": error,
        "saved": saved,
        "public_url": public_url,
        "admin_mundane_new_url": f"{MUNDANE_ADMIN_PREFIX}/new",
        "admin_mundane_create_url": MUNDANE_ADMIN_PREFIX,
        "admin_mundane_generate_url": f"{MUNDANE_ADMIN_PREFIX}/generate-yaml",
        "admin_mundane_edit_url": edit_url,
        "form_action": edit_url if is_edit else MUNDANE_ADMIN_PREFIX,
        "submit_label": "更新する" if is_edit else "作成する",
        "saved_label": "更新しました。" if is_edit else "保存しました。",
        "statuses": ("draft", "published"),
    }


@app.get(f"{MUNDANE_ADMIN_PREFIX}/new", response_class=HTMLResponse)
def mundane_new(request: Request):
    return templates.TemplateResponse(
        "mundane_form.html",
        _mundane_form_context(request),
    )


@app.post(MUNDANE_ADMIN_PREFIX, response_class=HTMLResponse)
def mundane_create(
    request: Request,
    title: str = Form(""),
    slug: str = Form(""),
    target_year: int = Form(...),
    target_month: int = Form(...),
    summary: str = Form(""),
    yaml_content: str = Form(""),
    body_markdown: str = Form(""),
    status: str = Form("draft"),
    published_at: str = Form(""),
):
    logger.info("mundane_post_create_endpoint method=POST path=%s action=insert", request.url.path)
    try:
        values = _parse_mundane_form(
            title=title,
            slug=slug,
            target_year=target_year,
            target_month=target_month,
            summary=summary,
            yaml_content=yaml_content,
            body_markdown=body_markdown,
            status=status,
            published_at=published_at,
        )
        post = pg_store.create_mundane_post(**values)
    except Exception as exc:
        logger.exception("mundane_post_create_failed error=%r", exc)
        form = {
            "title": title,
            "slug": slug,
            "target_year": target_year,
            "target_month": target_month,
            "summary": summary,
            "yaml_content": yaml_content,
            "body_markdown": body_markdown,
            "status": status,
            "published_at": published_at,
        }
        return templates.TemplateResponse(
            "mundane_form.html",
            _mundane_form_context(request, form=form, error=str(exc)),
            status_code=400,
        )
    return RedirectResponse(f"{MUNDANE_ADMIN_PREFIX}/{post['id']}/edit?saved=1", status_code=303)


@app.post(f"{MUNDANE_ADMIN_PREFIX}/generate-yaml")
def mundane_generate_yaml(payload: dict[str, object] = Body(...)):
    try:
        title = str(payload.get("title") or "").strip()
        slug = str(payload.get("slug") or "").strip().lower()
        target_year = int(payload.get("target_year") or 0)
        target_month = int(payload.get("target_month") or 0)
        if not title:
            raise ValueError("titleを入力してください。")
        if not MUNDANE_SLUG_RE.fullmatch(slug):
            raise ValueError("slugは半角小文字英数字とハイフンで入力してください。例: 2026-07")
        yaml_content = generate_mundane_yaml(
            title=title,
            slug=slug,
            target_year=target_year,
            target_month=target_month,
        )
    except Exception as exc:
        logger.exception("mundane_yaml_generate_failed error=%r", exc)
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
    return {"ok": True, "yaml_content": yaml_content}


@app.get(f"{MUNDANE_ADMIN_PREFIX}/{{post_id}}/edit", response_class=HTMLResponse)
def mundane_edit(request: Request, post_id: str):
    post = pg_store.get_mundane_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="mundane post not found")
    return templates.TemplateResponse(
        "mundane_form.html",
        _mundane_form_context(request, post=post, saved=request.query_params.get("saved") == "1"),
    )


@app.post(f"{MUNDANE_ADMIN_PREFIX}/{{post_id}}/edit", response_class=HTMLResponse)
def mundane_update(
    request: Request,
    post_id: str,
    title: str = Form(""),
    slug: str = Form(""),
    target_year: int = Form(...),
    target_month: int = Form(...),
    summary: str = Form(""),
    yaml_content: str = Form(""),
    body_markdown: str = Form(""),
    status: str = Form("draft"),
    published_at: str = Form(""),
):
    logger.info("mundane_post_update_endpoint method=POST path=%s post_id=%s action=update", request.url.path, post_id)
    try:
        values = _parse_mundane_form(
            title=title,
            slug=slug,
            target_year=target_year,
            target_month=target_month,
            summary=summary,
            yaml_content=yaml_content,
            body_markdown=body_markdown,
            status=status,
            published_at=published_at,
        )
        post = pg_store.update_mundane_post(post_id, **values)
    except Exception as exc:
        logger.exception("mundane_post_update_failed post_id=%s error=%r", post_id, exc)
        form = {
            "id": post_id,
            "title": title,
            "slug": slug,
            "target_year": target_year,
            "target_month": target_month,
            "summary": summary,
            "yaml_content": yaml_content,
            "body_markdown": body_markdown,
            "status": status,
            "published_at": published_at,
        }
        return templates.TemplateResponse(
            "mundane_form.html",
            _mundane_form_context(request, form=form, post=form, error=str(exc)),
            status_code=400,
        )
    if not post:
        raise HTTPException(status_code=404, detail="mundane post not found")
    return RedirectResponse(f"{MUNDANE_ADMIN_PREFIX}/{post_id}/edit?saved=1", status_code=303)


def _load_published_mundane_post_or_404(slug: str) -> dict:
    post = pg_store.get_published_mundane_post_by_slug(slug.strip().lower())
    if not post:
        raise HTTPException(status_code=404, detail="mundane post not found")
    return post


@app.get("/mundane/{slug}/raw", response_class=PlainTextResponse)
def mundane_raw(slug: str):
    post = _load_published_mundane_post_or_404(slug)
    return PlainTextResponse(str(post.get("yaml_content") or ""), media_type="text/plain; charset=utf-8")


@app.get("/mundane/{slug}/chart.svg", response_class=PlainTextResponse)
def mundane_chart_svg(slug: str):
    post = _load_published_mundane_post_or_404(slug)
    svg = build_mundane_chart_svg_from_yaml(str(post.get("yaml_content") or ""))
    if not svg:
        raise HTTPException(status_code=404, detail="mundane chart not found")
    response = PlainTextResponse(svg, media_type="image/svg+xml; charset=utf-8")
    response.headers["Content-Disposition"] = f'inline; filename="mundane-{post["slug"]}-chart.svg"'
    return response


@app.get("/mundane/{slug}", response_class=HTMLResponse)
def mundane_public(request: Request, slug: str):
    post = _load_published_mundane_post_or_404(slug)
    public_url = f"{_public_base_url(request)}/mundane/{post['slug']}"
    yaml_content = str(post.get("yaml_content") or "")
    chart_svg = build_mundane_chart_svg_from_yaml(yaml_content)
    chart_aspects = mundane_aspect_summary_from_yaml(yaml_content)[:18] if chart_svg else []
    return templates.TemplateResponse(
        "mundane_page.html",
        {
            "request": request,
            "post": post,
            "public_url": public_url,
            "chart_svg": chart_svg,
            "chart_aspects": chart_aspects,
            "chart_svg_url": f"{_public_base_url(request)}/mundane/{post['slug']}/chart.svg",
            "body_html": _render_simple_markdown(post.get("body_markdown")),
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
    url_expiry_policy: str = Form(NO_EXPIRY_CHART_POLICY),
):
    auth_error = _admin_basic_auth_error(request)
    if auth_error:
        return auth_error

    if not isinstance(url_expiry_policy, str):
        url_expiry_policy = NO_EXPIRY_CHART_POLICY
    url_expiry_policy = url_expiry_policy if url_expiry_policy == NO_EXPIRY_CHART_POLICY else "standard"
    is_post_sample_url = url_expiry_policy == NO_EXPIRY_CHART_POLICY
    effective_include_transit = bool(include_transit) or is_post_sample_url
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
            include_transit=effective_include_transit,
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
                    "url_expiry_policy": url_expiry_policy,
                },
            },
            status_code=400,
        )

    if include_shichusuimei and not include_asteroids and not effective_include_transit:
        admin_product_type = "shichu"
    elif effective_include_transit or include_asteroids:
        admin_product_type = "western_full"
    else:
        admin_product_type = "western_basic"
    chart_options = {**doc.get("product", {}).get("options", {}), "product_type": admin_product_type}
    if url_expiry_policy == NO_EXPIRY_CHART_POLICY:
        chart_options = {
            **chart_options,
            "expires_policy": NO_EXPIRY_CHART_POLICY,
            "url_purpose": "post_sample",
        }
    artifacts = _build_chart_artifacts(yaml_text=yaml_text, doc=doc, product_type=admin_product_type)
    expires_at = None if url_expiry_policy == NO_EXPIRY_CHART_POLICY else _chart_expires_at()

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
        logger.exception(
            "admin_chart_save_failed error_type=%s error=%r",
            type(e).__name__,
            e,
        )
        return templates.TemplateResponse(
            "yaml_form.html",
            {
                "request": request,
                "prefectures": PREFECTURE_OPTIONS,
                "error": _public_error_message(e, fallback="DB保存に失敗しました。時間をおいて再試行してください。"),
                "form": {
                    "title": title,
                    "birth_date": birth_date,
                    "birth_time": birth_time,
                    "prefecture": prefecture,
                    "gender": gender,
                    "url_expiry_policy": url_expiry_policy,
                },
            },
            status_code=500,
        )
    return RedirectResponse(f"/admin/yaml/result/{token}", status_code=303)


@app.get("/admin/yaml/result/{token}", response_class=HTMLResponse)
def admin_yaml_result(request: Request, token: str):
    auth_error = _admin_basic_auth_error(request)
    if auth_error:
        return auth_error
    chart = _load_chart_or_404(token)
    base_url = _public_base_url(request)
    expires_at = _chart_expiry(chart)
    return templates.TemplateResponse(
        "admin_result.html",
        {
            "request": request,
            "token": token,
            "chart": chart,
            "expires_label": "有効期限なし" if _chart_has_no_expiry(chart) else _chart_expiry_label(expires_at),
            "chart_url": f"{base_url}/chart/{token}",
            "yaml_url": f"{base_url}/chart/{token}.yaml",
            "prompt_url": f"{base_url}/chart/{token}/prompt.txt",
        },
    )


ADDON_FORM_OPTIONS = [
    {"value": "western_asteroids_addon", "label": "小惑星追加"},
    {"value": "western_31days_transit_addon", "label": "38日トランジット追加"},
    {"value": "western_long_term_transits_addon", "label": "長期トランジット（1年）追加"},
]


def _localized_addon_options(lang: str) -> list[dict[str, str]]:
    if lang == "en":
        labels = {
            "western_asteroids_addon": "Asteroid add-on",
            "western_31days_transit_addon": "38-day transit add-on",
            "western_long_term_transits_addon": "Long-term transits add-on (1 year)",
        }
    else:
        labels = {
            "western_asteroids_addon": "小惑星追加",
            "western_31days_transit_addon": "38日トランジット追加",
            "western_long_term_transits_addon": "長期トランジット（1年）追加",
        }
    return [{"value": item["value"], "label": labels.get(item["value"], item["label"])} for item in ADDON_FORM_OPTIONS]


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
    today_jst = datetime.now(ZoneInfo("Asia/Tokyo")).date()
    lang_ctx = _i18n_context(request)
    response = templates.TemplateResponse(
        "addon_form.html",
        {
            "request": request,
            **lang_ctx,
            "addon_options": _localized_addon_options(lang_ctx["lang"]),
            "form": form or {
                "addon_type": "western_asteroids_addon",
                "order_code": "",
                "order_provider": "stores",
                "payhip_email": "",
                "payhip_product_code": "",
                "payhip_order_id": "",
                "base_yaml": "",
                "previous_chart_url": "",
                "transit_start_date": today_jst.isoformat(),
            },
            "result_yaml": result_yaml,
            "transit_result_url": transit_result_url,
            "transit_download_url": transit_download_url,
            "transit_expires_label": transit_expires_label,
            "error": error,
            "addon_form_action": "/addon/generate" if request.url.path.startswith("/addon/") else "/admin/addon/generate",
            "payhip_products": _payhip_product_options(),
            "today_label": today_jst.isoformat(),
            "transit_min_date": _shift_years(today_jst, -5).isoformat(),
            "transit_max_date": _shift_years(today_jst, 5).isoformat(),
        },
        status_code=status_code,
    )
    if error or status_code >= 400:
        return _mark_no_store(response)
    return response


def _addon_initial_form_from_request(request: Request) -> dict[str, str]:
    today_jst = datetime.now(ZoneInfo("Asia/Tokyo")).date().isoformat()
    requested_addon_type = (request.query_params.get("addon_type") or "").strip()
    addon_type = (
        requested_addon_type
        if requested_addon_type in {item["value"] for item in ADDON_FORM_OPTIONS}
        else "western_asteroids_addon"
    )
    previous_chart_url = (request.query_params.get("previous_chart_url") or "").strip()
    return {
        "addon_type": addon_type,
        "order_code": "",
        "order_provider": "stores",
        "payhip_email": "",
        "payhip_product_code": "",
        "payhip_order_id": "",
        "base_yaml": "",
        "previous_chart_url": previous_chart_url,
        "transit_start_date": today_jst,
    }


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

    if addon_type in {"western_asteroids_addon", "western_31days_transit_addon", "western_long_term_transits_addon"}:
        if not isinstance(western, dict) or not isinstance(western.get("natal"), dict):
            raise ValueError("western addon には western の基本版YAMLが必要です。")
        return

    if addon_type == "shichu_fortune_cycles_addon":
        if not isinstance(shichu, dict) or not isinstance(shichu.get("normalized_data"), dict):
            raise ValueError("shichu addon には shichusuimei の基本版YAMLが必要です。")
        return

    raise ValueError("未対応のaddon種別です。")


def _build_addon_yaml_from_base(
    doc: dict,
    addon_type: str,
    *,
    transit_start_date: datetime | None = None,
) -> str:
    _validate_addon_base_doc(doc, addon_type)
    args = _addon_args_from_base_doc(doc)
    if addon_type == "western_asteroids_addon":
        yaml_text, _prompt_text, _addon_doc = build_asteroid_addon_yaml(**args)
        return yaml_text
    if addon_type == "western_31days_transit_addon":
        yaml_text, _prompt_text, _addon_doc = build_31days_transit_addon_yaml(
            **args,
            transit_start_date=transit_start_date,
        )
        return yaml_text

    shichu = ((doc.get("systems") or {}).get("shichusuimei") or {})
    assumptions = ((shichu.get("input") or {}).get("assumptions") or {})
    args["day_change_at_23"] = bool(assumptions.get("day_change_at_23"))
    yaml_text, _prompt_text, _addon_doc = build_shichu_fortune_cycles_addon_yaml(**args)
    return yaml_text


ASTEROID_ADDON_CHART_PROMPT = """あなたは西洋占星術の鑑定者です。以下のYAMLは、出生図に小惑星データを統合した鑑定用データです。

重要ルール:
- systems.western.natal と systems.western.asteroids の両方を根拠にしてください。
- 小惑星位置・ハウス・度数の計算結果は変更しないでください。
- 生年月日から再計算しないでください。
- 小惑星は性格・テーマ・関係性の深掘りとして扱い、出生図全体と統合して読んでください。

以下のYAMLを読み込んで、小惑星込みの出生図鑑定を行ってください。
"""


def _build_asteroid_addon_from_base(doc: dict) -> tuple[str, str, dict, str, str, dict]:
    _validate_addon_base_doc(doc, "western_asteroids_addon")
    args = _addon_args_from_base_doc(doc)
    addon_yaml_text, addon_prompt_text, addon_doc = build_asteroid_addon_yaml(**args)

    chart_doc = copy.deepcopy(doc)
    systems = chart_doc.setdefault("systems", {})
    western = systems.setdefault("western", {})
    western["asteroids"] = (((addon_doc.get("systems") or {}).get("western") or {}).get("asteroids"))
    western["transit"] = None

    product = chart_doc.setdefault("product", {})
    product["type"] = "western_asteroids_addon"
    product["label"] = "ホロスコープ：小惑星追加"
    product_options = product.setdefault("options", {})
    product_options["western_natal"] = True
    product_options["asteroids"] = True
    product_options["transit"] = False
    product_options["shichusuimei"] = False
    product_options["product_type"] = "western_asteroids_addon"

    meta = chart_doc.setdefault("meta", {})
    meta["product_type"] = "western_asteroids_addon"
    meta["data_role"] = "addon"
    meta["addon_type"] = "western_asteroids"
    chart_doc["generated_at"] = addon_doc.get("generated_at") or chart_doc.get("generated_at")

    assets = chart_doc.setdefault("assets", {})
    assets["yaml_natal_asteroids"] = {
        "available": True,
        "file_name": "natal-asteroids.yaml",
    }
    validate_yaml_option_section_consistency(chart_doc)
    chart_yaml_text = yaml.safe_dump(chart_doc, allow_unicode=True, sort_keys=False, width=120)
    chart_prompt_text = ASTEROID_ADDON_CHART_PROMPT.strip() + "\n"
    return addon_yaml_text, addon_prompt_text, addon_doc, chart_yaml_text, chart_prompt_text, chart_doc


def _build_transit_addon_from_base(
    doc: dict,
    *,
    transit_start_date: datetime,
    transit_days: int = 38,
    product_type: str = "western_31days_transit_addon",
    product_label: str | None = None,
    addon_type: str = "western_31days_transit",
    extra_meta: dict[str, object] | None = None,
    extra_options: dict[str, object] | None = None,
    extra_root: dict[str, object] | None = None,
) -> tuple[str, str, dict, str, str, dict]:
    _validate_addon_base_doc(doc, "western_31days_transit_addon")
    args = _addon_args_from_base_doc(doc)
    addon_yaml_text, addon_prompt_text, addon_doc = build_31days_transit_addon_yaml(
        **args,
        transit_start_date=transit_start_date,
        transit_days=transit_days,
    )
    if transit_days != 38:
        addon_prompt_text = addon_prompt_text.replace("38日", f"{transit_days}日")
    addon_meta = addon_doc.setdefault("meta", {})
    addon_meta["product_type"] = product_type
    addon_meta["data_role"] = "addon"
    addon_meta["addon_type"] = addon_type
    addon_meta.update(extra_meta or {})
    addon_product = addon_doc.setdefault("product", {})
    addon_product["type"] = product_type
    if product_label:
        addon_product["label"] = product_label
    addon_options = addon_product.setdefault("options", {})
    addon_options["transit_days"] = transit_days
    addon_options.update(extra_options or {})
    addon_doc.update(copy.deepcopy(extra_root or {}))
    addon_yaml_text = yaml.safe_dump(addon_doc, allow_unicode=True, sort_keys=False, width=120)

    has_asteroids = _doc_has_western_asteroids(doc)
    _generated_yaml_text, chart_prompt_text, _generated_doc = build_product_yaml(
        **args,
        include_asteroids=has_asteroids,
        include_shichusuimei=False,
        include_transit=True,
        transit_start_date=transit_start_date,
        transit_days=transit_days,
    )
    if transit_days != 31:
        chart_prompt_text = chart_prompt_text.replace("31日", f"{transit_days}日")
    chart_doc = copy.deepcopy(doc)
    systems = chart_doc.setdefault("systems", {})
    western = systems.setdefault("western", {})
    western["transit"] = (((addon_doc.get("systems") or {}).get("western") or {}).get("transit"))
    product = chart_doc.setdefault("product", {})
    product["type"] = product_type
    if product_label:
        product["label"] = product_label
    product_options = product.setdefault("options", {})
    product_options["transit"] = True
    product_options["transit_days"] = transit_days
    product_options["product_type"] = product_type
    product_options.update(extra_options or {})
    if "western_natal" not in product_options:
        product_options["western_natal"] = True
    product_options["asteroids"] = has_asteroids
    meta = chart_doc.setdefault("meta", {})
    meta["product_type"] = product_type
    meta["data_role"] = "addon"
    meta["addon_type"] = addon_type
    meta.update(extra_meta or {})
    chart_doc.update(copy.deepcopy(extra_root or {}))
    chart_doc["generated_at"] = addon_doc.get("generated_at") or chart_doc.get("generated_at")
    validate_yaml_option_section_consistency(addon_doc)
    validate_yaml_option_section_consistency(chart_doc)
    chart_yaml_text = yaml.safe_dump(chart_doc, allow_unicode=True, sort_keys=False, width=120)
    return addon_yaml_text, addon_prompt_text, addon_doc, chart_yaml_text, chart_prompt_text, chart_doc


LONG_TERM_TRANSITS_ADDON_CHART_PROMPT = """あなたは西洋占星術の鑑定者です。以下のYAMLは、出生図の最低限情報と年単位の長期トランジットをまとめた追加鑑定用データです。

重要ルール:
- このYAML内の出生図データと長期トランジットだけを根拠にしてください。
- 生年月日から天体位置を再計算しないでください。
- 38日トランジット、今日の運勢、短期的な日別予報として扱わないでください。
- Saturn / Uranus / Neptune / Pluto / Jupiter などの長期的な流れを中心に、今後1年のテーマを読んでください。
- systems.western.transit_long_term.samples は約7日間隔の観測点です。日別予報ではなく、主要天体のサイン・逆行・ネイタルとのアスペクトの推移として読んでください。
- Chiron / North Node / South Node は補助情報として扱い、主要5天体より優先しないでください。
- 断定しすぎず、長期テーマ・変化の方向性・活かし方として解釈してください。

以下のYAMLを読み込んで、年単位の長期トランジット鑑定を行ってください。
"""


def _build_long_term_transits_addon_from_base(
    doc: dict,
    *,
    transit_start_date: datetime,
) -> tuple[str, str, dict, str, str, dict]:
    _validate_addon_base_doc(doc, "western_long_term_transits_addon")
    args = _addon_args_from_base_doc(doc)
    _full_yaml_text, _prompt_text, full_doc = build_product_yaml(
        **args,
        include_asteroids=False,
        include_shichusuimei=False,
        include_transit=True,
        transit_days=365,
        transit_profile="long_term",
        transit_start_date=transit_start_date,
    )
    generated_western = ((full_doc.get("systems") or {}).get("western") or {})
    generated_western["transit_long_term"] = generated_western.get("transit")
    generated_western["transit"] = None
    product_options = ((full_doc.get("product") or {}).get("options") or {})
    product_options["transit"] = False
    product_options["western_long_term_transits"] = True
    addon_yaml_text = build_long_term_transits_yaml(doc=full_doc)
    if not addon_yaml_text:
        raise ValueError("長期トランジットAddon YAMLを生成できませんでした。出生図データを確認してください。")
    addon_doc = yaml.safe_load(addon_yaml_text) or {}

    chart_doc = copy.deepcopy(doc)
    systems = chart_doc.setdefault("systems", {})
    western = systems.setdefault("western", {})
    western["transit_long_term"] = (((addon_doc.get("systems") or {}).get("western") or {}).get("transit_long_term"))

    product = chart_doc.setdefault("product", {})
    product["type"] = "western_long_term_transits_addon"
    product["label"] = "ホロスコープ：長期トランジット追加"
    product_options = product.setdefault("options", {})
    existing_transit = western.get("transit")
    product_options["western_natal"] = True
    product_options["transit"] = bool(existing_transit)
    product_options["western_long_term_transits"] = True
    product_options["product_type"] = "western_long_term_transits_addon"

    meta = chart_doc.setdefault("meta", {})
    meta["product_type"] = "western_long_term_transits_addon"
    meta["data_role"] = "addon"
    meta["addon_type"] = "western_long_term_transits"
    chart_doc["generated_at"] = addon_doc.get("generated_at") or chart_doc.get("generated_at")

    assets = chart_doc.setdefault("assets", {})
    assets["yaml_long_term_transits"] = {
        "available": True,
        "file_name": "long-term-transits.yaml",
        "merge_path": "systems.western.transit_long_term",
    }

    validate_yaml_option_section_consistency(chart_doc)
    chart_yaml_text = yaml.safe_dump(chart_doc, allow_unicode=True, sort_keys=False, width=120)
    chart_prompt_text = LONG_TERM_TRANSITS_ADDON_CHART_PROMPT.strip() + "\n"
    return addon_yaml_text, chart_prompt_text, addon_doc, chart_yaml_text, chart_prompt_text, chart_doc


def _transit_addon_chart_payload(
    *,
    yaml_text: str,
    prompt_text: str,
    chart_doc: dict,
) -> dict[str, object]:
    input_block = chart_doc.get("input") or {}
    try:
        share_yaml_text = build_light_astrology_yaml(yaml_text, doc=chart_doc)
    except Exception:
        share_yaml_text = yaml_text
    try:
        horoscope_svg = optimize_svg(build_horoscope_svg_from_yaml(yaml_text, doc=chart_doc))
    except Exception:
        horoscope_svg = None
    return {
        "buyer_name": str(input_block.get("title") or "").strip() or None,
        "birth_date": str(input_block.get("birth_date") or "").strip(),
        "birth_time": str(input_block.get("birth_time") or input_block.get("calculation_time") or "").strip() or None,
        "birth_place": str(input_block.get("birth_place") or input_block.get("prefecture") or "").strip() or None,
        "options": {
            **(chart_doc.get("product", {}).get("options", {}) or {}),
            "product_type": (
                ((chart_doc.get("product") or {}).get("options") or {}).get("product_type")
                or "western_31days_transit_addon"
            ),
        },
        "yaml_text": yaml_text,
        "prompt_text": prompt_text,
        "share_yaml_text": share_yaml_text,
        "horoscope_svg": horoscope_svg,
        "shichusuimei_svg": None,
    }


def _asteroid_addon_chart_payload(
    *,
    yaml_text: str,
    prompt_text: str,
    chart_doc: dict,
) -> dict[str, object]:
    input_block = chart_doc.get("input") or {}
    try:
        share_yaml_text = build_natal_asteroids_yaml(yaml_text)
    except Exception:
        try:
            share_yaml_text = build_detail_astrology_yaml(yaml_text)
        except Exception:
            share_yaml_text = yaml_text
    try:
        horoscope_svg = optimize_svg(build_horoscope_svg_from_yaml(yaml_text, doc=chart_doc))
    except Exception:
        horoscope_svg = None
    return {
        "buyer_name": str(input_block.get("title") or "").strip() or None,
        "birth_date": str(input_block.get("birth_date") or "").strip(),
        "birth_time": str(input_block.get("birth_time") or input_block.get("calculation_time") or "").strip() or None,
        "birth_place": str(input_block.get("birth_place") or input_block.get("prefecture") or "").strip() or None,
        "options": {**(chart_doc.get("product", {}).get("options", {}) or {}), "product_type": "western_asteroids_addon"},
        "yaml_text": yaml_text,
        "prompt_text": prompt_text,
        "share_yaml_text": share_yaml_text,
        "horoscope_svg": horoscope_svg,
        "shichusuimei_svg": None,
    }


def _long_term_transits_addon_chart_payload(
    *,
    yaml_text: str,
    prompt_text: str,
    chart_doc: dict,
) -> dict[str, object]:
    input_block = chart_doc.get("input") or {}
    try:
        share_yaml_text = build_light_astrology_yaml(
            yaml_text,
            doc=chart_doc,
            include_asteroids=_doc_has_western_asteroids(chart_doc),
        )
    except Exception:
        share_yaml_text = yaml_text
    try:
        horoscope_svg = optimize_svg(build_horoscope_svg_from_yaml(yaml_text, doc=chart_doc))
    except Exception:
        horoscope_svg = None
    return {
        "buyer_name": str(input_block.get("title") or "").strip() or None,
        "birth_date": str(input_block.get("birth_date") or "").strip(),
        "birth_time": str(input_block.get("birth_time") or input_block.get("calculation_time") or "").strip() or None,
        "birth_place": str(input_block.get("birth_place") or input_block.get("prefecture") or "").strip() or None,
        "options": {**(chart_doc.get("product", {}).get("options", {}) or {}), "product_type": "western_long_term_transits_addon"},
        "yaml_text": yaml_text,
        "prompt_text": prompt_text,
        "share_yaml_text": share_yaml_text,
        "horoscope_svg": horoscope_svg,
        "shichusuimei_svg": None,
    }


def _doc_has_western_asteroids(doc: dict) -> bool:
    western = ((doc.get("systems") or {}).get("western") or {})
    asteroids = western.get("asteroids") or {}
    return isinstance(asteroids, dict) and bool(asteroids)


def _shift_years(value: date, years: int) -> date:
    try:
        return value.replace(year=value.year + years)
    except ValueError:
        # うるう年の 2/29 は、対象年に存在しない場合だけ 2/28 に寄せる。
        return value.replace(month=2, day=28, year=value.year + years)


def _parse_transit_start_date(value: str) -> datetime:
    raw = (value or "").strip()
    if not raw:
        raise ValueError("開始日を入力してください。現在日から前後5年以内の日付を指定できます。")
    try:
        selected = date.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError("開始日の形式が不正です。YYYY-MM-DD で入力してください。") from exc

    today_jst = datetime.now(ZoneInfo("Asia/Tokyo")).date()
    min_date = _shift_years(today_jst, -5)
    max_date = _shift_years(today_jst, 5)
    if not (min_date <= selected <= max_date):
        raise ValueError(
            f"開始日は現在日から前後5年以内で指定してください。"
            f"{min_date.isoformat()}〜{max_date.isoformat()} の範囲で選び直してください。"
        )
    return datetime(selected.year, selected.month, selected.day, tzinfo=ZoneInfo("Asia/Tokyo"))


def _load_addon_base_doc_from_previous_chart_url(previous_chart_url: str, addon_type: str = "western_31days_transit_addon") -> dict:
    raw_url = (previous_chart_url or "").strip()
    try:
        parsed = urlparse(raw_url)
    except ValueError as exc:
        raise ValueError("前回鑑定URLを読み取れません。鑑定結果ページのURLをそのまま貼り付けてください。") from exc

    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("前回鑑定URLが不正です。https:// から始まる鑑定結果ページのURLを貼り付けてください。")

    token_match = re.fullmatch(r"/chart/([A-Za-z0-9_-]{20,120})(?:\\.yaml)?/?", parsed.path or "")
    if not token_match:
        raise ValueError("前回鑑定URLが不正です。鑑定結果ページのURLをそのまま貼り付けてください。")

    token = token_match.group(1)
    chart = pg_store.get_chart(token, include_svgs=False)
    if not chart:
        raise ValueError("前回鑑定URLが見つかりません。90日以内の有効な鑑定結果URLを入力してください。")

    expires_at = _chart_expiry(chart)
    if expires_at and datetime.now(timezone.utc) >= expires_at:
        raise ValueError("前回鑑定URLの有効期限が切れています。基本版YAMLを貼り付けるか、90日以内の鑑定結果URLを入力してください。")

    doc = _load_addon_base_yaml(str(chart.get("yaml_text") or ""))
    try:
        _validate_addon_base_doc(doc, addon_type)
    except ValueError as exc:
        raise ValueError("このURLにはaddonに使えるネイタル情報がありません。基本版ホロスコープのYAMLまたはURLを入力してください。") from exc
    return doc


class NoteTransitRequestError(ValueError):
    def __init__(self, message: str, *, code: str, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


def _require_note_transit_campaign(access_key: str) -> NoteTransitCampaign:
    campaign = get_note_transit_campaign_by_access_key(access_key)
    if campaign is None:
        raise NoteTransitRequestError(
            "このURLは利用できません。noteに記載されたURLを確認してください。",
            code="campaign_not_found",
            status_code=404,
        )
    if not campaign.enabled:
        raise NoteTransitRequestError(
            "このキャンペーンは現在利用できません。",
            code="campaign_disabled",
            status_code=403,
        )
    return campaign


def _load_note_transit_source_doc(data_url: str) -> dict:
    raw_url = (data_url or "").strip()
    if not raw_url:
        raise NoteTransitRequestError("データURLを入力してください。", code="url_required")
    try:
        parsed = urlparse(raw_url)
    except ValueError as exc:
        raise NoteTransitRequestError("URL形式が不正です。", code="invalid_url") from exc
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise NoteTransitRequestError(
            "URL形式が不正です。http:// または https:// から始まるURLを入力してください。",
            code="invalid_url",
        )

    token_match = re.fullmatch(r"/chart/([A-Za-z0-9_-]{20,120})(?:\.yaml)?/?", parsed.path or "")
    if not token_match:
        raise NoteTransitRequestError(
            "対応していないURLです。基本版またはFULL版の鑑定データURLを入力してください。",
            code="unsupported_url",
        )

    try:
        chart = pg_store.get_chart(token_match.group(1), include_svgs=False)
    except Exception as exc:
        logger.exception("note_transit_source_load_failed url=%s error=%r", raw_url, exc)
        raise NoteTransitRequestError(
            "データ取得に失敗しました。時間をおいて再度お試しください。",
            code="data_fetch_failed",
            status_code=502,
        ) from exc
    if not chart:
        raise NoteTransitRequestError(
            "データを取得できませんでした。URLが正しいか確認してください。",
            code="data_fetch_failed",
            status_code=404,
        )
    chart_options = chart.get("options") or {}
    chart_product_type = chart_options.get("product_type") if isinstance(chart_options, dict) else None
    if chart_product_type and chart_product_type not in {"western_basic", "western_full"}:
        raise NoteTransitRequestError(
            "対応していないURLです。基本版またはFULL版の鑑定データURLを入力してください。",
            code="unsupported_url",
        )

    expires_at = _chart_expiry(chart)
    if expires_at and datetime.now(timezone.utc) >= expires_at:
        raise NoteTransitRequestError(
            "このデータURLの有効期限は終了しています。",
            code="data_fetch_failed",
            status_code=410,
        )
    try:
        doc = _load_addon_base_yaml(str(chart.get("yaml_text") or ""))
        _validate_addon_base_doc(doc, "western_31days_transit_addon")
    except ValueError as exc:
        raise NoteTransitRequestError(
            "対応していないURLです。基本版またはFULL版の鑑定データURLを入力してください。",
            code="unsupported_url",
        ) from exc
    return doc


def _load_note_transit_source_yaml(base_yaml: str) -> dict:
    raw_yaml = (base_yaml or "").strip()
    if not raw_yaml:
        raise NoteTransitRequestError(
            "データURLまたはYAMLを入力してください。",
            code="source_required",
        )
    try:
        doc = _load_addon_base_yaml(raw_yaml)
        _validate_addon_base_doc(doc, "western_31days_transit_addon")
    except ValueError as exc:
        raise NoteTransitRequestError(
            f"YAMLを確認してください。{exc}",
            code="invalid_yaml",
        ) from exc

    product = doc.get("product") or {}
    options = product.get("options") or {}
    product_type = options.get("product_type") if isinstance(options, dict) else None
    if product_type and product_type not in {"western_basic", "western_full"}:
        raise NoteTransitRequestError(
            "対応していないYAMLです。基本版またはFULL版のYAMLを貼り付けてください。",
            code="unsupported_yaml",
        )
    return doc


def _resolve_note_transit_source(data_url: str, base_yaml: str) -> tuple[dict, str, str | None]:
    if (data_url or "").strip():
        warning = "URLとYAMLの両方が入力されたため、URLを優先しました。" if (base_yaml or "").strip() else None
        return _load_note_transit_source_doc(data_url), "url", warning
    if (base_yaml or "").strip():
        return _load_note_transit_source_yaml(base_yaml), "yaml", None
    raise NoteTransitRequestError(
        "データURLまたはYAMLを入力してください。",
        code="source_required",
    )


def _save_note_transit_result(
    addon_yaml_text: str,
    *,
    chart_payload: dict[str, object],
) -> tuple[str, datetime]:
    if not os.environ.get("DATABASE_URL"):
        raise NoteTransitRequestError(
            "発行データの保存設定がありません。管理者に連絡してください。",
            code="save_unavailable",
            status_code=503,
        )
    last_exc: Exception | None = None
    for _ in range(3):
        token = secrets.token_urlsafe(24)
        expires_at = _chart_expires_at()
        try:
            pg_store.save_transit_addon_link_and_chart(
                token=token,
                yaml_text=addon_yaml_text,
                expires_at=expires_at,
                chart_payload=chart_payload,
            )
            return token, expires_at
        except Exception as exc:
            last_exc = exc
            logger.warning(
                "note_transit_save_failed token_prefix=%s error_type=%s error=%r",
                token[:8],
                type(exc).__name__,
                exc,
                exc_info=True,
            )
            time.sleep(0.15)
    raise NoteTransitRequestError(
        _public_error_message(
            last_exc or RuntimeError("note transit save failed"),
            fallback="発行データの保存に失敗しました。時間をおいて再度お試しください。",
        ),
        code="save_failed",
        status_code=500,
    )


@app.get("/note-transit/{access_key}", response_class=HTMLResponse)
def note_transit_page(request: Request, access_key: str):
    try:
        campaign = _require_note_transit_campaign(access_key)
    except NoteTransitRequestError as exc:
        return templates.TemplateResponse(
            "note_transit.html",
            {
                "request": request,
                "campaign": None,
                "target_month": "",
                "api_url": "",
                "unavailable_error": str(exc),
            },
            status_code=exc.status_code,
        )
    return templates.TemplateResponse(
        "note_transit.html",
        {
            "request": request,
            "campaign": campaign,
            "target_month": campaign.target_month,
            "api_url": f"/api/note-transit/{access_key}",
            "unavailable_error": None,
        },
    )


@app.post("/api/note-transit/{access_key}", response_class=JSONResponse)
def note_transit_generate(request: Request, access_key: str, payload: dict = Body(default={})):
    try:
        campaign = _require_note_transit_campaign(access_key)
        source_doc, source_type, warning = _resolve_note_transit_source(
            str(payload.get("data_url") or ""),
            str(payload.get("base_yaml") or ""),
        )
        start_dt = datetime(
            campaign.start_date.year,
            campaign.start_date.month,
            campaign.start_date.day,
            tzinfo=ZoneInfo(str(((source_doc.get("input") or {}).get("timezone") or "Asia/Tokyo"))),
        )
        campaign_data = {
            "id": campaign.campaign_id,
            "label": campaign.label,
            "target_month": campaign.target_month,
            "start_date": campaign.start_date.isoformat(),
            "end_date": campaign.end_date.isoformat(),
        }
        (
            result_yaml,
            _addon_prompt_text,
            _addon_doc,
            chart_yaml_text,
            chart_prompt_text,
            chart_doc,
        ) = _build_transit_addon_from_base(
            source_doc,
            transit_start_date=start_dt,
            transit_days=campaign.days,
            extra_meta={
                "campaign_id": campaign.campaign_id,
                "target_month": campaign.target_month,
            },
            extra_options={
                "campaign_id": campaign.campaign_id,
                "target_month": campaign.target_month,
            },
            extra_root={"campaign": campaign_data},
        )
        chart_payload = _transit_addon_chart_payload(
            yaml_text=chart_yaml_text,
            prompt_text=chart_prompt_text,
            chart_doc=chart_doc,
        )
        chart_payload["options"] = {
            **dict(chart_payload["options"]),
            "order_provider": "note",
            "order_strict_check": False,
        }
        token, expires_at = _save_note_transit_result(
            result_yaml,
            chart_payload=chart_payload,
        )
    except NoteTransitRequestError as exc:
        return JSONResponse(
            {"ok": False, "error": str(exc), "code": exc.code},
            status_code=exc.status_code,
        )
    except Exception as exc:
        logger.exception(
            "note_transit_generation_failed campaign_id=%s error=%r",
            campaign.campaign_id,
            exc,
        )
        return JSONResponse(
            {
                "ok": False,
                "error": "トランジット生成に失敗しました。時間をおいて再度お試しください。",
                "code": "generation_failed",
            },
            status_code=500,
        )
    base_url = _public_base_url(request)
    return JSONResponse(
        {
            "ok": True,
            "campaign_id": campaign.campaign_id,
            "target_month": campaign.target_month,
            "start_date": campaign.start_date.isoformat(),
            "end_date": campaign.end_date.isoformat(),
            "result_url": f"{base_url}/chart/{token}",
            "download_url": f"{base_url}/chart/{token}/transit.yaml",
            "expires_at": expires_at.isoformat(),
            "expires_label": _chart_expiry_label(expires_at),
            "source_type": source_type,
            "warning": warning,
            "yaml": result_yaml,
        }
    )


def _transit_addon_expires_at() -> datetime:
    # 38日トランジット addon も /chart/{token} の鑑定データページとして扱うため、
    # 基本版・FULL版と同じ公開寿命にそろえる。
    return _chart_expires_at()


def _redeem_and_save_transit_addon_or_raise(
    order_code: str,
    order_provider: str,
    addon_type: str,
    yaml_text: str,
    *,
    chart_payload: dict[str, object] | None = None,
    payhip_metadata: dict[str, str] | None = None,
) -> tuple[str, datetime]:
    if not os.environ.get("DATABASE_URL"):
        raise ValueError("注文番号照合用のDATABASE_URLが未設定です。管理者に連絡してください。")
    order_code_clean = _normalize_stores_order_no(order_code)
    if not order_code_clean:
        raise ValueError("注文番号を入力してください。")
    if not _is_valid_order_code(order_code_clean):
        raise ValueError("注文番号には英数字、ハイフン、アンダースコア、イコールのみ使用できます。")
    order_provider_clean = _resolve_order_provider(order_code_clean, order_provider)
    policy = _get_order_check_policy(order_provider_clean)
    if order_provider_clean not in ORDER_PROVIDERS:
        _log_order_check(
            provider=order_provider_clean,
            order_id=order_code_clean,
            strict_check=bool(policy["strict"]),
            check_result="provider_unknown",
            reason="provider could not be resolved",
        )
        raise ValueError(f"注文番号（{order_code_clean}）を確認できません。購入確認メールに記載の番号を確認してください。")
    if order_provider_clean == "gumroad":
        _log_order_check(
            provider=order_provider_clean,
            order_id=order_code_clean,
            strict_check=True,
            check_result="unsupported",
            reason="gumroad product tags are only mapped for western_basic/western_full",
        )
        raise ValueError("Gumroad注文はこの追加商品では使用できません。対応商品タグを確認してください。")

    last_exc: Exception | None = None
    for _ in range(3):
        token = secrets.token_urlsafe(24)
        expires_at = _transit_addon_expires_at()
        try:
            if policy["strict"]:
                status, order_row = pg_store.redeem_addon_order_and_save_transit_link(
                    order_code=order_code_clean,
                    addon_type=addon_type,
                    token=token,
                    yaml_text=yaml_text,
                    expires_at=expires_at,
                    chart_payload=chart_payload,
                )
                if status == "not_found" and _truthy(os.getenv("STORES_MAIL_SYNC_ON_SUBMIT", "1")):
                    _sync_stores_orders_for_lookup()
                    status, order_row = pg_store.redeem_addon_order_and_save_transit_link(
                        order_code=order_code_clean,
                        addon_type=addon_type,
                        token=token,
                        yaml_text=yaml_text,
                        expires_at=expires_at,
                        chart_payload=chart_payload,
                    )
            else:
                status, order_row = pg_store.redeem_addon_order_and_save_transit_link_relaxed(
                    order_code=order_code_clean,
                    addon_type=addon_type,
                    token=token,
                    yaml_text=yaml_text,
                    expires_at=expires_at,
                    chart_payload=chart_payload,
                    provider=order_provider_clean or "gumroad",
                    metadata=payhip_metadata if order_provider_clean == "payhip" else None,
                )
        except Exception as exc:
            last_exc = exc
            logger.warning(
                "transit_addon_save_transient_error order_id=%s addon_type=%s error_type=%s error=%r",
                order_code_clean,
                addon_type,
                type(exc).__name__,
                exc,
                exc_info=True,
            )
            time.sleep(0.15)
            continue

        _log_order_check(
            provider=order_provider_clean,
            order_id=order_code_clean,
            strict_check=bool(policy["strict"]),
            check_result=status,
            reason="stores strict check" if policy["strict"] else f"{_provider_label(order_provider_clean)} relaxed check",
        )

        if status == "ok":
            return token, expires_at
        if status == "not_found":
            raise ValueError(f"注文番号（{order_code_clean}）が見つかりません。購入確認メールに記載の番号を確認してください。")
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

    if last_exc:
        raise ValueError(_public_error_message(last_exc, fallback="トランジットデータの一時保存に失敗しました。時間をおいて再試行してください。")) from last_exc
    raise ValueError("トランジットデータの一時保存に失敗しました。時間をおいて再試行してください。")


def _redeem_and_save_chart_addon_or_raise(
    order_code: str,
    order_provider: str,
    addon_type: str,
    *,
    chart_payload: dict[str, object],
    payhip_metadata: dict[str, str] | None = None,
) -> tuple[str, datetime]:
    if not os.environ.get("DATABASE_URL"):
        raise ValueError("注文番号照合用のDATABASE_URLが未設定です。管理者に連絡してください。")
    order_code_clean = _normalize_stores_order_no(order_code)
    if not order_code_clean:
        raise ValueError("注文番号を入力してください。")
    if not _is_valid_order_code(order_code_clean):
        raise ValueError("注文番号には英数字、ハイフン、アンダースコア、イコールのみ使用できます。")
    order_provider_clean = _resolve_order_provider(order_code_clean, order_provider)
    policy = _get_order_check_policy(order_provider_clean)
    if order_provider_clean not in ORDER_PROVIDERS:
        _log_order_check(
            provider=order_provider_clean,
            order_id=order_code_clean,
            strict_check=bool(policy["strict"]),
            check_result="provider_unknown",
            reason="provider could not be resolved",
        )
        raise ValueError(f"注文番号（{order_code_clean}）を確認できません。購入確認メールに記載の番号を確認してください。")
    if order_provider_clean == "gumroad":
        _log_order_check(
            provider=order_provider_clean,
            order_id=order_code_clean,
            strict_check=True,
            check_result="unsupported",
            reason="gumroad product tags are only mapped for western_basic/western_full",
        )
        raise ValueError("Gumroad注文はこの追加商品では使用できません。対応商品タグを確認してください。")

    last_exc: Exception | None = None
    for _ in range(3):
        token = secrets.token_urlsafe(24)
        expires_at = _chart_expires_at()
        try:
            if policy["strict"]:
                status, order_row = pg_store.redeem_addon_order_and_save_chart(
                    order_code=order_code_clean,
                    addon_type=addon_type,
                    token=token,
                    expires_at=expires_at,
                    chart_payload=chart_payload,
                )
                if status == "not_found" and _truthy(os.getenv("STORES_MAIL_SYNC_ON_SUBMIT", "1")):
                    _sync_stores_orders_for_lookup()
                    status, order_row = pg_store.redeem_addon_order_and_save_chart(
                        order_code=order_code_clean,
                        addon_type=addon_type,
                        token=token,
                        expires_at=expires_at,
                        chart_payload=chart_payload,
                    )
            else:
                status, order_row = pg_store.redeem_addon_order_and_save_chart_relaxed(
                    order_code=order_code_clean,
                    addon_type=addon_type,
                    token=token,
                    expires_at=expires_at,
                    chart_payload=chart_payload,
                    provider=order_provider_clean or "gumroad",
                    metadata=payhip_metadata if order_provider_clean == "payhip" else None,
                )
        except Exception as exc:
            last_exc = exc
            logger.warning(
                "chart_addon_save_transient_error order_id=%s addon_type=%s error_type=%s error=%r",
                order_code_clean,
                addon_type,
                type(exc).__name__,
                exc,
                exc_info=True,
            )
            time.sleep(0.15)
            continue

        _log_order_check(
            provider=order_provider_clean,
            order_id=order_code_clean,
            strict_check=bool(policy["strict"]),
            check_result=status,
            reason="stores strict check" if policy["strict"] else f"{_provider_label(order_provider_clean)} relaxed check",
        )

        if status == "ok":
            return token, expires_at
        if status == "not_found":
            raise ValueError(f"注文番号（{order_code_clean}）が見つかりません。購入確認メールに記載の番号を確認してください。")
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

    if last_exc:
        raise ValueError(_public_error_message(last_exc, fallback="追加データの保存に失敗しました。時間をおいて再試行してください。")) from last_exc
    raise ValueError("追加データの保存に失敗しました。時間をおいて再試行してください。")


def _redeem_addon_order_or_raise(
    order_code: str,
    order_provider: str,
    addon_type: str,
    *,
    payhip_metadata: dict[str, str] | None = None,
) -> str:
    order_code_clean = _normalize_stores_order_no(order_code)
    if not order_code_clean:
        raise ValueError("注文番号を入力してください。")
    if not _is_valid_order_code(order_code_clean):
        raise ValueError("注文番号には英数字、ハイフン、アンダースコア、イコールのみ使用できます。")
    order_provider_clean = _resolve_order_provider(order_code_clean, order_provider)
    policy = _get_order_check_policy(order_provider_clean)
    if order_provider_clean not in ORDER_PROVIDERS:
        _log_order_check(
            provider=order_provider_clean,
            order_id=order_code_clean,
            strict_check=bool(policy["strict"]),
            check_result="provider_unknown",
            reason="provider could not be resolved",
        )
        raise ValueError(f"注文番号（{order_code_clean}）を確認できません。購入確認メールに記載の番号を確認してください。")
    if order_provider_clean == "gumroad":
        _log_order_check(
            provider=order_provider_clean,
            order_id=order_code_clean,
            strict_check=True,
            check_result="unsupported",
            reason="gumroad product tags are only mapped for western_basic/western_full",
        )
        raise ValueError("Gumroad注文はこの追加商品では使用できません。対応商品タグを確認してください。")
    if not os.environ.get("DATABASE_URL"):
        raise ValueError("注文番号照合用のDATABASE_URLが未設定です。管理者に連絡してください。")

    try:
        if policy["strict"]:
            status, order_row = pg_store.redeem_addon_order(order_code=order_code_clean, addon_type=addon_type)
            if status == "not_found" and _truthy(os.getenv("STORES_MAIL_SYNC_ON_SUBMIT", "1")):
                _sync_stores_orders_for_lookup()
                status, order_row = pg_store.redeem_addon_order(order_code=order_code_clean, addon_type=addon_type)
        else:
            if order_provider_clean == "payhip":
                status, order_row = pg_store.redeem_addon_order_relaxed_with_metadata(
                    order_code=order_code_clean,
                    addon_type=addon_type,
                    provider="payhip",
                    metadata=payhip_metadata,
                )
            else:
                status, order_row = pg_store.redeem_addon_order_relaxed(order_code=order_code_clean, addon_type=addon_type)
    except Exception as exc:
        logger.exception(
            "addon_order_check_failed order_id=%s addon_type=%s error_type=%s error=%r",
            order_code_clean,
            addon_type,
            type(exc).__name__,
            exc,
        )
        raise ValueError(_public_error_message(exc, fallback="注文番号の照合に失敗しました。時間をおいて再試行してください。")) from exc

    _log_order_check(
        provider=order_provider_clean,
        order_id=order_code_clean,
        strict_check=bool(policy["strict"]),
        check_result=status,
        reason="stores strict check" if policy["strict"] else f"{_provider_label(order_provider_clean)} relaxed check",
    )

    if status == "ok":
        return order_code_clean
    if status == "not_found":
        raise ValueError(f"注文番号（{order_code_clean}）が見つかりません。購入確認メールに記載の番号を確認してください。")
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
    return _addon_form_response(request, form=_addon_initial_form_from_request(request))


@app.get("/addon/new", response_class=HTMLResponse)
def public_addon_new(request: Request):
    return _addon_form_response(request, form=_addon_initial_form_from_request(request))


@app.post("/admin/addon/generate", response_class=HTMLResponse)
@app.post("/addon/generate", response_class=HTMLResponse)
def addon_generate(
    request: Request,
    addon_type: str = Form("western_asteroids_addon"),
    order_code: str = Form(""),
    order_provider: str = Form(""),
    payhip_email: str = Form(""),
    payhip_product_code: str = Form(""),
    payhip_order_id: str = Form(""),
    base_yaml: str = Form(""),
    previous_chart_url: str = Form(""),
    transit_start_date: str = Form(""),
):
    form = {
        "addon_type": addon_type,
        "order_code": order_code,
        "order_provider": order_provider,
        "payhip_email": payhip_email,
        "payhip_product_code": payhip_product_code,
        "payhip_order_id": payhip_order_id,
        "base_yaml": base_yaml,
        "previous_chart_url": previous_chart_url,
        "transit_start_date": transit_start_date,
    }
    if addon_type not in {item["value"] for item in ADDON_FORM_OPTIONS}:
        return _addon_form_response(request, form=form, error="addon種別が不正です。", status_code=400)
    requested_provider = (order_provider or "").strip().lower()
    payhip_metadata: dict[str, str] = {}
    order_code_for_redeem = order_code
    order_provider_for_redeem = order_provider
    if requested_provider == "payhip":
        payhip_metadata, payhip_error = _payhip_metadata_from_form(
            payhip_email=payhip_email,
            payhip_product_code=payhip_product_code,
            payhip_order_id=payhip_order_id,
            expected_product_type=addon_type,
        )
        if payhip_error:
            return _addon_form_response(request, form=form, error=payhip_error, status_code=400)
        order_code_for_redeem, _payhip_order_row, payhip_order_error, payhip_order_error_status = _resolve_payhip_order_from_metadata(payhip_metadata)
        if payhip_order_error:
            return _addon_form_response(request, form=form, error=payhip_order_error, status_code=payhip_order_error_status)
        order_provider_for_redeem = "payhip"
    try:
        if addon_type == "western_asteroids_addon":
            if not base_yaml.strip() and not previous_chart_url.strip():
                return _addon_form_response(
                    request,
                    form=form,
                    error="基本版YAML または 90日以内の前回鑑定URLを入力してください。入力後、もう一度生成してください。",
                    status_code=400,
                )
            doc = (
                _load_addon_base_yaml(base_yaml)
                if base_yaml.strip()
                else _load_addon_base_doc_from_previous_chart_url(previous_chart_url, addon_type)
            )
            (
                _addon_yaml_text,
                _addon_prompt_text,
                _addon_doc,
                chart_yaml_text,
                chart_prompt_text,
                chart_doc,
            ) = _build_asteroid_addon_from_base(doc)
            chart_payload = _asteroid_addon_chart_payload(
                yaml_text=chart_yaml_text,
                prompt_text=chart_prompt_text,
                chart_doc=chart_doc,
            )
            order_provider_clean = _resolve_order_provider(_normalize_stores_order_no(order_code_for_redeem), order_provider_for_redeem)
            chart_payload["options"] = {
                **dict(chart_payload["options"]),
                "order_provider": order_provider_clean,
                "order_strict_check": _get_order_check_policy(order_provider_clean)["strict"],
                **payhip_metadata,
            }
            token, _expires_at = _redeem_and_save_chart_addon_or_raise(
                order_code_for_redeem,
                order_provider_for_redeem,
                addon_type,
                chart_payload=chart_payload,
                payhip_metadata=payhip_metadata or None,
            )
            return RedirectResponse(f"/chart/{token}", status_code=303)
        if addon_type == "western_31days_transit_addon":
            if not base_yaml.strip() and not previous_chart_url.strip():
                return _addon_form_response(
                    request,
                    form=form,
                    error="基本版YAML または 90日以内の前回鑑定URLを入力してください。入力後、もう一度生成してください。",
                    status_code=400,
                )
            doc = (
                _load_addon_base_yaml(base_yaml)
                if base_yaml.strip()
                else _load_addon_base_doc_from_previous_chart_url(previous_chart_url, addon_type)
            )
            start_dt = _parse_transit_start_date(transit_start_date)
            (
                result_yaml,
                _addon_prompt_text,
                _addon_doc,
                chart_yaml_text,
                chart_prompt_text,
                chart_doc,
            ) = _build_transit_addon_from_base(
                doc,
                transit_start_date=start_dt,
            )
            chart_payload = _transit_addon_chart_payload(
                yaml_text=chart_yaml_text,
                prompt_text=chart_prompt_text,
                chart_doc=chart_doc,
            )
            order_provider_clean = _resolve_order_provider(_normalize_stores_order_no(order_code_for_redeem), order_provider_for_redeem)
            chart_payload["options"] = {
                **dict(chart_payload["options"]),
                "order_provider": order_provider_clean,
                "order_strict_check": _get_order_check_policy(order_provider_clean)["strict"],
                **payhip_metadata,
            }
            token, _expires_at = _redeem_and_save_transit_addon_or_raise(
                order_code_for_redeem,
                order_provider_for_redeem,
                addon_type,
                result_yaml,
                chart_payload=chart_payload,
                payhip_metadata=payhip_metadata or None,
            )
            return RedirectResponse(f"/chart/{token}", status_code=303)
        if addon_type == "western_long_term_transits_addon":
            if not base_yaml.strip() and not previous_chart_url.strip():
                return _addon_form_response(
                    request,
                    form=form,
                    error="基本版YAML または 90日以内の前回鑑定URLを入力してください。入力後、もう一度生成してください。",
                    status_code=400,
                )
            doc = (
                _load_addon_base_yaml(base_yaml)
                if base_yaml.strip()
                else _load_addon_base_doc_from_previous_chart_url(previous_chart_url, addon_type)
            )
            start_dt = _parse_transit_start_date(transit_start_date)
            (
                result_yaml,
                _addon_prompt_text,
                _addon_doc,
                chart_yaml_text,
                chart_prompt_text,
                chart_doc,
            ) = _build_long_term_transits_addon_from_base(
                doc,
                transit_start_date=start_dt,
            )
            chart_payload = _long_term_transits_addon_chart_payload(
                yaml_text=chart_yaml_text,
                prompt_text=chart_prompt_text,
                chart_doc=chart_doc,
            )
            order_provider_clean = _resolve_order_provider(_normalize_stores_order_no(order_code_for_redeem), order_provider_for_redeem)
            chart_payload["options"] = {
                **dict(chart_payload["options"]),
                "order_provider": order_provider_clean,
                "order_strict_check": _get_order_check_policy(order_provider_clean)["strict"],
                **payhip_metadata,
            }
            token, _expires_at = _redeem_and_save_transit_addon_or_raise(
                order_code_for_redeem,
                order_provider_for_redeem,
                addon_type,
                result_yaml,
                chart_payload=chart_payload,
                payhip_metadata=payhip_metadata or None,
            )
            return RedirectResponse(f"/chart/{token}", status_code=303)
        if not base_yaml.strip():
            return _addon_form_response(request, form=form, error="基本版YAMLを貼り付けてください。", status_code=400)
        doc = _load_addon_base_yaml(base_yaml)
        result_yaml = _build_addon_yaml_from_base(doc, addon_type)
        _redeem_addon_order_or_raise(
            order_code_for_redeem,
            order_provider_for_redeem,
            addon_type,
            payhip_metadata=payhip_metadata or None,
        )
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


@app.get("/addon/long-term-transits/{token}.yaml", response_class=PlainTextResponse)
@app.get("/admin/addon/long-term-transits/{token}.yaml", response_class=PlainTextResponse)
def long_term_transits_addon_yaml(token: str):
    link, expired = _load_transit_addon_link(token)
    if expired:
        return PlainTextResponse("この長期トランジットデータの有効期限は終了しました。\n", status_code=410)
    response = PlainTextResponse(str((link or {}).get("yaml_text") or ""), media_type="text/yaml; charset=utf-8")
    response.headers["Content-Disposition"] = 'attachment; filename="nanami-long-term-transits-addon.yaml"'
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


@app.get("/addon/long-term-transits/{token}", response_class=HTMLResponse)
@app.get("/admin/addon/long-term-transits/{token}", response_class=HTMLResponse)
def long_term_transits_addon_page(request: Request, token: str):
    link, expired = _load_transit_addon_link(token)
    chart = pg_store.get_chart(token, include_svgs=False)
    if chart and not expired:
        chart_expires_at = _chart_expiry(chart)
        if not chart_expires_at or datetime.now(timezone.utc) < chart_expires_at:
            return RedirectResponse(f"/chart/{token}", status_code=303)
    expires_at = _chart_expiry(link or {})
    return templates.TemplateResponse(
        "long_term_transits_addon_page.html",
        {
            "request": request,
            "expired": expired,
            "yaml_text": "" if expired else str((link or {}).get("yaml_text") or ""),
            "expires_label": _chart_expiry_label(expires_at),
            "download_url": f"/addon/long-term-transits/{token}.yaml",
            "expired_message": "この長期トランジットデータの有効期限は終了しました。",
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


def _chart_has_western_natal(chart: dict, *, doc: dict | None = None) -> bool:
    options = chart.get("options") or {}
    if bool(options.get("western_natal")):
        return True
    doc = doc if isinstance(doc, dict) else {}
    western = ((doc.get("systems") or {}).get("western") or {})
    return isinstance(western.get("natal"), dict) and bool(western.get("natal"))


def _chart_has_31day_transit(chart: dict, *, doc: dict | None = None) -> bool:
    options = chart.get("options") or {}
    if options.get("transit_days") in {31, 38} or bool(options.get("transit_31days_summary")):
        return True
    if bool(options.get("transit")) and options.get("product_type") in {"western_31days_transit_addon", "western_note_transit_addon"}:
        return True
    doc = doc if isinstance(doc, dict) else {}
    western = ((doc.get("systems") or {}).get("western") or {})
    transit = western.get("transit") or {}
    if not isinstance(transit, dict):
        return False
    daily = transit.get("daily")
    if isinstance(daily, list) and len(daily) >= 31:
        return True
    period = transit.get("period") or {}
    return period.get("days") in {31, 38}


def _chart_has_western_asteroids(chart: dict, *, doc: dict | None = None) -> bool:
    options = chart.get("options") or {}
    if bool(options.get("asteroids")):
        return True
    doc = doc if isinstance(doc, dict) else {}
    western = ((doc.get("systems") or {}).get("western") or {})
    asteroids = western.get("asteroids") or {}
    return isinstance(asteroids, dict) and bool(asteroids)


def _chart_expiry(chart: dict) -> datetime | None:
    if _chart_has_no_expiry(chart):
        return None
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


def _chart_share_yaml_text(chart: dict, *, doc: dict | None = None) -> str:
    yaml_text = chart["yaml_text"]
    chart_doc = doc if isinstance(doc, dict) else None
    if chart_doc is None:
        try:
            loaded_doc = yaml.safe_load(yaml_text) or {}
            chart_doc = loaded_doc if isinstance(loaded_doc, dict) else {}
        except Exception:
            chart_doc = None
    has_western_natal = _chart_has_western_natal(chart, doc=chart_doc)
    has_western_asteroids = _chart_has_western_asteroids(chart, doc=chart_doc)
    has_31day_transit = _chart_has_31day_transit(chart, doc=chart_doc)
    full_like_western = has_western_natal and has_31day_transit
    long_term_like_western = has_western_natal and has_long_term_transits(doc=chart_doc)
    asteroid_like_western = has_western_natal and has_western_asteroids
    if full_like_western or long_term_like_western:
        return build_light_astrology_yaml(
            yaml_text,
            doc=chart_doc,
            include_asteroids=long_term_like_western and has_western_asteroids,
        )
    return yaml_text


def _chart_ai_paste_text(chart: dict, share_yaml_text: str | None = None, *, doc: dict | None = None) -> str:
    yaml_text = share_yaml_text or chart.get("share_yaml_text") or chart.get("yaml_text") or ""
    prompt_text = _chart_prompt_for_yaml_text(chart, str(yaml_text), fallback_doc=doc).rstrip()
    parts = [prompt_text, "", "---", "", "以下がYAMLデータです。", "", "```yaml", str(yaml_text), "```"]
    return "\n".join(parts).rstrip() + "\n"


def _chart_prompt_for_yaml_text(chart: dict, yaml_text: str, *, fallback_doc: dict | None = None) -> str:
    try:
        loaded_doc = yaml.safe_load(yaml_text) or {}
        prompt_doc = loaded_doc if isinstance(loaded_doc, dict) else {}
    except Exception:
        prompt_doc = fallback_doc if isinstance(fallback_doc, dict) else {}
    product_options = ((prompt_doc.get("product") or {}).get("options") or {}) if isinstance(prompt_doc, dict) else {}
    western = (((prompt_doc.get("systems") or {}).get("western") or {}) if isinstance(prompt_doc, dict) else {})
    if isinstance(product_options, dict) and isinstance(western, dict) and product_options:
        include_transit = bool(
            product_options.get("transit")
            or product_options.get("transit_today")
            or product_options.get("transit_31days_summary")
            or western.get("transit")
        )
        include_asteroids = bool(product_options.get("asteroids") and western.get("asteroids"))
        include_shichusuimei = bool(product_options.get("shichusuimei"))
        return build_prompt(
            include_shichusuimei=include_shichusuimei,
            include_asteroids=include_asteroids,
            include_transit=include_transit,
            birth_time_accuracy=str((prompt_doc.get("birth_time") or {}).get("accuracy") or "exact"),
            interpretation_flags=prompt_doc.get("interpretation_flags") or {},
        )
    return _chart_prompt_text(chart, doc=fallback_doc)


def _chart_prompt_text(chart: dict, *, doc: dict | None = None) -> str:
    prompt_text = str(chart.get("prompt_text") or "")
    guided_prompt = ensure_transit_date_guidance(prompt_text)
    if guided_prompt == prompt_text:
        return prompt_text
    chart_doc = doc if isinstance(doc, dict) else None
    if chart_doc is None:
        try:
            loaded_doc = yaml.safe_load(chart.get("yaml_text") or "") or {}
            chart_doc = loaded_doc if isinstance(loaded_doc, dict) else {}
        except Exception:
            chart_doc = {}
    if _chart_has_western_natal(chart, doc=chart_doc) and _chart_has_31day_transit(chart, doc=chart_doc):
        return guided_prompt
    return prompt_text


def _chart_zip_readme(chart: dict) -> str:
    no_expiry = _chart_has_no_expiry(chart)
    expires_label = "有効期限なし" if no_expiry else _chart_expiry_label(_chart_expiry(chart))
    expiry_line = (
        "共有URLに有効期限はありません。"
        if no_expiry
        else f"共有URLの有効期限は発行から90日間です。このデータページは {expires_label} に開けなくなります。"
    )
    options = chart.get("options") or {}
    product_type = _chart_product_type(options)
    try:
        loaded_doc = yaml.safe_load(chart["yaml_text"]) or {}
        chart_doc = loaded_doc if isinstance(loaded_doc, dict) else {}
    except Exception:
        chart_doc = None
    has_western_natal = _chart_has_western_natal(chart, doc=chart_doc)
    has_western_asteroids = _chart_has_western_asteroids(chart, doc=chart_doc)
    has_31day_transit = _chart_has_31day_transit(chart, doc=chart_doc)
    full_like_western = has_western_natal and has_31day_transit
    asteroid_like_western = has_western_natal and has_western_asteroids
    files: list[str] = [
        "ai_paste.txt: AIにそのまま貼るための推奨テキストです。ファイル名の末尾の日付はダウンロード当日です。迷ったらまずこれを使ってください。",
        "detail.yaml: AIに渡しやすい軽量版YAMLです。完全版より読みやすく、通常の鑑定向けです。",
        "full.yaml: 保存・検証用の完全版YAMLです。内容を細かく確認したいときに使います。",
        "prompt.txt: AIへの読み方を指定する文章です。ai_paste.txt の中にも同じ指示が含まれています。",
    ]
    if (product_type == "western_basic" or (has_western_natal and has_long_term_transits(doc=chart_doc))) and not full_like_western and not asteroid_like_western:
        files.extend([
            "natal.yaml: ネイタル基本データです。出生図だけを確認したいときに使います。",
        ])
    elif full_like_western:
        files.extend([
            "natal.yaml: ネイタル基本データです。出生図だけを確認したいときに使います。",
            "natal-asteroids.yaml: ネイタルに小惑星を追加したデータです。小惑星を詳しく見たいときに使います。",
            "transit.yaml: 38日分のトランジットデータです。今後の流れを詳しく見たいときに使います。",
        ])
    elif asteroid_like_western:
        files.extend([
            "natal.yaml: ネイタル基本データです。出生図だけを確認したいときに使います。",
            "natal-asteroids.yaml: ネイタルに小惑星を追加したデータです。小惑星を詳しく見たいときに使います。",
        ])
    if has_long_term_transits(doc=chart_doc):
        files.extend([
            "long-term-transits-ai.yaml: AI共有用に主要イベントだけへ軽量化した長期トランジットYAMLです。",
            "long-term-transits-full.yaml: 週次samplesを含む保存・検証用の長期トランジット詳細YAMLです。",
            "long-term-transits.yaml: 互換用の長期トランジット詳細YAMLです。内容はlong-term-transits-full.yamlと同等です。",
        ])
    if chart.get("horoscope_svg"):
        files.append("horoscope.svg: ホロスコープ図のSVGです。図として確認したいときに使います。")
    if chart.get("shichusuimei_svg"):
        files.append("shichusuimei.svg: 四柱推命の命式図SVGです。図として確認したいときに使います。")

    file_lines = "\n".join(f"- {line}" for line in files)
    return f"""nanami-products 鑑定データ保存用ZIP

このZIPは鑑定データを手元に保存するためのファイルです。
{expiry_line}

このZIPに入っているファイル:
{file_lines}

使い分けの目安:
- AIに貼るだけなら ai_paste.txt か detail.yaml を使ってください。
- もっと厳密に確認したいときは full.yaml を見てください。
- 図で確認したいときは SVG ファイルを開いてください。

注意:
- YAML内の天体位置・ハウス・アスペクトなどは計算済みデータです。
- AIに依頼するときは、生年月日から再計算せず、このYAMLを根拠に解釈するよう伝えてください。
"""


def _apply_public_chart_headers(response: Response, chart: dict, *, max_age: int) -> None:
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    # 星読みの暦アプリ（別オリジン）が ?load= で YAML/SVG を fetch できるようにする。
    # token を知っている人には元々公開のデータなので、CORS 許可で公開範囲は変わらない。
    response.headers["Access-Control-Allow-Origin"] = "*"
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


def _load_chart_or_404(token: str, *, include_svgs: bool = True) -> dict:
    try:
        chart = pg_store.get_chart(token, include_svgs=include_svgs)
    except Exception as exc:
        logger.exception(
            "chart_load_failed token_prefix=%s include_svgs=%s error=%r",
            token[:8],
            include_svgs,
            exc,
        )
        raise
    if not chart:
        logger.info("chart_not_found token_prefix=%s include_svgs=%s", token[:8], include_svgs)
        raise HTTPException(status_code=404, detail="chart not found")
    expires_at = _chart_expiry(chart)
    if expires_at and datetime.now(timezone.utc) >= expires_at:
        logger.info("chart_expired token_prefix=%s include_svgs=%s", token[:8], include_svgs)
        raise HTTPException(status_code=410, detail="chart expired")
    return chart
