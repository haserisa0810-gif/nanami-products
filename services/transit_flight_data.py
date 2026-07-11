"""Transit Flight 用データ変換。

nanami-products の western 31日トランジット YAML（FULL / detail / lite）を
3D飛行用の固定スキーマへ変換する。

出力スキーマ:
{
  "profile": { "name", "birth_date", "period_start", "period_end" },
  "events": [{ "date", "transit_planet", "natal_planet", "aspect", "orb", "level", "theme" }],
  "source": { ... 任意メタ ... }
}

Chart URL 解決（MCP 連携と同系統）:
- https://chart.nanami-astro.com/chart/{id}
- https://chart.nanami-astro.com/chart/{id}.yaml
- /chart/{id}/transit.yaml / detail.yaml
- 素の chart_id / token
"""
from __future__ import annotations

import os
import re
from typing import Any
from urllib.parse import urlparse

import yaml

from services.mcp_chart_service import CHART_ID_RE, chart_expiry

MAJOR_ASPECTS = frozenset({"conjunction", "opposition", "square", "trine", "sextile"})
OUTER_TRANSIT = frozenset({"Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"})
SLOW_NATAL = frozenset({"Saturn", "Uranus", "Neptune", "Pluto", "Sun", "Moon", "ASC", "MC"})
HARD_ASPECTS = frozenset({"conjunction", "opposition", "square"})
PERSONAL_TRANSIT = frozenset({"Sun", "Moon", "Mercury", "Venus", "Mars"})

# 煽らない短テーマ（フライト表示用）
THEME_BY_TRANSIT = {
    "Sun": "自己表現や活動の焦点が動く時期",
    "Moon": "感情のリズムが変化しやすい時期",
    "Mercury": "思考・対話・情報の流れが動く時期",
    "Venus": "価値観・関係・心地よさが再編されやすい時期",
    "Mars": "行動の向きや勢いが切り替わりやすい時期",
    "Jupiter": "視野や活動範囲が広がりやすい時期",
    "Saturn": "責任・構造・土台を整え直す時期",
    "Uranus": "固定した枠が動きやすい時期",
    "Neptune": "直感と境界が揺らぎやすい時期",
    "Pluto": "深いレベルの再編が起きやすい時期",
}

ASPECT_SOFT = {
    "conjunction": "結びつきが強まる",
    "opposition": "対になる力が向かい合う",
    "square": "調整が求められる",
    "trine": "流れがつながりやすい",
    "sextile": "連携が生まれやすい",
}


class TransitFlightDataError(ValueError):
    """YAML から飛行データを作れないときのユーザー向けエラー。"""


def _safe_load(yaml_text: str) -> dict[str, Any]:
    try:
        doc = yaml.safe_load(yaml_text or "")
    except yaml.YAMLError as exc:
        raise TransitFlightDataError("YAMLの解析に失敗しました。形式を確認してください。") from exc
    if not isinstance(doc, dict):
        raise TransitFlightDataError("YAMLはオブジェクト形式である必要があります。")
    return doc


def _norm_aspect(value: Any) -> str | None:
    raw = str(value or "").strip().lower().replace(" ", "_")
    aliases = {
        "conj": "conjunction",
        "opp": "opposition",
        "sq": "square",
        "tri": "trine",
        "sex": "sextile",
        "合": "conjunction",
        "衝": "opposition",
        "矩": "square",
        "三分": "trine",
        "六分": "sextile",
    }
    raw = aliases.get(raw, raw)
    return raw if raw in MAJOR_ASPECTS else None


def _body_name(value: Any) -> str:
    return str(value or "").strip()


def _theme_for(transit: str, natal: str, aspect: str, meaning_hint: str | None = None) -> str:
    hint = (meaning_hint or "").strip()
    if hint and len(hint) >= 4:
        # light_yaml の meaning_hint は短いので、フライト向けに整える
        if "、" in hint:
            return f"{hint.replace('、', 'と')}が進みやすい時期"
        return f"{hint}が進みやすい時期"
    base = THEME_BY_TRANSIT.get(transit, "天体配置の変化を感じやすい時期")
    soft = ASPECT_SOFT.get(aspect, "")
    if soft and natal:
        return f"{base}（ネイタル{_ja_body(natal)}と{soft}）"
    return base


