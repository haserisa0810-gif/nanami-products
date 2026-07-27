# -*- coding: utf-8 -*-
"""Bilingual (en/ja) strings, name maps, and formatters for the planner.

Data only, no reportlab dependency, so both pipeline stages can import it.
"""

from __future__ import annotations

from datetime import date, datetime


PLANETS = {
    "Sun": "太陽", "Moon": "月", "Mercury": "水星", "Venus": "金星", "Mars": "火星",
    "Jupiter": "木星", "Saturn": "土星", "Uranus": "天王星", "Neptune": "海王星",
    "Pluto": "冥王星", "Chiron": "キロン", "North Node": "ドラゴンヘッド",
    "South Node": "ドラゴンテイル", "Ascendant": "アセンダント", "Midheaven": "MC",
    "ASC": "アセンダント", "MC": "MC",
}

SIGNS_JA = {
    "Aries": "牡羊座", "Taurus": "牡牛座", "Gemini": "双子座", "Cancer": "蟹座",
    "Leo": "獅子座", "Virgo": "乙女座", "Libra": "天秤座", "Scorpio": "蠍座",
    "Sagittarius": "射手座", "Capricorn": "山羊座", "Aquarius": "水瓶座", "Pisces": "魚座",
}

ASPECTS_JA = {
    "Conjunction": "合", "Sextile": "セクスタイル", "Square": "スクエア",
    "Trine": "トライン", "Opposition": "オポジション",
    "conjunction": "合", "sextile": "セクスタイル", "square": "スクエア",
    "trine": "トライン", "opposition": "オポジション",
}

PHASE_EVENTS_JA = {
    "New Moon": "新月", "First Quarter": "上弦の月",
    "Full Moon": "満月", "Last Quarter": "下弦の月",
}

PHASE_LABELS_JA = {
    "New": "新月", "Waxing Crescent": "三日月", "First Quarter": "上弦の月",
    "Waxing Gibbous": "十三夜月", "Full": "満月", "Waning Gibbous": "寝待月",
    "Last Quarter": "下弦の月", "Waning Crescent": "有明月",
}
# "New"/"Full" need the word Moon in English; the other phase names stand alone.
PHASE_LABELS_EN = {"New": "New Moon", "Full": "Full Moon"}


def phase_label(lang: str, name: str) -> str:
    if lang == "ja":
        return PHASE_LABELS_JA.get(name, name)
    return PHASE_LABELS_EN.get(name, name)

MONTHS_JA = ["1月", "2月", "3月", "4月", "5月", "6月", "7月", "8月", "9月", "10月", "11月", "12月"]
WEEKDAYS_JA = ["月", "火", "水", "木", "金", "土", "日"]  # Monday first
WEEKDAY_FULL_JA = ["月曜日", "火曜日", "水曜日", "木曜日", "金曜日", "土曜日", "日曜日"]

TZ_LABELS = {
    "UTC": "UTC", "Asia/Tokyo": "JST",
}

# Long-term transit hint templates: theme of the transiting body + tone of the aspect.
TRANSIT_THEMES = {
    "Jupiter": {"en": "Growth and opportunity", "ja": "拡大や可能性"},
    "Saturn": {"en": "Structure and responsibility", "ja": "責任や現実化"},
    "Uranus": {"en": "Change and independence", "ja": "変化や独立"},
    "Neptune": {"en": "Vision and intuition", "ja": "理想や直感"},
    "Pluto": {"en": "Deep transformation", "ja": "深い変容"},
    "Chiron": {"en": "Healing and vulnerability", "ja": "癒しや弱点の扱い"},
    "North Node": {"en": "Your growth direction", "ja": "今後伸ばす方向性"},
    "South Node": {"en": "Release and old patterns", "ja": "手放しや過去パターン"},
}

ASPECT_TONES = {
    "conjunction": {"en": "strongly activates", "ja": "強く始動する"},
    "sextile": {"en": "opens an opportunity around", "ja": "機会として使いやすい"},
    "square": {"en": "creates productive tension with", "ja": "調整課題として表れやすい"},
    "trine": {"en": "flows easily with", "ja": "自然に活かしやすい"},
    "opposition": {"en": "brings awareness through others to", "ja": "外部との関係から意識化される"},
}


