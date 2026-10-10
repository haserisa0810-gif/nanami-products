from __future__ import annotations

import html
import io
import json
import re
import subprocess
import sys
import threading
import zipfile
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from services.acg_api import personal_geojson


ROOT = Path(__file__).resolve().parent.parent
PE_DIR = ROOT / "personal-edition"
VERSION = "1.1.5"
_build_lock = threading.Lock()


def _template_zip(lang: str) -> Path:
    variant = "JA" if lang == "ja" else "EN"
    return PE_DIR / "dist" / f"BirthChartMuseum-PersonalEdition-{variant}-v{VERSION}.zip"


def ensure_template_zip(lang: str) -> Path:
    target = _template_zip(lang)
    if target.is_file():
        return target
    with _build_lock:
        if not target.is_file():
            subprocess.run(
                [sys.executable, str(PE_DIR / "build.py")],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
                timeout=120,
            )
    if not target.is_file():
        raise RuntimeError("Personal Edition template ZIP was not created")
    return target


def _autoload_script(*, include_acg: bool, lang: str) -> str:
    acg_link = ""
    if include_acg:
        acg_label = {
            "ja": "あなたのACG地図を開く",
            "en": "View your ACG map",
            "es": "Ver tu mapa ACG",
            "de": "Deine ACG-Karte ansehen",
        }.get(lang, "View your ACG map")
        acg_link = f"""
      var acg = document.createElement('a');
      acg.href = '/acg/';
      acg.textContent = {json.dumps(acg_label, ensure_ascii=False)};
      acg.style.cssText = 'position:fixed;right:18px;bottom:18px;z-index:9999;padding:11px 16px;border-radius:999px;background:#c9a227;color:#0a1128;text-decoration:none;font-weight:700;box-shadow:0 5px 18px rgba(0,0,0,.35)';
      document.body.appendChild(acg);
"""
    return """
  <script>
  document.addEventListener('DOMContentLoaded', function () {
    fetch('/birth-chart.yaml', {cache: 'no-store'}).then(function (r) {
      if (!r.ok) throw new Error('chart not found');
      return r.text();
    }).then(function (yaml) {
      sessionStorage.setItem('ht-last-yaml', yaml);
      sessionStorage.setItem('ht-chart-pref', 'yaml');
      sessionStorage.setItem('ds-last-yaml', yaml);
      sessionStorage.setItem('ds-chart-pref', 'yaml');
      var input = document.getElementById('me-yaml-input');
      if (input) input.value = yaml;
    }).catch(function () {});
%s
  });
  </script>
""" % acg_link


def _personal_acg_online_url(chart_url: str | None) -> str | None:
    if not chart_url:
        return None
    parts = urlsplit(chart_url)
    chart_path = parts.path.rstrip("/")
    online_path = f"{chart_path}/acg-app/"
    lang_query = [(key, value) for key, value in parse_qsl(parts.query) if key == "lang"]
    return urlunsplit(
        (parts.scheme, parts.netloc, online_path, urlencode(lang_query), "")
    )


def _localize_personal_acg_geojson(acg_data: dict, lang: str) -> dict:
    """Localize display-only ACG properties without changing any coordinates."""
    if lang == "ja":
        return acg_data
    safe_lang = lang if lang in {"en", "es", "de"} else "en"
    catalog_path = ROOT / "static" / f"acg_interpretations_{safe_lang}.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    localized = json.loads(json.dumps(acg_data, ensure_ascii=False))
    for feature in localized.get("features") or []:
        properties = feature.get("properties") if isinstance(feature, dict) else None
        if not isinstance(properties, dict):
            continue
        entry = catalog.get(str(properties.get("line_group") or ""))
        if not isinstance(entry, dict):
            continue
        for key in ("label", "meaning", "meaning_hint"):
            if entry.get(key):
                properties[key] = entry[key]
    context = ((localized.get("meta") or {}).get("personal_context") or {})
    if isinstance(context, dict):
        context["note"] = {
            "en": "See the full YAML for detailed natal chart interpretation",
            "es": "Consulta el YAML completo para una interpretación detallada de la carta natal",
            "de": "Für eine ausführliche Radixdeutung das vollständige YAML heranziehen",
        }[safe_lang]
    return localized


def _acg_licenses() -> str:
    return """NANAMI ASTRO Personal ACG - Third-party licenses
==================================================

Leaflet 1.9.4
https://leafletjs.com/
Copyright (c) 2010-2023, Vladimir Agafonkin
License: BSD 2-Clause

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:
1. Redistributions of source code must retain the above copyright notice,
   this list of conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES ARE DISCLAIMED.

Natural Earth
https://www.naturalearthdata.com/
Public domain map and place-name data.

OpenStreetMap
https://www.openstreetmap.org/copyright
Background map tiles are provided by OpenStreetMap contributors and are not
bundled in this package.
"""


