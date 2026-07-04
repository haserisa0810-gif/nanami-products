"""Astro Earth（3Dアストロカートグラフィ地球儀）のバックエンド。

3D表示そのものはフロント（Three.js）で行い、ACGラインは既存の
/api/acg/personal を流用する。ここでは「クリック地点」の洞察だけを担う:
出生YAML＋緯度経度から、近いACGラインとリロケーション概要を計算し、
さらに一般ユーザー向けの要約（一言・テーマ別スコア・使い方）を組み立て、
AI解釈用YAML／プロンプトを返す（ステートレス、保存しない）。

占術計算（ACGライン・リロケーション）そのものは旅行アプリ（services.travel）の
関数を流用し、変更しない。ここで足すのは「文脈と要約」だけ。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import swisseph as swe
import yaml

from services.acg_api import natal_dt_utc_from_yaml
from services.acg_core import PLANET_JA
from services.travel.location_engine import normalize_lat_lon
from services.travel.travel_generator import (
    _julday_utc,
    _natal_planets,
    _nearest_acg_lines,
    _relocation,
    _validate_yaml_size,
)
from services.western_calc import configure_ephemeris

SCHEMA_VERSION = "1.1"
APP_NAME = "astro_earth"

# 地点の由来（source）と日本語ラベル・AIへ渡す前提文。
SOURCE_LABELS = {
    "globe_click": "地球儀でクリックした地点",
    "manual_search": "検索・手入力した地点",
    "birth_place": "出生地",
    "current_location": "現在地",
    "unknown": "地点",
}
SOURCE_AI_PREFIX = {
    "globe_click": (
        "これは出生地ではなく、ユーザーが地球儀上で選択した地点です。"
        "出生図を土台に、この地点で活性化しやすいテーマを読んでください。"
    ),
    "manual_search": "これはユーザーが検索または手入力した任意地点です。",
    "birth_place": "これは出生地を基準にしたリロケーション/ACG確認です。",
    "current_location": "これはユーザーの現在地を基準にした確認です。",
    "unknown": "これは出生図に任意地点を重ねた確認です。",
}

# 相対ハウスごとのテーマ（表示ラベル・短い要約フレーズ・使い方）。
# angle はアングル系ハウス（1/4/7/10）で、対応するACGラインが近いとスコア加点。
HOUSE_THEME = {
    1: {"label": "自分らしさの刷新", "frag": "自分らしさを見直し・刷新しやすい",
        "howto": ["自分のスタイルを試す", "第一印象を新しくする"], "angle": "ASC"},
    2: {"label": "お金・豊かさ", "frag": "お金や価値観と向き合いやすい",
        "howto": ["持ち物や価値観を整理する", "価値あるものにお金を使う"]},
    3: {"label": "学び・移動", "frag": "学びや情報のやり取りが活発になりやすい",
        "howto": ["学びや発信を増やす", "短い移動や交流を楽しむ"]},
    4: {"label": "休息・のんびり", "frag": "休息や生活の土台を整えやすい",
        "howto": ["休息や生活リズムを整える", "住まいや家族と過ごす"], "angle": "IC"},
    5: {"label": "創作・楽しみ", "frag": "創作や楽しみを広げやすい",
        "howto": ["創作や趣味に取り組む", "遊びや自己表現を楽しむ"]},
    6: {"label": "習慣・健康", "frag": "習慣や健康を整えやすい",
        "howto": ["習慣や健康を整える", "日々の役割を見直す"]},
    7: {"label": "恋愛・パートナーシップ", "frag": "人との一対一の関わりが深まりやすい",
        "howto": ["一対一の関係を深める", "協力できる相手と過ごす"], "angle": "DSC"},
    8: {"label": "深い変容", "frag": "深い変化や再生に向き合いやすい",
        "howto": ["深いテーマにじっくり向き合う", "手放しと再生を意識する"]},
    9: {"label": "旅・学び", "frag": "旅や学びで視野が広がりやすい",
        "howto": ["旅や学びに出る", "視野を広げる体験をする"]},
    10: {"label": "仕事・社会的な見え方", "frag": "仕事や社会的な活動を育てやすい",
         "howto": ["長期的な仕事や発信の拠点として考える", "社会的な活動に取り組む"], "angle": "MC"},
    11: {"label": "仲間・ネットワーク", "frag": "仲間やネットワークが広がりやすい",
         "howto": ["同じテーマを持つ人とつながる", "ネットワークを広げる"]},
    12: {"label": "研究・内面整理", "frag": "研究や内面の整理を深めやすい",
         "howto": ["表に出す前の研究・準備の場として使う", "静かに内面を整理する"]},
}

EARTH_PROMPT = """あなたは西洋占星術・アストロカートグラフィの解説者です。

以下のYAMLは、出生図・任意地点・その地点に近いACG（アストロカートグラフィ）ライン・
リロケーションチャート概要を含む計算済みデータです。

重要ルール:
- 天体位置・ハウス・ACGライン・リロケーション結果は変更しないでください。
- 生年月日や緯度経度から再計算しないでください。
- YAML内の計算結果を唯一の根拠として解釈してください。
- その地点で活性化しやすいテーマを、傾向・活かし方として表現してください。
- 断定・不安を煽る表現（災害・事故・病気・「住むべき」「危険」など）は避けてください。
- 「必ず良い」「絶対に成功する」などの断定はしないでください。

出力してほしい内容:
1. この地点で活性化しやすいテーマ
2. 近いACGラインの読み解き
3. リロケーションから見た印象
4. この地点の活かし方
5. ひとことで言うなら

