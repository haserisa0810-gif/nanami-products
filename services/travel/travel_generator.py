"""travel_report YAML を生成する中心処理。

処理順:
1. 出生YAMLから出生日時(UTC)を抽出（既存 acg_api を再利用）
2. 入力値を検証（日付・目的・緯度経度）
3. 旅行先情報を作る（location_engine）
4. ACG情報を取得（既存 acg_core を再利用し、旅行先に近い線を抽出）
5. リロケーションチャートを計算（出生時刻・旅行先の緯度経度でハウス再計算）
6. 旅行期間中のトランジットを計算
7. travel_report YAML を生成
8. AI解釈用プロンプトを生成
9. （呼び出し側で）結果を保存し token を返す

占術計算はすべて計算済みデータとして YAML に載せ、AI には再計算させない。
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

import swisseph as swe
import yaml

from services.acg_api import natal_dt_utc_from_yaml
from services.acg_core import ANGLE_THEME, PLANET_JA, PLANET_THEME, lines_to_geojson
from services.travel.location_engine import build_location, distance_point_to_line_km
from services.travel.travel_prompt import build_travel_prompt
from services.travel.travel_schema import (
    APP_NAME,
    SCHEMA_VERSION,
    TravelInput,
    TravelPurpose,
    TravelStay,
    is_valid_purpose,
    purpose_label,
)
from services.travel.travel_scoring import (
    HARD_ASPECTS,
    compute_score,
    recommended_actions,
)
from services.western_calc import PLANETS, configure_ephemeris, house_of, norm360, sign_of

MAX_YAML_BYTES = 256 * 1024
MAX_TRAVEL_DAYS = 40  # トランジット計算の暴走を防ぐ上限（MVP）

ASPECT_ANGLES = {
    "conjunction": 0.0,
    "sextile": 60.0,
    "square": 90.0,
    "trine": 120.0,
    "opposition": 180.0,
}
ASPECT_JA = {
    "conjunction": "重なり",
    "sextile": "調和(60度)",
    "square": "緊張(90度)",
    "trine": "好調(120度)",
    "opposition": "対向(180度)",
}
# トランジット天体ごとのオーブ許容（度）。速い天体ほど狭く。
TRANSIT_ORB = {
    "Sun": 1.5, "Mercury": 1.5, "Venus": 1.5, "Mars": 1.5, "Moon": 3.0,
    "Jupiter": 2.5, "Saturn": 2.5, "Uranus": 2.0, "Neptune": 2.0, "Pluto": 2.0,
}
ANGULAR_HOUSES = {1, 4, 7, 10}


class TravelInputError(ValueError):
    """旅行診断の入力エラー（HTTP 400 相当）。"""


# ─── 入力検証 ──────────────────────────────────────────────

def _validate_dates(arrival: str, departure: str) -> TravelStay:
    try:
        a = date.fromisoformat((arrival or "").strip())
    except ValueError as exc:
        raise TravelInputError("出発日は YYYY-MM-DD 形式で入力してください。") from exc
    try:
        d = date.fromisoformat((departure or "").strip())
    except ValueError as exc:
        raise TravelInputError("帰着日は YYYY-MM-DD 形式で入力してください。") from exc
    if d < a:
        raise TravelInputError("帰着日は出発日と同じか、それより後の日付にしてください。")
    days = (d - a).days + 1
    if days > MAX_TRAVEL_DAYS:
        raise TravelInputError(f"MVPでは旅行期間は最大{MAX_TRAVEL_DAYS}日までに対応しています。")
    return TravelStay(arrival_date=a.isoformat(), departure_date=d.isoformat(), days=days)


def _validate_yaml_size(yaml_text: str) -> str:
    text = (yaml_text or "").strip()
    if not text:
        raise TravelInputError("出生YAMLを貼り付けてください。")
    if len(text.encode("utf-8")) > MAX_YAML_BYTES:
        raise TravelInputError("YAMLが大きすぎます。256KB以内にしてください。")
    return text


# ─── 天体計算 ──────────────────────────────────────────────

def _julday_utc(dt_utc: datetime) -> float:
    utc = dt_utc.astimezone(timezone.utc)
    ut = utc.hour + utc.minute / 60.0 + utc.second / 3600.0
    return swe.julday(utc.year, utc.month, utc.day, ut)


def _natal_planets(jd: float, flags: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for name, body_id in PLANETS:
        xx, _ = swe.calc_ut(jd, body_id, flags)
        out.append({"name": name, "lon": norm360(xx[0])})
    return out


def _relocation(jd: float, lat: float, lon: float, natal_planets: list[dict[str, Any]]) -> dict[str, Any]:
    """出生時刻・旅行先の緯度経度でハウスを再計算する（リロケーション）。"""
    cusps: list[float] = []
    asc = mc = None
    for hsys in (b"P", b"W"):
        try:
            cusps_, ascmc = swe.houses(jd, lat, lon, hsys)
            cusps = list(cusps_)[:12]
            asc, mc = ascmc[0], ascmc[1]
            break
        except Exception:
            continue

    reloc_planets: list[dict[str, Any]] = []
    house_counts: dict[int, int] = {}
    for p in natal_planets:
        house = house_of(p["lon"], cusps) if cusps else None
        sign, _deg = sign_of(p["lon"])
        reloc_planets.append({"name": p["name"], "sign": sign, "house": house})
        if house is not None:
            house_counts[house] = house_counts.get(house, 0) + 1

    house_theme = {
        1: "自分の見せ方・第一印象", 2: "お金・所有・価値観", 3: "学び・移動・情報",
        4: "住まい・家族・安心", 5: "創作・遊び・自己表現", 6: "習慣・健康・役割",
        7: "出会い・パートナーシップ", 8: "深い関わり・変容", 9: "旅・学び・異文化",
        10: "仕事・社会的な見え方", 11: "仲間・つながり・希望", 12: "休息・内面・癒やし",
    }
    house_emphasis = [
        {"house": h, "theme": house_theme.get(h, ""), "natal_body_count": c}
        for h, c in sorted(house_counts.items(), key=lambda kv: (-kv[1], kv[0]))
        if c >= 1
    ][:4]

    result: dict[str, Any] = {"house_emphasis": house_emphasis, "planets": reloc_planets}
    if asc is not None:
        s, d = sign_of(asc)
        result["ascendant"] = {"sign": s, "degree": round(d, 4)}
    if mc is not None:
        s, d = sign_of(mc)
        result["midheaven"] = {"sign": s, "degree": round(d, 4)}
    return result


def _nearest_acg_lines(dt_utc: datetime, lat: float, lon: float, *, limit: int = 5) -> list[dict[str, Any]]:
    """旅行先に近い出生 ACG 線を抽出する。既存の lines_to_geojson を再利用。"""
    geojson = lines_to_geojson(dt_utc, natal=True)
    best_by_group: dict[str, dict[str, Any]] = {}
    for feature in geojson.get("features", []):
        props = feature.get("properties") or {}
        group = props.get("line_group")
        if not group:
            continue
        coords = (feature.get("geometry") or {}).get("coordinates") or []
        is_meridian = props.get("line_type") == "meridian"
        dist = distance_point_to_line_km(lat, lon, coords, is_meridian=is_meridian)
        prev = best_by_group.get(group)
        if prev is None or dist < prev["distance_km"]:
            planet = props.get("planet")
            angle = props.get("angle")
            best_by_group[group] = {
                "planet": planet,
                "angle": angle,
                "distance_km": round(dist, 1),
                "meaning_hint": f"{PLANET_THEME.get(planet, planet)} / {ANGLE_THEME.get(angle, angle)}",
            }
    ordered = sorted(best_by_group.values(), key=lambda x: x["distance_km"])
    return ordered[:limit]


def _transit_highlights(
    stay: TravelStay,
    natal_planets: list[dict[str, Any]],
    relocation: dict[str, Any],
    flags: int,
) -> list[dict[str, Any]]:
    """滞在期間中の主要トランジット（対 出生天体・対 リロケーション角）を抽出。"""
    targets: list[tuple[str, float]] = [(f"natal {p['name']}", p["lon"]) for p in natal_planets]
    asc = relocation.get("ascendant")
    mc = relocation.get("midheaven")
    if isinstance(asc, dict):
        targets.append(("relocated ASC", _sign_degree_to_lon(asc)))
    if isinstance(mc, dict):
        targets.append(("relocated MC", _sign_degree_to_lon(mc)))

    start = date.fromisoformat(stay.arrival_date)
    end = date.fromisoformat(stay.departure_date)
    candidates: dict[tuple[str, str, str], dict[str, Any]] = {}

    day = start
    while day <= end:
        jd = swe.julday(day.year, day.month, day.day, 12.0)
        for name, body_id in PLANETS:
            xx, _ = swe.calc_ut(jd, body_id, flags)
            t_lon = norm360(xx[0])
            orb_limit = TRANSIT_ORB.get(name, 1.5)
            for target_label, target_lon in targets:
                sep = _angle_diff(t_lon, target_lon)
                for aspect, angle in ASPECT_ANGLES.items():
                    orb = abs(sep - angle)
                    if orb <= orb_limit:
                        key = (name, target_label, aspect)
                        prev = candidates.get(key)
                        if prev is None or orb < prev["orb"]:
                            candidates[key] = {
                                "date": day.isoformat(),
                                "body": name,
                                "aspect": aspect,
                                "target": target_label,
                                "orb": round(orb, 2),
                                "meaning_hint": f"{PLANET_THEME.get(name, name)} / {ASPECT_JA.get(aspect, aspect)}",
                            }
        day = day.fromordinal(day.toordinal() + 1)

    ordered = sorted(candidates.values(), key=lambda x: x["orb"])
    highlights: list[dict[str, Any]] = []
    moon_count = 0
    for hl in ordered:
        if hl["body"] == "Moon":
            if moon_count >= 3:
                continue
            moon_count += 1
        highlights.append(hl)
        if len(highlights) >= 8:
            break
    return highlights


_SIGN_INDEX = {name: i for i, name in enumerate(
    ["Ari", "Tau", "Gem", "Can", "Leo", "Vir", "Lib", "Sco", "Sag", "Cap", "Aqu", "Pis"]
)}


def _sign_degree_to_lon(block: dict[str, Any]) -> float:
    idx = _SIGN_INDEX.get(str(block.get("sign") or "Ari"), 0)
    return norm360(idx * 30.0 + float(block.get("degree") or 0.0))


def _angle_diff(a: float, b: float) -> float:
    d = abs(norm360(a) - norm360(b))
    return min(d, 360.0 - d)


# ─── テーマ・注意点（決定的な下地） ────────────────────────

def _themes(purpose_key: str, nearest_lines: list[dict[str, Any]], relocation: dict[str, Any]) -> list[str]:
    themes: list[str] = []
    for line in nearest_lines[:2]:
        if float(line.get("distance_km") or 9e9) <= 700:
            planet_ja = PLANET_JA.get(line.get("planet"), line.get("planet"))
            themes.append(f"{planet_ja}{line.get('angle')}線の影響：{line.get('meaning_hint')}")
    for h in relocation.get("house_emphasis", [])[:2]:
        if h.get("theme"):
            themes.append(f"リロケーションで{h.get('house')}ハウス（{h.get('theme')}）が強調されやすい")
    if not themes:
        themes.append("特定テーマへの強い偏りは控えめ。旅そのものを味わう時間になりやすい")
    return themes[:4]


def _cautions(purpose_key: str, transit_highlights: list[dict[str, Any]]) -> list[str]:
    cautions = ["予定を詰め込みすぎない", "体調と睡眠を優先する"]
    if any(hl.get("aspect") in HARD_ASPECTS for hl in transit_highlights):
        cautions.append("滞在中に緊張しやすい配置があるので、無理をせず余白を持って動く")
    return cautions[:4]


# ─── メイン ────────────────────────────────────────────────

def build_travel_report(
    *,
    natal_yaml_text: str,
    purpose_key: str,
    location_name: str,
    country: str,
    latitude: Any,
    longitude: Any,
    timezone_name: str | None,
    arrival_date: str,
    departure_date: str,
) -> dict[str, Any]:
    """travel_report を生成し、yaml_text / prompt_text / doc / summary を返す。"""
    yaml_text = _validate_yaml_size(natal_yaml_text)
    if not is_valid_purpose(purpose_key):
        raise TravelInputError("旅行目的を選択してください。")
    stay = _validate_dates(arrival_date, departure_date)
    location = build_location(
        name=location_name, country=country, latitude=latitude, longitude=longitude, timezone=timezone_name,
    )

    # 出生日時（UTC）を抽出（対応外YAMLは AcgYamlFormatError を送出 → 呼び出し側で 400/422）
    natal_dt_utc = natal_dt_utc_from_yaml(yaml_text)

    flags = configure_ephemeris() | swe.FLG_SPEED
    natal_jd = _julday_utc(natal_dt_utc)
    natal_planets = _natal_planets(natal_jd, flags)

    nearest_lines = _nearest_acg_lines(natal_dt_utc, location.latitude, location.longitude)
    relocation = _relocation(natal_jd, location.latitude, location.longitude, natal_planets)
    transit_highlights = _transit_highlights(stay, natal_planets, relocation, flags)

    scoring = compute_score(
        purpose_key=purpose_key,
        nearest_lines=nearest_lines,
        relocation_houses=relocation.get("house_emphasis", []),
        relocation_planets=relocation.get("planets", []),
        transit_highlights=transit_highlights,
    )

    purpose = TravelPurpose(key=purpose_key, label=purpose_label(purpose_key))
    themes = _themes(purpose_key, nearest_lines, relocation)
    actions = recommended_actions(purpose_key)
    cautions = _cautions(purpose_key, transit_highlights)

    travel_input = TravelInput(natal_yaml_text=yaml_text, purpose=purpose, location=location, stay=stay)

    doc = _build_doc(
        travel_input=travel_input,
        nearest_lines=nearest_lines,
        relocation=relocation,
        transit_highlights=transit_highlights,
        stay=stay,
        scoring=scoring,
        themes=themes,
        actions=actions,
        cautions=cautions,
    )
    yaml_out = yaml.safe_dump({"travel_report": doc}, allow_unicode=True, sort_keys=False, width=120)
    prompt_text = build_travel_prompt()

    summary = {
        "location": location.to_dict(),
        "stay": stay.to_dict(),
        "purpose": purpose.to_dict(),
        "scoring": scoring,
        "themes": themes,
        "recommended_actions": actions,
        "cautions": cautions,
        "nearest_lines": nearest_lines,
        "relocation": relocation,
        "transit_highlights": transit_highlights,
    }
    return {"yaml_text": yaml_out, "prompt_text": prompt_text, "doc": doc, "summary": summary}


def _build_doc(
    *,
    travel_input: TravelInput,
    nearest_lines: list[dict[str, Any]],
    relocation: dict[str, Any],
    transit_highlights: list[dict[str, Any]],
    stay: TravelStay,
    scoring: dict[str, Any],
    themes: list[str],
    actions: list[str],
    cautions: list[str],
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "app": APP_NAME,
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "input": {
            "purpose": travel_input.purpose.to_dict(),
            "stay": stay.to_dict(),
            "location": travel_input.location.to_dict(),
        },
        "source": {
            "natal_yaml_summary": {
                "owner_label": "user",
                "birth_data_present": True,
            },
        },
        "acg": {"nearest_lines": nearest_lines},
        "relocation": relocation,
        "transit": {
            "period": {"start": stay.arrival_date, "end": stay.departure_date},
            "highlights": transit_highlights,
        },
        "scoring": scoring,
        "interpretation": {
            "summary": "",
            "themes": themes,
            "recommended_actions": actions,
            "cautions": cautions,
        },
    }
