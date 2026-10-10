"""Build a provider-neutral, date-specific AI prompt for planner buyers."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import yaml

from services.yaml_exporter import build_transit_for_profile


PLANNER_AI_UI = {
    "ja": {
        "title": "この日の星をAIで読む",
        "lead": "この日専用の計算済みデータと依頼文です。コピーして、普段お使いのAIへ貼り付けてください。",
        "copy_button": "AI用プロンプトをコピー",
        "copied": "コピーしました。お好きなAIを開いて貼り付けてください。",
        "safety_note": "個人データをAIへ自動送信することはありません。コピー後に、利用者ご自身の判断でAIへ貼り付けます。AIの回答は誤ることがあります。医療・法律・金銭・安全に関わる判断には使用しないでください。",
        "invalid_date": "日付はYYYY-MM-DD形式で入力してください。",
        "outside_range": "指定した日付は対応期間外です。",
        "not_available": "この商品では日別AIプロンプトを利用できません。",
        "unavailable": "日別AIプロンプトを生成できませんでした。",
    },
    "en": {
        "title": "Read this day with AI",
        "lead": "Copy this calculated, date-specific prompt into the AI service you normally use.",
        "copy_button": "Copy AI prompt",
        "copied": "Copied. Open your preferred AI and paste it.",
        "safety_note": "Nothing is sent to an AI automatically. You decide whether to paste the copied text. AI can be wrong; do not use it for medical, legal, financial, or safety-critical decisions.",
        "invalid_date": "Enter the date in YYYY-MM-DD format.",
        "outside_range": "The selected date is outside the supported range.",
        "not_available": "The daily AI prompt is not available for this product.",
        "unavailable": "The daily AI prompt could not be generated.",
    },
    "es": {
        "title": "Interpreta este día con IA",
        "lead": "Copia este prompt, calculado para la fecha seleccionada, y pégalo en el servicio de IA que uses habitualmente.",
        "copy_button": "Copiar prompt para IA",
        "copied": "Copiado. Abre tu IA preferida y pega el texto.",
        "safety_note": "No se envían datos personales automáticamente a ninguna IA. Tú decides si pegas el texto copiado. La IA puede equivocarse; no la uses para tomar decisiones médicas, legales, financieras o relacionadas con la seguridad.",
        "invalid_date": "Introduce la fecha en formato AAAA-MM-DD.",
        "outside_range": "La fecha seleccionada está fuera del periodo disponible.",
        "not_available": "El prompt diario para IA no está disponible para este producto.",
        "unavailable": "No se pudo generar el prompt diario para IA.",
    },
    "de": {
        "title": "Diesen Tag mit KI deuten",
        "lead": "Kopiere diesen für das gewählte Datum berechneten Prompt in den KI-Dienst, den du normalerweise verwendest.",
        "copy_button": "KI-Prompt kopieren",
        "copied": "Kopiert. Öffne deinen bevorzugten KI-Dienst und füge den Text ein.",
        "safety_note": "Es werden keine persönlichen Daten automatisch an eine KI gesendet. Du entscheidest selbst, ob du den kopierten Text einfügst. KI kann Fehler machen; nutze sie nicht für medizinische, rechtliche, finanzielle oder sicherheitskritische Entscheidungen.",
        "invalid_date": "Gib das Datum im Format JJJJ-MM-TT ein.",
        "outside_range": "Das gewählte Datum liegt außerhalb des verfügbaren Zeitraums.",
        "not_available": "Der tägliche KI-Prompt ist für dieses Produkt nicht verfügbar.",
        "unavailable": "Der tägliche KI-Prompt konnte nicht erstellt werden.",
    },
}


def get_planner_ai_ui(lang: str) -> dict[str, str]:
    return PLANNER_AI_UI.get(lang, PLANNER_AI_UI["en"])


def _strip_japanese_display_fields(value):
    """Remove buyer-visible Japanese helper fields from non-Japanese prompts.

    The stored chart remains unchanged.  Only the small, date-specific payload
    rendered in the textarea is sanitized, so calculation and persistence keep
    their existing data shape.
    """
    if isinstance(value, dict):
        return {
            key: _strip_japanese_display_fields(item)
            for key, item in value.items()
            if not str(key).endswith("_ja")
        }
    if isinstance(value, list):
        return [_strip_japanese_display_fields(item) for item in value]
    return value


def build_daily_ai_prompt(*, chart_yaml: str, target_date: date, lang: str = "ja") -> str:
    source_doc = yaml.safe_load(chart_yaml) or {}
    source = source_doc.get("input") or {}
    # International planners display the sky in UTC. Keep the
    # date-specific prompt on that same calendar day instead of silently
    # recalculating it in the buyer's local timezone.
    tz_name = str(source.get("timezone") or "Asia/Tokyo") if lang == "ja" else "UTC"
    western = ((source_doc.get("systems") or {}).get("western") or {})
    natal = western.get("natal") or {}
    natal_bodies = natal.get("bodies") or {}
    natal_houses = natal.get("houses") or {}
    lat = source.get("birth_lat")
    lng = source.get("birth_lng")
    if not natal_bodies or lat is None or lng is None:
        raise ValueError("chart YAML is missing stored natal data or birth coordinates")
    start = datetime.combine(target_date, datetime.min.time(), tzinfo=ZoneInfo(tz_name))
    transit = build_transit_for_profile(
        profile="standard",
        start_date=start,
        days=1,
        lat=float(lat),
        lng=float(lng),
        pref_name=str(source.get("prefecture") or source.get("birth_place") or ""),
        tz_name=tz_name,
        natal_bodies=natal_bodies,
        natal_houses=natal_houses,
    )
    daily = transit.get("daily") or []
    day_data = daily[0] if daily else {}
    ai_data = {
        "target_date": target_date.isoformat(),
        "timezone": tz_name,
        "natal_bodies": natal.get("bodies") or {},
        "transit": {
            "date": day_data.get("date"),
            "time": day_data.get("time"),
            "transiting_bodies": day_data.get("transiting_bodies") or {},
            "natal_aspects": day_data.get("natal_aspects") or [],
            "moon_timepoints": day_data.get("moon_timepoints") or [],
        },
    }
    if lang != "ja":
        ai_data = _strip_japanese_display_fields(ai_data)
    data_text = yaml.safe_dump(ai_data, allow_unicode=True, sort_keys=False)
    instructions = {
        "en": (
            "Interpret the calculated astrology data below without recalculating it. "
            "Explain this person's day in plain language under: overall theme, work, "
            "relationships, emotional/physical condition, helpful actions, and cautions. "
            "Treat astrology as a reflective aid, not a certainty or professional advice."
        ),
        "es": (
            "Interpreta los datos astrológicos ya calculados que aparecen a continuación, "
            "sin volver a calcularlos. Explica el día de esta persona con un lenguaje claro "
            "y divide la respuesta en: tema general, trabajo, relaciones, estado emocional y "
            "físico, acciones favorables y precauciones. Trata la astrología como una herramienta "
            "de reflexión, no como una certeza ni como asesoramiento profesional."
        ),
        "de": (
            "Deute die folgenden bereits berechneten astrologischen Daten, ohne sie neu zu berechnen. "
            "Erkläre den Tag dieser Person in verständlicher Sprache und gliedere die Antwort in: "
            "Gesamtthema, Arbeit, Beziehungen, emotionales und körperliches Befinden, hilfreiche "
            "Handlungen und Hinweise. Behandle Astrologie als Reflexionshilfe, nicht als Gewissheit "
            "oder professionelle Beratung."
        ),
        "ja": (
            "以下の計算済み占星術データを再計算せずに読み解いてください。専門用語を減らし、"
            "この人の一日について「全体テーマ・仕事・人間関係・心身の状態・おすすめの行動・"
            "気をつけたいこと」に分けて説明してください。断定や不安をあおる表現を避け、"
            "占星術は振り返りのヒントとして扱ってください。"
        ),
    }
    instruction = instructions.get(lang, instructions["en"])
    return f"{instruction}\n\n```yaml\n{data_text}```\n"