def _ja_body(name: str) -> str:
    table = {
        "Sun": "太陽", "Moon": "月", "Mercury": "水星", "Venus": "金星", "Mars": "火星",
        "Jupiter": "木星", "Saturn": "土星", "Uranus": "天王星", "Neptune": "海王星", "Pluto": "冥王星",
        "ASC": "ASC", "MC": "MC", "North Node": "北ノード", "South Node": "南ノード",
    }
    return table.get(name, name)


def _score_event(transit: str, natal: str, aspect: str, orb: float) -> int:
    score = 0
    if transit in OUTER_TRANSIT:
        score += 3
    elif transit in {"Sun", "Mars", "Venus", "Mercury"}:
        score += 1
    if natal in SLOW_NATAL:
        score += 1
    if aspect in HARD_ASPECTS:
        score += 2
    elif aspect == "trine":
        score += 1
    if orb <= 0.25:
        score += 2
    elif orb <= 0.6:
        score += 1
    if transit == "Moon":
        score -= 2
    if transit in PERSONAL_TRANSIT and natal not in SLOW_NATAL and aspect not in HARD_ASPECTS:
        score -= 1
    return score


def _level_from_score(score: int) -> int:
    if score >= 6:
        return 3
    if score >= 3:
        return 2
    return 1


def _iter_daily_aspects(transit_block: dict[str, Any]) -> list[dict[str, Any]]:
    """FULL YAML の daily[].natal_aspects と、summary 系 key_aspects をまとめる。"""
    out: list[dict[str, Any]] = []

    daily = transit_block.get("daily") or []
    if isinstance(daily, list):
        for day in daily:
            if not isinstance(day, dict):
                continue
            date = str(day.get("date") or "").strip()
            for item in day.get("natal_aspects") or []:
                if isinstance(item, dict):
                    row = dict(item)
                    if date and not row.get("date"):
                        row["date"] = date
                    out.append(row)

    # light / detail: next_31_days_summary.key_aspects
    summary = transit_block.get("next_31_days_summary") or {}
    if isinstance(summary, dict):
        for item in summary.get("key_aspects") or []:
            if isinstance(item, dict):
                out.append(dict(item))
        for period in summary.get("key_periods") or summary.get("active_periods") or []:
            if not isinstance(period, dict):
                continue
            for item in period.get("source_aspects") or []:
                if isinstance(item, dict):
                    row = dict(item)
                    if period.get("date") and not row.get("date"):
                        row["date"] = period.get("date")
                    if period.get("start_date") and not row.get("date"):
                        row["date"] = period.get("start_date")
                    out.append(row)

    # today ブロック（補助）
    today = transit_block.get("today") or {}
    if isinstance(today, dict):
        date = str(today.get("date") or today.get("selected_date") or "").strip()
        for item in today.get("natal_aspects") or []:
            if isinstance(item, dict):
                row = dict(item)
                if date and not row.get("date"):
                    row["date"] = date
                out.append(row)

    return out


def _period_from_doc(doc: dict[str, Any], events: list[dict[str, Any]]) -> tuple[str, str]:
    western = ((doc.get("systems") or {}).get("western") or {})
    transit = western.get("transit") or {}
    period = transit.get("period") or {}
    start = str(period.get("start_date") or "").strip()
    days_raw = period.get("days")
    end = ""
    if start and days_raw:
        try:
            from datetime import date, timedelta

            d0 = date.fromisoformat(start)
            days = max(int(days_raw), 1)
            end = (d0 + timedelta(days=days - 1)).isoformat()
        except (TypeError, ValueError):
            end = ""

    if not start and events:
        dates = sorted(e["date"] for e in events)
        start = dates[0]
        end = dates[-1]
    if not end and events:
        end = sorted(e["date"] for e in events)[-1]
    if not start or not end:
        # meta target_month からのフォールバック
        meta = doc.get("meta") or {}
        target = str(meta.get("target_month") or "").strip()
        if len(target) == 7 and target[4] == "-":
            try:
                from calendar import monthrange
                from datetime import date

                y, m = int(target[:4]), int(target[5:7])
                start = date(y, m, 1).isoformat()
                end = date(y, m, monthrange(y, m)[1]).isoformat()
            except ValueError:
                pass
    if not start or not end:
        raise TransitFlightDataError(
            "トランジットの対象期間（period.start_date / days）が見つかりません。"
            " western_31days_transit の FULL または detail YAML を渡してください。"
        )
    return start, end