def _standalone_acg_html(
    *,
    acg_html: str,
    leaflet_css: str,
    leaflet_js: str,
    acg_data: dict,
    city_data: dict,
    world_data: dict,
    chart_url: str | None,
    show_ipad_online_link: bool = False,
    lang: str = "ja",
) -> str:
    """Build a file://-safe ACG app with personal data and Leaflet embedded."""
    acg_data = _localize_personal_acg_geojson(acg_data, lang)
    data_json = json.dumps(acg_data, ensure_ascii=False, separators=(",", ":"))
    cities_json = json.dumps(city_data.get("cities", []), ensure_ascii=False, separators=(",", ":"))
    world_json = json.dumps(world_data, ensure_ascii=False, separators=(",", ":"))
    status_label, status_fallback = {
        "ja": ("計算基準: ", "確認済み出生日時"),
        "en": ("Calculation time: ", "confirmed birth time"),
        "es": ("Momento de cálculo: ", "hora de nacimiento confirmada"),
        "de": ("Berechnungszeit: ", "bestätigte Geburtszeit"),
    }.get(lang, ("Calculation time: ", "confirmed birth time"))
    embedded_code = (
        f"data={data_json};render();renderPlaces();"
        "document.getElementById('status').textContent="
        f"{json.dumps(status_label, ensure_ascii=False)}+"
        f"((data.meta&&data.meta.datetime_utc)||{json.dumps(status_fallback, ensure_ascii=False)});"
    )
    result = _localize_personal_acg_html(acg_html, lang).replace(
        '<link rel="stylesheet" href="/static/vendor/leaflet/leaflet.css">',
        f"<style>\n{leaflet_css}\n</style>",
        1,
    ).replace(
        '<script src="/static/vendor/leaflet/leaflet.js"></script>',
        f"<script>\n{leaflet_js}\n</script>",
        1,
    )
    result, embedded_count = re.subn(
        r"/\* PERSONAL_ACG_DATA_START \*/.*?/\* PERSONAL_ACG_DATA_END \*/",
        embedded_code,
        result,
        count=1,
        flags=re.DOTALL,
    )
    result, city_embedded_count = re.subn(
        r"/\* PERSONAL_CITY_DATA_START \*/.*?/\* PERSONAL_CITY_DATA_END \*/",
        f"cityCatalog={cities_json};",
        result,
        count=1,
        flags=re.DOTALL,
    )
    result, world_embedded_count = re.subn(
        r"/\* PERSONAL_WORLD_DATA_START \*/.*?/\* PERSONAL_WORLD_DATA_END \*/",
        f"worldData={world_json};renderWorld();",
        result,
        count=1,
        flags=re.DOTALL,
    )
    if chart_url:
        result = result.replace('href="/"', f'href="{chart_url}"', 1)
        if show_ipad_online_link:
            online_url = _personal_acg_online_url(chart_url)
            online_label = {
                "ja": "iPad・iPhone：オンラインACG地図を開く",
                "en": "iPad / iPhone: Open the online ACG map",
                "es": "iPad / iPhone: Abrir el mapa ACG online",
                "de": "iPad / iPhone: Online-ACG-Karte öffnen",
            }.get(lang, "iPad / iPhone: Open the online ACG map")
            ipad_link = (
                '<style>.ipad-online-acg{display:block;padding:9px 12px;background:#c9a227;'
                'color:#0a1128;text-decoration:none;font-size:.78rem;font-weight:700;'
                'text-align:center}</style>'
                '<a class="ipad-online-acg" href="'
                + html.escape(online_url, quote=True)
                + '">' + html.escape(online_label) + '</a>'
            )
            result = result.replace("</header>", "</header>" + ipad_link, 1)
    else:
        result = result.replace('href="/"', 'href="#" onclick="return false"', 1)
    if (
        embedded_count != 1
        or city_embedded_count != 1
        or world_embedded_count != 1
        or "/acg-personal.geojson" in result
        or "cities.min.json" in result
        or "ne_110m_admin_0_countries.geojson" in result
    ):
        raise RuntimeError("Standalone ACG data embedding failed")
    return result


