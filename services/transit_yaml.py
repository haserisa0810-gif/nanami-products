from __future__ import annotations

import math
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import swisseph as swe
import yaml

from services.western_calc import PLANETS, calc_aspects, configure_ephemeris, ephemeris_debug_info, sign_of

TRANSIT_ONLY_FORMAT = "transit-only-yaml-v1"

PLANET_KEYS = {
    "Sun": "sun",
    "Moon": "moon",
    "Mercury": "mercury",
    "Venus": "venus",
    "Mars": "mars",
    "Jupiter": "jupiter",
    "Saturn": "saturn",
    "Uranus": "uranus",
    "Neptune": "neptune",
    "Pluto": "pluto",
}

TRANSIT_ONLY_PROMPT = """あなたは占星術と歴史解釈を扱う分析者です。以下のYAMLは、特定イベント日時・場所の天体配置だけを記録した計算済みデータです。

重要ルール:
- 天体位置・月相・アスペクトの計算結果は変更しないでください。
- 日付や場所から再計算しないでください。
- YAML内の計算結果を唯一の根拠として解釈してください。
- このYAMLは出生図ではありません。個人の性格診断として読まないでください。
- 歴史イベントの日付には諸説があり得るため、断定しすぎず、象徴的な読みとして扱ってください。
- house が null の場合、ハウス解釈は行わないでください。

出力してほしい内容:
- イベント時点の天体配置の全体像
- 太陽・月・主要個人天体の特徴
- 社会天体・時代天体の特徴
- 月相から見た局面
- タイトなアスペクトの優先解釈
- 歴史解釈やテーマ分析に使う場合の注意点

以下のYAMLを読み込んで分析してください。
"""

TRANSIT_ONLY_PROMPTS = {
    "ja": TRANSIT_ONLY_PROMPT,
    "en": """You are an analyst working with astrology and historical interpretation. The following YAML contains pre-calculated planetary data for one event, time and place.

Rules:
- Do not change or recalculate planetary positions, lunar phase or aspects.
- Treat the YAML as the sole source for astronomical values.
- This is not a birth chart; do not read it as a personality profile.
- Historical dates may be disputed, so frame conclusions as symbolic interpretation rather than certainty.
- If house is null, do not interpret houses.

Cover the overall pattern, personal and social planets, lunar phase, the tightest aspects, and appropriate cautions for historical interpretation. Analyze the YAML below.""",
    "es": """Eres especialista en astrología e interpretación histórica. El siguiente YAML contiene datos planetarios ya calculados para un evento, una hora y un lugar concretos.

Reglas:
- No cambies ni recalcules las posiciones, la fase lunar ni los aspectos.
- Usa el YAML como única fuente de los valores astronómicos.
- No es una carta natal; no lo interpretes como un perfil de personalidad.
- Las fechas históricas pueden ser discutidas, así que presenta las conclusiones como una lectura simbólica y no como certezas.
- Si house es null, no interpretes las casas.

Explica el patrón general, los planetas personales y sociales, la fase lunar, los aspectos más cerrados y las cautelas necesarias para una interpretación histórica. Analiza el YAML que aparece a continuación.""",
    "de": """Du analysierst Astrologie im historischen Kontext. Die folgende YAML-Datei enthält bereits berechnete Planetendaten für ein bestimmtes Ereignis an einem bestimmten Ort und Zeitpunkt.

Regeln:
- Verändere oder berechne Planetenpositionen, Mondphase und Aspekte nicht neu.
- Verwende die YAML-Daten als einzige Quelle für astronomische Werte.
- Dies ist kein Geburtshoroskop; deute es nicht als Persönlichkeitsprofil.
- Historische Datierungen können umstritten sein. Formuliere Ergebnisse daher als symbolische Deutung, nicht als Gewissheit.
- Wenn house null ist, deute keine Häuser.

Beschreibe das Gesamtbild, persönliche und gesellschaftliche Planeten, die Mondphase, die engsten Aspekte und notwendige Hinweise zur historischen Einordnung. Analysiere die folgende YAML-Datei.""",
}


def _parse_timezone(value: str) -> timezone | ZoneInfo:
    raw = (value or "Asia/Tokyo").strip()
    if raw.upper() == "UTC":
        return timezone.utc
    offset_match = re.fullmatch(r"([+-])(\d{1,2})(?::?(\d{2}))?", raw)
    if offset_match:
        sign, hours, minutes = offset_match.groups()
        delta = timedelta(hours=int(hours), minutes=int(minutes or 0))
        return timezone(delta if sign == "+" else -delta)
    try:
        return ZoneInfo(raw)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"タイムゾーンが見つかりません: {raw}") from exc


def _parse_local_datetime(date_value: str, time_value: str, timezone_value: str) -> datetime:
    date_text = (date_value or "").strip()
    time_text = (time_value or "12:00").strip()
    if len(time_text.split(":")) == 2:
        time_text = f"{time_text}:00"
    try:
        naive = datetime.fromisoformat(f"{date_text}T{time_text}")
    except ValueError as exc:
        raise ValueError("日付または時刻の形式が不正です。日付は YYYY-MM-DD、時刻は HH:MM で入力してください。") from exc
    return naive.replace(tzinfo=_parse_timezone(timezone_value))


