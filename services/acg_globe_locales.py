"""Buyer-facing copy for the educational ACG 3D globe."""

from __future__ import annotations

from services.acg_locales import get_acg_ui


_JA = {
    "title": "ACG仕組み理解デモ — MC/ICライン地球儀", "heading": "ACG 仕組み理解デモ",
    "subtitle": "出生瞬間に各天体がどの経度で南中(MC)/反対側で反南中(IC)になるかを可視化する教育用デモ。鑑定用ではありません。",
    "caveat_title": "計算精度に関する注意", "caveat": "このデモは簡易計算です。黄経のみの天体は黄緯0と仮定して赤経へ変換します。正確な値は製品側の計算を正としてください。",
    "yaml_input": "YAML 入力 (natal.planets / subject.datetime)", "yaml_placeholder": "ここにYAMLを貼り付け", "load": "読み込む", "sample": "サンプルを挿入",
    "result": "読み込み結果", "not_loaded": "未読み込み。サンプルで動作を確認できます。", "planet_toggle": "天体 ON/OFF（実線=MC / 破線=IC）", "after_load": "YAML読み込み後に表示",
    "reset_title": "出生時へ戻る", "play_title": "再生/停止", "speed_title": "再生速度", "follow_title": "MC点を画面中央に追跡", "follow_none": "追跡: なし", "follow_prefix": "追跡: ",
    "education": "天体はほぼ動かず、地球の自転によってMCになる地域が移り変わります。", "education_points": "太陽MC=真昼 / 太陽IC=真夜中 / 昼夜境界の円=日の出・日の入り（≒太陽のASC/DSC）", "education_note": "実際には天体も公転で動きます。本デモは出生時の天体位置に固定した簡易表示です。",
    "legend_mc": "━ MCライン（南中する経度）", "legend_ic": "┄ ICライン（対蹠経度）", "legend_point": "● MC点（天体が真上の地点）", "hud": "ドラッグ: 回転 / ホイール: ズーム / 線・●クリック: 詳細 / MC ▸: 自動回転",
    "cdn_error": "3D表示に必要なライブラリを読み込めませんでした。", "cdn_detail": "ネットワーク設定またはCDNへの接続を確認してください。", "webgl_error": "WebGLを初期化できませんでした。", "webgl_detail": "別のブラウザ、GPU設定、または端末設定を確認してください。",
    "coastline": "海岸線: Natural Earth 1:110m 埋め込み", "coastline_error": "海岸線の描画エラー", "fly": "MC地点へ回転中…", "current": "現在", "ground_longitude": "の地上経度", "zenith": "天頂点(MC)", "birth": "出生時", "zenith_detail": "この地点では天体が真上に見えます。緯度=赤緯。", "line": "ライン", "birth_longitude": "出生時の経度", "mc_detail": "この経度上では天体が真南側の子午線を通過します。", "ic_detail": "MCの正反対で、天体が地下側の子午線を通過します。", "approx_value": "黄緯0仮定の簡易値",
    "yaml_empty": "YAMLが空です。", "yaml_parse_error": "YAML解析エラー", "planet_missing": "natal.planets から天体データを読み取れませんでした。", "planet_required": "必要: 天体名 + 黄経(longitude) または 赤経(ra)", "datetime": "日時", "gmst": "GMST（概算）", "datetime_missing": "subject.datetime が無いため GMST=0° と仮定。ラインの絶対位置は不正確です。", "daylight": "昼夜表現", "daylight_disabled": "太陽データまたは日時が無いため昼夜表現は無効です。", "loaded_prefix": "天体", "loaded_suffix": "件を読み込みました。", "approx_count": "件は黄経のみのため簡易変換しています。", "asc_missing": "ASC/DSCラインはこの教育デモでは未実装です。", "rotate_title": "クリックでMC地点へ回転", "approx_note": "* = 黄緯0仮定の簡易変換", "solo_title": "のみ表示 / もう一度で全表示", "simulation_unavailable": "日時が無いため時間シミュレーション不可",
}

