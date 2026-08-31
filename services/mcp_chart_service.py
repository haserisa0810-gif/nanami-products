from __future__ import annotations

import math
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import yaml

from services import pg_store
from services.long_term_transit_yaml import has_long_term_transits

ALLOWED_CHART_HOST = "chart.nanami-astro.com"
CHART_ID_RE = re.compile(r"^[A-Za-z0-9_-]{5,128}$")
CHART_EXPIRES_DAYS = 90
SUPPORTED_SECTIONS = ("natal", "transit_31days", "long_term", "asteroid", "shichu", "indian")
DEFAULT_MAX_YAML_BYTES = 4_000_000
SUPPORTED_PROMPT_PURPOSES = ("today_fortune", "natal_with_transit")


WESTERN_TODAY_FORTUNE_PROMPT = """あなたは西洋占星術の鑑定者です。以下のYAMLは、出生図・38日分のトランジットと、商品に含まれる場合は小惑星を含む計算済みデータです。

重要ルール:
- 天体位置・ハウス・アスペクト・トランジットの計算結果は変更しないでください。
- 生年月日から再計算しないでください。
- YAML内の計算結果を唯一の根拠として解釈してください。
- 断定しすぎず、傾向・使い方・活かし方として表現してください。
- 出生図を土台に、今後38日分のトランジットをつなげて読んでください。
- 小惑星はYAML内に実データが存在する場合だけ解釈してください。存在しない、空、nullの場合は、不足の指摘や断り書きをせず、小惑星への言及を省略してください。
- 月は朝・昼・夜の動きが入っています。日内の変化を読む時に参照してください。
- transitデータは「現在の流れ」の根拠として使ってください。
- moon_timepoints は「朝・昼・夜」の日内の使い方の根拠として使ってください。
- 今後数日の動きは、トランジットのタイトなアスペクトを優先して判断してください。
- today.selected_date を基準日として扱い、next_31_days_summary 内の日付が基準日より前の場合は、「今後の予定」ではなく「過去の流れ・振り返り」として扱ってください。
- 「動きやすい日」「注意したい日」には、today.selected_date 以降の日付を優先して出力してください。
- next_31_days_summary に過去日しか存在しない場合は、過去日を無理に未来の予定として書かず、「この期間に出た違和感や発想は今後の参考になる」などの振り返り表現にしてください。
- 当日以降の判断は today と next_few_days を優先し、next_31_days_summary は補助として使ってください。
- 「良い・悪い」ではなく、「どう使うとズレにくいか」を優先して書いてください。
- 「ラッキー」などの軽い表現は避け、具体的な行動ヒントに置き換えてください。

出力してほしい内容:
- 全体像
- 才能・強み
- つまずきやすいパターン
- 仕事・活動の向き
- 人間関係の傾向
- 今後38日間の流れ
- 動きやすい日・注意したい日
- 現在の流れ（トランジット）
- 今日の使い方（朝・昼・夜）
- 今後数日の動き
- 今後の活かし方"""