def _localize_personal_acg_html(source: str, lang: str) -> str:
    """Localize the self-contained ACG shell without changing its calculations."""
    if lang == "ja":
        return source
    translations = {
        "en": {
            "ACG · あなたの天空線": "ACG · Your Sky Lines", "出生時刻・タイムゾーン確認済みの計算済みデータを表示しています。": "Showing pre-calculated data based on your confirmed birth time and time zone.", "占術データへ戻る": "Back to your chart", "表示テーマ": "Theme", "基本": "Essentials", "仕事": "Career", "人の縁": "Relationships", "すべて": "All", "アングル": "Angles", "3都市比較": "Compare 3 places", "検索": "Search", "例：": "Example: ", "検索結果を選ぶか、地図をクリックして最大3地点を登録できます。都市検索はローカル内蔵データを使用します。": "Choose a search result or click the map to save up to three places. City search uses built-in offline data.", "選んだ場所の星のメッセージをAIに聞く": "Ask AI about the selected places", "地図＋3都市レポートを印刷・PDF保存": "Print or save the map and report as PDF", "個人線データを読み込んでいます…": "Loading your personal lines…", "個人の天空線": "Personal sky lines", "約": "About ", "緯度 ": "Lat ", " / 経度 ": " / Lon ", "検索する都市名を入力してください。": "Enter a city name.", "検索結果を選択してください。": "Choose a search result.", "比較地点に追加しました。": "Added to comparison.", "コピーに失敗しました。ブラウザの権限を確認してください。": "Copy failed. Check your browser permissions.", "個人線データを読み込めませんでした。": "Your personal lines could not be loaded.",
        },
        "es": {
            "ACG · あなたの天空線": "ACG · Tus líneas celestes", "出生時刻・タイムゾーン確認済みの計算済みデータを表示しています。": "Datos ya calculados con tu hora y zona horaria de nacimiento confirmadas.", "占術データへ戻る": "Volver a tu carta", "表示テーマ": "Tema", "基本": "Esencial", "仕事": "Profesión", "人の縁": "Relaciones", "すべて": "Todo", "アングル": "Ángulos", "3都市比較": "Comparar 3 lugares", "検索": "Buscar", "例：": "Ejemplo: ", "検索結果を選ぶか、地図をクリックして最大3地点を登録できます。都市検索はローカル内蔵データを使用します。": "Elige un resultado o toca el mapa para guardar hasta tres lugares. La búsqueda usa datos locales.", "選んだ場所の星のメッセージをAIに聞く": "Preguntar a la IA por los lugares elegidos", "地図＋3都市レポートを印刷・PDF保存": "Imprimir o guardar el mapa y el informe en PDF", "個人線データを読み込んでいます…": "Cargando tus líneas personales…", "個人の天空線": "Líneas celestes personales", "検索する都市名を入力してください。": "Introduce una ciudad.", "検索結果を選択してください。": "Elige un resultado.", "比較地点に追加しました。": "Lugar añadido a la comparación.", "コピーに失敗しました。ブラウザの権限を確認してください。": "No se pudo copiar. Comprueba los permisos del navegador.", "個人線データを読み込めませんでした。": "No se pudieron cargar tus líneas personales.",
        },
        "de": {
            "ACG · あなたの天空線": "ACG · Deine Himmelslinien", "出生時刻・タイムゾーン確認済みの計算済みデータを表示しています。": "Bereits berechnete Daten auf Basis der bestätigten Geburtszeit und Zeitzone.", "占術データへ戻る": "Zurück zum Horoskop", "表示テーマ": "Thema", "基本": "Grundlagen", "仕事": "Beruf", "人の縁": "Beziehungen", "すべて": "Alle", "アングル": "Achsen", "3都市比較": "3 Orte vergleichen", "検索": "Suchen", "例：": "Beispiel: ", "検索結果を選ぶか、地図をクリックして最大3地点を登録できます。都市検索はローカル内蔵データを使用します。": "Wähle ein Suchergebnis oder klicke auf die Karte, um bis zu drei Orte zu speichern. Die Ortssuche nutzt integrierte Offline-Daten.", "選んだ場所の星のメッセージをAIに聞く": "KI zu den gewählten Orten befragen", "地図＋3都市レポートを印刷・PDF保存": "Karte und Bericht drucken oder als PDF speichern", "個人線データを読み込んでいます…": "Deine persönlichen Linien werden geladen…", "個人の天空線": "Persönliche Himmelslinien", "検索する都市名を入力してください。": "Gib einen Ortsnamen ein.", "検索結果を選択してください。": "Wähle ein Suchergebnis.", "比較地点に追加しました。": "Zum Vergleich hinzugefügt.", "コピーに失敗しました。ブラウザの権限を確認してください。": "Kopieren fehlgeschlagen. Prüfe die Browser-Berechtigungen.", "個人線データを読み込めませんでした。": "Deine persönlichen Linien konnten nicht geladen werden.",
        },
    }.get(lang, {})
    translations.update({
        "en": {
            "このレポートは、登録地点から近い出生時のACGラインを距離順に整理したものです。土地との相性を断定するものではなく、移住・旅行・活動拠点を考えるための占星術的な参考情報としてお使いください。": "This report lists natal ACG lines near your saved places by distance. It is astrological reference material for travel, relocation or activity planning, not a guarantee of compatibility with a place.",
            "個人線データの読み込み後に追加してください。": "Wait until your personal lines have loaded.", "比較できる地点は3件までです。": "You can compare up to three places.", "選択した地点": "Selected place", "この地点はすでに追加されています。": "This place is already saved.", "選択中のテーマでは500km以内に対象ラインがありません。": "No matching line is within 500 km for this theme.", "を削除": "Remove ", "テーマ: ": "Theme: ", " ｜ 作成日: ": " | Created: ", " ｜ 表示地点: ": " | Places: ", "都市データを読み込んでいます。少し待ってから再度お試しください。": "City data is loading. Please try again shortly.", "内蔵データに見つかりませんでした。地図をクリックして地点を追加できます。": "Not found in the built-in data. Click the map to add the place.", "以下は、出生時刻とタイムゾーンを確認して計算済みの個人アストロカートグラフィ（ACG）地点データです。": "The following personal astrocartography place data was pre-calculated using a confirmed birth time and time zone.", "天体位置やラインを生年月日から再計算せず、記載された計算結果をそのまま使って相談に答えてください。": "Do not recalculate planets or lines from the birth date. Use the stated results as given.", "各地点は出生地ではなく、旅行・移住・仕事・活動拠点などの候補地です。占星術的な傾向として読み、現実の安全・費用・制度なども別途確認するよう促してください。": "These are candidate places for travel, relocation, work or activities. Read them as astrological tendencies and recommend separate checks for safety, cost and regulations.", "相談したいこと:": "Consultation request:", "登録地点ごとの特徴、活かしやすいテーマ、注意点を具体的に説明してください。": "Explain the character, useful themes and cautions for each saved place.", "複数地点がある場合は、共通点と違いを比較し、目的別に向く地点を整理してください。": "Compare similarities and differences and organize the places by purpose.", "情報が足りなければ、最初に私の目的や滞在期間などを質問してください。": "If information is missing, first ask about my purpose and intended length of stay.", "計算基準（UTC）: ": "Calculation time (UTC): ", "確認済み出生日時": "confirmed birth time", "登録地点と500km以内の近接ライン:": "Saved places and lines within 500 km:", "座標: 緯度 ": "Coordinates: lat ", "現在の表示テーマでは500km以内に対象ラインなし": "No matching line within 500 km for the current theme", "まず、私が今回いちばん知りたい目的を一つ質問してから読み解きを始めてください。": "Before interpreting, ask one question about what I most want to learn this time.", "AIに貼り付ける内容をコピーしました。お好きなAIで、選んだ場所の星のメッセージを聞けます。": "Copied. Paste it into your preferred AI to explore the selected places.", "選択地点 ": "Selected point ", "都市データを読み込めませんでした。地図クリックは利用できます。": "City data could not be loaded. You can still click the map.", "計算基準: ": "Calculation time: ",
        },
        "es": {
            "このレポートは、登録地点から近い出生時のACGラインを距離順に整理したものです。土地との相性を断定するものではなく、移住・旅行・活動拠点を考えるための占星術的な参考情報としてお使いください。": "Este informe ordena por distancia las líneas ACG natales cercanas. Es una referencia astrológica para viajes, mudanzas o actividades, no una garantía de compatibilidad con un lugar.", "個人線データの読み込み後に追加してください。": "Espera a que se carguen tus líneas personales.", "比較できる地点は3件までです。": "Puedes comparar hasta tres lugares.", "選択した地点": "Lugar elegido", "この地点はすでに追加されています。": "Este lugar ya está guardado.", "選択中のテーマでは500km以内に対象ラインがありません。": "No hay líneas del tema elegido a menos de 500 km.", "を削除": "Eliminar ", "テーマ: ": "Tema: ", " ｜ 作成日: ": " | Creado: ", " ｜ 表示地点: ": " | Lugares: ", "都市データを読み込んでいます。少し待ってから再度お試しください。": "Los datos de ciudades se están cargando. Inténtalo de nuevo en breve.", "内蔵データに見つかりませんでした。地図をクリックして地点を追加できます。": "No aparece en los datos locales. Toca el mapa para añadirlo.", "以下は、出生時刻とタイムゾーンを確認して計算済みの個人アストロカートグラフィ（ACG）地点データです。": "Estos datos personales de astrocartografía se calcularon con una hora y zona horaria de nacimiento confirmadas.", "天体位置やラインを生年月日から再計算せず、記載された計算結果をそのまま使って相談に答えてください。": "No recalcules planetas ni líneas. Usa directamente los resultados indicados.", "各地点は出生地ではなく、旅行・移住・仕事・活動拠点などの候補地です。占星術的な傾向として読み、現実の安全・費用・制度なども別途確認するよう促してください。": "Son lugares candidatos para viajar, mudarse, trabajar o desarrollar actividades. Léelos como tendencias astrológicas y recomienda comprobar aparte seguridad, costes y normas.", "相談したいこと:": "Consulta:", "登録地点ごとの特徴、活かしやすいテーマ、注意点を具体的に説明してください。": "Explica las características, temas favorables y precauciones de cada lugar.", "複数地点がある場合は、共通点と違いを比較し、目的別に向く地点を整理してください。": "Compara semejanzas y diferencias y organiza los lugares según el objetivo.", "情報が足りなければ、最初に私の目的や滞在期間などを質問してください。": "Si falta información, pregunta primero por mi objetivo y la duración de la estancia.", "計算基準（UTC）: ": "Momento de cálculo (UTC): ", "確認済み出生日時": "hora de nacimiento confirmada", "登録地点と500km以内の近接ライン:": "Lugares guardados y líneas a menos de 500 km:", "座標: 緯度 ": "Coordenadas: lat. ", "現在の表示テーマでは500km以内に対象ラインなし": "No hay líneas del tema actual a menos de 500 km", "まず、私が今回いちばん知りたい目的を一つ質問してから読み解きを始めてください。": "Antes de interpretar, hazme una pregunta sobre lo que más quiero saber esta vez.", "AIに貼り付ける内容をコピーしました。お好きなAIで、選んだ場所の星のメッセージを聞けます。": "Copiado. Pégalo en tu IA preferida para explorar los lugares elegidos.", "選択地点 ": "Punto elegido ", "都市データを読み込めませんでした。地図クリックは利用できます。": "No se cargaron las ciudades. Aún puedes tocar el mapa.", "計算基準: ": "Momento de cálculo: ", "緯度 ": "Lat. ", " / 経度 ": " / Long. ", "約": "Aprox. ",
        },
        "de": {
            "このレポートは、登録地点から近い出生時のACGラインを距離順に整理したものです。土地との相性を断定するものではなく、移住・旅行・活動拠点を考えるための占星術的な参考情報としてお使いください。": "Dieser Bericht ordnet geburtsbezogene ACG-Linien in der Nähe deiner Orte nach Entfernung. Er dient als astrologische Orientierung für Reisen, Umzug oder Aktivitäten und ist keine Garantie für die Eignung eines Ortes.", "個人線データの読み込み後に追加してください。": "Warte, bis deine persönlichen Linien geladen sind.", "比較できる地点は3件までです。": "Du kannst bis zu drei Orte vergleichen.", "選択した地点": "Gewählter Ort", "この地点はすでに追加されています。": "Dieser Ort ist bereits gespeichert.", "選択中のテーマでは500km以内に対象ラインがありません。": "Für dieses Thema liegt keine passende Linie innerhalb von 500 km.", "を削除": " entfernen", "テーマ: ": "Thema: ", " ｜ 作成日: ": " | Erstellt: ", " ｜ 表示地点: ": " | Orte: ", "都市データを読み込んでいます。少し待ってから再度お試しください。": "Ortsdaten werden geladen. Versuche es gleich noch einmal.", "内蔵データに見つかりませんでした。地図をクリックして地点を追加できます。": "Nicht in den integrierten Daten gefunden. Klicke zum Hinzufügen auf die Karte.", "以下は、出生時刻とタイムゾーンを確認して計算済みの個人アストロカートグラフィ（ACG）地点データです。": "Die folgenden persönlichen Astrokartografie-Daten wurden mit bestätigter Geburtszeit und Zeitzone berechnet.", "天体位置やラインを生年月日から再計算せず、記載された計算結果をそのまま使って相談に答えてください。": "Berechne Planeten oder Linien nicht neu. Verwende die angegebenen Ergebnisse unverändert.", "各地点は出生地ではなく、旅行・移住・仕事・活動拠点などの候補地です。占星術的な傾向として読み、現実の安全・費用・制度なども別途確認するよう促してください。": "Es sind mögliche Orte für Reise, Umzug, Arbeit oder Aktivitäten. Deute sie als astrologische Tendenzen und empfehle zusätzliche Prüfungen zu Sicherheit, Kosten und Regeln.", "相談したいこと:": "Beratungswunsch:", "登録地点ごとの特徴、活かしやすいテーマ、注意点を具体的に説明してください。": "Erkläre Merkmale, nutzbare Themen und Hinweise für jeden Ort.", "複数地点がある場合は、共通点と違いを比較し、目的別に向く地点を整理してください。": "Vergleiche Gemeinsamkeiten und Unterschiede und ordne die Orte nach Zweck.", "情報が足りなければ、最初に私の目的や滞在期間などを質問してください。": "Falls Angaben fehlen, frage zuerst nach meinem Ziel und der Aufenthaltsdauer.", "計算基準（UTC）: ": "Berechnungszeit (UTC): ", "確認済み出生日時": "bestätigte Geburtszeit", "登録地点と500km以内の近接ライン:": "Gespeicherte Orte und Linien innerhalb von 500 km:", "座標: 緯度 ": "Koordinaten: Breite ", "現在の表示テーマでは500km以内に対象ラインなし": "Keine passende Linie innerhalb von 500 km", "まず、私が今回いちばん知りたい目的を一つ質問してから読み解きを始めてください。": "Frage mich vor der Deutung zuerst, was ich diesmal vor allem wissen möchte.", "AIに貼り付ける内容をコピーしました。お好きなAIで、選んだ場所の星のメッセージを聞けます。": "Kopiert. Füge den Text in deine bevorzugte KI ein, um die gewählten Orte zu erkunden.", "選択地点 ": "Gewählter Punkt ", "都市データを読み込めませんでした。地図クリックは利用できます。": "Ortsdaten konnten nicht geladen werden. Du kannst weiterhin auf die Karte klicken.", "計算基準: ": "Berechnungszeit: ", "緯度 ": "Breite ", " / 経度 ": " / Länge ", "約": "Ca. ",
        },
    }.get(lang, {}))
    result = source.replace('<html lang="ja">', f'<html lang="{lang}">', 1)
    for original, translated in sorted(translations.items(), key=lambda item: len(item[0]), reverse=True):
        result = result.replace(original, translated)
    return result