def _collapse_peaks(raw_aspects: list[dict[str, Any]], *, max_events: int) -> list[dict[str, Any]]:
    """同一 (transit, natal, aspect) は最タイト日をピークとして1件にまとめる。"""
    best: dict[tuple[str, str, str], dict[str, Any]] = {}

    for item in raw_aspects:
        transit = _body_name(item.get("transit_body") or item.get("body1"))
        natal = _body_name(item.get("natal_body") or item.get("body2"))
        aspect = _norm_aspect(item.get("aspect"))
        date = str(item.get("date") or "").strip()
        if not transit or not natal or not aspect or not date:
            continue
        try:
            orb = float(item.get("orb"))
        except (TypeError, ValueError):
            continue
        # フライトでは緩めすぎるアスペクトは除外
        if orb > 1.5:
            continue
        # Moon トランジットはノイズになりやすいので、タイトなものだけ
        if transit == "Moon" and orb > 0.5:
            continue

        key = (transit, natal, aspect)
        score = _score_event(transit, natal, aspect, orb)
        theme = _theme_for(transit, natal, aspect, str(item.get("meaning_hint") or "") or None)
        candidate = {
            "date": date,
            "transit_planet": transit,
            "natal_planet": natal,
            "aspect": aspect,
            "orb": round(orb, 2),
            "level": _level_from_score(score),
            "theme": theme,
            "_score": score,
        }
        prev = best.get(key)
        if prev is None or orb < float(prev["orb"]) or (
            orb == float(prev["orb"]) and score > int(prev["_score"])
        ):
            best[key] = candidate

    ranked = sorted(
        best.values(),
        key=lambda e: (-int(e["_score"]), float(e["orb"]), e["date"]),
    )
    # 日付順に戻す前に上位を確保。最低でもレベル2以上を優先しつつ件数制限。
    selected = ranked[:max_events]
    # 少なすぎる場合は ranked から補完済み。日付順へ。
    selected.sort(key=lambda e: e["date"])
    for e in selected:
        e.pop("_score", None)
    return selected


def build_flight_data_from_doc(
    doc: dict[str, Any],
    *,
    max_events: int = 10,
) -> dict[str, Any]:
    """nanami YAML ドキュメント → Transit Flight JSON。"""
    if not isinstance(doc, dict):
        raise TransitFlightDataError("YAMLデータが不正です。")

    # すでに飛行用スキーマならそのまま正規化
    if isinstance(doc.get("events"), list) and isinstance(doc.get("profile"), dict):
        return _normalize_flight_doc(doc)

    western = ((doc.get("systems") or {}).get("western") or {})
    if not isinstance(western, dict):
        western = {}
    transit = western.get("transit") or {}
    if not isinstance(transit, dict) or not transit:
        # natal only
        has_natal = bool(western.get("natal"))
        if has_natal:
            raise TransitFlightDataError(
                "ネイタルデータはありますが、トランジット期間データ（systems.western.transit）がありません。"
                " western_31days_transit の FULL YAML、または AI貼り付け用 detail/lite（next_31_days_summary 付き）を渡してください。"
            )
        raise TransitFlightDataError(
            "トランジットデータが見つかりません。nanami-products の western トランジット YAML を貼り付けてください。"
        )

    raw = _iter_daily_aspects(transit)
    if not raw:
        raise TransitFlightDataError(
            "トランジット内にアスペクト（natal_aspects / key_aspects）が見つかりませんでした。"
        )

    events = _collapse_peaks(raw, max_events=max_events)
    if not events:
        raise TransitFlightDataError(
            "飛行に使える主要アスペクトを抽出できませんでした（オーブが広い、または対応外の配置のみ）。"
        )

    period_start, period_end = _period_from_doc(doc, events)
    input_block = doc.get("input") or {}
    meta = doc.get("meta") or {}
    name = (
        str(input_block.get("title") or "").strip()
        or str(meta.get("profile_id") or "").strip()
        or "Chart"
    )
    birth = str(input_block.get("birth_date") or "").strip() or "—"

    return {
        "profile": {
            "name": name,
            "birth_date": birth,
            "period_start": period_start,
            "period_end": period_end,
        },
        "events": events,
        "source": {
            "format": str(doc.get("version") or "nanami-products-yaml"),
            "product_type": str((doc.get("product") or {}).get("type") or meta.get("product_type") or ""),
            "chart_id": str(meta.get("chart_id") or ""),
            "event_count": len(events),
            "raw_aspect_hits": len(raw),
        },
    }


