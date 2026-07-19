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
import re
from typing import Any

import yaml
from yaml.events import AliasEvent

from services.acg_core import lines_to_geojson
from services.yaml_exporter import read_body_house, read_natal_angles

# 貼り付け YAML の受け入れ上限（仕様: 256KB 程度で 413）
MAX_YAML_BYTES = 256 * 1024
MAX_YAML_DOCUMENTS = 8
MAX_YAML_DEPTH = 40
MAX_YAML_ALIASES = 50
MAX_YAML_NODES = 20_000

YAML_PARSE_ERROR = (
    "YAMLを解析できませんでした。インデントやYAMLコードブロックの囲み方を確認してください。"
)
YAML_MISSING_BIRTH_DATA_ERROR = (
    "YAMLは読み込めましたが、ACG計算に必要な出生日時データが見つかりませんでした。"
    "必要項目: systems.western.natal.subject.datetime、または input.birth_date"
    "（任意: input.birth_time、input.timezone_offset_hours）"
)
YAML_AMBIGUOUS_DOCUMENT_ERROR = (
    "出生日時データを含むYAMLドキュメントが複数見つかりました。"
    "ACGへ読み込む占術データを1件だけ含めてください。"
)
ACG_BIRTH_TIME_NOT_CONFIRMED_ERROR = (
    "アストロカートグラフィの計算には、正確な出生時刻が必要です。"
    "出生時刻が不明・推定・暫定の場合、線が世界規模で大きく移動するため生成できません。"
)
ACG_TIMEZONE_NOT_CONFIRMED_ERROR = (
    "出生地のタイムゾーンを確認できませんでした。"
    "タイムゾーン名とUTCオフセットが記録された鑑定YAMLを使用してください。"
)
ACG_BIRTH_PLACE_MISSING_ERROR = (
    "出生地を確認できませんでした。出生地が記録された鑑定YAMLを使用してください。"
)