def build_personal_acg_html(*, yaml_text: str, chart_url: str | None = None, lang: str = "ja") -> str:
    """Build the self-contained Personal ACG app used by web and ZIP delivery."""
    acg_html = (PE_DIR / "acg" / "index.html").read_text(encoding="utf-8")
    city_data = json.loads((PE_DIR / "acg" / "cities.min.json").read_text(encoding="utf-8"))
    leaflet_dir = ROOT / "static" / "vendor" / "leaflet"
    return _standalone_acg_html(
        acg_html=acg_html,
        leaflet_css=(leaflet_dir / "leaflet.css").read_text(encoding="utf-8"),
        leaflet_js=(leaflet_dir / "leaflet.js").read_text(encoding="utf-8"),
        acg_data=personal_geojson(yaml_text),
        city_data=city_data,
        world_data=json.loads((ROOT / "static" / "geo" / "ne_110m_admin_0_countries.geojson").read_text(encoding="utf-8")),
        chart_url=chart_url,
        lang=lang,
    )


def _acg_direct_start_readme(*, lang: str, chart_url: str | None) -> str:
    online_url = _personal_acg_online_url(chart_url)
    if lang in {"es", "de"}:
        copy = {
            "es": (
                "NANAMI ASTRO - APLICACIÓN ACG PERSONAL\nLEE PRIMERO ESTE ARCHIVO\n\n",
                "WINDOWS / MAC\n1. Extrae completamente el ZIP.\n2. Abre la carpeta extraída y haz doble clic en START-ACG.html.\n3. El mapa se abrirá en tu navegador.\n\nIPAD / IPHONE\nAbre la aplicación ACG en Safari desde tu página privada y usa Añadir a la pantalla de inicio. Se necesita conexión a internet para el mapa de fondo.\n\nUSO\nElige un tema, busca o marca hasta tres lugares y compara las líneas cercanas. El botón de IA copia una consulta basada en los datos ya calculados.\n",
                "Tu aplicación ACG online", "Tu página privada",
            ),
            "de": (
                "NANAMI ASTRO – PERSÖNLICHE ACG-APP\nBITTE ZUERST LESEN\n\n",
                "WINDOWS / MAC\n1. Entpacke die ZIP-Datei vollständig.\n2. Öffne den entpackten Ordner und doppelklicke START-ACG.html.\n3. Die Karte öffnet sich im Browser.\n\nIPAD / IPHONE\nÖffne die ACG-App über deine private Seite in Safari und nutze Zum Home-Bildschirm. Für die Hintergrundkarte ist Internet erforderlich.\n\nVERWENDUNG\nWähle ein Thema, suche oder markiere bis zu drei Orte und vergleiche nahe Linien. Die KI-Schaltfläche kopiert eine Anfrage auf Basis der bereits berechneten Daten.\n",
                "Deine persönliche Online-ACG-App", "Deine private Horoskopseite",
            ),
        }[lang]
        links = ""
        if online_url:
            links += f"\n{copy[2]}:\n{online_url}\n"
        if chart_url:
            links += f"\n{copy[3]}:\n{chart_url}\n"
        return copy[0] + copy[1] + links
    if lang == "en":
        online = (
            "\nYour personal online ACG app:\n"
            f"{online_url}\n"
            if online_url else ""
        )
        chart = f"\nYour private chart page:\n{chart_url}\n" if chart_url else ""
        return (
            "NANAMI ASTRO - PERSONAL ACG APP\n"
            "PLEASE READ THIS FILE FIRST\n\n"
            "WINDOWS / MAC (use the downloaded ZIP)\n"
            "1. Extract the complete ZIP archive.\n"
            "   Do not open START-ACG.html while it is still inside the ZIP.\n"
            "2. Open the extracted folder and double-click START-ACG.html.\n"
            "3. Your default browser opens your personal ACG map.\n"
            "No installation, App Store download, command file, PowerShell, or local server "
            "is required.\n\n"
            "IPAD / IPHONE (recommended: use the online ACG app in Safari)\n"
            "START-ACG.html may not display the map when opened from the Files app preview.\n"
            "1. Open your private chart page below in Safari.\n"
            "2. Expand 'Save your data'.\n"
            "3. Tap 'Open your Personal ACG app'.\n"
            "4. In the ACG app, tap 'Add to Home Screen' for guidance. Then tap Safari's "
            "Share button and select 'Add to Home Screen'.\n"
            "5. Next time, start it from the My ACG icon on your Home Screen.\n"
            "This is a web app, so there is nothing to install from the App Store. An internet "
            "connection is required.\n"
            + online
            + chart
            + "\nHOW TO USE THE MAP\n"
            "1. Select Basic, Work, Relationships, or All.\n"
            "2. Search for a city or click the map to add up to three places.\n"
            "3. Compare the nearest ACG lines shown for each place.\n"
            "4. Use 'Ask AI about the selected places' to copy a consultation prompt.\n"
            "5. Use Print to print the map and comparison or save them as a PDF.\n\n"
            "IF THE MAP DOES NOT APPEAR\n"
            "- iPad/iPhone: do not use the Files preview; open the online ACG app in Safari.\n"
            "- Windows/Mac: make sure the ZIP was fully extracted before opening the HTML.\n"
            "- Check your internet connection. Only the background map tiles are downloaded.\n\n"
            "Your personal birth data and ACG lines are embedded in START-ACG.html. "
            "Place-name search, personal ACG calculation, and comparison all run inside "
            "the file. Only background map tiles require an internet connection.\n"
            "Keep the ZIP and private URLs confidential. Personal use only; do not redistribute.\n"
        )
    online = f"\nあなた専用のオンラインACGアプリ：\n{online_url}\n" if online_url else ""
    chart = f"\n専用鑑定ページ：\n{chart_url}\n" if chart_url else ""
    return (
        "NANAMI ASTRO - 個人用ACGアプリ\n"
        "このファイルを最初にお読みください\n\n"
        "【Windows / Mac：ダウンロードしたZIPを使う】\n"
        "1. ZIPを右クリックし、「すべて展開」します。ZIPの中から直接開かないでください。\n"
        "2. 展開したフォルダー内の START-ACG.html をダブルクリックします。\n"
        "3. いつも使うブラウザで、あなた専用のACG地図が開きます。\n"
        "インストール、App Storeからのダウンロード、バッチファイル、PowerShell、"
        "ローカルサーバーは不要です。\n\n"
        "【iPad / iPhone：SafariのオンラインACGアプリがおすすめ】\n"
        "「ファイル」アプリのプレビューで START-ACG.html を開くと、地図が表示されないことがあります。\n"
        "1. 下記の専用鑑定ページをSafariで開きます。\n"
        "2. ページ内の「データを保存」を開きます。\n"
        "3. 「あなたのACGアプリを開く」を押します。\n"
        "4. ACG画面の「ホーム画面に追加」で案内を確認し、Safariの共有ボタンから"
        "「ホーム画面に追加」を選びます。\n"
        "5. 次回から、ホーム画面の「My ACG」アイコンで起動できます。\n"
        "Webアプリのため、App Storeからインストールするものはありません。利用時はインターネット接続が必要です。\n"
        + online
        + chart
        + "\n【地図の使い方】\n"
        "1. 「基本」「仕事」「人の縁」「すべて」から表示テーマを選びます。\n"
        "2. 都市名検索または地図クリックで、最大3地点を登録します。\n"
        "3. 各地点に近いACGラインとメッセージを比較します。\n"
        "4. 「選んだ場所の星のメッセージをAIに聞く」で、AI相談用の文章をコピーできます。\n"
        "5. 印刷ボタンから、地図と比較結果を印刷またはPDF保存できます。\n\n"
        "【地図が表示されないとき】\n"
        "・iPad / iPhone：「ファイル」アプリではなく、SafariでオンラインACGアプリを開いてください。\n"
        "・Windows / Mac：ZIPをすべて展開してから START-ACG.html を開いてください。\n"
        "・インターネット接続を確認してください。背景地図の表示には通信が必要です。\n\n"
        "出生データとACGラインはSTART-ACG.html内に保存されています。"
        "都市名検索・個人ACGの計算結果・比較処理はファイル内で動作します。"
        "インターネット接続を使用するのは背景地図だけです。\n"
        "ZIPと専用URLは他人に共有しないでください。個人利用専用です。再配布・転売は禁止です。\n"
    )