以下のYAMLを読み込んで解釈してください。
"""


def _coord_ja(lat: float, lon: float) -> str:
    ns = "北緯" if lat >= 0 else "南緯"
    ew = "東経" if lon >= 0 else "西経"
    return f"{ns}{abs(lat):.2f} / {ew}{abs(lon):.2f}"


def _build_location(lat: float, lon: float, name: str, source: str) -> dict[str, Any]:
    source = source if source in SOURCE_LABELS else "unknown"
    clean_name = (name or "").strip() or None
    display_name = clean_name or f"名称未取得の地点（{_coord_ja(lat, lon)}）"
    return {
        "name": clean_name,
        "latitude": round(lat, 6),
        "longitude": round(lon, 6),
        "source": source,
        "source_label": SOURCE_LABELS[source],
        "display_name": display_name,
        "name_resolved": clean_name is not None,
    }


def _house_bodies_ja(relocation: dict[str, Any]) -> dict[int, list[str]]:
    out: dict[int, list[str]] = {}
    for p in relocation.get("planets", []):
        house = p.get("house")
        if house is None:
            continue
        out.setdefault(int(house), []).append(PLANET_JA.get(p.get("name"), p.get("name")))
    return out


def _build_interpretation(relocation: dict[str, Any], nearest_lines: list[dict[str, Any]]) -> dict[str, Any]:
    """相対ハウスの天体集中と近いACGラインから、テーマ別スコアと要約を作る。

    スコアは5段階（テーマの強さ）で、厳密な吉凶判定ではない。
    計算値（ハウス配置・ライン距離）は変更せず、読み手向けの要約に変換するだけ。
    """
    house_bodies = _house_bodies_ja(relocation)
    # アングル系ハウスに、対応するアングルの近いラインがあるか（500km以内）。
    near_angles = {
        line.get("angle")
        for line in nearest_lines
        if float(line.get("distance_km") or 9e9) <= 500
    }

    themes: list[dict[str, Any]] = []
    for house, meta in HOUSE_THEME.items():
        bodies = house_bodies.get(house, [])
        count = len(bodies)
        angle = meta.get("angle")
        angle_bonus = 1 if (angle and angle in near_angles) else 0
        if count == 0 and angle_bonus == 0:
            continue
        score = max(1, min(5, 1 + min(3, count) + angle_bonus))
        reason_parts = []
        if bodies:
            reason_parts.append(f"{house}ハウスに{'・'.join(bodies)}")
        if angle_bonus:
            near = next((l for l in nearest_lines if l.get("angle") == angle), None)
            if near:
                reason_parts.append(f"{near.get('planet')}{angle}ラインが近い")
        themes.append({
            "house": house,
            "label": meta["label"],
            "score": score,
            "reason": "、".join(reason_parts) or f"{house}ハウス",
            "_frag": meta["frag"],
            "_howto": meta["howto"],
            "_count": count,
        })

    themes.sort(key=lambda t: (t["score"], t["_count"]), reverse=True)
    top = themes[:5]

    if top:
        frag1 = top[0]["_frag"]
        if len(top) >= 2:
            summary = f"{frag1}場所です。{top[1]['_frag']}傾向もあります。"
        else:
            summary = f"{frag1}場所です。"
    else:
        summary = "この地点で特に強く出るテーマは控えめです。旅や滞在そのものを楽しみやすい場所です。"

    how_to_use: list[str] = []
    for t in top[:3]:
        for tip in t["_howto"]:
            if tip not in how_to_use:
                how_to_use.append(tip)
    how_to_use = how_to_use[:4]

    public_themes = [
        {"label": t["label"], "score": t["score"], "reason": t["reason"]}
        for t in top
    ]
    return {"summary": summary, "themes": public_themes, "how_to_use": how_to_use}


def build_point_insight(
    *,
    natal_yaml_text: str,
    latitude: Any,
    longitude: Any,
    location_name: str = "",
    source: str = "globe_click",
) -> dict[str, Any]:
    """クリック地点の洞察（由来・要約・近いACGライン・リロケーション・AI用YAML）を返す。"""
    yaml_text = _validate_yaml_size(natal_yaml_text)
    lat, lon = normalize_lat_lon(latitude, longitude)
    natal_dt_utc = natal_dt_utc_from_yaml(yaml_text)

    flags = configure_ephemeris() | swe.FLG_SPEED
    natal_jd = _julday_utc(natal_dt_utc)
    natal_planets = _natal_planets(natal_jd, flags)

    # 既存の計算ロジックはそのまま流用（変更しない）。
    nearest_lines = _nearest_acg_lines(natal_dt_utc, lat, lon)
    relocation = _relocation(natal_jd, lat, lon, natal_planets)

    location = _build_location(lat, lon, location_name, source)
    interpretation = _build_interpretation(relocation, nearest_lines)
    ai_prefix = SOURCE_AI_PREFIX.get(location["source"], SOURCE_AI_PREFIX["unknown"])

    doc = {
        "schema_version": SCHEMA_VERSION,
        "app": APP_NAME,
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "location": location,
        "acg": {"nearest_lines": nearest_lines},
        "relocation": relocation,
        "interpretation": interpretation,
    }
    yaml_out = yaml.safe_dump({"astro_earth_point": doc}, allow_unicode=True, sort_keys=False, width=120)
    prompt_text = f"{ai_prefix}\n\n{EARTH_PROMPT.strip()}\n"

    return {
        "location": location,
        "interpretation": interpretation,
        "nearest_lines": nearest_lines,
        "relocation": relocation,
        "yaml_text": yaml_out,
        "prompt_text": prompt_text,
    }