_EN = {
    "title": "How ACG Works — 3D MC/IC Globe", "heading": "How Astrocartography Works",
    "subtitle": "An educational globe showing where each planet was on the Midheaven (MC) or opposite it (IC) at the moment of birth. This is not a reading.",
    "caveat_title": "About calculation accuracy", "caveat": "This globe uses a simplified calculation. Bodies with ecliptic longitude only are converted assuming zero ecliptic latitude. Use the product calculation as the authoritative value.",
    "yaml_input": "YAML input (natal.planets / subject.datetime)", "yaml_placeholder": "Paste YAML here", "load": "Load", "sample": "Insert sample",
    "result": "Load result", "not_loaded": "Nothing loaded yet. Insert the sample to try it.", "planet_toggle": "Planets ON/OFF (solid=MC / dashed=IC)", "after_load": "Shown after YAML is loaded",
    "reset_title": "Return to birth time", "play_title": "Play / pause", "speed_title": "Playback speed", "follow_title": "Keep an MC point centered", "follow_none": "Follow: none", "follow_prefix": "Follow: ",
    "education": "The planets stay nearly fixed while Earth's rotation moves the regions where each planet reaches the MC.", "education_points": "Sun MC=noon / Sun IC=midnight / day-night boundary=sunrise and sunset (approximately Sun ASC/DSC)", "education_note": "Planets also move in reality. This simplified view keeps them fixed at their birth-time positions.",
    "legend_mc": "━ MC line (culminating longitude)", "legend_ic": "┄ IC line (opposite longitude)", "legend_point": "● MC point (planet overhead)", "hud": "Drag: rotate / Wheel: zoom / Select a line or point: details / MC ▸: auto-rotate",
    "cdn_error": "The libraries required for the 3D view could not be loaded.", "cdn_detail": "Check your network settings or access to the CDN.", "webgl_error": "WebGL could not be initialized.", "webgl_detail": "Try another browser or check your GPU and device settings.",
    "coastline": "Coastline: embedded Natural Earth 1:110m", "coastline_error": "Coastline rendering error", "fly": "Rotating to the MC point…", "current": "Current", "ground_longitude": "ground longitude", "zenith": "zenith point (MC)", "birth": "At birth", "zenith_detail": "At this point the planet is overhead; latitude equals declination.", "line": "line", "birth_longitude": "Longitude at birth", "mc_detail": "At this longitude the planet crosses the upper meridian.", "ic_detail": "This is opposite the MC, where the planet crosses the lower meridian.", "approx_value": "simplified value assuming zero ecliptic latitude",
    "yaml_empty": "The YAML is empty.", "yaml_parse_error": "YAML parse error", "planet_missing": "Planet data could not be read from natal.planets.", "planet_required": "Required: planet name plus longitude or right ascension (RA)", "datetime": "Date and time", "gmst": "GMST (approx.)", "datetime_missing": "subject.datetime was not found, so GMST is assumed to be 0°. Absolute line positions are not accurate.", "daylight": "Day/night lighting", "daylight_disabled": "Day/night lighting is unavailable because Sun data or a date and time is missing.", "loaded_prefix": "Loaded", "loaded_suffix": "planets.", "approx_count": "entries used the simplified longitude conversion.", "asc_missing": "ASC/DSC lines are not implemented in this educational demo.", "rotate_title": "Rotate to the MC point", "approx_note": "* = simplified conversion assuming zero ecliptic latitude", "solo_title": "only / select again to show all", "simulation_unavailable": "Time simulation is unavailable without a date and time",
}


def _overlay(base: dict[str, object], **changes: str) -> dict[str, object]:
    return {**base, **changes}


GLOBE_UI = {
    "ja": _JA,
    "en": _EN,
    "es": _overlay(_EN, title="Cómo funciona ACG — Globo 3D MC/IC", heading="Cómo funciona la astrocartografía", load="Cargar", sample="Insertar ejemplo", result="Resultado", not_loaded="Aún no hay datos. Inserta el ejemplo para probar.", planet_toggle="Planetas SÍ/NO (continua=MC / discontinua=IC)", after_load="Se muestra después de cargar el YAML", follow_none="Seguimiento: ninguno", follow_prefix="Seguimiento: ", yaml_empty="El YAML está vacío.", yaml_parse_error="Error al analizar el YAML", simulation_unavailable="La simulación requiere fecha y hora"),
    "de": _overlay(_EN, title="So funktioniert ACG — 3D-MC/IC-Globus", heading="So funktioniert Astrokartografie", load="Laden", sample="Beispiel einfügen", result="Ladeergebnis", not_loaded="Noch nichts geladen. Füge das Beispiel ein.", planet_toggle="Planeten AN/AUS (durchgezogen=MC / gestrichelt=IC)", after_load="Wird nach dem Laden der YAML angezeigt", follow_none="Folgen: aus", follow_prefix="Folgen: ", yaml_empty="Die YAML ist leer.", yaml_parse_error="YAML-Fehler", simulation_unavailable="Die Zeitsimulation benötigt Datum und Uhrzeit"),
}


def get_globe_ui(lang: str) -> dict[str, object]:
    locale = lang if lang in GLOBE_UI else "ja"
    return {**GLOBE_UI[locale], "planet_names": get_acg_ui(locale).get("planet_names", {})}
