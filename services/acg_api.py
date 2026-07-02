"""ACG API 用のアプリケーション層。

- マンデン線: 対象日 03:00 UTC（= 日本時間の正午）固定。日付単位で全ユーザー共通
  なのでプロセス内メモリに日次キャッシュする。
- パーソナル線: 購入者向け YAML（nanami-products-yaml-v1）貼り付けテキストから
  出生日時のみを抽出してネイタル線を計算する。YAML 内の天体黄経は使わない
  （ACG 線には赤経・赤緯が必要で、Swiss Ephemeris での再計算が唯一正しい経路）。
  貼り付け内容はサーバーに保存せず、ログにも本文を出さない。
"""
from __future__ import annotations

from collections import OrderedDict
from datetime import date as date_type, datetime, timedelta, timezone
from typing import Any

import yaml

from services.acg_core import lines_to_geojson

# 貼り付け YAML の受け入れ上限（仕様: 256KB 程度で 413）
MAX_YAML_BYTES = 256 * 1024

# マンデン線の代表時刻（対象日の 03:00 UTC 固定 = 日本時間の正午時点の空）
MUNDANE_HOUR_UTC = 3

# マンデン側のみの日付範囲チェック（搭載エフェメリス sepl_18.se1 系: 1800〜2399年）。
# パーソナル側は過去日を弾かない（se1 範囲外は pyswisseph が Moshier 近似に
# 自動フォールバックする。歴史人物チャート対応のため必須）。
MUNDANE_MIN_YEAR = 1800
MUNDANE_MAX_YEAR = 2399

_MUNDANE_CACHE_MAX = 64
_mundane_cache: OrderedDict[str, dict[str, Any]] = OrderedDict()


class AcgInputError(ValueError):
    """利用者入力に起因するエラー（HTTP 400 相当）。"""


class AcgYamlFormatError(AcgInputError):
    """貼り付け YAML から出生日時を抽出できないエラー（HTTP 422 相当）。"""


def _validate_mundane_date(value: str) -> str:
    try:
        parsed = date_type.fromisoformat(str(value).strip())
    except ValueError as exc:
        raise AcgInputError("日付は YYYY-MM-DD 形式で指定してください。") from exc
    if not (MUNDANE_MIN_YEAR <= parsed.year <= MUNDANE_MAX_YEAR):
        raise AcgInputError(
            f"日付は {MUNDANE_MIN_YEAR}〜{MUNDANE_MAX_YEAR} 年の範囲で指定してください。"
        )
    return parsed.isoformat()


def mundane_geojson(date_value: str) -> dict[str, Any]:
    """指定日のマンデン ACG 線 GeoJSON を返す（日次メモリキャッシュ付き）。"""
    key = _validate_mundane_date(date_value)
    cached = _mundane_cache.get(key)
    if cached is not None:
        _mundane_cache.move_to_end(key)
        return cached
    target = date_type.fromisoformat(key)
    dt_utc = datetime(
        target.year, target.month, target.day, MUNDANE_HOUR_UTC, tzinfo=timezone.utc
    )
    result = lines_to_geojson(dt_utc, natal=False)
    _mundane_cache[key] = result
    while len(_mundane_cache) > _MUNDANE_CACHE_MAX:
        _mundane_cache.popitem(last=False)
    return result


def _parse_hh_mm(value: Any) -> tuple[int, int]:
    parts = str(value).strip().split(":")
    if len(parts) < 2:
        raise AcgYamlFormatError("対応していないYAML形式です")
    try:
        hour, minute = int(parts[0]), int(parts[1])
    except ValueError as exc:
        raise AcgYamlFormatError("対応していないYAML形式です") from exc
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise AcgYamlFormatError("対応していないYAML形式です")
    return hour, minute


def _from_subject_datetime(doc: dict[str, Any]) -> datetime | None:
    """優先パス: systems.western.natal.subject.datetime（ISO 8601 オフセット付き）。

    秒単位オフセット（LMT。例: +09:18:59）があり得る。subject.location は使わない
    （ネイタル ACG 線は出生時刻のみに依存し、出生地はハウス計算用）。
    """
    subject = (
        ((doc.get("systems") or {}).get("western") or {}).get("natal") or {}
    ).get("subject") or {}
    raw = subject.get("datetime")
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(str(raw).strip())
    except ValueError as exc:
        raise AcgYamlFormatError("対応していないYAML形式です") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone(timedelta(hours=9)))
    return dt.astimezone(timezone.utc)


def _from_input_block(doc: dict[str, Any]) -> datetime | None:
    """フォールバック: input.birth_date + input.birth_time + input.timezone_offset_hours。"""
    input_block = doc.get("input")
    if not isinstance(input_block, dict) or not input_block.get("birth_date"):
        return None
    try:
        birth = date_type.fromisoformat(str(input_block["birth_date"]).strip())
    except ValueError as exc:
        raise AcgYamlFormatError("対応していないYAML形式です") from exc
    time_value = (
        input_block.get("birth_time")
        or input_block.get("calculation_time")
        or "12:00"
    )
    hour, minute = _parse_hh_mm(time_value)
    tz_raw = input_block.get("timezone_offset_hours")
    try:
        tz_hours = float(tz_raw) if tz_raw is not None else 9.0
    except (TypeError, ValueError) as exc:
        raise AcgYamlFormatError("対応していないYAML形式です") from exc
    local = datetime(
        birth.year, birth.month, birth.day, hour, minute,
        tzinfo=timezone(timedelta(hours=tz_hours)),
    )
    return local.astimezone(timezone.utc)


def natal_dt_utc_from_yaml(yaml_text: str) -> datetime:
    """貼り付け YAML から出生日時（UTC）を抽出する。

    抽出パス優先順:
    1. systems.western.natal.subject.datetime
    2. input.birth_date + input.birth_time + input.timezone_offset_hours

    version が nanami-products-yaml-v1 でなくても、抽出パスが存在すれば処理続行。
    抽出パスが無ければ AcgYamlFormatError（422 相当）。
    """
    if not yaml_text or not yaml_text.strip():
        raise AcgYamlFormatError("対応していないYAML形式です")

    try:
        doc = yaml.safe_load(yaml_text)
    except yaml.YAMLError as exc:
        raise AcgYamlFormatError("対応していないYAML形式です") from exc
    if not isinstance(doc, dict):
        raise AcgYamlFormatError("対応していないYAML形式です")

    dt_utc = _from_subject_datetime(doc)
    if dt_utc is None:
        dt_utc = _from_input_block(doc)
    if dt_utc is None:
        raise AcgYamlFormatError("対応していないYAML形式です")
    return dt_utc


def personal_geojson(yaml_text: str) -> dict[str, Any]:
    """貼り付け YAML からパーソナル（ネイタル）ACG 線 GeoJSON を返す。保存しない。"""
    dt_utc = natal_dt_utc_from_yaml(yaml_text)
    return lines_to_geojson(dt_utc, natal=True)