def _buyer_readme(*, lang: str, include_acg: bool, chart_url: str | None) -> str:
    safe_lang = lang if lang in {"ja", "en", "es", "de"} else "en"
    copy = {
        "ja": {
            "title": "NANAMI ASTRO - PERSONAL EDITION FULL",
            "quick": "【最初にすること】",
            "steps": [
                "このZIPを安全な場所に保存し、すべて展開します。",
                "ASTROLOGY-DATA.yamlで、計算済みの出生図・小惑星・トランジットデータを確認できます。",
                "AI-PROMPT.txtとASTROLOGY-DATA.yamlをAIへ渡すと、再計算せず保存済みデータを読ませられます。",
                "専用鑑定ページから、1年Plannerの作成・保存や各データの再ダウンロードができます。",
            ],
            "files": "【同梱ファイル】\n・ASTROLOGY-DATA.yaml：計算済み占術データ\n・AI-PROMPT.txt：AI相談用の案内文\n・専用鑑定ページ_URL.txt：専用ページURLの控え",
            "url": "【専用鑑定ページ】",
            "privacy": "出生情報を含むため、ZIPと専用URLは他人へ共有しないでください。個人利用専用です。再配布・転売は禁止です。",
        },
        "en": {
            "title": "NANAMI ASTRO - PERSONAL EDITION FULL",
            "quick": "QUICK START",
            "steps": [
                "Save this ZIP in a secure place and extract all files.",
                "Open ASTROLOGY-DATA.yaml to view your calculated natal, asteroid, and transit data.",
                "Give AI-PROMPT.txt and ASTROLOGY-DATA.yaml to an AI to interpret the stored values without recalculating them.",
                "Use your private chart page to create and save the 1-year Planner or download your data again.",
            ],
            "files": "INCLUDED FILES\n- ASTROLOGY-DATA.yaml: calculated astrology data\n- AI-PROMPT.txt: instructions for an AI consultation\n- PRIVATE-CHART-URL.txt: a copy of your private page URL",
            "url": "PRIVATE CHART PAGE",
            "privacy": "The ZIP and private URL contain personal birth information. Keep them private. Personal use only; do not redistribute or resell.",
        },
        "es": {
            "title": "NANAMI ASTRO - EDICIÓN PERSONAL FULL",
            "quick": "INICIO RÁPIDO",
            "steps": [
                "Guarda este ZIP en un lugar seguro y extrae todos los archivos.",
                "Abre ASTROLOGY-DATA.yaml para consultar tus datos calculados de carta natal, asteroides y tránsitos.",
                "Entrega AI-PROMPT.txt y ASTROLOGY-DATA.yaml a una IA para interpretar los valores guardados sin recalcularlos.",
                "Utiliza tu página privada para crear y guardar el Planner de 1 año o volver a descargar tus datos.",
            ],
            "files": "ARCHIVOS INCLUIDOS\n- ASTROLOGY-DATA.yaml: datos astrológicos calculados\n- AI-PROMPT.txt: instrucciones para una consulta con IA\n- PRIVATE-CHART-URL.txt: copia de la URL de tu página privada",
            "url": "PÁGINA PRIVADA DE TU CARTA",
            "privacy": "El ZIP y la URL privada contienen datos personales de nacimiento. No los compartas. Solo para uso personal; no se permite redistribuir ni revender.",
        },
        "de": {
            "title": "NANAMI ASTRO - PERSONAL EDITION FULL",
            "quick": "SCHNELLSTART",
            "steps": [
                "Speichere diese ZIP-Datei an einem sicheren Ort und entpacke alle Dateien.",
                "Öffne ASTROLOGY-DATA.yaml, um berechnete Radix-, Asteroiden- und Transitdaten anzusehen.",
                "Übergib AI-PROMPT.txt und ASTROLOGY-DATA.yaml an eine KI, damit sie die gespeicherten Werte ohne Neuberechnung deutet.",
                "Nutze deine private Horoskopseite, um den 1-Jahres-Planer zu erstellen und zu speichern oder deine Daten erneut herunterzuladen.",
            ],
            "files": "ENTHALTENE DATEIEN\n- ASTROLOGY-DATA.yaml: berechnete Astrologiedaten\n- AI-PROMPT.txt: Anleitung für eine KI-Beratung\n- PRIVATE-CHART-URL.txt: Kopie der URL deiner privaten Seite",
            "url": "PRIVATE HOROSKOPSEITE",
            "privacy": "ZIP und private URL enthalten persönliche Geburtsdaten. Gib sie nicht weiter. Nur zur persönlichen Nutzung; Weitergabe und Weiterverkauf sind untersagt.",
        },
    }[safe_lang]
    steps = "\n".join(f"{index}. {step}" for index, step in enumerate(copy["steps"], 1))
    url = f"\n\n{copy['url']}\n{chart_url}" if chart_url else ""
    return f"{copy['title']}\n\n{copy['quick']}\n{steps}\n\n{copy['files']}{url}\n\n{copy['privacy']}\n"