_YAML_FENCE_RE = re.compile(
    r"\A\s*```(?:yaml|yml)?[ \t]*\r?\n(?P<body>[\s\S]*?)\r?\n```[ \t]*\s*\Z",
    re.IGNORECASE,
)
_EMBEDDED_YAML_FENCE_RE = re.compile(
    r"^```(?:yaml|yml)[ \t]*\r?\n(?P<body>[\s\S]*?)\r?\n```[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)

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


class _AcgSafeLoader(yaml.SafeLoader):
    """SafeLoader に入力複雑度の上限を加えた ACG 専用ローダー。"""

    def __init__(self, stream: Any) -> None:
        super().__init__(stream)
        self._acg_depth = 0
        self._acg_aliases = 0
        self._acg_nodes = 0

    def compose_node(self, parent: Any, index: Any) -> Any:
        if self.check_event(AliasEvent):
            self._acg_aliases += 1
            if self._acg_aliases > MAX_YAML_ALIASES:
                raise yaml.YAMLError("YAML alias limit exceeded")
        self._acg_depth += 1
        self._acg_nodes += 1
        try:
            if self._acg_depth > MAX_YAML_DEPTH:
                raise yaml.YAMLError("YAML nesting limit exceeded")
            if self._acg_nodes > MAX_YAML_NODES:
                raise yaml.YAMLError("YAML node limit exceeded")
            return super().compose_node(parent, index)
        finally:
            self._acg_depth -= 1


def _load_yaml_documents(yaml_text: str) -> list[Any]:
    try:
        return list(yaml.load_all(yaml_text, Loader=_AcgSafeLoader))
    except (yaml.YAMLError, RecursionError) as exc:
        raise AcgYamlFormatError(YAML_PARSE_ERROR) from exc


def _as_mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _western_natal(doc: dict[str, Any]) -> dict[str, Any]:
    systems = _as_mapping(doc.get("systems"))
    western = _as_mapping(systems.get("western"))
    return _as_mapping(western.get("natal"))


def _has_supported_birth_source(doc: dict[str, Any]) -> bool:
    subject = _as_mapping(_western_natal(doc).get("subject"))
    input_block = _as_mapping(doc.get("input"))
    return bool(
        subject.get("datetime") or input_block.get("birth_date")
    )


def _normalize_acg_document(doc: dict[str, Any]) -> dict[str, Any]:
    """ACGが参照する既知セクションだけを新しいマッピングへ抽出する。"""
    source_natal = _western_natal(doc)
    natal = {
        key: dict(value)
        for key in ("subject", "bodies", "angles", "time_sensitive_provisional")
        if isinstance((value := source_natal.get(key)), dict)
    }
    input_block = _as_mapping(doc.get("input"))
    normalized_input = {
        key: input_block[key]
        for key in (
            "birth_date",
            "birth_time",
            "calculation_time",
            "timezone_offset_hours",
            "timezone",
            "birth_place",
            "birth_lat",
            "birth_lng",
            "birth_time_accuracy",
            "birth_time_note",
        )
        if key in input_block
    }
    birth_time = _as_mapping(doc.get("birth_time"))
    normalized_birth_time = (
        {"accuracy": birth_time["accuracy"]} if "accuracy" in birth_time else {}
    )
    return {
        "systems": {"western": {"natal": natal}},
        "input": normalized_input,
        "birth_time": normalized_birth_time,
    }


def parse_acg_yaml_document(yaml_text: str) -> dict[str, Any]:
    """安全にYAMLを読み、既知の出生日時パスを持つ文書だけを選択する。"""
    if not yaml_text or not yaml_text.strip():
        raise AcgYamlFormatError("占術YAMLを貼り付けてください。")
    if len(yaml_text.encode("utf-8")) > MAX_YAML_BYTES:
        raise AcgYamlFormatError("YAMLテキストが大きすぎます（上限256KB）。")

    stripped = yaml_text.strip()
    outer_fence = _YAML_FENCE_RE.fullmatch(stripped)
    embedded = list(_EMBEDDED_YAML_FENCE_RE.finditer(stripped))
    outer_is_explicit_yaml = stripped.lower().startswith(("```yaml", "```yml"))
    if outer_fence and (not outer_is_explicit_yaml or len(embedded) == 1):
        documents = _load_yaml_documents(outer_fence.group("body"))
    else:
        try:
            documents = _load_yaml_documents(yaml_text)
        except AcgYamlFormatError as full_parse_error:
            if len(embedded) > 1:
                raise AcgYamlFormatError(
                    "YAMLコードブロックが複数見つかりました。出生図を含むブロックを1つだけ貼り付けてください。"
                ) from full_parse_error
            if not embedded:
                if "```" in stripped:
                    raise AcgYamlFormatError(
                        "入力全文をYAMLとして解析できませんでした。前後に文章がある場合は、"
                        "YAMLコードブロックを ```yaml または ```yml で明示してください。"
                    ) from full_parse_error
                raise
            documents = _load_yaml_documents(embedded[0].group("body"))
    if len(documents) > MAX_YAML_DOCUMENTS:
        raise AcgYamlFormatError(
            f"YAMLドキュメントが多すぎます（上限{MAX_YAML_DOCUMENTS}件）。"
        )

    candidates = [
        doc
        for doc in documents
        if isinstance(doc, dict) and _has_supported_birth_source(doc)
    ]
    if not candidates:
        raise AcgYamlFormatError(YAML_MISSING_BIRTH_DATA_ERROR)
    if len(candidates) > 1:
        raise AcgYamlFormatError(YAML_AMBIGUOUS_DOCUMENT_ERROR)
    return _normalize_acg_document(candidates[0])


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
        raise AcgYamlFormatError("input.birth_time は HH:MM 形式で指定してください。")
    try:
        hour, minute = int(parts[0]), int(parts[1])
    except ValueError as exc:
        raise AcgYamlFormatError("input.birth_time は HH:MM 形式で指定してください。") from exc
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise AcgYamlFormatError("input.birth_time の時刻が有効範囲外です。")
    return hour, minute


def _from_subject_datetime(doc: dict[str, Any]) -> datetime | None:
    """優先パス: systems.western.natal.subject.datetime（ISO 8601 オフセット付き）。

    秒単位オフセット（LMT。例: +09:18:59）があり得る。subject.location は使わない
    （ネイタル ACG 線は出生時刻のみに依存し、出生地はハウス計算用）。
    """
    subject = _as_mapping(_western_natal(doc).get("subject"))
    raw = subject.get("datetime")
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(str(raw).strip())
    except ValueError as exc:
        raise AcgYamlFormatError(
            "systems.western.natal.subject.datetime はISO 8601形式で指定してください。"
        ) from exc
    if dt.tzinfo is None:
        raise AcgYamlFormatError(ACG_TIMEZONE_NOT_CONFIRMED_ERROR)
    return dt.astimezone(timezone.utc)


def _from_input_block(doc: dict[str, Any]) -> datetime | None:
    """フォールバック: input.birth_date + input.birth_time + input.timezone_offset_hours。"""
    input_block = _as_mapping(doc.get("input"))
    if not input_block.get("birth_date"):
        return None
    try:
        birth = date_type.fromisoformat(str(input_block["birth_date"]).strip())
    except ValueError as exc:
        raise AcgYamlFormatError("input.birth_date は YYYY-MM-DD 形式で指定してください。") from exc
    time_value = input_block.get("birth_time") or input_block.get("calculation_time")
    if not time_value:
        raise AcgYamlFormatError(ACG_BIRTH_TIME_NOT_CONFIRMED_ERROR)
    hour, minute = _parse_hh_mm(time_value)
    tz_raw = input_block.get("timezone_offset_hours")
    if tz_raw is None:
        raise AcgYamlFormatError(ACG_TIMEZONE_NOT_CONFIRMED_ERROR)
    try:
        tz_hours = float(tz_raw)
    except (TypeError, ValueError) as exc:
        raise AcgYamlFormatError(
            "input.timezone_offset_hours は数値で指定してください。"
        ) from exc
    if not (-24 < tz_hours < 24):
        raise AcgYamlFormatError(
            "input.timezone_offset_hours は -24 より大きく 24 より小さい値で指定してください。"
        )
    local = datetime(
        birth.year, birth.month, birth.day, hour, minute,
        tzinfo=timezone(timedelta(hours=tz_hours)),
    )
    return local.astimezone(timezone.utc)


def _natal_dt_utc_from_doc(doc: dict[str, Any]) -> datetime:
    dt_utc = _from_subject_datetime(doc)
    if dt_utc is None:
        dt_utc = _from_input_block(doc)
    if dt_utc is None:
        raise AcgYamlFormatError(YAML_MISSING_BIRTH_DATA_ERROR)
    return dt_utc


def _validate_acg_eligibility(doc: dict[str, Any]) -> None:
    """個人ACGを確定データだけに限定する入力ゲート。"""
    natal = _western_natal(doc)
    input_block = _as_mapping(doc.get("input"))
    birth_time = _as_mapping(doc.get("birth_time"))
    accuracy = str(
        birth_time.get("accuracy")
        or input_block.get("birth_time_accuracy")
        or ""
    ).strip().lower()
    provisional = bool(_as_mapping(natal.get("time_sensitive_provisional")))

    # 旧YAMLはaccuracyを持たないため、明示された出生時刻がある場合だけexact相当として扱う。
    explicit_time = input_block.get("birth_time")
    legacy_exact = not accuracy and bool(explicit_time) and str(explicit_time).lower() not in {
        "unknown", "approximate", "provisional", "12:00仮置き"
    }
    if provisional or (accuracy not in {"exact", "confirmed"} and not legacy_exact):
        raise AcgYamlFormatError(ACG_BIRTH_TIME_NOT_CONFIRMED_ERROR)

    if not input_block.get("timezone") or input_block.get("timezone_offset_hours") is None:
        raise AcgYamlFormatError(ACG_TIMEZONE_NOT_CONFIRMED_ERROR)

    has_place = bool(input_block.get("birth_place")) or (
        input_block.get("birth_lat") is not None and input_block.get("birth_lng") is not None
    )
    if not has_place:
        raise AcgYamlFormatError(ACG_BIRTH_PLACE_MISSING_ERROR)


def _acg_calculation_basis(doc: dict[str, Any], dt_utc: datetime) -> dict[str, Any]:
    input_block = _as_mapping(doc.get("input"))
    subject = _as_mapping(_western_natal(doc).get("subject"))
    local_datetime = subject.get("datetime")
    if not local_datetime:
        local_datetime = f"{input_block.get('birth_date')}T{input_block.get('calculation_time') or input_block.get('birth_time')}"
    offset_hours = float(input_block["timezone_offset_hours"])
    sign = "+" if offset_hours >= 0 else "-"
    absolute_minutes = round(abs(offset_hours) * 60)
    offset_text = f"{sign}{absolute_minutes // 60:02d}:{absolute_minutes % 60:02d}"
    return {
        "birth_datetime_local": str(local_datetime),
        "timezone": str(input_block["timezone"]),
        "utc_offset": offset_text,
        "birth_datetime_utc": dt_utc.isoformat().replace("+00:00", "Z"),
        "birth_time_status": "confirmed",
        "acg_eligible": True,
    }


def natal_dt_utc_from_yaml(yaml_text: str) -> datetime:
    """貼り付け YAML から出生日時（UTC）を抽出する。

    抽出パス優先順:
    1. systems.western.natal.subject.datetime
    2. input.birth_date + input.birth_time + input.timezone_offset_hours

    version が nanami-products-yaml-v1 でなくても、抽出パスが存在すれば処理続行。
    抽出パスが無ければ AcgYamlFormatError（422 相当）。
    """
    return _natal_dt_utc_from_doc(parse_acg_yaml_document(yaml_text))


def _format_natal_body(body: Any, *, include_house: bool) -> str | None:
    if not isinstance(body, dict):
        return None
    sign = body.get("sign") or body.get("sign_ja")
    if not sign:
        return None
    parts = [str(sign)]
    house = body.get("house")
    if include_house and house is not None:
        parts.append(f"{house}H")
    return " ".join(parts)


def _personal_context_from_doc(doc: dict[str, Any]) -> dict[str, Any]:
    natal = _western_natal(doc)
    bodies = dict(_as_mapping(natal.get("bodies")))
    safe_natal = dict(natal)
    safe_natal["bodies"] = bodies
    safe_natal["time_sensitive_provisional"] = _as_mapping(
        natal.get("time_sensitive_provisional")
    )
    angles = read_natal_angles(safe_natal)
    for key, name in (("asc", "ASC"), ("mc", "MC")):
        if isinstance(angles.get(key), dict):
            bodies.setdefault(name, angles[key])
    for name in ("Sun", "Moon"):
        body = bodies.get(name)
        if isinstance(body, dict) and body.get("house") is None:
            body = dict(body)
            body["house"] = read_body_house(safe_natal, name)
            bodies[name] = body
    natal_summary = {
        "sun": _format_natal_body(bodies.get("Sun"), include_house=True),
        "moon": _format_natal_body(bodies.get("Moon"), include_house=True),
        "asc": _format_natal_body(bodies.get("ASC"), include_house=False),
        "mc": _format_natal_body(bodies.get("MC"), include_house=False),
    }
    return {
        "source": "uploaded_birth_yaml",
        "natal_summary": natal_summary,
        "note": "出生図の詳しい解釈は、別途YAML本文を参照",
    }


def personal_context_from_yaml(yaml_text: str) -> dict[str, Any]:
    """AIへ渡すACG combined用に、出生YAMLから最小限の文脈だけ抽出する。"""
    return _personal_context_from_doc(parse_acg_yaml_document(yaml_text))


def personal_geojson(yaml_text: str) -> dict[str, Any]:
    """貼り付け YAML からパーソナル（ネイタル）ACG 線 GeoJSON を返す。保存しない。"""
    doc = parse_acg_yaml_document(yaml_text)
    _validate_acg_eligibility(doc)
    dt_utc = _natal_dt_utc_from_doc(doc)
    result = lines_to_geojson(dt_utc, natal=True)
    result.setdefault("meta", {})["personal_context"] = _personal_context_from_doc(doc)
    result["meta"]["acg_calculation_basis"] = _acg_calculation_basis(doc, dt_utc)
    birth_time = doc.get("birth_time") if isinstance(doc, dict) else {}
    input_block = doc.get("input") if isinstance(doc, dict) else {}
    accuracy = (
        (birth_time.get("accuracy") if isinstance(birth_time, dict) else None)
        or (input_block.get("birth_time_accuracy") if isinstance(input_block, dict) else None)
        or "confirmed"
    )
    result["time_sensitive_warning"] = False
    return result