def build_flight_data_from_yaml(yaml_text: str, *, max_events: int = 10) -> dict[str, Any]:
    return build_flight_data_from_doc(_safe_load(yaml_text), max_events=max_events)


# ── Chart URL / token → flight data ─────────────────────────────────

ALLOWED_CHART_HOSTS = frozenset(
    {
        "chart.nanami-astro.com",
        "pay.nanami-astro.com",
        "localhost",
        "127.0.0.1",
    }
)

# /chart/{id}[.yaml|/transit.yaml|/detail.yaml|/full.yaml]
_CHART_PATH_RE = re.compile(
    r"^/chart/(?P<id>[A-Za-z0-9_-]{5,128})"
    r"(?:"
    r"\.yaml"
    r"|/(?P<variant>transit|detail|full|natal)\.yaml"
    r")?"
    r"/?$"
)


def _extra_allowed_hosts() -> set[str]:
    raw = (os.getenv("TRANSIT_FLIGHT_ALLOWED_HOSTS") or os.getenv("PUBLIC_BASE_URL") or "").strip()
    hosts: set[str] = set()
    if not raw:
        return hosts
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        if "://" in part:
            try:
                host = (urlparse(part).hostname or "").lower()
            except ValueError:
                host = ""
        else:
            host = part.lower().split("/")[0].split(":")[0]
        if host:
            hosts.add(host)
    return hosts


def parse_chart_ref(value: str) -> tuple[str, str]:
    """URL / パス / token から (chart_id, variant) を返す。

    variant: full | transit | detail  （natal は飛行不可として別扱い）
    """
    raw = (value or "").strip()
    if not raw:
        raise TransitFlightDataError("Chart URL または chart_id を指定してください。")

    # bare token
    if CHART_ID_RE.fullmatch(raw) and "://" not in raw and "/" not in raw:
        return raw, "full"

    try:
        parsed = urlparse(raw if "://" in raw else f"https://dummy.local{raw if raw.startswith('/') else '/' + raw}")
    except ValueError as exc:
        raise TransitFlightDataError("URLの形式が不正です。") from exc

    # absolute URL host check
    if "://" in raw:
        host = (parsed.hostname or "").lower()
        if host not in ALLOWED_CHART_HOSTS and host not in _extra_allowed_hosts():
            raise TransitFlightDataError(
                "許可されていないドメインです。"
                " chart.nanami-astro.com の Chart URL、または同一サービスの /chart/{id} を指定してください。"
            )
        if parsed.scheme not in {"http", "https"}:
            raise TransitFlightDataError("Chart URL は http(s) で指定してください。")
        # localhost 以外は https を推奨だが、pay も https 想定。開発用 http は localhost のみ許可。
        if parsed.scheme == "http" and host not in {"localhost", "127.0.0.1"}:
            raise TransitFlightDataError("Chart URL は https で指定してください。")

    path = parsed.path or ""
    match = _CHART_PATH_RE.fullmatch(path)
    if not match:
        raise TransitFlightDataError(
            "対応形式: https://chart.nanami-astro.com/chart/{id} "
            "または /chart/{id}.yaml /chart/{id}/transit.yaml /chart/{id}/detail.yaml"
        )
    chart_id = match.group("id")
    variant = (match.group("variant") or "full").lower()
    if variant == "natal":
        raise TransitFlightDataError(
            "natal.yaml にはトランジット期間がありません。FULL（.yaml）または transit.yaml / detail.yaml を指定してください。"
        )
    if variant not in {"full", "transit", "detail"}:
        variant = "full"
    return chart_id, variant