def _free_museum_readme(lang: str) -> str:
    if lang in {"es", "de"}:
        return {
            "es": "BIRTH CHART MUSEUM + DREAM SKY - EDICIÓN GRATUITA\n\nExtrae por completo el ZIP. En Windows abre START-MUSEUM-WINDOWS.bat; en Mac abre START-MUSEUM-MAC.command. Mantén abierta la ventana del servidor mientras usas el museo. Pega tu YAML astrológico en la entrada o utiliza la carta de ejemplo. La edición gratuita no incluye ACG personal ni el planificador personal.\n",
            "de": "BIRTH CHART MUSEUM + DREAM SKY – KOSTENLOSE EDITION\n\nEntpacke die ZIP-Datei vollständig. Öffne unter Windows START-MUSEUM-WINDOWS.bat und auf dem Mac START-MUSEUM-MAC.command. Lass das Serverfenster während der Nutzung geöffnet. Füge am Eingang deine Astrologie-YAML ein oder nutze das Beispielhoroskop. Persönliches ACG und der persönliche Planer sind nicht enthalten.\n",
        }[lang]
    if lang == "en":
        return (
            "BIRTH CHART MUSEUM + DREAM SKY - FREE EDITION\n\n"
            "IMPORTANT: Do not open HTML files inside the app folder directly.\n"
            "1. Extract the complete ZIP archive.\n"
            "2. Windows: double-click START-MUSEUM-WINDOWS.bat.\n"
            "   Mac: Control-click START-MUSEUM-MAC.command, then choose Open.\n"
            "3. Keep the server window open while using the Museum.\n"
            "4. Paste your astrology YAML at the entrance, or use the sample chart.\n\n"
            "This separate free package includes the Symbolic Museum, Architecture Museum, "
            "and Dream Sky. Personal ACG and the Personal Planner are not included.\n"
        )
    return (
        "出生図ミュージアム＋Dream Sky 無料版\n"
        "このファイルを最初にお読みください\n\n"
        "【重要】appフォルダー内のHTMLは直接開かないでください。\n"
        "1. ZIPを右クリックして「すべて展開」します。\n"
        "2. Windows：START-MUSEUM-WINDOWS.bat をダブルクリックします。\n"
        "   Mac：START-MUSEUM-MAC.command をControl＋クリックし、「開く」を選びます。\n"
        "3. 利用中は、起動時に表示されるサーバー画面を閉じないでください。\n"
        "4. 入口で占術データYAMLを貼り付けるか、サンプル出生図を選びます。\n\n"
        "この無料ZIPには、象徴ミュージアム、建築ミュージアム、Dream Skyが入っています。\n"
        "個人用ACGと個人プランナーは含まれません。\n"
    )


