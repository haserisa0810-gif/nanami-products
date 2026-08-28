"""Localized labels and validation messages for buyer birth-data forms.

The Japanese prefecture value remains the stable resolver key.  Only the
customer-visible label changes with the requested locale.
"""

from __future__ import annotations


PREFECTURE_LABELS_EN = (
    "Hokkaido", "Aomori", "Iwate", "Miyagi", "Akita", "Yamagata", "Fukushima",
    "Ibaraki", "Tochigi", "Gunma", "Saitama", "Chiba", "Tokyo", "Kanagawa",
    "Niigata", "Toyama", "Ishikawa", "Fukui", "Yamanashi", "Nagano", "Gifu",
    "Shizuoka", "Aichi", "Mie", "Shiga", "Kyoto", "Osaka", "Hyogo", "Nara",
    "Wakayama", "Tottori", "Shimane", "Okayama", "Hiroshima", "Yamaguchi",
    "Tokushima", "Kagawa", "Ehime", "Kochi", "Fukuoka", "Saga", "Nagasaki",
    "Kumamoto", "Oita", "Miyazaki", "Kagoshima", "Okinawa",
)


FORM_UI = {
    "ja": {
        "order_placeholder": "例：9824333454 / cU-yVsYa22tGvZCc4A5cWw==",
        "coconala_placeholder": "例：nanami_user",
        "order_format_title": "英数字、ハイフン、アンダースコア、イコールのみ使用できます",
        "domestic_map_note": "国内の方でも緯度・経度を指定したい場合は「海外」を選び、地図から出生地を選択してください。",
        "city_placeholder": "例：新宿区",
        "map_click_note": "地図をクリックすると緯度・経度が自動入力されます（手入力も可能）。",
        "overseas_place_placeholder": "例：New York, USA",
        "latitude_placeholder": "例：35.6895",
        "longitude_placeholder": "例：139.6917",
        "birth_date_title": "日付は YYYY-MM-DD 形式で入力してください",
    },
    "en": {
        "order_placeholder": "Example: 9824333454 / cU-yVsYa22tGvZCc4A5cWw==",
        "coconala_placeholder": "Example: nanami_user",
        "order_format_title": "Use letters, numbers, hyphens, underscores, and equals signs only.",
        "domestic_map_note": "To specify exact coordinates for a birth in Japan, choose Outside Japan and select the birthplace on the map.",
        "city_placeholder": "Example: Shinjuku",
        "map_click_note": "Click the map to fill in latitude and longitude automatically; you can also enter them manually.",
        "overseas_place_placeholder": "Example: New York, USA",
        "latitude_placeholder": "Example: 35.6895",
        "longitude_placeholder": "Example: 139.6917",
        "birth_date_title": "Enter the date as YYYY-MM-DD.",
    },
    "es": {
        "order_placeholder": "Ejemplo: 9824333454 / cU-yVsYa22tGvZCc4A5cWw==",
        "coconala_placeholder": "Ejemplo: nanami_user",
        "order_format_title": "Utiliza solo letras, números, guiones, guiones bajos y signos igual.",
        "domestic_map_note": "Para indicar coordenadas exactas de un nacimiento en Japón, elige Fuera de Japón y selecciona el lugar en el mapa.",
        "city_placeholder": "Ejemplo: Shinjuku",
        "map_click_note": "Haz clic en el mapa para completar la latitud y longitud; también puedes introducirlas manualmente.",
        "overseas_place_placeholder": "Ejemplo: Nueva York, EE. UU.",
        "latitude_placeholder": "Ejemplo: 35.6895",
        "longitude_placeholder": "Ejemplo: 139.6917",
        "birth_date_title": "Introduce la fecha con el formato AAAA-MM-DD.",
    },
    "de": {
        "order_placeholder": "Beispiel: 9824333454 / cU-yVsYa22tGvZCc4A5cWw==",
        "coconala_placeholder": "Beispiel: nanami_user",
        "order_format_title": "Verwende nur Buchstaben, Zahlen, Bindestriche, Unterstriche und Gleichheitszeichen.",
        "domestic_map_note": "Um genaue Koordinaten für eine Geburt in Japan anzugeben, wähle Außerhalb Japans und den Geburtsort auf der Karte.",
        "city_placeholder": "Beispiel: Shinjuku",
        "map_click_note": "Klicke auf die Karte, um Breiten- und Längengrad automatisch einzutragen; eine manuelle Eingabe ist ebenfalls möglich.",
        "overseas_place_placeholder": "Beispiel: New York, USA",
        "latitude_placeholder": "Beispiel: 35.6895",
        "longitude_placeholder": "Beispiel: 139.6917",
        "birth_date_title": "Gib das Datum im Format JJJJ-MM-TT ein.",
    },
}