def load_chart_yaml_text(chart_id: str, *, variant: str = "full") -> tuple[str, dict[str, Any]]:
    """DB からチャート YAML を取得（MCP と同じストア）。"""
    from services import pg_store

    try:
        chart = pg_store.get_chart(chart_id, include_svgs=False)
    except Exception as exc:
        raise TransitFlightDataError("Chartデータの取得に失敗しました。時間をおいて再試行してください。") from exc
    if not chart:
        raise TransitFlightDataError("Chart URL が見つかりません。")

    expires_at = chart_expiry(chart)
    if expires_at is not None:
        from datetime import datetime, timezone

        if datetime.now(timezone.utc) >= expires_at:
            raise TransitFlightDataError("この Chart URL は期限切れです。")

    full_yaml = str(chart.get("yaml_text") or "")
    if not full_yaml.strip():
        raise TransitFlightDataError("Chart に YAML データがありません。")

    variant = (variant or "full").lower()
    if variant == "transit":
        from services.light_yaml import build_transit_astrology_yaml

        try:
            yaml_text = build_transit_astrology_yaml(full_yaml)
        except Exception as exc:
            raise TransitFlightDataError("transit.yaml の生成に失敗しました。FULL YAML を指定してください。") from exc
    elif variant == "detail":
        from services.light_yaml import build_detail_astrology_yaml

        try:
            yaml_text = build_detail_astrology_yaml(full_yaml)
        except Exception as exc:
            raise TransitFlightDataError("detail.yaml の生成に失敗しました。FULL YAML を指定してください。") from exc
    else:
        yaml_text = full_yaml

    meta = {
        "chart_id": chart_id,
        "variant": variant,
        "product_type": ((chart.get("options") or {}).get("product_type") if isinstance(chart.get("options"), dict) else None),
    }
    return yaml_text, meta


def build_flight_data_from_chart_ref(ref: str, *, max_events: int = 10) -> dict[str, Any]:
    """Chart URL / token から飛行データを構築。"""
    chart_id, variant = parse_chart_ref(ref)
    yaml_text, meta = load_chart_yaml_text(chart_id, variant=variant)
    data = build_flight_data_from_yaml(yaml_text, max_events=max_events)
    source = data.get("source") if isinstance(data.get("source"), dict) else {}
    source = {
        **source,
        "chart_id": meta.get("chart_id") or source.get("chart_id"),
        "chart_variant": meta.get("variant"),
        "load_mode": "chart_url",
    }
    data["source"] = source
    return data


def _normalize_flight_doc(doc: dict[str, Any]) -> dict[str, Any]:
    profile = doc.get("profile") or {}
    events_in = doc.get("events") or []
    events: list[dict[str, Any]] = []
    for item in events_in:
        if not isinstance(item, dict):
            continue
        aspect = _norm_aspect(item.get("aspect"))
        if not aspect:
            continue
        try:
            level = int(item.get("level") or 1)
        except (TypeError, ValueError):
            level = 1
        level = max(1, min(3, level))
        try:
            orb = float(item.get("orb") or 0)
        except (TypeError, ValueError):
            orb = 0.0
        events.append(
            {
                "date": str(item.get("date") or ""),
                "transit_planet": _body_name(item.get("transit_planet") or item.get("transit_body")),
                "natal_planet": _body_name(item.get("natal_planet") or item.get("natal_body")),
                "aspect": aspect,
                "orb": round(orb, 2),
                "level": level,
                "theme": str(item.get("theme") or ""),
            }
        )
    events = [e for e in events if e["date"] and e["transit_planet"] and e["natal_planet"]]
    if not events:
        raise TransitFlightDataError("events が空、または形式が不正です。")
    period_start = str(profile.get("period_start") or events[0]["date"])
    period_end = str(profile.get("period_end") or events[-1]["date"])
    return {
        "profile": {
            "name": str(profile.get("name") or "Sample"),
            "birth_date": str(profile.get("birth_date") or "—"),
            "period_start": period_start,
            "period_end": period_end,
        },
        "events": sorted(events, key=lambda e: e["date"]),
        "source": doc.get("source") if isinstance(doc.get("source"), dict) else {"format": "flight-json"},
    }