def transit_hint(lang: str, transit_body: str, aspect: str, natal_body: str) -> str:
    theme = TRANSIT_THEMES.get(transit_body, {"en": "This cycle", "ja": "この周期"})[lang if lang in ("en", "ja") else "en"]
    tone = ASPECT_TONES.get(aspect.lower(), ASPECT_TONES["conjunction"])[lang if lang in ("en", "ja") else "en"]
    if lang == "ja":
        return f"{theme}が{body_name('ja', natal_body)}のテーマに{tone}時期"
    return f"{theme} {tone} your natal {natal_body} themes"


def body_name(lang: str, name: str) -> str:
    if lang == "ja":
        return PLANETS.get(name, name)
    return name


def sign_name(lang: str, name: str) -> str:
    if lang == "ja":
        return SIGNS_JA.get(name, name)
    return name


def aspect_name(lang: str, name: str) -> str:
    if lang == "ja":
        return ASPECTS_JA.get(name, name)
    return name


def month_name(lang: str, month: int) -> str:
    import calendar
    if lang == "ja":
        return MONTHS_JA[month - 1]
    return calendar.month_name[month]


def month_abbr(lang: str, month: int) -> str:
    import calendar
    if lang == "ja":
        return MONTHS_JA[month - 1]
    return calendar.month_abbr[month]


def fmt_month_day(lang: str, value: date | datetime) -> str:
    if lang == "ja":
        return f"{value.month}/{value.day}"
    return value.strftime("%b %d")


def fmt_month_day_long(lang: str, value: date | datetime) -> str:
    if lang == "ja":
        return f"{value.month}月{value.day}日"
    return value.strftime("%B %d")


def fmt_full_date(lang: str, value: date | datetime) -> str:
    if lang == "ja":
        return f"{value.year}年{value.month}月{value.day}日"
    return value.strftime("%B %d, %Y")


def fmt_weekday(lang: str, value: date | datetime) -> str:
    if lang == "ja":
        return WEEKDAY_FULL_JA[value.weekday()]
    return value.strftime("%A")


def fmt_month_year(lang: str, year: int, month: int) -> str:
    if lang == "ja":
        return f"{year}年{MONTHS_JA[month - 1]}"
    import calendar
    return f"{calendar.month_name[month]} {year}"


def tz_label(tz_name: str) -> str:
    return TZ_LABELS.get(tz_name, tz_name)


def event_display(lang: str, event: dict) -> str:
    """Localized display name for a common-layer event (structured fields preferred)."""
    kind = event.get("type")
    if kind == "moon_phase":
        base = PHASE_EVENTS_JA[event["name"]] if lang == "ja" else event["name"]
        if lang == "ja":
            return f"{sign_name('ja', event['sign'])}の{base}"
        return f"{base} in {event['sign']}"
    if kind == "station":
        body = body_name(lang, event["body"])
        if lang == "ja":
            return f"{body}が逆行開始" if event["direction"] == "Retrograde" else f"{body}が順行に戻る"
        return event["name"]
    if kind == "ingress":
        if lang == "ja":
            return f"{body_name('ja', event['body'])}が{sign_name('ja', event['sign'])}入り"
        return event["name"]
    if kind == "outer_aspect":
        if lang == "ja" and "bodies" in event:
            a, b = event["bodies"]
            return f"{body_name('ja', a)} {aspect_name('ja', event['aspect'])} {body_name('ja', b)}"
        return event["name"]
    return event.get("name", "")


def aspect_display(lang: str, item: dict) -> str:
    """Localized display for a daily aspect item (needs body_a/aspect/body_b fields)."""
    if lang == "ja" and "body_a" in item:
        return f"{body_name('ja', item['body_a'])} {aspect_name('ja', item['aspect'])} {body_name('ja', item['body_b'])}"
    return item["name"]


def personal_window_display(lang: str, item: dict) -> str:
    t = body_name(lang, item["transiting_body"])
    n = body_name(lang, item["natal_body"])
    a = aspect_name(lang, item["aspect"])
    if lang == "ja":
        return f"{t}→出生の{n}（{a}）"
    return f"{item['transiting_body']} {item['aspect'].capitalize()} natal {item['natal_body']}"