def _free_museum_direct_file_guard(lang: str) -> str:
    if lang != "ja":
        title = "Please start the Museum from the START file"
        lead = "This page was opened directly from the app folder, so its design and features cannot load."
        steps = (
            "<li>Close this page and extract the complete ZIP archive.</li>"
            "<li>Windows: double-click <strong>START-MUSEUM-WINDOWS.bat</strong>.</li>"
            "<li>Mac: Control-click <strong>START-MUSEUM-MAC.command</strong>, then choose Open.</li>"
        )
        note = "Do not open HTML files inside the app folder directly."
        if lang == "es":
            title = "Inicia el museo desde el archivo START"
            lead = "Esta página se abrió directamente desde la carpeta app, por lo que no puede cargar el diseño ni las funciones."
            steps = ("<li>Cierra esta página y extrae por completo el ZIP.</li><li>Windows: abre <strong>START-MUSEUM-WINDOWS.bat</strong>.</li><li>Mac: abre <strong>START-MUSEUM-MAC.command</strong>.</li>")
            note = "No abras directamente los archivos HTML de la carpeta app."
        elif lang == "de":
            title = "Starte das Museum über die START-Datei"
            lead = "Diese Seite wurde direkt aus dem app-Ordner geöffnet; Design und Funktionen können so nicht geladen werden."
            steps = ("<li>Schließe die Seite und entpacke die ZIP-Datei vollständig.</li><li>Windows: öffne <strong>START-MUSEUM-WINDOWS.bat</strong>.</li><li>Mac: öffne <strong>START-MUSEUM-MAC.command</strong>.</li>")
            note = "Öffne HTML-Dateien im app-Ordner nicht direkt."
    else:
        title = "STARTファイルからミュージアムを起動してください"
        lead = "appフォルダー内のHTMLを直接開いたため、デザインや機能を読み込めていません。"
        steps = (
            "<li>この画面を閉じ、ZIPを右クリックして「すべて展開」します。</li>"
            "<li>Windows：<strong>START-MUSEUM-WINDOWS.bat</strong> をダブルクリックします。</li>"
            "<li>Mac：<strong>START-MUSEUM-MAC.command</strong> をControl＋クリックし、「開く」を選びます。</li>"
        )
        note = "appフォルダー内のHTMLは直接開かないでください。"
    panel = (
        '<main class="museum-file-warning">'
        '<p class="museum-file-warning__eyebrow">BIRTH CHART MUSEUM + DREAM SKY</p>'
        f"<h1>{title}</h1><p>{lead}</p><ol>{steps}</ol>"
        f'<p class="museum-file-warning__note">{note}</p></main>'
    )
    return f"""
  <style id="museum-direct-file-style">
    html:has(.museum-file-warning), body:has(.museum-file-warning) {{ min-height: 100%; }}
    body:has(.museum-file-warning) {{ margin: 0 !important; padding: 28px !important; box-sizing: border-box;
      display: grid !important; place-items: center !important; background: #081127 !important;
      color: #f6f0df !important; font-family: system-ui, -apple-system, 'Segoe UI', sans-serif !important; }}
    .museum-file-warning {{ width: min(680px, 100%); box-sizing: border-box; padding: clamp(28px, 6vw, 56px);
      border: 1px solid #c9a227; border-radius: 20px; background: #101b38; box-shadow: 0 18px 60px #0008; }}
    .museum-file-warning__eyebrow {{ color: #e2bd39 !important; font-size: 13px !important;
      font-weight: 800 !important; letter-spacing: .12em; }}
    .museum-file-warning h1 {{ margin: 12px 0 18px !important; color: #fff !important;
      font-size: clamp(26px, 5vw, 40px) !important; line-height: 1.35 !important; }}
    .museum-file-warning p, .museum-file-warning li {{ font-size: 17px !important; line-height: 1.8 !important; }}
    .museum-file-warning ol {{ margin: 24px 0; padding-left: 1.5em; }}
    .museum-file-warning li + li {{ margin-top: 10px; }}
    .museum-file-warning strong {{ color: #ffdc5b !important; overflow-wrap: anywhere; }}
    .museum-file-warning__note {{ margin: 24px 0 0 !important; padding: 14px 16px;
      border-radius: 10px; background: #e2bd3918; color: #ffdf70 !important; font-weight: 700 !important; }}
  </style>
  <script>
  if (window.location.protocol === 'file:') {{
    document.addEventListener('DOMContentLoaded', function () {{
      document.title = {json.dumps(title, ensure_ascii=False)};
      document.body.innerHTML = {json.dumps(panel, ensure_ascii=False)};
    }});
  }}
  </script>
"""