class ChartMcpError(ValueError):
    def __init__(self, message: str, *, code: str = "invalid_request", status: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.status = status


def mask_chart_id(chart_id: str) -> str:
    value = str(chart_id or "")
    if len(value) <= 10:
        return value[:2] + "***" if value else ""
    return f"{value[:6]}...{value[-4:]}"


def extract_chart_id_from_url(chart_url: str) -> str:
    raw = (chart_url or "").strip()
    if not raw:
        raise ChartMcpError("chart_url が必要です。", code="chart_url_required")
    try:
        parsed = urlparse(raw)
    except ValueError as exc:
        raise ChartMcpError("Chart URLの形式が不正です。", code="invalid_chart_url") from exc
    if parsed.scheme != "https":
        raise ChartMcpError("Chart URLは https://chart.nanami-astro.com/chart/{chart_id} 形式で指定してください。", code="invalid_scheme")
    if parsed.hostname != ALLOWED_CHART_HOST:
        raise ChartMcpError("許可されていないドメインです。chart.nanami-astro.com のChart URLだけ利用できます。", code="domain_not_allowed")
    if parsed.params or parsed.query or parsed.fragment:
        raise ChartMcpError("Chart URLは /chart/{chart_id} 形式だけ利用できます。", code="unsupported_chart_url")
    match = re.fullmatch(r"/chart/([^/]+)", parsed.path or "")
    if not match:
        raise ChartMcpError("Chart URLは /chart/{chart_id} 形式だけ利用できます。", code="unsupported_chart_url")
    chart_id = match.group(1)
    if not CHART_ID_RE.fullmatch(chart_id):
        raise ChartMcpError("chart_id の形式が不正です。", code="invalid_chart_id")
    return chart_id


def chart_expiry(chart: dict[str, Any]) -> datetime | None:
    options = chart.get("options") or {}
    if isinstance(options, dict) and options.get("expires_policy") == "no_expiry":
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


def _jst_iso(value: datetime | None) -> str | None:
    return value.astimezone(ZoneInfo("Asia/Tokyo")).isoformat() if value else None


def days_until_expiry(expires_at: datetime | None, *, now: datetime | None = None) -> int | None:
    if not expires_at:
        return None
    seconds = (expires_at - (now or datetime.now(timezone.utc))).total_seconds()
    return 0 if seconds <= 0 else int(math.ceil(seconds / 86400))


def expiry_notice(days: int | None, *, expired: bool = False) -> str:
    if expired:
        return "このChart URLは期限切れです。保存済みYAMLがある場合はそちらをご利用ください。最新トランジットが必要な場合は再購入してください。"
    if days is None:
        return "このURLはアクセスキーとして扱われます。継続して使いたい場合はYAMLをダウンロードして保存してください。"
    if days <= 7:
        return f"このデータはあと{days}日で期限切れになります。継続して使いたい場合は、YAMLをダウンロードしてローカル保存してください。最新トランジットが必要な場合は再購入してください。"
    if days <= 14:
        return f"このデータはあと{days}日で期限切れになります。継続して使いたい場合はYAMLをダウンロードして保存してください。"
    if days <= 30:
        return f"このデータはあと{days}日で期限切れになります。必要に応じてYAMLを保存してください。"
    return ""


def _safe_load_yaml(yaml_text: str) -> dict[str, Any]:
    try:
        loaded = yaml.safe_load(yaml_text) or {}
    except Exception as exc:
        raise ChartMcpError("YAMLデータを読み取れませんでした。", code="yaml_parse_failed", status=500) from exc
    return loaded if isinstance(loaded, dict) else {}


def available_sections_for_doc(doc: dict[str, Any]) -> list[str]:
    systems = doc.get("systems") if isinstance(doc.get("systems"), dict) else {}
    western = systems.get("western") if isinstance(systems.get("western"), dict) else {}
    sections: list[str] = []
    if isinstance(western.get("natal"), dict) and western.get("natal"):
        sections.append("natal")
    transit = western.get("transit") if isinstance(western.get("transit"), dict) else {}
    daily = transit.get("daily") if isinstance(transit.get("daily"), list) else []
    period = transit.get("period") if isinstance(transit.get("period"), dict) else {}
    if daily or period.get("days") in {31, 38}:
        sections.append("transit_31days")
    if has_long_term_transits(doc=doc):
        sections.append("long_term")
    if isinstance(western.get("asteroids"), dict) and western.get("asteroids"):
        sections.append("asteroid")
    if isinstance(systems.get("shichusuimei"), dict) and systems.get("shichusuimei"):
        sections.append("shichu")
    if any(isinstance(systems.get(key), dict) and systems.get(key) for key in ("indian", "vedic")):
        sections.append("indian")
    return sections


def build_section_yaml(source: dict[str, Any], requested_sections: list[str]) -> str:
    systems = source.get("systems") if isinstance(source.get("systems"), dict) else {}
    western = systems.get("western") if isinstance(systems.get("western"), dict) else {}
    western_out: dict[str, Any] = {}
    if "natal" in requested_sections:
        western_out["natal"] = western.get("natal")
    if "asteroid" in requested_sections:
        western_out["asteroids"] = western.get("asteroids")
    if "transit_31days" in requested_sections:
        western_out["transit"] = western.get("transit")
    if "long_term" in requested_sections:
        western_out["transit_long_term"] = western.get("transit_long_term")
    out_systems: dict[str, Any] = {}
    if western_out:
        out_systems["western"] = western_out
    if "shichu" in requested_sections:
        out_systems["shichusuimei"] = systems.get("shichusuimei")
    if "indian" in requested_sections:
        out_systems["indian"] = systems.get("indian") or systems.get("vedic")
    out = {
        "version": "nanami-products-mcp-yaml-v1",
        "meta": {
            **(source.get("meta") if isinstance(source.get("meta"), dict) else {}),
            "yaml_variant": "mcp_sections",
            "returned_sections": requested_sections,
        },
        "base": source.get("base"),
        "generated_at": source.get("generated_at"),
        "calculation": source.get("calculation") or {},
        "birth_time": source.get("birth_time") or {},
        "interpretation_flags": source.get("interpretation_flags") or {},
        "input": source.get("input") or {},
        "usage_note": {
            "for_ai": "このYAMLは購入済みChart URLからMCP経由で取得した計算済みデータです。生年月日から再計算せず、この値を根拠に解釈してください。",
            "url_as_access_key": "Chart URLを知っている人はこのデータへアクセスできます。URLの共有範囲に注意してください。",
        },
        "systems": out_systems,
    }
    return yaml.safe_dump(out, allow_unicode=True, sort_keys=False, width=120)


def _load_chart(chart_id: str) -> dict[str, Any]:
    try:
        chart = pg_store.get_chart(chart_id, include_svgs=False)
    except Exception as exc:
        raise ChartMcpError("Chartデータを取得できませんでした。時間をおいて再度お試しください。", code="chart_load_failed", status=502) from exc
    if not chart:
        raise ChartMcpError("Chart URLが見つかりません。", code="chart_not_found", status=404)
    return chart


def _max_yaml_bytes() -> int:
    try:
        return max(100_000, int(os.getenv("MCP_CHART_YAML_MAX_BYTES", str(DEFAULT_MAX_YAML_BYTES))))
    except ValueError:
        return DEFAULT_MAX_YAML_BYTES


def _enforce_yaml_size(yaml_text: str) -> None:
    if len((yaml_text or "").encode("utf-8")) > _max_yaml_bytes():
        raise ChartMcpError("YAMLデータが大きすぎるため返却できません。sections を指定して必要な範囲だけ取得してください。", code="yaml_too_large", status=413)


def _download_url(chart_id: str) -> str:
    return f"https://{ALLOWED_CHART_HOST}/chart/{chart_id}.yaml"


def _filename(chart_id: str) -> str:
    safe_id = re.sub(r"[^A-Za-z0-9_-]+", "_", chart_id)[:80] or "chart"
    return f"nanami_astrology_data_{safe_id}.yaml"


def _base_payload(chart_id: str, chart: dict[str, Any], doc: dict[str, Any]) -> dict[str, Any]:
    expires_at = chart_expiry(chart)
    days = days_until_expiry(expires_at)
    return {
        "chart_id": chart_id,
        "product_type": ((chart.get("options") or {}).get("product_type") if isinstance(chart.get("options"), dict) else None),
        "generated_at": chart.get("created_at").isoformat() if isinstance(chart.get("created_at"), datetime) else chart.get("created_at"),
        "expires_at": _jst_iso(expires_at),
        "days_until_expiry": days,
        "available_sections": available_sections_for_doc(doc),
        "download_url": _download_url(chart_id),
        "filename": _filename(chart_id),
        "notice": expiry_notice(days, expired=False),
    }


def get_chart_yaml_from_url(*, chart_url: str, sections: list[str] | None = None, format: str = "full") -> dict[str, Any]:
    chart_id = extract_chart_id_from_url(chart_url)
    chart = _load_chart(chart_id)
    expires_at = chart_expiry(chart)
    days = days_until_expiry(expires_at)
    if expires_at and datetime.now(timezone.utc) >= expires_at:
        return {
            "ok": False,
            "chart_id": chart_id,
            "yaml": "",
            "available_sections": [],
            "returned_sections": [],
            "missing_sections": [],
            "expires_at": _jst_iso(expires_at),
            "days_until_expiry": 0,
            "download_url": _download_url(chart_id),
            "filename": _filename(chart_id),
            "notice": expiry_notice(0, expired=True),
            "error_code": "chart_expired",
        }
    doc = _safe_load_yaml(str(chart.get("yaml_text") or ""))
    available = available_sections_for_doc(doc)
    requested = [str(item).strip() for item in (sections or []) if str(item).strip()]
    unsupported = [item for item in requested if item not in SUPPORTED_SECTIONS]
    requested_supported = [item for item in requested if item in SUPPORTED_SECTIONS]
    returned = [item for item in requested_supported if item in available]
    missing = [item for item in requested_supported if item not in available] + unsupported
    if requested:
        yaml_text = build_section_yaml(doc, returned) if returned else ""
    else:
        yaml_text = str(chart.get("yaml_text") or "")
        returned = available
    if yaml_text:
        _enforce_yaml_size(yaml_text)
    payload = _base_payload(chart_id, chart, doc)
    payload.update({"ok": True, "yaml": yaml_text, "returned_sections": returned, "missing_sections": missing, "format": format or "full", "notice": expiry_notice(days, expired=False)})
    return payload


def get_chart_summary_from_url(*, chart_url: str) -> dict[str, Any]:
    chart_id = extract_chart_id_from_url(chart_url)
    chart = _load_chart(chart_id)
    expires_at = chart_expiry(chart)
    expired = bool(expires_at and datetime.now(timezone.utc) >= expires_at)
    doc = {} if expired else _safe_load_yaml(str(chart.get("yaml_text") or ""))
    payload = _base_payload(chart_id, chart, doc)
    payload.update({
        "ok": not expired,
        "chart_id": chart_id,
        "yaml_storage_guidance": "継続して使いたい場合は、期限内にYAMLをダウンロードしてローカル保存してください。",
        "expired_guidance": expiry_notice(0, expired=True) if expired else "",
        "notice": expiry_notice(payload.get("days_until_expiry"), expired=expired),
    })
    return payload


def get_available_sections_from_url(*, chart_url: str) -> dict[str, Any]:
    chart_id = extract_chart_id_from_url(chart_url)
    chart = _load_chart(chart_id)
    expires_at = chart_expiry(chart)
    if expires_at and datetime.now(timezone.utc) >= expires_at:
        return {"ok": False, "chart_id": chart_id, "available_sections": [], "notice": expiry_notice(0, expired=True), "error_code": "chart_expired"}
    doc = _safe_load_yaml(str(chart.get("yaml_text") or ""))
    return {"ok": True, "chart_id": chart_id, "available_sections": available_sections_for_doc(doc)}


def get_download_info_from_url(*, chart_url: str) -> dict[str, Any]:
    chart_id = extract_chart_id_from_url(chart_url)
    chart = _load_chart(chart_id)
    expires_at = chart_expiry(chart)
    days = days_until_expiry(expires_at)
    expired = bool(expires_at and datetime.now(timezone.utc) >= expires_at)
    return {
        "ok": not expired,
        "chart_id": chart_id,
        "download_url": _download_url(chart_id),
        "filename": _filename(chart_id),
        "expires_at": _jst_iso(expires_at),
        "days_until_expiry": 0 if expired else days,
        "notice": expiry_notice(0 if expired else days, expired=expired),
        "save_recommendation": "期限内にYAMLをダウンロードしてローカル保存してください。期限後に最新トランジットが必要な場合は再購入してください。",
    }


def get_astrology_prompt(*, purpose: str = "today_fortune", product_type: str = "") -> dict[str, Any]:
    purpose_value = (purpose or "today_fortune").strip()
    if purpose_value not in SUPPORTED_PROMPT_PURPOSES:
        raise ChartMcpError(
            "MVPでは today_fortune / natal_with_transit の鑑定プロンプトのみ対応しています。",
            code="unsupported_prompt_purpose",
        )
    product_value = (product_type or "").strip() or "western_31days_transit_addon"
    return {
        "ok": True,
        "purpose": purpose_value,
        "product_type": product_value,
        "prompt": WESTERN_TODAY_FORTUNE_PROMPT,
        "recommended_sections": ["natal", "asteroid", "transit_31days"],
        "usage_order": [
            "get_chart_summary_from_url でChart URLの有効期限と含まれるセクションを確認する",
            "get_astrology_prompt で鑑定ルールを取得する",
            "get_chart_yaml_from_url で recommended_sections を取得する",
            "YAML内の計算結果だけを根拠に、プロンプトの出力構成で解釈する",
        ],
        "notice": "MCPサーバーは鑑定本文を生成しません。このプロンプトとChart YAMLをAI側で組み合わせ、再計算せずに解釈してください。",
    }
