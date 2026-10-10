"""地名 → 座標のジオコーディング（プロバイダ差し替え可能）。

MVP は OpenStreetMap Nominatim を使う。利用ポリシーに配慮して:
- User-Agent を明示する
- 過剰リクエストしない（同一クエリはプロセス内キャッシュ）
- タイムアウトを短めに設定

返却はアプリ内部の共通形式に正規化する。将来 Google Maps / Mapbox /
LocationIQ などへ差し替える場合は `_provider` を置き換えるだけでよい。
"""
from __future__ import annotations

import json
import inspect
import os
import urllib.parse
import urllib.request
from collections import OrderedDict
from typing import Any, Callable

SOURCE = "manual_search"
SOURCE_LABELS = {
    "ja": "検索・手入力した地点",
    "en": "Searched or manually entered place",
    "es": "Lugar buscado o introducido manualmente",
    "de": "Gesuchter oder manuell eingegebener Ort",
}

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = os.getenv(
    "GEOCODER_USER_AGENT",
    "nanami-products-astro-earth/1.0 (+https://chart.nanami-astro.com)",
)
TIMEOUT_SECONDS = float(os.getenv("GEOCODER_TIMEOUT_SECONDS", "5"))
DEFAULT_LIMIT = 5

_CACHE_MAX = 256
_cache: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()


class GeocodingError(RuntimeError):
    """ジオコーディングの外部通信・応答エラー（HTTP 502 相当）。"""


def _nominatim_provider(query: str, limit: int, lang: str) -> list[dict[str, Any]]:
    """Nominatim を叩いて生の結果（name/lat/lon/display_name）を返す。"""
    params = urllib.parse.urlencode({
        "q": query,
        "format": "jsonv2",
        "limit": str(limit),
        "accept-language": lang,
    })
    req = urllib.request.Request(
        f"{NOMINATIM_URL}?{params}",
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise GeocodingError(str(exc)) from exc

    raw: list[dict[str, Any]] = []
    if isinstance(payload, list):
        for item in payload:
            if not isinstance(item, dict):
                continue
            try:
                lat = float(item["lat"])
                lon = float(item["lon"])
            except (KeyError, TypeError, ValueError):
                continue
            display = str(item.get("display_name") or "").strip()
            name = str(item.get("name") or "").strip() or display
            raw.append({"name": name, "latitude": lat, "longitude": lon, "display_name": display or name})
    return raw


# 差し替えポイント。テストやプロバイダ変更ではここを置き換える。
_provider: Callable[[str, int, str], list[dict[str, Any]]] = _nominatim_provider


def _normalize(raw: dict[str, Any], *, lang: str) -> dict[str, Any]:
    name = (raw.get("name") or raw.get("display_name") or "").strip() or None
    display_name = (raw.get("display_name") or raw.get("name") or "").strip() or (name or "")
    return {
        "name": name,
        "latitude": round(float(raw["latitude"]), 6),
        "longitude": round(float(raw["longitude"]), 6),
        "display_name": display_name,
        "source": SOURCE,
        "source_label": SOURCE_LABELS.get(lang, SOURCE_LABELS["en"]),
    }


def search(query: str, *, limit: int = DEFAULT_LIMIT, lang: str = "ja") -> list[dict[str, Any]]:
    """地名を検索して内部共通形式のリストを返す。空クエリは空リスト。"""
    q = (query or "").strip()
    if not q:
        return []
    safe_lang = lang if lang in SOURCE_LABELS else "en"
    key = f"{safe_lang}:{q.lower()}"
    cached = _cache.get(key)
    if cached is not None:
        _cache.move_to_end(key)
        return [dict(item) for item in cached]

    # Keep compatibility with existing two-argument provider adapters while the
    # built-in provider receives the requested language.
    if len(inspect.signature(_provider).parameters) >= 3:
        raw_results = _provider(q, limit, safe_lang)
    else:
        raw_results = _provider(q, limit)  # type: ignore[call-arg]
    results = [_normalize(item, lang=safe_lang) for item in raw_results]

    _cache[key] = [dict(item) for item in results]
    _cache.move_to_end(key)
    while len(_cache) > _CACHE_MAX:
        _cache.popitem(last=False)
    return results