STR = {
    "en": {
        "brand": "nanami-astro",
        "planner_title": "Astrology Transit Planner",
        "tagline": "Observe the Sky, Record Your Life",
        "cover_kicker": "NANAMI-ASTRO  /  ANNUAL TRANSIT PLANNER",
        "cover_format": "PORTRAIT DIGITAL PLANNER",
        "cover_edition_common": "Common Edition + Fictional Personal Edition Sample",
        "cover_edition_personal": "Personal Edition  /  {name}",
        "cover_note": "Calculated sky data shown in {tz}  |  Hyperlinked PDF",
        "eyebrow_default": "OBSERVE THE SKY. RECORD YOUR LIFE.",
        "footer": "{period} ASTROLOGY TRANSIT PLANNER  |  {tz}  |  {edition}",
        "edition_prototype": "PROTOTYPE",
        "edition_full": "FULL EDITION",
        "edition_personal": "PERSONAL EDITION",
        "nav_index": "INDEX", "nav_year": "YEAR", "nav_personal": "PERSONAL",
        "guide_title": "How to Use This Planner",
        "guide_intro": "This is a record of observation, not a script for your day. Notice the sky, document real experience, and compare the two with curiosity.",
        "guide_1_head": "1  OBSERVE", "guide_1_body": "Read the calculated transits and note what draws your attention.",
        "guide_2_head": "2  RECORD", "guide_2_body": "Track events, mood, body signals, decisions, and context in your own words.",
        "guide_3_head": "3  REFLECT", "guide_3_body": "Ask what matched, what did not, and what pattern is actually supported by your notes.",
        "calc_standard": "CALCULATION STANDARD",
        "calc_items": [
            "Tropical zodiac; geocentric planetary positions",
            "Swiss Ephemeris with built-in Moshier planetary calculations",
            "Daily placements sampled at 12:00 {tz}; exact events include {tz} time",
            "Calendar dates follow the {tz} time zone",
            "Production release must be cross-checked with the nanami-astro engine",
        ],
        "personal_boundary_head": "PERSONAL EDITION BOUNDARY",
        "personal_boundary_body": "The Personal Edition pages in this prototype use fictional birth data. A commercial personalized product needs explicit consent, a secure order process, a correction policy for birth data, and a defined deletion schedule.",
        "your_data_head": "ABOUT YOUR DATA",
        "your_data_body": "This planner was generated from the birth data shown on the profile page. Check it before reading further: if anything is wrong, request a correction. Calculations were made once at generation time; this PDF works offline and nothing in it phones home.",
        "index_title": "Index",
        "idx_year": "YEAR AT A GLANCE", "idx_aspects": "MAJOR TRANSITS", "idx_retro": "RETROGRADES",
        "idx_phases": "MOON PHASES", "idx_personal": "PERSONAL", "idx_personal_sample": "PERSONAL SAMPLE",
        "idx_ai": "NOTES FOR AI", "idx_daily_full": "DAILY PAGES", "idx_daily_sample": "DAILY SAMPLE (JAN 1-7)",
        "idx_reflection": "MONTHLY REFLECTION", "idx_notes": "NOTES",
        "idx_months": "MONTHS", "idx_month_sub": "OVERVIEW  +  CALENDAR",
        "scope_head_full": "EDITION SCOPE",
        "scope_full": "All {count} monthly dashboards, calendars, dated daily pages, monthly reflections, and notes pages are included. Daily pages link to the previous and next day and back to the month calendar.",
        "scope_head_proto": "PROTOTYPE SCOPE",
        "scope_proto": "All twelve month dashboards and calendars are included. January 1-7 demonstrate dated daily pages. The full build mode generates all 365 daily pages and monthly reflections.",
        "scope_head_personal": "YOUR EDITION",
        "scope_personal": "Calculated from your birth details: twelve months from {start}, all dated daily pages, monthly reflections, your personal transit seasons, and monthly focus dates.",
        "year_title": "Year at a Glance",
        "weekday_letters": ["M", "T", "W", "T", "F", "S", "S"],
        "new_short": "New", "full_short": "Full",
        "aspects_title": "Selected Major Transits",
        "aspects_eyebrow": "SKY OVERVIEW  /  EXACT TIMES IN {tz}",
        "aspects_intro": "Selected exact major aspects among Jupiter, Saturn, Uranus, Neptune, and Pluto. Treat these as observation markers rather than guaranteed outcomes.",
        "exact": "EXACT",
        "what_observe": "WHAT WILL YOU OBSERVE?",
        "retro_title": "Retrograde Overview",
        "retro_eyebrow": "STATIONS AND RETROGRADE PERIODS  /  {tz}",
        "retro_intro": "Each period below runs between calculated stations (the moments a planet turns retrograde or direct). 'Before {start}' means the cycle was already under way when this planner begins.",
        "retro_planet": "PLANET", "retro_begins": "RETROGRADE BEGINS", "retro_ends": "DIRECT / END",
        "before_start": "Before {start}", "into_next": "Into {year}", "beyond_end": "Beyond {date}",
        "station_notes": "OBSERVATION NOTES",
        "phases_title_1": "Moon Phases I", "phases_title_2": "Moon Phases II",
        "phases_eyebrow": "LUNAR CYCLE  /  EXACT TIMES IN {tz}",
        "moon_in": "Moon in {sign}  /  {tz}",
        "month_eyebrow": "MONTHLY TRANSIT DASHBOARD  /  {tz}",
        "key_sky_dates": "KEY SKY DATES",
        "monthly_intention": "MONTHLY INTENTION", "what_to_observe": "WHAT TO OBSERVE",
        "body_energy": "BODY + ENERGY BASELINE",
        "baseline_items": ["Sleep", "Energy", "Focus", "Tension"],
        "questions_month": "QUESTIONS FOR THIS MONTH",
        "month_questions": ["What actually changed?", "What repeated?", "What did the forecast not explain?"],
        "calendar_title": "{month} Calendar",
        "calendar_eyebrow": "MONTH AT A GLANCE  /  TAP A DATED PAGE",
        "weekday_heads": ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"],
        "linked_daily": "Has a linked daily page",
        "back_overview": "BACK TO OVERVIEW",
        "personal_peak_legend": "Personal focus date",
        "daily_eyebrow": "{weekday}  /  DAILY TRANSIT RECORD  /  12:00 {tz} SNAPSHOT",
        "moon_head": "MOON", "phase_suffix": "{phase}",
        "major_aspects": "MAJOR ASPECTS",
        "no_major_aspect": "No major aspect within the display orb",
        "orb_deg": "orb {orb} deg",
        "long_term": "LONG-TERM TRANSITS",
        "your_transits": "YOUR ACTIVE TRANSITS",
        "no_long_term": "No major outer-planet aspect within the display orb",
        "no_personal_active": "No long-term transit active today",
        "peak": "peak {date}",
        "mood": "MOOD", "low": "LOW", "high": "HIGH",
        "body_health": "BODY + HEALTH",
        "health_items": ["Headache", "Fatigue", "Poor sleep"],
        "what_happened": "WHAT HAPPENED TODAY?",
        "transit_reflection": "TRANSIT REFLECTION",
        "reflection_hint": "What matched? What did not? What else explains the day?",
        "notes_head": "NOTES",
        "ai_guide_link": "AI PROMPT GUIDE",
        "day_calendar_link": "{month} CALENDAR",
        "reflection_title": "{month} Reflection",
        "reflection_eyebrow": "REVIEW THE RECORD  /  KEEP WHAT YOUR NOTES SUPPORT",
        "reflection_prompts": [
            "What events or feelings repeated?",
            "Which transit descriptions seemed relevant?",
            "Which descriptions did not match lived experience?",
            "What non-astrological factors mattered most?",
            "What would you like to observe next month?",
        ],
        "personal_title_sample": "Personal Edition Sample",
        "personal_title": "Your Personal Edition",
        "personal_eyebrow_sample": "FICTIONAL PROFILE  /  CUSTOM TRANSITS DEMONSTRATION",
        "personal_eyebrow": "PERSONAL EDITION  /  CALCULATED FOR YOUR BIRTH CHART",
        "profile_head_sample": "SAMPLE PROFILE A",
        "profile_head": "YOUR PROFILE",
        "birth_label": "Birth: {value}", "place_label": "Place: {value}",
        "zodiac_label": "Zodiac: {zodiac}  |  Houses: {houses}",
        "tz_line": "Planner time zone: {tz}",
        "layer_personal_head": "PERSONALIZED LAYER",
        "layer_personal_body": "Natal placements, angles, long-term transit seasons to your natal chart, personal focus dates, and house context.",
        "layer_common_head": "COMMON LAYER",
        "layer_common_body": "Moon phases, ingresses, stations, collective aspects, and the same reflective journal structure.",
        "safeguards_head": "FULFILLMENT SAFEGUARDS",
        "safeguards": [
            "Collect only the birth data required for calculation.",
            "Show the customer the interpreted time zone before generating.",
            "Allow one correction when supplied birth data is wrong.",
            "Delete order data and generated working files on a published schedule.",
            "Keep the finished PDF usable without the nanami-astro server.",
        ],
        "natal_title": "Natal Snapshot",
        "natal_eyebrow": "PERSONAL EDITION  /  {suffix}",
        "natal_fictional": "FICTIONAL SAMPLE DATA",
        "natal_yours": "YOUR BIRTH CHART",
        "placements": "PLACEMENTS", "outer_angles": "OUTER PLANETS + ANGLES",
        "reading_boundary": "READING BOUNDARY",
        "reading_boundary_body_sample": "These placements are calculated from the fictional sample profile. A customer edition should show the exact submitted birth data and calculation standard on this page so errors can be identified before interpretation.",
        "reading_boundary_body": "These placements are calculated from the birth data on the previous page. If the birth time or place is wrong, every personal page changes: verify before interpreting.",
        "natal_themes": "NATAL THEMES TO OBSERVE",
        "seasons_title": "Your Transit Seasons",
        "seasons_title_2": "Your Transit Seasons II",
        "seasons_eyebrow": "PERSONAL EDITION  /  LONG-TERM TRANSITS TO YOUR CHART",
        "seasons_intro": "Each bar is a period when a slow-moving body forms an exact aspect to your natal chart. The diamond marks the peak. Darker bars are higher priority.",
        "seasons_importance_high": "HIGH", "seasons_importance_medium": "MEDIUM",
        "timeline_title_1": "Personal Transit Timeline I",
        "timeline_title_2": "Personal Transit Timeline II",
        "timeline_eyebrow": "PERSONAL EDITION  /  EXACT TRANSIT-TO-NATAL ASPECTS",
        "timeline_intro": "Selected exact aspects from transiting Jupiter through Pluto to the sample natal Sun, Moon, Mercury, Venus, Mars, Ascendant, and Midheaven.",
        "observation_notes": "OBSERVATION NOTES",
        "continue_timeline": "CONTINUE TIMELINE",
        "personal_month_title": "{month} Personal Focus",
        "personal_month_eyebrow": "PERSONAL EDITION  /  {name}",
        "personal_dates": "PERSONAL FOCUS DATES",
        "month_dashboard": "{month} DASHBOARD",
        "no_personal_month": "No personal focus dates this month.",
        "pm_q1": "WHAT CHANGED AROUND THESE DATES?",
        "pm_q2": "WHERE DID I HAVE MORE CHOICE?",
        "pm_q3": "WHAT OTHER CONTEXT MATTERED?",
        "active_seasons": "ACTIVE THIS MONTH",
        "ai_title": "Notes for AI",
        "ai_eyebrow": "OPTIONAL REFLECTION AID  /  YOU CONTROL WHAT YOU SHARE",
        "privacy_first": "PRIVACY FIRST",
        "privacy_body": "Do not paste names, addresses, medical identifiers, or private third-party details. AI output can be mistaken. Use it to organize observations, not to make medical, legal, financial, or safety-critical decisions.",
        "copyable_prompt": "COPYABLE REFLECTION PROMPT",
        "ai_prompt_text": (
            "I am reviewing a personal journal entry alongside an astrology transit list. "
            "Separate observations from interpretations. Summarize what happened, identify repeated themes, "
            "note evidence that does not fit the transit description, and suggest three neutral questions for future observation. "
            "Do not predict events or treat astrology as proven causation.\n\n"
            "TRANSITS:\n[Paste only the transit lines you want to discuss.]\n\n"
            "JOURNAL NOTES:\n[Paste a privacy-edited summary.]"
        ),
        "questions_ask": "QUESTIONS I WANT TO ASK",
        "notes_title": "Notes",
        "notes_eyebrow": "FREEFORM OBSERVATION SPACE",
        "date_topic": "Date / topic:",
    },
    "ja": {
        "brand": "nanami-astro",
        "planner_title": "星のトランジット手帳",
        "tagline": "空を観察し、日々を記録する",
        "cover_kicker": "NANAMI-ASTRO  /  年間トランジット手帳",
        "cover_format": "縦型デジタルプランナー",
        "cover_edition_common": "共通版＋架空プロフィールのパーソナル版サンプル",
        "cover_edition_personal": "パーソナル版  /  {name} さん",
        "cover_note": "天体データは {tz} 表示  |  リンク付きPDF",
        "eyebrow_default": "空を観察し、日々を記録する",
        "footer": "{period} トランジット手帳  |  {tz}  |  {edition}",
        "edition_prototype": "プロトタイプ",
        "edition_full": "完全版",
        "edition_personal": "パーソナル版",
        "nav_index": "目次", "nav_year": "年間", "nav_personal": "パーソナル",
        "guide_title": "この手帳の使い方",
        "guide_intro": "これは「予言の台本」ではなく観察の記録です。空の動きに気づき、実際の体験を書き留め、両者を好奇心をもって照らし合わせてください。",
        "guide_1_head": "1  観察する", "guide_1_body": "計算されたトランジットを読み、気になったものをメモします。",
        "guide_2_head": "2  記録する", "guide_2_body": "出来事・気分・体調・決断・状況を自分の言葉で記録します。",
        "guide_3_head": "3  振り返る", "guide_3_body": "何が合い、何が合わなかったか。記録が本当に裏付けるパターンは何かを問います。",
        "calc_standard": "計算基準",
        "calc_items": [
            "トロピカル方式・地心黄経",
            "Swiss Ephemeris（内蔵Moshier計算）",
            "日々の配置は {tz} 正午時点／正確なイベントは {tz} 時刻付き",
            "日付は {tz} 基準です",
            "製品版は nanami-astro エンジンとの照合を必須とする",
        ],
        "personal_boundary_head": "パーソナル版の境界",
        "personal_boundary_body": "このプロトタイプのパーソナル版ページは架空の出生データを使用しています。商用のパーソナライズ商品には、明示的な同意、安全な注文プロセス、出生データの訂正ポリシー、削除スケジュールの明示が必要です。",
        "your_data_head": "あなたのデータについて",
        "your_data_body": "この手帳はプロフィールページに記載の出生データから生成されています。読み進める前にご確認ください。誤りがある場合は訂正を依頼できます。計算は生成時に一度だけ行われ、このPDFはオフラインで動作し、外部への通信は一切ありません。",
        "index_title": "目次",
        "idx_year": "年間カレンダー", "idx_aspects": "主要トランジット", "idx_retro": "逆行一覧",
        "idx_phases": "月相カレンダー", "idx_personal": "パーソナル", "idx_personal_sample": "パーソナル（サンプル）",
        "idx_ai": "AI活用ノート", "idx_daily_full": "日次ページ", "idx_daily_sample": "日次サンプル（1/1-7）",
        "idx_reflection": "月次振り返り", "idx_notes": "ノート",
        "idx_months": "月別ページ", "idx_month_sub": "ダッシュボード＋カレンダー",
        "scope_head_full": "収録内容",
        "scope_full": "{count}ヶ月分のダッシュボード・カレンダー・日付入り日次ページ・月次振り返り・ノートページを収録。日次ページには前日・翌日・月カレンダーへのリンクがあります。",
        "scope_head_proto": "プロトタイプの範囲",
        "scope_proto": "12ヶ月分のダッシュボードとカレンダーを収録。日次ページは1月1〜7日のサンプルです。完全版ビルドでは365日分の日次ページと月次振り返りが生成されます。",
        "scope_head_personal": "この手帳について",
        "scope_personal": "パーソナルページ記載のプロフィールに基づき計算：{start}からの12ヶ月、全日次ページ、月次振り返り、あなたのトランジット・シーズン、月ごとの注目日を収録。",
        "year_title": "年間カレンダー",
        "weekday_letters": ["月", "火", "水", "木", "金", "土", "日"],
        "new_short": "新月", "full_short": "満月",
        "aspects_title": "主要トランジット",
        "aspects_eyebrow": "年間の空の概観  /  正確な {tz} 時刻",
        "aspects_intro": "木星・土星・天王星・海王星・冥王星の間で正確に成立する主要アスペクトの抜粋です。結果の保証ではなく、観察の目印として扱ってください。",
        "exact": "EXACT",
        "what_observe": "何を観察しますか？",
        "retro_title": "逆行一覧",
        "retro_eyebrow": "留と観察の期間  /  {tz}",
        "retro_intro": "以下の期間は、計算した留（逆行の折り返し）の日付で区切っています。「{start}以前」は、期間の開始時点ですでに逆行中だったことを示します。",
        "retro_planet": "天体", "retro_begins": "逆行開始", "retro_ends": "順行 / 終了",
        "before_start": "{start}以前", "into_next": "{year}年へ継続", "beyond_end": "{date}以降も継続",
        "station_notes": "観察メモ",
        "phases_title_1": "月相カレンダー I", "phases_title_2": "月相カレンダー II",
        "phases_eyebrow": "月のサイクル  /  正確な {tz} 時刻",
        "moon_in": "{sign}の月  /  {tz}",
        "month_eyebrow": "月間トランジット・ダッシュボード  /  {tz}",
        "key_sky_dates": "今月の空の注目日",
        "monthly_intention": "今月の意図", "what_to_observe": "観察すること",
        "body_energy": "体調・エネルギーの記録",
        "baseline_items": ["睡眠", "エネルギー", "集中", "緊張"],
        "questions_month": "今月の問い",
        "month_questions": ["実際に何が変わった？", "何が繰り返された？", "予報が説明しなかったことは？"],
        "calendar_title": "{month}カレンダー",
        "calendar_eyebrow": "月間ビュー  /  日付をタップで日次ページへ",
        "weekday_heads": ["月", "火", "水", "木", "金", "土", "日"],
        "linked_daily": "リンク付き日次ページあり",
        "back_overview": "ダッシュボードへ戻る",
        "personal_peak_legend": "パーソナル注目日",
        "daily_eyebrow": "{weekday}  /  日次トランジット記録  /  {tz} 正午時点",
        "moon_head": "月", "phase_suffix": "{phase}",
        "major_aspects": "主要アスペクト",
        "no_major_aspect": "表示オーブ内の主要アスペクトなし",
        "orb_deg": "オーブ {orb} 度",
        "long_term": "長期トランジット",
        "your_transits": "進行中のトランジット",
        "no_long_term": "表示オーブ内の外惑星アスペクトなし",
        "no_personal_active": "本日は進行中の長期トランジットはありません",
        "peak": "ピーク {date}",
        "mood": "気分", "low": "低", "high": "高",
        "body_health": "体調",
        "health_items": ["頭痛", "だるさ", "睡眠不足"],
        "what_happened": "今日あったこと",
        "transit_reflection": "トランジットの振り返り",
        "reflection_hint": "何が合った？合わなかった？他にこの日を説明するものは？",
        "notes_head": "メモ",
        "ai_guide_link": "AI活用ガイド",
        "day_calendar_link": "{month}カレンダー",
        "reflection_title": "{month}の振り返り",
        "reflection_eyebrow": "記録を見直す  /  記録が裏づけたものだけ残す",
        "reflection_prompts": [
            "繰り返された出来事や感情は？",
            "当てはまると感じたトランジットは？",
            "実際とは合わなかったものは？",
            "占星術以外で最も影響した要因は？",
            "来月観察したいことは？",
        ],
        "personal_title_sample": "パーソナル版サンプル",
        "personal_title": "あなたのパーソナル版",
        "personal_eyebrow_sample": "架空プロフィール  /  カスタムトランジットのデモ",
        "personal_eyebrow": "パーソナル版  /  あなたの出生図から計算",
        "profile_head_sample": "サンプルプロフィール A",
        "profile_head": "プロフィール",
        "birth_label": "出生: {value}", "place_label": "出生地: {value}",
        "zodiac_label": "方式: {zodiac}  |  ハウス: {houses}",
        "tz_line": "手帳のタイムゾーン: {tz}",
        "layer_personal_head": "パーソナル層",
        "layer_personal_body": "出生図の配置・感受点、出生図への長期トランジット・シーズン、月ごとの注目日、ハウスの文脈。",
        "layer_common_head": "共通層",
        "layer_common_body": "月相・イングレス・留・全体に共通するアスペクトと、同じ振り返りページの構成。",
        "safeguards_head": "フルフィルメント・セーフガード",
        "safeguards": [
            "計算に必要な出生データのみを収集する。",
            "生成前に解釈したタイムゾーンを購入者に提示する。",
            "出生データの誤りに対して1回の訂正を受け付ける。",
            "注文データと生成中間ファイルは公表スケジュールで削除する。",
            "完成PDFは nanami-astro サーバーなしで使えるようにする。",
        ],
        "natal_title": "出生図スナップショット",
        "natal_eyebrow": "パーソナル版  /  {suffix}",
        "natal_fictional": "架空サンプルデータ",
        "natal_yours": "あなたの出生図",
        "placements": "天体の配置", "outer_angles": "外惑星・感受点",
        "reading_boundary": "読む前の確認",
        "reading_boundary_body_sample": "これらの配置は架空サンプルプロフィールから計算されています。顧客版ではこのページに提出された出生データと計算基準を明示し、解釈の前に誤りを特定できるようにしてください。",
        "reading_boundary_body": "これらの配置は前ページの出生データから計算されています。出生時刻や出生地が違っていればパーソナルページ全体が変わります。解釈の前にご確認ください。",
        "natal_themes": "観察したい出生図のテーマ",
        "seasons_title": "あなたのトランジット・シーズン",
        "seasons_title_2": "あなたのトランジット・シーズン II",
        "seasons_eyebrow": "パーソナル版  /  出生図への長期トランジット",
        "seasons_intro": "各バーは、ゆっくり動く天体があなたの出生図と正確なアスペクトを組む期間です。◆はピーク。濃いバーほど優先度が高い配置です。",
        "seasons_importance_high": "高", "seasons_importance_medium": "中",
        "timeline_title_1": "パーソナル・トランジット年表 I",
        "timeline_title_2": "パーソナル・トランジット年表 II",
        "timeline_eyebrow": "パーソナル版  /  出生図への正確なアスペクト",
        "timeline_intro": "トランジットの木星〜冥王星から、サンプル出生図の太陽・月・水星・金星・火星・ASC・MCへの正確なアスペクトの抜粋です。",
        "observation_notes": "観察メモ",
        "continue_timeline": "年表のつづき",
        "personal_month_title": "{month}のパーソナル・フォーカス",
        "personal_month_eyebrow": "パーソナル版  /  {name}",
        "personal_dates": "パーソナル注目日",
        "month_dashboard": "{month}ダッシュボード",
        "no_personal_month": "今月はパーソナル注目日がありません。",
        "pm_q1": "この日付の前後で何が変わった？",
        "pm_q2": "自分で選べたと感じたのはどこ？",
        "pm_q3": "他に影響した状況は？",
        "active_seasons": "今月進行中のシーズン",
        "ai_title": "AI活用ノート",
        "ai_eyebrow": "任意の振り返り補助  /  共有する内容はあなたが決める",
        "privacy_first": "プライバシー最優先",
        "privacy_body": "氏名・住所・医療識別情報・第三者の私的な情報は貼り付けないでください。AIの出力は誤ることがあります。観察の整理に使い、医療・法律・金銭・安全に関わる判断には使わないでください。",
        "copyable_prompt": "コピーして使える振り返りプロンプト",
        "ai_prompt_text": (
            "個人の日記とトランジットのリストを照らし合わせて振り返りをしています。"
            "観察と解釈を分けてください。起きたことを要約し、繰り返しのテーマを特定し、"
            "トランジットの説明に合わない証拠も挙げ、今後の観察のための中立的な問いを3つ提案してください。"
            "出来事の予言はせず、占星術を証明された因果として扱わないでください。\n\n"
            "トランジット:\n[話したいトランジット行だけ貼り付け]\n\n"
            "日記メモ:\n[プライバシーに配慮した要約を貼り付け]"
        ),
        "questions_ask": "AIに聞きたいこと",
        "notes_title": "ノート",
        "notes_eyebrow": "自由な観察スペース",
        "date_topic": "日付・トピック:",
    },
}


def S(lang: str, key: str, **kwargs) -> str:
    value = STR.get(lang, STR["en"]).get(key, STR["en"].get(key, key))
    if isinstance(value, str) and kwargs:
        return value.format(**kwargs)
    return value