ERROR_MESSAGES = {
    "ja": {
        "number": "{field}は数値で入力してください。",
        "latitude_range": "緯度は -90 から 90 の範囲で入力してください。",
        "overseas_prefecture": "海外出生の場合は、出生都道府県を未選択にしてください。",
        "overseas_place": "海外出生の場合は出生地名を入力してください。",
        "overseas_timezone": "海外出生の場合はタイムゾーンを入力してください。",
        "timezone_invalid": "タイムゾーンが正しくありません。例: America/New_York",
        "overseas_coordinates": "海外出生の場合は緯度・経度を入力してください。",
        "prefecture_required": "出生都道府県を選択してください。",
        "domestic_overseas_fields": "国内出生の場合は、海外出生地名とタイムゾーン欄を空にしてください。",
        "coordinate_pair": "緯度・経度を指定する場合は、両方入力してください。",
        "latitude": "緯度", "longitude": "経度",
        "exact_time_required": "正確な出生時刻ありを選んだ場合は、出生時刻を入力してください。",
        "time_choice_invalid": "出生時刻の選択肢が不正です。",
        "exact_time_note": "出生時刻あり。ハウス・ASC・MCを通常通り使用できます。",
        "unknown_time_note": "出生時刻不明のため12:00で仮計算しています。ハウス・ASC・MCは参考値です。",
        "approximate_time_note": "出生時刻は{period}の推定レンジです。ハウス・ASC・MCは参考値です。",
        "morning": "午前", "afternoon": "午後", "night": "夜",
    },
    "en": {
        "number": "Enter {field} as a number.",
        "latitude_range": "Latitude must be between -90 and 90.",
        "overseas_prefecture": "For a birth outside Japan, leave the prefecture field unselected.",
        "overseas_place": "Enter the birthplace for a birth outside Japan.",
        "overseas_timezone": "Select or enter the timezone for a birth outside Japan.",
        "timezone_invalid": "The timezone is invalid. Example: America/New_York",
        "overseas_coordinates": "Enter both latitude and longitude for a birth outside Japan.",
        "prefecture_required": "Select the birth prefecture.",
        "domestic_overseas_fields": "For a birth in Japan, leave the international birthplace and timezone fields empty.",
        "coordinate_pair": "Enter both latitude and longitude when specifying coordinates.",
        "latitude": "latitude", "longitude": "longitude",
        "exact_time_required": "Enter the birth time when Exact time is selected.",
        "time_choice_invalid": "The selected birth-time accuracy is invalid.",
        "exact_time_note": "Exact birth time provided. Houses, ASC, and MC can be used normally.",
        "unknown_time_note": "Birth time is unknown, so the chart is provisionally calculated for 12:00. Houses, ASC, and MC are approximate.",
        "approximate_time_note": "Birth time is estimated as {period}. Houses, ASC, and MC are approximate.",
        "morning": "morning", "afternoon": "afternoon", "night": "evening/night",
    },
    "es": {
        "number": "Introduce {field} como número.", "latitude_range": "La latitud debe estar entre -90 y 90.",
        "overseas_prefecture": "Para un nacimiento fuera de Japón, deja la prefectura sin seleccionar.",
        "overseas_place": "Introduce el lugar de nacimiento fuera de Japón.", "overseas_timezone": "Selecciona o introduce la zona horaria.",
        "timezone_invalid": "La zona horaria no es válida. Ejemplo: America/New_York", "overseas_coordinates": "Introduce la latitud y la longitud.",
        "prefecture_required": "Selecciona la prefectura de nacimiento.", "domestic_overseas_fields": "Para un nacimiento en Japón, deja vacíos el lugar internacional y la zona horaria.",
        "coordinate_pair": "Introduce tanto la latitud como la longitud.", "latitude": "latitud", "longitude": "longitud",
        "exact_time_required": "Introduce la hora de nacimiento al seleccionar Hora exacta.", "time_choice_invalid": "La precisión de la hora seleccionada no es válida.",
        "exact_time_note": "Se proporcionó una hora exacta. Las casas, ASC y MC pueden utilizarse normalmente.",
        "unknown_time_note": "La hora es desconocida; el cálculo provisional usa las 12:00. Las casas, ASC y MC son aproximados.",
        "approximate_time_note": "La hora se estima como {period}. Las casas, ASC y MC son aproximados.", "morning": "mañana", "afternoon": "tarde", "night": "noche",
    },
    "de": {
        "number": "Gib {field} als Zahl ein.", "latitude_range": "Der Breitengrad muss zwischen -90 und 90 liegen.",
        "overseas_prefecture": "Lass bei einer Geburt außerhalb Japans die Präfektur unausgewählt.",
        "overseas_place": "Gib den Geburtsort außerhalb Japans ein.", "overseas_timezone": "Wähle die Zeitzone aus oder gib sie ein.",
        "timezone_invalid": "Die Zeitzone ist ungültig. Beispiel: America/New_York", "overseas_coordinates": "Gib Breiten- und Längengrad ein.",
        "prefecture_required": "Wähle die Geburtspräfektur.", "domestic_overseas_fields": "Lass bei einer Geburt in Japan den internationalen Ort und die Zeitzone leer.",
        "coordinate_pair": "Gib sowohl Breiten- als auch Längengrad ein.", "latitude": "Breitengrad", "longitude": "Längengrad",
        "exact_time_required": "Gib die Geburtszeit ein, wenn Genaue Uhrzeit ausgewählt ist.", "time_choice_invalid": "Die gewählte Genauigkeit der Geburtszeit ist ungültig.",
        "exact_time_note": "Eine genaue Geburtszeit wurde angegeben. Häuser, AC und MC können normal verwendet werden.",
        "unknown_time_note": "Die Geburtszeit ist unbekannt; vorläufig wird 12:00 verwendet. Häuser, AC und MC sind Näherungswerte.",
        "approximate_time_note": "Die Geburtszeit wird als {period} geschätzt. Häuser, AC und MC sind Näherungswerte.", "morning": "morgens", "afternoon": "nachmittags", "night": "abends/nachts",
    },
}


def normalized_lang(lang: str) -> str:
    return lang if lang in FORM_UI else "ja"


def form_ui(lang: str) -> dict[str, str]:
    return FORM_UI[normalized_lang(lang)]


def buyer_error(lang: str, key: str, **values: object) -> str:
    locale = normalized_lang(lang)
    template = ERROR_MESSAGES[locale].get(key) or ERROR_MESSAGES["en"].get(key) or key
    return template.format(**values)


def prefecture_options(prefectures: list[str], lang: str) -> list[dict[str, str]]:
    if normalized_lang(lang) == "ja":
        return [{"value": value, "label": value} for value in prefectures]
    if len(prefectures) != len(PREFECTURE_LABELS_EN):
        raise ValueError("prefecture catalogue length mismatch")
    return [
        {"value": value, "label": label}
        for value, label in zip(prefectures, PREFECTURE_LABELS_EN)
    ]