def _julian_day_ut(local_dt: datetime, input_calendar: str) -> float:
    calendar_flag = swe.JUL_CAL if input_calendar == "julian" else swe.GREG_CAL
    offset_hours = local_dt.utcoffset().total_seconds() / 3600 if local_dt.utcoffset() else 0.0
    local_hour = local_dt.hour + local_dt.minute / 60 + local_dt.second / 3600
    return swe.julday(local_dt.year, local_dt.month, local_dt.day, local_hour, calendar_flag) - offset_hours / 24


def _normalized_gregorian_date(local_dt: datetime, input_calendar: str) -> str:
    calendar_flag = swe.JUL_CAL if input_calendar == "julian" else swe.GREG_CAL
    local_hour = local_dt.hour + local_dt.minute / 60 + local_dt.second / 3600
    year, month, day, _hour = swe.revjul(
        swe.julday(local_dt.year, local_dt.month, local_dt.day, local_hour, calendar_flag),
        swe.GREG_CAL,
    )
    return f"{year:04d}-{month:02d}-{day:02d}"


def _phase_label(elongation: float) -> str:
    if elongation < 22.5 or elongation >= 337.5:
        return "new_moon"
    if elongation < 67.5:
        return "waxing_crescent"
    if elongation < 112.5:
        return "first_quarter"
    if elongation < 157.5:
        return "waxing_gibbous"
    if elongation < 202.5:
        return "full_moon"
    if elongation < 247.5:
        return "waning_gibbous"
    if elongation < 292.5:
        return "last_quarter"
    return "waning_crescent"


def _lunar_payload(sun_lon: float, moon_lon: float) -> dict[str, Any]:
    elongation = (moon_lon - sun_lon) % 360
    illumination = (1 - math.cos(math.radians(elongation))) / 2
    return {
        "phase": _phase_label(elongation),
        "illumination": round(illumination, 4),
        "elongation": round(elongation, 4),
    }


def build_transit_only_yaml(
    *,
    event_name: str,
    event_date: str,
    event_time: str,
    location_name: str,
    latitude: float,
    longitude: float,
    timezone_name: str,
    input_calendar: str = "gregorian",
    calendar_note: str = "歴史日付は諸説あり。必要に応じて検証してください。",
    lang: str = "ja",
) -> tuple[str, str, dict[str, Any]]:
    calendar = (input_calendar or "gregorian").strip().lower()
    if calendar not in {"gregorian", "julian"}:
        raise ValueError("暦種別は Gregorian または Julian を選択してください。")

    local_dt = _parse_local_datetime(event_date, event_time, timezone_name)
    jd_ut = _julian_day_ut(local_dt, calendar)
    normalized_date = _normalized_gregorian_date(local_dt, calendar)
    engine_flag = configure_ephemeris()
    flags = engine_flag | swe.FLG_SPEED

    planet_items: list[dict[str, Any]] = []
    planets: dict[str, Any] = {}
    sun_lon = moon_lon = None
    for name, body_id in PLANETS:
        xx, _ = swe.calc_ut(jd_ut, body_id, flags)
        sign, degree = sign_of(xx[0])
        item = {
            "name": name,
            "lon": round(xx[0] % 360, 6),
            "sign": sign,
            "degree": round(degree, 6),
            "retrograde": bool(xx[3] < 0),
            "house": None,
        }
        planet_items.append(item)
        planets[PLANET_KEYS[name]] = {
            "sign": item["sign"],
            "degree": item["degree"],
            "longitude": item["lon"],
            "retrograde": item["retrograde"],
            "house": None,
        }
        if name == "Sun":
            sun_lon = item["lon"]
        elif name == "Moon":
            moon_lon = item["lon"]

    aspects = [
        {
            "planet1": aspect["planet1"].lower().replace(" ", "_"),
            "planet2": aspect["planet2"].lower().replace(" ", "_"),
            "aspect": aspect["type"],
            "orb": aspect["orb"],
        }
        for aspect in calc_aspects(planet_items)
    ]

    doc = {
        "version": "nanami-products-yaml-v1",
        "product": {
            "type": "transit_only_yaml",
            "options": {
                "western_natal": False,
                "asteroids": False,
                "transit": True,
                "shichusuimei": False,
                "natal_required": False,
            },
        },
        "event": {
            "name": event_name.strip(),
            "date": normalized_date,
            "time": local_dt.strftime("%H:%M"),
            "timezone": timezone_name.strip(),
            "location": {
                "name": location_name.strip(),
                "latitude": latitude,
                "longitude": longitude,
            },
            "calendar": {
                "input_calendar": calendar,
                "normalized_calendar": "gregorian",
                "note": calendar_note.strip() or "歴史日付は諸説あり。必要に応じて検証してください。",
            },
        },
        "transit": {
            "planets": planets,
            "lunar": _lunar_payload(float(sun_lon), float(moon_lon)),
            "aspects": aspects,
        },
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "engine": "swisseph",
            "ephemeris": ephemeris_debug_info(),
            "format": TRANSIT_ONLY_FORMAT,
            "disclaimer": "このログは天文計算データであり、歴史解釈や占断はAI側で行います。",
        },
    }
    yaml_text = yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=120)
    prompt = TRANSIT_ONLY_PROMPTS.get(lang, TRANSIT_ONLY_PROMPTS["en"])
    return yaml_text, prompt.strip() + "\n", doc