def build_free_museum_zip(lang: str = "ja") -> bytes:
    safe_lang = lang if lang in {"ja", "en", "es", "de"} else "ja"
    source_path = ensure_template_zip(safe_lang)
    output = io.BytesIO()
    free_root = "BirthChartMuseum-Free"
    excluded_prefixes = (
        "app/acg/",
        "app/static/vendor/leaflet/",
        "app/static/geo/",
    )
    with zipfile.ZipFile(source_path, "r") as source, zipfile.ZipFile(
        output, "w", zipfile.ZIP_DEFLATED
    ) as target:
        for item in source.infolist():
            if "/" not in item.filename or item.is_dir():
                continue
            relative_name = item.filename.split("/", 1)[1]
            if (
                not relative_name
                or relative_name.startswith(excluded_prefixes)
                or relative_name.startswith("START-ACG-")
                or relative_name in {"README.txt", "YOUR_CHART.txt"}
            ):
                continue
            data = source.read(item.filename)
            if relative_name == "app/index.html":
                page = data.decode("utf-8")
                page = page.replace(
                    "</head>", _free_museum_direct_file_guard(safe_lang) + "</head>", 1
                )
                data = page.encode("utf-8")
            target.writestr(f"{free_root}/{relative_name}", data)
        readme_name = "README-FIRST.txt" if safe_lang != "ja" else "00-はじめに_README.txt"
        target.writestr(
            f"{free_root}/{readme_name}",
            _free_museum_readme(safe_lang).encode("utf-8-sig"),
        )
    return output.getvalue()


def build_personalized_zip(
    *,
    yaml_text: str,
    lang: str,
    include_acg: bool = False,
    chart_url: str | None = None,
    prompt_text: str | None = None,
) -> bytes:
    if not include_acg:
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as target:
            target.writestr("ASTROLOGY-DATA.yaml", yaml_text.encode("utf-8"))
            fallback_prompts = {
                "ja": "ASTROLOGY-DATA.yamlの計算済みデータを再計算せず、日本語で解釈してください。\n",
                "en": "Interpret the calculated values in ASTROLOGY-DATA.yaml in English without recalculating them.\n",
                "es": "Interpreta en español los valores calculados de ASTROLOGY-DATA.yaml sin volver a calcularlos.\n",
                "de": "Deute die berechneten Werte in ASTROLOGY-DATA.yaml auf Deutsch, ohne sie neu zu berechnen.\n",
            }
            ai_prompt = prompt_text or fallback_prompts.get(lang, fallback_prompts["en"])
            target.writestr("AI-PROMPT.txt", ai_prompt.encode("utf-8-sig"))
            guide_name = "README-FIRST.txt" if lang != "ja" else "はじめに_README.txt"
            target.writestr(
                guide_name,
                _buyer_readme(lang=lang, include_acg=False, chart_url=chart_url).encode("utf-8-sig"),
            )
            if chart_url:
                url_name = "PRIVATE-CHART-URL.txt" if lang != "ja" else "専用鑑定ページ_URL.txt"
                target.writestr(url_name, (chart_url + "\n").encode("utf-8-sig"))
        return output.getvalue()

    source_path = ensure_template_zip(lang)
    output = io.BytesIO()
    with zipfile.ZipFile(source_path, "r") as source, zipfile.ZipFile(
        output, "w", zipfile.ZIP_DEFLATED
    ) as target:
        acg_html = None
        city_data = None
        city_json_data = None
        leaflet_css = None
        leaflet_js = None
        source_names = source.namelist()
        root_name = next((name.split("/", 1)[0] for name in source_names if "/" in name), None)
        if not root_name:
            raise RuntimeError("Personal Edition ZIP root was not found")
        for item in source.infolist():
            if "/" not in item.filename:
                continue
            relative_name = item.filename.split("/", 1)[1]
            if not relative_name or item.is_dir():
                continue
            data = source.read(item.filename)
            if relative_name == "app/acg/index.html":
                acg_html = data.decode("utf-8")
            elif relative_name == "app/acg/cities.min.json":
                city_json_data = data.decode("utf-8")
                city_data = json.loads(city_json_data)
            elif relative_name == "app/static/vendor/leaflet/leaflet.css":
                leaflet_css = data.decode("utf-8")
            elif relative_name == "app/static/vendor/leaflet/leaflet.js":
                leaflet_js = data.decode("utf-8")
            continue
        if include_acg:
            if city_data is None and city_json_data is None:
                fallback_city_path = PE_DIR / "acg" / "cities.min.json"
                if not fallback_city_path.is_file():
                    raise RuntimeError("Personal Edition ACG city data asset was not found")
                city_json_data = fallback_city_path.read_text(encoding="utf-8")
                city_data = json.loads(city_json_data)
            acg_data = personal_geojson(yaml_text)
            standalone_acg_html = acg_html
            if (
                standalone_acg_html is None
                or "/* PERSONAL_ACG_DATA_START */" not in standalone_acg_html
                or "/* PERSONAL_CITY_DATA_START */" not in standalone_acg_html
                or "/* PERSONAL_WORLD_DATA_START */" not in standalone_acg_html
            ):
                standalone_acg_html = (PE_DIR / "acg" / "index.html").read_text(
                    encoding="utf-8"
                )
            if (
                standalone_acg_html is None
                or city_data is None
                or leaflet_css is None
                or leaflet_js is None
                or not city_json_data
            ):
                raise RuntimeError("Personal Edition ACG assets were not found")
            target.writestr(
                "START-ACG.html",
                _standalone_acg_html(
                    acg_html=standalone_acg_html,
                    leaflet_css=leaflet_css,
                    leaflet_js=leaflet_js,
                    acg_data=acg_data,
                    city_data=city_data,
                    world_data=json.loads((ROOT / "static" / "geo" / "ne_110m_admin_0_countries.geojson").read_text(encoding="utf-8")),
                    chart_url=chart_url,
                    show_ipad_online_link=True,
                    lang=lang,
                ).encode("utf-8"),
            )
            target.writestr("LICENSES.txt", _acg_licenses().encode("utf-8-sig"))
        guide = _acg_direct_start_readme(lang=lang, chart_url=chart_url)
        guide_name = "README-FIRST.txt" if lang != "ja" else "00-はじめに_README.txt"
        target.writestr(guide_name, guide.encode("utf-8-sig"))
        if chart_url:
            url_name = "PRIVATE-CHART-URL.txt" if lang != "ja" else "専用鑑定ページ_URL.txt"
            target.writestr(url_name, (chart_url + "\n").encode("utf-8-sig"))
    return output.getvalue()
