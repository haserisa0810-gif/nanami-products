# -*- coding: utf-8 -*-
"""Generate the hyperlinked Astrology Transit Planner PDF (en/ja, any period)."""

from __future__ import annotations

import argparse
import calendar
import json
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from reportlab.lib.colors import Color, HexColor, white
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from . import planner_i18n as i18n
from .planner_i18n import S


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_ROOT = Path(__file__).resolve().parent
DEFAULT_DATA = MODULE_ROOT / "data" / "2027_transits.json"
# Year-less cover artwork; the year and edition lines are drawn over it.
COVER_IMAGE = MODULE_ROOT / "assets" / "planner_cover.jpg"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "output" / "pdf"

PAGE_WIDTH, PAGE_HEIGHT = A4
NAVY = HexColor("#1F2638")
INK = HexColor("#2D3142")
CREAM = HexColor("#F7F3ED")
PAPER = HexColor("#FCFAF7")
LAVENDER = HexColor("#8174A7")
PALE_LAVENDER = HexColor("#E9E3F0")
GOLD = HexColor("#C6A46B")
PALE_GOLD = HexColor("#EEE2CD")
SAGE = HexColor("#AAB6A2")
PALE_SAGE = HexColor("#E6EBE3")
MUTED = HexColor("#727686")
LINE = HexColor("#D8D3CC")
ROSE = HexColor("#B78083")

ASPECT_SHORT = {
    "en": {"conjunction": "conj", "sextile": "sext", "square": "square", "trine": "trine", "opposition": "opp"},
    "ja": {"conjunction": "合", "sextile": "60度", "square": "90度", "trine": "120度", "opposition": "180度"},
}

# Fonts are re-registered under the six standard PDF names so every draw call
# stays language-agnostic. Each logical name maps to an ordered list of
# (filename, subfontIndex) candidates; the first file found across the search
# directories wins. reportlab's TTFont embeds only glyf-outline TrueType, so
# the Japanese candidates deliberately avoid the CFF-based fonts-noto-cjk
# (NotoSansCJK-*.ttc) — use Google Noto Sans/Serif JP TTFs or IPAex instead.
LATIN_FONTS = {
    "Helvetica": [("arial.ttf", None), ("Arial.ttf", None), ("LiberationSans-Regular.ttf", None), ("DejaVuSans.ttf", None)],
    "Helvetica-Bold": [("arialbd.ttf", None), ("LiberationSans-Bold.ttf", None), ("DejaVuSans-Bold.ttf", None)],
    "Helvetica-Oblique": [("ariali.ttf", None), ("LiberationSans-Italic.ttf", None), ("DejaVuSans-Oblique.ttf", None)],
    "Times-Roman": [("times.ttf", None), ("LiberationSerif-Regular.ttf", None), ("DejaVuSerif.ttf", None)],
    "Times-Bold": [("timesbd.ttf", None), ("LiberationSerif-Bold.ttf", None), ("DejaVuSerif-Bold.ttf", None)],
    "Courier": [("cour.ttf", None), ("LiberationMono-Regular.ttf", None), ("DejaVuSansMono.ttf", None)],
}

JA_FONTS = {
    "Helvetica": [("meiryo.ttc", 0), ("NotoSansJP-Regular.ttf", None), ("NotoSansJP-VF.ttf", None), ("ipaexg.ttf", None)],
    "Helvetica-Bold": [("meiryob.ttc", 0), ("NotoSansJP-Bold.ttf", None), ("NotoSansJP-VF.ttf", None), ("ipaexg.ttf", None), ("meiryo.ttc", 0)],
    "Helvetica-Oblique": [("meiryo.ttc", 0), ("NotoSansJP-Regular.ttf", None), ("NotoSansJP-VF.ttf", None), ("ipaexg.ttf", None)],
    "Times-Roman": [("yumin.ttf", None), ("NotoSerifJP-Regular.ttf", None), ("NotoSerifJP-VF.ttf", None), ("ipaexm.ttf", None)],
    "Times-Bold": [("yumindb.ttf", None), ("NotoSerifJP-Bold.ttf", None), ("NotoSerifJP-VF.ttf", None), ("ipaexm.ttf", None), ("yumin.ttf", None)],
    "Courier": [("msgothic.ttc", 0), ("NotoSansJP-Regular.ttf", None), ("ipaexg.ttf", None), ("NotoSansJP-VF.ttf", None)],
}


def _font_dirs() -> list[Path]:
    dirs: list[Path] = []
    env = os.environ.get("PLANNER_FONT_DIR")
    if env:
        dirs.extend(Path(part) for part in env.split(os.pathsep) if part)
    dirs.append(MODULE_ROOT / "fonts")
    dirs.append(Path("C:/Windows/Fonts"))
    dirs.extend(Path(p) for p in [
        "/usr/share/fonts/truetype/noto",
        "/usr/share/fonts/opentype/noto",
        "/usr/share/fonts/truetype/ipaexfont-gothic",
        "/usr/share/fonts/truetype/ipaexfont-mincho",
        "/usr/share/fonts/opentype/ipaexfont-gothic",
        "/usr/share/fonts/opentype/ipaexfont-mincho",
        "/usr/share/fonts",
        str(Path.home() / ".fonts"),
    ])
    return [d for d in dirs if d.is_dir()]


def _resolve_font(candidates: list[tuple[str, int | None]], dirs: list[Path]) -> tuple[Path, int | None] | None:
    for filename, subfont in candidates:
        candidate = Path(filename)
        if candidate.is_absolute():
            if candidate.exists():
                return candidate, subfont
            continue
        for directory in dirs:
            found = directory / filename
            if found.exists():
                return found, subfont
    return None


def register_fonts(lang: str) -> None:
    dirs = _font_dirs()
    table = JA_FONTS if lang == "ja" else LATIN_FONTS
    resolved: dict[str, tuple[Path, int | None]] = {}
    for name, candidates in table.items():
        hit = _resolve_font(candidates, dirs)
        if hit:
            resolved[name] = hit
    if lang == "ja" and "Helvetica" not in resolved:
        raise SystemExit(
            "No embeddable Japanese font found. Set PLANNER_FONT_DIR, bundle Google "
            "Noto Sans/Serif JP TTFs under annual_transit_planner/fonts, or install "
            "fonts-ipaexfont. Note: fonts-noto-cjk (CFF) cannot be embedded by reportlab."
        )
    # Latin builds fall back to reportlab's built-in Helvetica/Times/Courier when
    # a file is missing; Japanese builds reuse the sans regular so no glyph is lost.
    if lang == "ja":
        fallback = resolved["Helvetica"]
        for name in table:
            resolved.setdefault(name, fallback)
    for font_name, (path, subfont) in resolved.items():
        if subfont is None:
            pdfmetrics.registerFont(TTFont(font_name, str(path)))
        else:
            pdfmetrics.registerFont(TTFont(font_name, str(path), subfontIndex=subfont))


@dataclass
class PageSpec:
    bookmark: str
    kind: str
    title: str
    payload: Any = None


def clean_text(value: str) -> str:
    return (
        value.replace("–", "-")
        .replace("—", "-")
        .replace("‑", "-")
        .replace(" ", " ")
    )


def wrap_lines(text: str, font: str, size: float, max_width: float) -> list[str]:
    result: list[str] = []
    for paragraph in clean_text(text).splitlines() or [""]:
        words = paragraph.split()
        if not words:
            result.append("")
            continue
        # CJK paragraphs arrive as one long "word": break them by character.
        pieces: list[str] = []
        for word in words:
            if stringWidth(word, font, size) <= max_width:
                pieces.append(word)
                continue
            chunk = ""
            for char in word:
                if stringWidth(chunk + char, font, size) <= max_width:
                    chunk += char
                elif char in HANGING_PUNCTUATION:
                    # 行頭禁則 / ぶら下がり: a closing punctuation that would
                    # start the next line hangs past the margin at the end of
                    # this one instead.
                    if chunk:
                        pieces.append(chunk + char)
                        chunk = ""
                    elif pieces:
                        pieces[-1] += char
                    else:
                        chunk = char
                else:
                    pieces.append(chunk)
                    chunk = char
            if chunk:
                pieces.append(chunk)
        current = pieces[0]
        for word in pieces[1:]:
            candidate = f"{current} {word}"
            if stringWidth(candidate, font, size) <= max_width and not _is_cjk_join(current, word):
                current = candidate
            elif stringWidth(current + word, font, size) <= max_width and _is_cjk_join(current, word):
                current = current + word
            else:
                result.append(current)
                current = word
        result.append(current)
    return result


# Characters barred from starting a line (行頭禁則); they hang instead.
HANGING_PUNCTUATION = set("、。，．・：；！？）］｝」』】〕》〉‐ー～%’”")


def _is_cjk_join(left: str, right: str) -> bool:
    """Join CJK fragments without inserting a space."""
    if not left or not right:
        return False
    return ord(left[-1]) > 0x2E80 and ord(right[0]) > 0x2E80


def draw_wrapped(
    pdf: canvas.Canvas,
    text: str,
    x: float,
    y: float,
    width: float,
    font: str = "Helvetica",
    size: float = 10,
    leading: float | None = None,
    color: Color = INK,
    max_lines: int | None = None,
) -> float:
    leading = leading or size * 1.35
    lines = wrap_lines(text, font, size, width)
    if max_lines is not None:
        lines = lines[:max_lines]
    pdf.setFont(font, size)
    pdf.setFillColor(color)
    for line in lines:
        pdf.drawString(x, y, line)
        y -= leading
    return y


def fit_text(text: str, font: str, preferred: float, max_width: float, minimum: float = 6) -> float:
    size = preferred
    while size > minimum and stringWidth(clean_text(text), font, size) > max_width:
        size -= 0.25
    return size


class Planner:
    def __init__(self, data: dict[str, Any], output: Path, mode: str, lang: str) -> None:
        self.data = data
        self.output = output
        self.mode = mode
        self.lang = lang
        meta = data["metadata"]
        self.tz = i18n.tz_label(meta.get("tz", "UTC"))
        self.period_label = meta.get("period_label", "2027")
        self.start_date = date.fromisoformat(meta["start_date"])
        self.end_date = date.fromisoformat(meta["end_date"])
        self.months = [tuple(pair) for pair in meta["months"]]
        self.rolling = self.start_date.year != self.end_date.year
        self.personal = data.get("personal")
        self.sample = data.get("personal_sample")
        self.daily_by_date = {item["date"]: item for item in data["daily"]}
        self.events = sorted(
            data["moon_phases"] + data["stations"] + data["ingresses"] + data["outer_aspects"],
            key=lambda item: item["utc"],
        )
        self.window_chunks: list[list[dict[str, Any]]] = []
        self.personal_dates: dict[str, list[dict[str, Any]]] = {}
        if self.personal:
            windows = sorted(self.personal["windows"], key=lambda w: w["start_date"])
            self.window_chunks = [windows[i:i + 16] for i in range(0, len(windows), 16)]
            for window in windows:
                hits = window.get("exact_hits") or [{"date": window["peak_date"], "orb": window.get("peak_orb")}]
                for hit in hits:
                    day = hit["date"]
                    if self.start_date.isoformat() <= day <= self.end_date.isoformat():
                        self.personal_dates.setdefault(day, []).append(window)
        self.pages = self._build_page_plan()
        self.page_numbers = {page.bookmark: index + 1 for index, page in enumerate(self.pages)}
        self.destinations = set(self.page_numbers)
        self.pdf = canvas.Canvas(str(output), pagesize=A4, pageCompression=1)
        self.pdf.setTitle(f"{self.period_label} {S(lang, 'planner_title')} - {S(lang, 'tagline')}")
        self.pdf.setAuthor("nanami-astro")
        self.pdf.setSubject("Hyperlinked astrology transit planner")
        self._outline_created: set[str] = set()

    # ------------------------------------------------------------------ plan

    def mk(self, year: int, month: int) -> str:
        return f"{year}_{month:02d}"

    def month_title(self, year: int, month: int) -> str:
        if self.rolling:
            return i18n.fmt_month_year(self.lang, year, month)
        return i18n.month_name(self.lang, month)

    def _build_page_plan(self) -> list[PageSpec]:
        lang = self.lang
        pages = [
            PageSpec("cover", "cover", "Cover"),
            PageSpec("guide", "guide", S(lang, "guide_title")),
            PageSpec("index", "index", S(lang, "index_title")),
            PageSpec("year", "year", S(lang, "year_title")),
            PageSpec("aspects", "aspects", S(lang, "aspects_title")),
            PageSpec("retrogrades", "retrogrades", S(lang, "retro_title")),
            PageSpec("phases_1", "phases", S(lang, "phases_title_1"), (0, 6)),
            PageSpec("phases_2", "phases", S(lang, "phases_title_2"), (6, 12)),
        ]
        if self.mode == "personal":
            pages.append(PageSpec("personal", "personal_intro", S(lang, "personal_title")))
            pages.append(PageSpec("natal", "natal", S(lang, "natal_title")))
            for index in range(len(self.window_chunks)):
                title = S(lang, "seasons_title") if index == 0 else S(lang, "seasons_title_2")
                pages.append(PageSpec(f"seasons_{index + 1}", "seasons", title, index))
        first_month = self.months[0]
        for year, month in self.months:
            key = self.mk(year, month)
            pages.append(PageSpec(f"month_{key}", "month", self.month_title(year, month), (year, month)))
            pages.append(PageSpec(f"calendar_{key}", "calendar", S(lang, "calendar_title", month=self.month_title(year, month)), (year, month)))
            if self.mode == "personal":
                pages.append(PageSpec(f"pmfocus_{key}", "personal_month", S(lang, "personal_month_title", month=self.month_title(year, month)), (year, month)))
            if self.mode in {"full", "personal"}:
                days = range(1, calendar.monthrange(year, month)[1] + 1)
            elif (year, month) == first_month:
                days = range(1, 8)
            else:
                days = range(0)
            for day in days:
                iso = date(year, month, day).isoformat()
                pages.append(PageSpec(f"day_{iso.replace('-', '_')}", "daily", iso, iso))
            if days:
                pages.append(PageSpec(f"reflection_{key}", "reflection", S(lang, "reflection_title", month=self.month_title(year, month)), (year, month)))
        if self.mode != "personal" and self.sample:
            pages.extend([
                PageSpec("personal", "personal_intro", S(lang, "personal_title_sample")),
                PageSpec("natal", "natal", S(lang, "natal_title")),
                PageSpec("personal_transits", "personal_transits", S(lang, "timeline_title_1"), (0, 7)),
                PageSpec("personal_transits_2", "personal_transits", S(lang, "timeline_title_2"), (7, None)),
                PageSpec("personal_month_sample", "personal_month", S(lang, "personal_month_title", month=self.month_title(*first_month)), first_month),
            ])
        pages.append(PageSpec("ai_prompt", "ai_prompt", S(lang, "ai_title")))
        note_count = 6 if self.mode in {"full", "personal"} else 1
        for index in range(1, note_count + 1):
            pages.append(PageSpec(f"notes_{index}", "notes", f"{S(lang, 'notes_title')} {index}", index))
        return pages

    def render(self) -> None:
        self.output.parent.mkdir(parents=True, exist_ok=True)
        for page_number, spec in enumerate(self.pages, start=1):
            self._begin_page(spec, page_number)
            getattr(self, f"draw_{spec.kind}")(spec)
            self.pdf.showPage()
        self.pdf.save()

    def _begin_page(self, spec: PageSpec, page_number: int) -> None:
        self.pdf.bookmarkPage(spec.bookmark)
        if spec.kind in {"cover", "guide", "index", "year", "aspects", "retrogrades", "phases", "personal_intro", "ai_prompt"}:
            if spec.bookmark not in self._outline_created:
                self.pdf.addOutlineEntry(spec.title if spec.kind != "cover" else S(self.lang, "planner_title"), spec.bookmark, level=0, closed=False)
                self._outline_created.add(spec.bookmark)
        elif spec.kind == "month":
            self.pdf.addOutlineEntry(spec.title, spec.bookmark, level=0, closed=True)
        elif spec.kind in {"calendar", "reflection", "personal_month"}:
            level = 1 if spec.bookmark != "personal_month_sample" else 1
            self.pdf.addOutlineEntry(spec.title, spec.bookmark, level=level, closed=True)
        elif spec.kind == "daily":
            label = i18n.fmt_month_day_long(self.lang, date.fromisoformat(spec.payload))
            self.pdf.addOutlineEntry(label, spec.bookmark, level=1, closed=True)
        elif spec.kind in {"natal", "personal_transits", "seasons"}:
            self.pdf.addOutlineEntry(spec.title, spec.bookmark, level=1, closed=True)
        elif spec.kind == "notes" and spec.payload == 1:
            self.pdf.addOutlineEntry(S(self.lang, "notes_title"), spec.bookmark, level=0, closed=True)
        if spec.kind != "cover":
            self.pdf.setFillColor(PAPER)
            self.pdf.rect(0, 0, PAGE_WIDTH, PAGE_HEIGHT, fill=1, stroke=0)
            self._draw_nav(spec, page_number)

    def _link(self, destination: str, x: float, y: float, width: float, height: float) -> None:
        if destination in self.destinations:
            self.pdf.linkRect("", destination, (x, y, x + width, y + height), relative=0, thickness=0)

    def _edition_label(self) -> str:
        key = {"prototype": "edition_prototype", "full": "edition_full", "personal": "edition_personal"}[self.mode]
        return S(self.lang, key)

    def _draw_nav(self, spec: PageSpec, page_number: int) -> None:
        pdf = self.pdf
        pdf.setFillColor(NAVY)
        pdf.rect(0, PAGE_HEIGHT - 45, PAGE_WIDTH, 45, fill=1, stroke=0)
        pdf.setFillColor(PALE_GOLD)
        pdf.setFont("Times-Bold", 11)
        pdf.drawString(31, PAGE_HEIGHT - 28, S(self.lang, "brand"))
        links = [
            (S(self.lang, "nav_index"), "index"),
            (S(self.lang, "nav_year"), "year"),
            (S(self.lang, "nav_personal"), "personal"),
        ]
        x = 285
        for label, destination in links:
            pdf.setFont("Helvetica-Bold", 7.2)
            pdf.setFillColor(white if destination != spec.bookmark else GOLD)
            pdf.drawString(x, PAGE_HEIGHT - 27, label)
            self._link(destination, x - 3, PAGE_HEIGHT - 36, 52, 22)
            x += 71

        month_current = spec.payload if spec.kind in {"month", "calendar", "reflection", "personal_month"} else None
        if spec.kind == "daily":
            iso = spec.payload
            month_current = (int(iso[:4]), int(iso[5:7]))
        tab_x = PAGE_WIDTH - 23
        tab_height = 45
        top = PAGE_HEIGHT - 64
        for index, (year, month) in enumerate(self.months, start=1):
            y = top - (index - 1) * (tab_height + 2)
            current = (year, month) == tuple(month_current) if month_current else False
            pdf.setFillColor(LAVENDER if current else PALE_LAVENDER)
            pdf.roundRect(tab_x, y - tab_height, 23, tab_height, 4, fill=1, stroke=0)
            pdf.saveState()
            pdf.translate(tab_x + 15, y - tab_height + 6)
            pdf.rotate(90)
            pdf.setFont("Helvetica-Bold", 6.6)
            pdf.setFillColor(white if current else INK)
            pdf.drawString(0, 0, i18n.month_abbr(self.lang, month).upper())
            pdf.restoreState()
            self._link(f"month_{self.mk(year, month)}", tab_x, y - tab_height, 23, tab_height)

        pdf.setStrokeColor(LINE)
        pdf.line(31, 28, PAGE_WIDTH - 31, 28)
        pdf.setFillColor(MUTED)
        pdf.setFont("Helvetica", 7)
        pdf.drawString(31, 16, S(self.lang, "footer", period=self.period_label, tz=self.tz, edition=self._edition_label()))
        pdf.drawRightString(PAGE_WIDTH - 31, 16, f"{page_number:03d}")

    def _page_title(self, title: str, eyebrow: str | None = None) -> float:
        pdf = self.pdf
        pdf.setFillColor(LAVENDER)
        pdf.setFont("Helvetica-Bold", 7.5)
        pdf.drawString(38, PAGE_HEIGHT - 78, eyebrow if eyebrow is not None else S(self.lang, "eyebrow_default"))
        pdf.setFillColor(NAVY)
        size = fit_text(clean_text(title), "Times-Bold", 25, 520, 15)
        pdf.setFont("Times-Bold", size)
        pdf.drawString(38, PAGE_HEIGHT - 108, clean_text(title))
        pdf.setStrokeColor(GOLD)
        pdf.setLineWidth(1.4)
        pdf.line(38, PAGE_HEIGHT - 119, 142, PAGE_HEIGHT - 119)
        return PAGE_HEIGHT - 137

    def _card(self, x: float, y_top: float, width: float, height: float, fill: Color = CREAM, stroke: Color = LINE, radius: float = 9) -> None:
        self.pdf.setFillColor(fill)
        self.pdf.setStrokeColor(stroke)
        self.pdf.setLineWidth(0.7)
        self.pdf.roundRect(x, y_top - height, width, height, radius, fill=1, stroke=1)

    def _section_label(self, text: str, x: float, y: float, color: Color = LAVENDER) -> None:
        self.pdf.setFillColor(color)
        self.pdf.setFont("Helvetica-Bold", 7.5)
        label = clean_text(text)
        if self.lang != "ja":
            label = label.upper()
        self.pdf.drawString(x, y, label)

    def _ruled_lines(self, x: float, y_top: float, width: float, count: int, gap: float = 19) -> None:
        self.pdf.setStrokeColor(LINE)
        self.pdf.setLineWidth(0.55)
        for index in range(count):
            y = y_top - index * gap
            self.pdf.line(x, y, x + width, y)

    def _pos_display(self, item: dict[str, Any]) -> str:
        if self.lang == "ja":
            return f"{i18n.sign_name('ja', item['sign'])} {item['degree']:02d}度{item['minute']:02d}分"
        return item["display"]

    def _events_for_month(self, year: int, month: int, maximum: int = 9) -> list[dict[str, Any]]:
        prefix = f"{year:04d}-{month:02d}"
        candidates = [event for event in self.events if event["date"].startswith(prefix)]
        priority = {"outer_aspect": 0, "station": 1, "moon_phase": 2, "ingress": 3}
        preferred = sorted(
            candidates,
            key=lambda event: (
                priority[event["type"]],
                0 if event.get("name") in {"New Moon", "Full Moon"} else 1,
                event["utc"],
            ),
        )[:maximum]
        return sorted(preferred, key=lambda event: event["utc"])

    # ----------------------------------------------------------------- pages

    def _cover_year_range(self) -> str:
        """Shared EN/JA year label, e.g. "2026-2027" (a single year when the
        edition happens to sit inside one calendar year)."""
        if self.start_date.year == self.end_date.year:
            return str(self.start_date.year)
        return f"{self.start_date.year}\u2013{self.end_date.year}"

    def _cover_edition_label(self) -> str:
        """English wording, to sit with the artwork's baked-in English."""
        return {
            "personal": "P E R S O N A L   E D I T I O N",
            "full": "F U L L   E D I T I O N",
            "prototype": "P R O T O T Y P E",
        }.get(self.mode, "")

    def draw_cover(self, spec: PageSpec) -> None:
        """Cover artwork plus the only two variable lines: year and edition.

        The artwork carries the masthead, title and tagline, so a single
        year-less image serves every period and both languages.
        """
        pdf = self.pdf
        navy = HexColor("#00162E")
        gold = HexColor("#C8A456")
        bright_gold = HexColor("#E1C477")

        pdf.setFillColor(navy)
        pdf.rect(0, 0, PAGE_WIDTH, PAGE_HEIGHT, fill=1, stroke=0)
        if COVER_IMAGE.exists():
            pdf.drawImage(str(COVER_IMAGE), 0, 0, width=PAGE_WIDTH, height=PAGE_HEIGHT)
        else:
            # Keep generation working even if the asset is missing from a build.
            pdf.setFillColor(bright_gold)
            pdf.setFont("Times-Roman", 34)
            pdf.drawCentredString(PAGE_WIDTH / 2, 470, "ASTROLOGY PLANNER")

        # Both lines sit in the clear band between the globe base and the rule.
        edition = self._cover_edition_label()
        if edition:
            pdf.setFillColor(gold)
            pdf.setFont("Helvetica", 6.4)
            pdf.drawCentredString(PAGE_WIDTH / 2, 156, edition)

        pdf.setFillColor(bright_gold)
        pdf.setFont("Times-Roman", 21)
        pdf.drawCentredString(PAGE_WIDTH / 2, 133, self._cover_year_range())

        self._link("index", 150, 110, 312, 95)

    def draw_guide(self, spec: PageSpec) -> None:
        lang = self.lang
        y = self._page_title(S(lang, "guide_title"))
        pdf = self.pdf
        draw_wrapped(pdf, S(lang, "guide_intro"), 38, y, 520, "Helvetica", 10.2, 14.5, MUTED)
        y -= 62
        cards = [
            (S(lang, "guide_1_head"), S(lang, "guide_1_body"), PALE_LAVENDER),
            (S(lang, "guide_2_head"), S(lang, "guide_2_body"), PALE_SAGE),
            (S(lang, "guide_3_head"), S(lang, "guide_3_body"), PALE_GOLD),
        ]
        x = 38
        width = 164
        for heading, body, fill in cards:
            self._card(x, y, width, 128, fill)
            self._section_label(heading, x + 14, y - 23)
            draw_wrapped(pdf, body, x + 14, y - 48, width - 28, "Helvetica", 9.3, 13.2, INK)
            x += width + 14
        y -= 157
        self._card(38, y, 520, 152, CREAM)
        self._section_label(S(lang, "calc_standard"), 54, y - 24, GOLD)
        cursor = y - 49
        for item in S(lang, "calc_items"):
            pdf.setFillColor(LAVENDER)
            pdf.circle(58, cursor + 9.5, 2.3, fill=1, stroke=0)
            cursor = draw_wrapped(pdf, item.format(tz=self.tz), 69, cursor + 7, 465, "Helvetica", 9, 12.5, INK) - 3
        y -= 180
        self._card(38, y, 520, 112, PALE_LAVENDER, LAVENDER)
        if self.mode == "personal":
            self._section_label(S(lang, "your_data_head"), 54, y - 24)
            draw_wrapped(pdf, S(lang, "your_data_body"), 54, y - 48, 488, "Helvetica", 9.4, 13.3, INK)
        else:
            self._section_label(S(lang, "personal_boundary_head"), 54, y - 24)
            draw_wrapped(pdf, S(lang, "personal_boundary_body"), 54, y - 48, 488, "Helvetica", 9.4, 13.3, INK)

    def draw_index(self, spec: PageSpec) -> None:
        lang = self.lang
        y = self._page_title(S(lang, "index_title"))
        pdf = self.pdf
        first_year, first_month = self.months[0]
        first_key = self.mk(first_year, first_month)
        first_day = self.start_date.isoformat().replace("-", "_")
        if self.mode == "prototype":
            daily_label = S(lang, "idx_daily_sample")
            personal_label = S(lang, "idx_personal_sample")
        else:
            daily_label = S(lang, "idx_daily_full")
            personal_label = S(lang, "idx_personal")
        quick = [
            (S(lang, "idx_year"), "year"),
            (S(lang, "idx_aspects"), "aspects"),
            (S(lang, "idx_retro"), "retrogrades"),
            (S(lang, "idx_phases"), "phases_1"),
            (personal_label, "personal"),
            (S(lang, "idx_ai"), "ai_prompt"),
            (daily_label, f"day_{first_day}"),
            (S(lang, "idx_reflection"), f"reflection_{first_key}"),
            (S(lang, "idx_notes"), "notes_1"),
        ]
        x, top = 38, y
        for index, (label, destination) in enumerate(quick):
            column = index % 3
            row = index // 3
            card_x = x + column * 177
            card_y = top - row * 58
            self._card(card_x, card_y, 164, 45, CREAM)
            pdf.setFont("Helvetica-Bold", fit_text(label, "Helvetica-Bold", 7.7, 118, 6))
            pdf.setFillColor(INK)
            pdf.drawString(card_x + 12, card_y - 20, label)
            pdf.setFillColor(LAVENDER)
            pdf.setFont("Helvetica-Bold", 7.7)
            pdf.drawRightString(card_x + 151, card_y - 20, f"{self.page_numbers[destination]:03d}")
            self._link(destination, card_x, card_y - 45, 164, 45)
        top -= 201
        self._section_label(S(lang, "idx_months"), 38, top)
        top -= 15
        for index, (year, month) in enumerate(self.months):
            column = index % 3
            row = index // 3
            card_x = 38 + column * 177
            card_y = top - row * 75
            fill = PALE_LAVENDER if index % 3 == 0 else CREAM
            self._card(card_x, card_y, 164, 62, fill)
            pdf.setFillColor(NAVY)
            title = self.month_title(year, month)
            pdf.setFont("Times-Bold", fit_text(title, "Times-Bold", 12, 105, 8))
            pdf.drawString(card_x + 13, card_y - 23, title)
            pdf.setFillColor(MUTED)
            pdf.setFont("Helvetica", 7)
            pdf.drawString(card_x + 13, card_y - 42, S(lang, "idx_month_sub"))
            pdf.setFillColor(LAVENDER)
            pdf.setFont("Helvetica-Bold", 7.7)
            pdf.drawRightString(card_x + 150, card_y - 23, f"{self.page_numbers[f'month_{self.mk(year, month)}']:03d}")
            self._link(f"month_{self.mk(year, month)}", card_x, card_y - 62, 164, 62)
        top -= 320
        self._card(38, top, 520, 76, PALE_GOLD)
        if self.mode == "personal":
            self._section_label(S(lang, "scope_head_personal"), 54, top - 22, GOLD)
            scope = S(lang, "scope_personal", start=i18n.fmt_month_year(lang, first_year, first_month))
        elif self.mode == "full":
            self._section_label(S(lang, "scope_head_full"), 54, top - 22, GOLD)
            scope = S(lang, "scope_full", count=len(self.months))
        else:
            self._section_label(S(lang, "scope_head_proto"), 54, top - 22, GOLD)
            scope = S(lang, "scope_proto")
        draw_wrapped(pdf, scope, 54, top - 43, 485, "Helvetica", 8.8, 12.2, INK)

    def draw_year(self, spec: PageSpec) -> None:
        lang = self.lang
        y = self._page_title(f"{self.period_label} {S(lang, 'year_title')}" if lang != "ja" else f"{S(lang, 'year_title')}（{self.period_label}）")
        pdf = self.pdf
        cell_w, cell_h = 164, 132
        for index, (year, month) in enumerate(self.months):
            column = index % 3
            row = index // 3
            x = 38 + column * 177
            top = y - row * 142
            self._card(x, top, cell_w, cell_h, CREAM)
            pdf.setFillColor(NAVY)
            title = self.month_title(year, month)
            pdf.setFont("Times-Bold", fit_text(title, "Times-Bold", 11, 120, 8))
            pdf.drawString(x + 10, top - 18, title)
            pdf.setFillColor(LAVENDER)
            pdf.setFont("Helvetica-Bold", 6.5)
            col_w = 20.5
            for day_index, label in enumerate(S(lang, "weekday_letters")):
                pdf.drawCentredString(x + 12 + day_index * col_w, top - 35, label)
            weeks = calendar.Calendar(firstweekday=0).monthdayscalendar(year, month)
            week_gap = 11.5 if len(weeks) == 6 else 13
            for week_index, week in enumerate(weeks):
                for day_index, day in enumerate(week):
                    if day:
                        pdf.setFillColor(INK)
                        pdf.setFont("Helvetica", 6.8)
                        pdf.drawCentredString(x + 12 + day_index * col_w, top - 51 - week_index * week_gap, str(day))
            prefix = f"{year:04d}-{month:02d}"
            month_phases = [item for item in self.data["moon_phases"] if item["date"].startswith(prefix) and item["name"] in {"New Moon", "Full Moon"}]
            pdf.setFillColor(MUTED)
            pdf.setFont("Helvetica", 5.8)
            phase_text = "  |  ".join(
                f"{S(lang, 'new_short') if item['name'] == 'New Moon' else S(lang, 'full_short')} {int(item['date'][8:10])}"
                for item in month_phases
            )
            pdf.drawString(x + 10, top - 122, phase_text)
            self._link(f"month_{self.mk(year, month)}", x, top - cell_h, cell_w, cell_h)

    def draw_aspects(self, spec: PageSpec) -> None:
        lang = self.lang
        y = self._page_title(S(lang, "aspects_title"), S(lang, "aspects_eyebrow", tz=self.tz))
        pdf = self.pdf
        draw_wrapped(pdf, S(lang, "aspects_intro"), 38, y, 520, "Helvetica", 9.6, 13.5, MUTED)
        y -= 55
        events = self.data["outer_aspects"]
        for index, event in enumerate(events[:8]):
            height = 54
            fill = PALE_LAVENDER if index % 2 == 0 else CREAM
            self._card(38, y, 520, height, fill)
            stamp = date.fromisoformat(event["date"])
            pdf.setFillColor(LAVENDER)
            pdf.setFont("Helvetica-Bold", 8)
            pdf.drawString(52, y - 21, i18n.fmt_month_day(lang, stamp).upper())
            pdf.setFillColor(MUTED)
            pdf.setFont("Helvetica", 6.7)
            pdf.drawString(52, y - 37, f"{event['time']} {self.tz}")
            pdf.setFillColor(NAVY)
            label = i18n.event_display(lang, event)
            pdf.setFont("Times-Bold", fit_text(label, "Times-Bold", 12, 380, 9))
            pdf.drawString(125, y - 26, label)
            pdf.setFillColor(MUTED)
            pdf.setFont("Helvetica", 7.2)
            pdf.drawRightString(541, y - 25, S(lang, "exact"))
            y -= height + 8
        if len(events) < 8:
            y -= 5
        self._section_label(S(lang, "what_observe"), 38, y)
        self._ruled_lines(38, y - 22, 520, 4, 22)

    def _retrograde_periods(self) -> list[dict[str, str]]:
        lang = self.lang
        periods: list[dict[str, str]] = []
        stations = self.data["stations"]
        first_daily = self.data["daily"][0]
        start_label = S(lang, "before_start", start=i18n.fmt_month_day(lang, self.start_date))
        for body in ["Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]:
            body_stations = [event for event in stations if event["body"] == body]
            initial_state = first_daily["positions"][body]["retrograde"]
            start = start_label if initial_state else None
            for event in body_stations:
                stamp = i18n.fmt_month_day(lang, date.fromisoformat(event["date"]))
                if event["direction"] == "Retrograde":
                    start = stamp
                elif start:
                    periods.append({"body": body, "start": start, "end": stamp})
                    start = None
            if start:
                if self.rolling:
                    tail = S(lang, "beyond_end", date=i18n.fmt_month_day(lang, self.end_date))
                else:
                    tail = S(lang, "into_next", year=self.end_date.year + 1)
                periods.append({"body": body, "start": start, "end": tail})
        return periods

    def draw_retrogrades(self, spec: PageSpec) -> None:
        lang = self.lang
        y = self._page_title(S(lang, "retro_title"), S(lang, "retro_eyebrow", tz=self.tz))
        pdf = self.pdf
        draw_wrapped(pdf, S(lang, "retro_intro", start=i18n.fmt_month_day(lang, self.start_date)), 38, y, 520, "Helvetica", 9.4, 13.2, MUTED)
        y -= 56
        periods = self._retrograde_periods()
        self._card(38, y, 520, 42 + len(periods) * 32, CREAM)
        pdf.setFillColor(NAVY)
        pdf.rect(38, y - 30, 520, 30, fill=1, stroke=0)
        pdf.setFillColor(white)
        pdf.setFont("Helvetica-Bold", 7)
        pdf.drawString(52, y - 19, S(lang, "retro_planet"))
        pdf.drawString(200, y - 19, S(lang, "retro_begins"))
        pdf.drawString(390, y - 19, S(lang, "retro_ends"))
        cursor = y - 49
        for index, period in enumerate(periods):
            if index % 2:
                pdf.setFillColor(PALE_LAVENDER)
                pdf.rect(39, cursor - 14, 518, 29, fill=1, stroke=0)
            pdf.setFillColor(INK)
            pdf.setFont("Helvetica-Bold", 8.5)
            pdf.drawString(52, cursor, i18n.body_name(lang, period["body"]))
            pdf.setFont("Helvetica", 8.5)
            pdf.drawString(200, cursor, period["start"])
            pdf.drawString(390, cursor, period["end"])
            cursor -= 32
        y = cursor - 20
        self._section_label(S(lang, "station_notes"), 38, y)
        self._ruled_lines(38, y - 22, 520, 6, 22)

    def draw_phases(self, spec: PageSpec) -> None:
        lang = self.lang
        start_idx, end_idx = spec.payload
        month_set = {f"{y:04d}-{m:02d}" for y, m in self.months[start_idx:end_idx]}
        y = self._page_title(spec.title, S(lang, "phases_eyebrow", tz=self.tz))
        pdf = self.pdf
        phases = [event for event in self.data["moon_phases"] if event["date"][:7] in month_set]
        columns = [38, 304]
        column_width = 254
        midpoint = (len(phases) + 1) // 2
        groups = [phases[:midpoint], phases[midpoint:]]
        for column, group in enumerate(groups):
            x = columns[column]
            cursor = y
            for event in group:
                stamp = date.fromisoformat(event["date"])
                fill = PALE_GOLD if event["name"] in {"New Moon", "Full Moon"} else CREAM
                self._card(x, cursor, column_width, 43, fill)
                pdf.setFillColor(LAVENDER if event["name"] in {"New Moon", "Full Moon"} else MUTED)
                pdf.setFont("Helvetica-Bold", 6.7)
                pdf.drawString(x + 10, cursor - 17, f"{i18n.fmt_month_day(lang, stamp).upper()}  {event['time']}")
                pdf.setFillColor(NAVY)
                name = i18n.PHASE_EVENTS_JA[event["name"]] if lang == "ja" else event["name"]
                pdf.setFont("Times-Bold", 9.2)
                pdf.drawString(x + 90, cursor - 17, name)
                pdf.setFillColor(MUTED)
                pdf.setFont("Helvetica", 6.7)
                pdf.drawString(x + 90, cursor - 31, S(lang, "moon_in", sign=i18n.sign_name(lang, event["sign"]), tz=self.tz))
                cursor -= 48

    def draw_month(self, spec: PageSpec) -> None:
        lang = self.lang
        year, month = spec.payload
        y = self._page_title(i18n.fmt_month_year(lang, year, month), S(lang, "month_eyebrow", tz=self.tz))
        pdf = self.pdf
        events = self._events_for_month(year, month, 9)
        left_w, right_w = 318, 184
        self._card(38, y, left_w, 292, CREAM)
        self._section_label(S(lang, "key_sky_dates"), 54, y - 23)
        cursor = y - 50
        for event in events:
            pdf.setFillColor(LAVENDER)
            pdf.setFont("Helvetica-Bold", 7.2)
            pdf.drawString(54, cursor, event["date"][8:10])
            pdf.setFillColor(INK)
            label = i18n.event_display(lang, event)
            size = fit_text(label, "Helvetica", 8.2, 252, 6.5)
            pdf.setFont("Helvetica", size)
            pdf.drawString(82, cursor, label)
            cursor -= 26
        self._link(f"calendar_{self.mk(year, month)}", 38, y - 292, left_w, 292)

        self._card(374, y, right_w, 137, PALE_LAVENDER)
        self._section_label(S(lang, "monthly_intention"), 390, y - 23)
        self._ruled_lines(390, y - 53, right_w - 32, 4, 21)
        self._card(374, y - 155, right_w, 137, PALE_SAGE)
        self._section_label(S(lang, "what_to_observe"), 390, y - 178, SAGE)
        self._ruled_lines(390, y - 208, right_w - 32, 4, 21)

        # The lower cards run down to just above the footer rule; the month
        # dashboard used to leave an eighth of the page unused.
        lower_top = y - 315
        self._card(38, lower_top, 254, 288, PALE_GOLD)
        self._section_label(S(lang, "body_energy"), 54, lower_top - 24, GOLD)
        prompts = list(S(lang, "baseline_items")) + [None] * 3
        cursor = lower_top - 52
        for prompt in prompts:
            if prompt is None:
                pdf.setStrokeColor(LINE)
                pdf.setLineWidth(0.55)
                pdf.line(54, cursor - 1, 148, cursor - 1)
            else:
                pdf.setFillColor(INK)
                pdf.setFont("Helvetica", 8.5)
                pdf.drawString(54, cursor, prompt)
            for dot in range(5):
                pdf.setStrokeColor(GOLD)
                pdf.circle(163 + dot * 21, cursor + 3, 4.3, fill=0, stroke=1)
            cursor -= 34
        self._card(310, lower_top, 248, 288, CREAM)
        self._section_label(S(lang, "questions_month"), 326, lower_top - 24)
        cursor = lower_top - 51
        for question in S(lang, "month_questions"):
            cursor = draw_wrapped(pdf, question, 326, cursor, 216, "Helvetica-Bold", 8, 11, INK)
            self._ruled_lines(326, cursor - 7, 216, 3, 17)
            cursor -= 67

    def _events_on_date(self, iso: str) -> list[dict[str, Any]]:
        events = [event for event in self.events if event["date"] == iso]
        priority = {"outer_aspect": 0, "station": 1, "moon_phase": 2, "ingress": 3}
        return sorted(events, key=lambda event: priority[event["type"]])

    def draw_calendar(self, spec: PageSpec) -> None:
        lang = self.lang
        year, month = spec.payload
        y = self._page_title(spec.title, S(lang, "calendar_eyebrow"))
        pdf = self.pdf
        grid_x, grid_width = 38, 520
        col_width = grid_width / 7
        header_height = 28
        weeks = calendar.Calendar(firstweekday=0).monthdayscalendar(year, month)
        row_height = min(91, (y - 56 - 48) / len(weeks))
        pdf.setFillColor(NAVY)
        pdf.roundRect(grid_x, y - header_height, grid_width, header_height, 6, fill=1, stroke=0)
        for index, label in enumerate(S(lang, "weekday_heads")):
            pdf.setFillColor(PALE_GOLD if index < 5 else PALE_LAVENDER)
            pdf.setFont("Helvetica-Bold", 6.6)
            pdf.drawCentredString(grid_x + index * col_width + col_width / 2, y - 18, label)
        top = y - header_height
        for week_index, week in enumerate(weeks):
            cell_top = top - week_index * row_height
            for weekday_index, day in enumerate(week):
                x = grid_x + weekday_index * col_width
                pdf.setFillColor(PAPER if weekday_index < 5 else CREAM)
                pdf.setStrokeColor(LINE)
                pdf.rect(x, cell_top - row_height, col_width, row_height, fill=1, stroke=1)
                if not day:
                    continue
                iso = date(year, month, day).isoformat()
                pdf.setFillColor(NAVY)
                pdf.setFont("Times-Bold", 10)
                pdf.drawString(x + 6, cell_top - 16, str(day))
                events = self._events_on_date(iso)[:2]
                cursor = cell_top - 32
                for event in events:
                    label = i18n.event_display(lang, event)
                    cursor = draw_wrapped(pdf, label, x + 6, cursor, col_width - 11, "Helvetica", 5.8, 7.2, MUTED, 2) - 2
                if iso in self.personal_dates:
                    pdf.setFillColor(GOLD)
                    pdf.circle(x + col_width - 8, cell_top - 20, 2.6, fill=1, stroke=0)
                destination = f"day_{iso.replace('-', '_')}"
                if destination in self.destinations:
                    pdf.setFillColor(LAVENDER)
                    pdf.circle(x + col_width - 8, cell_top - 10, 2.3, fill=1, stroke=0)
                    self._link(destination, x, cell_top - row_height, col_width, row_height)
        legend_y = top - len(weeks) * row_height - 20
        pdf.setFillColor(LAVENDER)
        pdf.circle(43, legend_y + 2, 2.3, fill=1, stroke=0)
        pdf.setFillColor(MUTED)
        pdf.setFont("Helvetica", 7.2)
        pdf.drawString(51, legend_y, S(lang, "linked_daily"))
        if self.mode == "personal":
            pdf.setFillColor(GOLD)
            pdf.circle(178, legend_y + 2, 2.6, fill=1, stroke=0)
            pdf.setFillColor(MUTED)
            pdf.drawString(186, legend_y, S(lang, "personal_peak_legend"))
        self._link(f"month_{self.mk(year, month)}", 432, legend_y - 8, 126, 20)
        pdf.setFillColor(LAVENDER)
        pdf.setFont("Helvetica-Bold", 7.2)
        pdf.drawRightString(558, legend_y, S(lang, "back_overview"))

    def _windows_active(self, iso: str) -> list[dict[str, Any]]:
        if not self.personal:
            return []
        return [w for w in self.personal["windows"] if w["start_date"] <= iso <= w["end_date"]]

    def draw_daily(self, spec: PageSpec) -> None:
        lang = self.lang
        record = self.daily_by_date[spec.payload]
        current = date.fromisoformat(spec.payload)
        weekday = i18n.fmt_weekday(lang, current)
        eyebrow = S(lang, "daily_eyebrow", weekday=weekday.upper() if lang != "ja" else weekday, tz=self.tz)
        y = self._page_title(i18n.fmt_full_date(lang, current), eyebrow)
        pdf = self.pdf
        moon = record["positions"]["Moon"]
        self._card(38, y, 164, 84, PALE_LAVENDER)
        self._section_label(S(lang, "moon_head"), 53, y - 20)
        pdf.setFillColor(NAVY)
        moon_text = self._pos_display(moon)
        pdf.setFont("Times-Bold", fit_text(moon_text, "Times-Bold", 14, 138, 9))
        pdf.drawString(53, y - 43, moon_text)
        pdf.setFillColor(MUTED)
        pdf.setFont("Helvetica", 8)
        phase = i18n.phase_label(lang, record["moon_phase"])
        pdf.drawString(53, y - 62, S(lang, "phase_suffix", phase=phase))

        self._card(216, y, 342, 84, CREAM)
        self._section_label(S(lang, "major_aspects"), 231, y - 20, GOLD)
        cursor = y - 42
        aspects = record["major_aspects"] or [{"name": S(lang, "no_major_aspect"), "orb": None}]
        for aspect in aspects[:3]:
            label = i18n.aspect_display(lang, aspect) if aspect.get("orb") is not None else aspect["name"]
            if aspect.get("orb") is not None:
                orb_text = f"{aspect['orb']:.2f}"
                label += f"  /  {S(lang, 'orb_deg', orb=orb_text)}"
            pdf.setFillColor(INK)
            pdf.setFont("Helvetica", fit_text(label, "Helvetica", 7.8, 310, 6.2))
            pdf.drawString(231, cursor, label)
            cursor -= 15

        y -= 99
        self._card(38, y, 520, 68, PALE_SAGE)
        if self.mode == "personal":
            self._section_label(S(lang, "your_transits"), 53, y - 20, SAGE)
            active = self._windows_active(spec.payload)
            active = sorted(active, key=lambda w: (0 if w["importance"] == "high" else 1, w["start_date"]))[:2]
            cursor = y - 38
            if not active:
                pdf.setFillColor(MUTED)
                pdf.setFont("Helvetica", 7.6)
                pdf.drawString(53, cursor - 4, S(lang, "no_personal_active"))
            for window in active:
                hits = window.get("exact_hits") or [{"date": window["peak_date"]}]
                nearest = min(hits, key=lambda h: abs((date.fromisoformat(h["date"]) - current).days))
                label = i18n.personal_window_display(lang, window)
                label += f"  /  {S(lang, 'peak', date=i18n.fmt_month_day(lang, date.fromisoformat(nearest['date'])))}"
                pdf.setFillColor(INK)
                pdf.setFont("Helvetica", fit_text(label, "Helvetica", 7.6, 490, 6.2))
                pdf.drawString(53, cursor, label)
                cursor -= 14
        else:
            self._section_label(S(lang, "long_term"), 53, y - 20, SAGE)
            long_term = record["long_term_aspects"] or [{"name": S(lang, "no_long_term"), "orb": None}]
            cursor = y - 42
            for aspect in long_term[:2]:
                label = i18n.aspect_display(lang, aspect) if aspect.get("orb") is not None else aspect["name"]
                if aspect.get("orb") is not None:
                    orb_text = f"{aspect['orb']:.2f}"
                    label += f"  /  {S(lang, 'orb_deg', orb=orb_text)}"
                pdf.setFillColor(INK)
                pdf.setFont("Helvetica", 7.8)
                pdf.drawString(53, cursor, label)
                cursor -= 14

        y -= 83
        self._card(38, y, 248, 78, CREAM)
        self._section_label(S(lang, "mood"), 53, y - 20)
        pdf.setStrokeColor(LAVENDER)
        for index in range(5):
            pdf.circle(63 + index * 31, y - 50, 7, fill=0, stroke=1)
        pdf.setFillColor(MUTED)
        pdf.setFont("Helvetica", 6.5)
        pdf.drawString(53, y - 68, S(lang, "low"))
        pdf.drawRightString(182, y - 68, S(lang, "high"))
        self._card(300, y, 258, 78, CREAM)
        self._section_label(S(lang, "body_health"), 315, y - 20, ROSE)
        for index, label in enumerate(S(lang, "health_items")):
            x = 315 + index * 79
            line_y = y - 42
            pdf.setStrokeColor(ROSE)
            pdf.rect(x, line_y - 2, 7, 7, fill=0, stroke=1)
            pdf.setFillColor(INK)
            pdf.setFont("Helvetica", 6.8)
            pdf.drawString(x + 11, line_y - 1, label)
        for col in range(3):
            x = 315 + col * 79
            line_y = y - 63
            pdf.setStrokeColor(ROSE)
            pdf.rect(x, line_y - 2, 7, 7, fill=0, stroke=1)
            pdf.setStrokeColor(LINE)
            pdf.setLineWidth(0.55)
            pdf.line(x + 11, line_y - 2, x + 68, line_y - 2)

        y -= 94
        sections = [
            (S(lang, "what_happened"), 124, 5),
            (S(lang, "transit_reflection"), 113, 4),
            (S(lang, "notes_head"), 91, 3),
        ]
        for section_index, (heading, height, line_count) in enumerate(sections):
            self._card(38, y, 520, height, PAPER)
            self._section_label(heading, 53, y - 20, GOLD if section_index == 1 else LAVENDER)
            if section_index == 1:
                pdf.setFillColor(MUTED)
                pdf.setFont("Helvetica-Oblique", 7.2)
                hint = S(lang, "reflection_hint")
                pdf.drawString(53 + stringWidth(heading, "Helvetica-Bold", 7.5) + 14, y - 20, hint)
            elif section_index == 2:
                pdf.setFillColor(LAVENDER)
                pdf.setFont("Helvetica-Bold", 6.8)
                pdf.drawRightString(543, y - 20, S(lang, "ai_guide_link"))
                self._link("ai_prompt", 460, y - 29, 90, 16)
            self._ruled_lines(53, y - 43, 490, line_count, 18)
            y -= height + 8

        prev_day = current - timedelta(days=1)
        next_day = current + timedelta(days=1)
        prev_dest = f"day_{prev_day.isoformat().replace('-', '_')}"
        next_dest = f"day_{next_day.isoformat().replace('-', '_')}"
        pdf.setFont("Helvetica-Bold", 6.8)
        if prev_dest in self.destinations:
            pdf.setFillColor(LAVENDER)
            pdf.drawString(287, 16, f"<  {i18n.fmt_month_day(lang, prev_day).upper()}")
            self._link(prev_dest, 282, 8, 52, 16)
        pdf.setFillColor(LAVENDER)
        pdf.drawCentredString(420, 16, S(lang, "day_calendar_link", month=i18n.month_name(lang, current.month)).upper())
        self._link(f"calendar_{self.mk(current.year, current.month)}", 360, 8, 120, 16)
        if next_dest in self.destinations:
            pdf.setFillColor(LAVENDER)
            pdf.drawRightString(533, 16, f"{i18n.fmt_month_day(lang, next_day).upper()}  >")
            self._link(next_dest, 486, 8, 52, 16)

    def draw_reflection(self, spec: PageSpec) -> None:
        lang = self.lang
        y = self._page_title(spec.title, S(lang, "reflection_eyebrow"))
        for index, prompt in enumerate(S(lang, "reflection_prompts")):
            height = 105 if index < 4 else 95
            fill = CREAM if index % 2 == 0 else PALE_LAVENDER
            self._card(38, y, 520, height, fill)
            self._section_label(f"{index + 1:02d}", 52, y - 22, GOLD)
            draw_wrapped(self.pdf, prompt, 82, y - 21, 455, "Helvetica-Bold", 8.4, 11, INK)
            self._ruled_lines(52, y - 48, 490, 3, 18)
            y -= height + 9

    def draw_personal_intro(self, spec: PageSpec) -> None:
        lang = self.lang
        pdf = self.pdf
        if self.mode == "personal":
            y = self._page_title(S(lang, "personal_title"), S(lang, "personal_eyebrow"))
            profile = self.personal["profile"]
            self._card(38, y, 520, 132, PALE_LAVENDER, LAVENDER)
            self._section_label(S(lang, "profile_head"), 55, y - 27)
            pdf.setFillColor(NAVY)
            pdf.setFont("Times-Bold", 18)
            pdf.drawString(55, y - 55, profile.get("display_name", ""))
            details = [
                S(lang, "birth_label", value=f"{profile.get('birth_display', '')} ({profile.get('birth_timezone', '')})"),
                S(lang, "place_label", value=profile.get("birthplace_label", "")),
                S(lang, "zodiac_label", zodiac=profile.get("zodiac", "Tropical"), houses=profile.get("house_system", "Placidus")),
            ]
        else:
            y = self._page_title(S(lang, "personal_title_sample"), S(lang, "personal_eyebrow_sample"))
            profile = self.sample["profile"]
            self._card(38, y, 520, 132, PALE_LAVENDER, LAVENDER)
            self._section_label(S(lang, "profile_head_sample"), 55, y - 27)
            pdf.setFillColor(NAVY)
            pdf.setFont("Times-Bold", 18)
            pdf.drawString(55, y - 55, profile["display_name"])
            details = [
                S(lang, "birth_label", value=profile["birth_utc"]),
                S(lang, "place_label", value=profile["birthplace_label"]),
                S(lang, "zodiac_label", zodiac=profile["zodiac"], houses=profile["house_system"]),
            ]
        cursor = y - 80
        for detail in details:
            pdf.setFillColor(INK)
            pdf.setFont("Helvetica", 8.6)
            pdf.drawString(55, cursor, detail)
            cursor -= 17
        y -= 157
        boxes = [
            (S(lang, "layer_personal_head"), S(lang, "layer_personal_body"), PALE_GOLD),
            (S(lang, "layer_common_head"), S(lang, "layer_common_body"), PALE_SAGE),
        ]
        for heading, body, fill in boxes:
            self._card(38, y, 520, 108, fill)
            self._section_label(heading, 54, y - 25, GOLD if fill == PALE_GOLD else SAGE)
            draw_wrapped(pdf, body, 54, y - 52, 485, "Helvetica", 9.6, 13.5, INK)
            y -= 124
        self._card(38, y, 520, 176, CREAM)
        if self.mode == "personal":
            self._section_label(S(lang, "your_data_head"), 54, y - 25, ROSE)
            draw_wrapped(pdf, S(lang, "your_data_body"), 54, y - 52, 485, "Helvetica", 9.2, 13.5, INK)
            self._section_label(S(lang, "tz_line", tz=f"{self.personal['profile'].get('birth_timezone', 'UTC')} ({self.tz})"), 54, y - 150, LAVENDER)
        else:
            self._section_label(S(lang, "safeguards_head"), 54, y - 25, ROSE)
            cursor = y - 52
            for item in S(lang, "safeguards"):
                pdf.setStrokeColor(ROSE)
                pdf.rect(55, cursor - 3, 7, 7, fill=0, stroke=1)
                cursor = draw_wrapped(pdf, item, 72, cursor + 1, 462, "Helvetica", 8.6, 12, INK) - 6

    def draw_natal(self, spec: PageSpec) -> None:
        lang = self.lang
        pdf = self.pdf
        if self.mode == "personal":
            y = self._page_title(S(lang, "natal_title"), S(lang, "natal_eyebrow", suffix=S(lang, "natal_yours")))
            natal = self.personal["natal_positions"]
            left_names = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"]
            right_names = ["Uranus", "Neptune", "Pluto", "North Node", "South Node", "Ascendant", "Midheaven"]
            row_gap = 27
            boundary = S(lang, "reading_boundary_body")
        else:
            y = self._page_title(S(lang, "natal_title"), S(lang, "natal_eyebrow", suffix=S(lang, "natal_fictional")))
            natal = self.sample["natal_positions"]
            left_names = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter"]
            right_names = ["Saturn", "Uranus", "Neptune", "Pluto", "Ascendant", "Midheaven"]
            row_gap = 34
            boundary = S(lang, "reading_boundary_body_sample")
        for column, names in enumerate([left_names, right_names]):
            x = 38 + column * 266
            self._card(x, y, 254, 252, CREAM)
            self._section_label(S(lang, "placements") if column == 0 else S(lang, "outer_angles"), x + 15, y - 24)
            cursor = y - 50 if row_gap == 27 else y - 57
            for index, name in enumerate(names):
                if name not in natal:
                    continue
                if index % 2:
                    pdf.setFillColor(PALE_LAVENDER)
                    pdf.rect(x + 1, cursor - 12, 252, row_gap - 3, fill=1, stroke=0)
                pdf.setFillColor(INK)
                label = i18n.body_name(lang, name)
                pdf.setFont("Helvetica-Bold", fit_text(label, "Helvetica-Bold", 8.5, 82, 6.5))
                pdf.drawString(x + 15, cursor, label)
                placement = natal[name]
                retro = "  R" if placement.get("retrograde") else ""
                house = placement.get("house")
                suffix = f"  ·  H{house}" if house and self.mode == "personal" else ""
                value = self._pos_display(placement) + retro + suffix
                pdf.setFont("Helvetica", fit_text(value, "Helvetica", 8.5, 140, 6.5))
                pdf.drawRightString(x + 239, cursor, value)
                cursor -= row_gap
        y -= 279
        self._card(38, y, 520, 110, PALE_GOLD)
        self._section_label(S(lang, "reading_boundary"), 54, y - 25, GOLD)
        draw_wrapped(pdf, boundary, 54, y - 52, 485, "Helvetica", 9.2, 13.2, INK)
        y -= 132
        self._section_label(S(lang, "natal_themes"), 38, y)
        self._ruled_lines(38, y - 24, 520, 7, 24)

    # ------------------------------------------------------------ personal

    def _gantt_label(self, window: dict[str, Any]) -> str:
        lang = self.lang
        short = ASPECT_SHORT[lang if lang in ASPECT_SHORT else "en"][window["aspect"]]
        if lang == "ja":
            return f"{i18n.body_name('ja', window['transiting_body'])}→{i18n.body_name('ja', window['natal_body'])} {short}"
        return f"{window['transiting_body']} {short} {window['natal_body']}"

    def _date_to_x(self, value: date, plot_x: float, plot_w: float) -> float:
        total = (self.end_date - self.start_date).days + 1
        offset = (value - self.start_date).days
        offset = max(0, min(total, offset))
        return plot_x + offset / total * plot_w

    def draw_seasons(self, spec: PageSpec) -> None:
        lang = self.lang
        y = self._page_title(spec.title, S(lang, "seasons_eyebrow"))
        pdf = self.pdf
        draw_wrapped(pdf, S(lang, "seasons_intro"), 38, y, 520, "Helvetica", 9.2, 13, MUTED)
        y -= 46
        windows = self.window_chunks[spec.payload]
        plot_x, plot_w = 190, 368
        label_x = 40
        # month grid
        top = y
        bottom = y - 24 - len(windows) * 26 - 8
        for year, month in self.months:
            x = self._date_to_x(date(year, month, 1), plot_x, plot_w)
            pdf.setStrokeColor(LINE)
            pdf.setLineWidth(0.4)
            pdf.line(x, bottom, x, top - 12)
            pdf.setFillColor(MUTED)
            pdf.setFont("Helvetica", 5.6)
            pdf.drawString(x + 2, top - 8, i18n.month_abbr(lang, month).upper())
        cursor = top - 24
        for window in windows:
            label = self._gantt_label(window)
            pdf.setFillColor(INK)
            pdf.setFont("Helvetica", fit_text(label, "Helvetica", 6.8, 142, 5.4))
            pdf.drawString(label_x, cursor - 3, label)
            start = max(self.start_date, date.fromisoformat(window["start_date"]))
            end = min(self.end_date, date.fromisoformat(window["end_date"]))
            x0 = self._date_to_x(start, plot_x, plot_w)
            x1 = max(self._date_to_x(end, plot_x, plot_w), x0 + 2.5)
            high = window["importance"] == "high"
            pdf.setFillColor(LAVENDER if high else SAGE)
            pdf.roundRect(x0, cursor - 5, x1 - x0, 7, 2.5, fill=1, stroke=0)
            hits = window.get("exact_hits") or [{"date": window["peak_date"]}]
            for hit in hits:
                hit_date = date.fromisoformat(hit["date"])
                if self.start_date <= hit_date <= self.end_date:
                    hx = self._date_to_x(hit_date, plot_x, plot_w)
                    pdf.setFillColor(GOLD)
                    pdf.saveState()
                    pdf.translate(hx, cursor - 1.5)
                    pdf.rotate(45)
                    pdf.rect(-2.6, -2.6, 5.2, 5.2, fill=1, stroke=0)
                    pdf.restoreState()
            cursor -= 26
        legend_y = bottom - 16
        pdf.setFillColor(LAVENDER)
        pdf.roundRect(40, legend_y, 18, 6, 2.5, fill=1, stroke=0)
        pdf.setFillColor(MUTED)
        pdf.setFont("Helvetica", 6.5)
        pdf.drawString(62, legend_y, S(lang, "seasons_importance_high"))
        pdf.setFillColor(SAGE)
        pdf.roundRect(122, legend_y, 18, 6, 2.5, fill=1, stroke=0)
        pdf.setFillColor(MUTED)
        pdf.drawString(144, legend_y, S(lang, "seasons_importance_medium"))
        pdf.setFillColor(GOLD)
        pdf.saveState()
        pdf.translate(210, legend_y + 3)
        pdf.rotate(45)
        pdf.rect(-2.6, -2.6, 5.2, 5.2, fill=1, stroke=0)
        pdf.restoreState()
        pdf.setFillColor(MUTED)
        pdf.drawString(220, legend_y, S(lang, "peak", date="").replace("  ", " ").strip().rstrip(":") or "peak")

    def _window_hint(self, window: dict[str, Any]) -> str:
        # The YAML hint_ja mixes English body names ("Uranusのテーマ"), so the
        # localized hint is always rebuilt from the i18n templates instead.
        return i18n.transit_hint(self.lang, window["transiting_body"], window["aspect"], window["natal_body"])

    def draw_personal_month(self, spec: PageSpec) -> None:
        lang = self.lang
        year, month = spec.payload
        pdf = self.pdf
        if self.mode != "personal":
            self._draw_personal_month_sample(spec)
            return
        name = self.personal["profile"].get("display_name", "")
        y = self._page_title(spec.title, S(lang, "personal_month_eyebrow", name=name))
        prefix = f"{year:04d}-{month:02d}"
        focus = [(day, window) for day, windows in sorted(self.personal_dates.items()) if day.startswith(prefix) for window in windows]
        active = [w for w in self.personal["windows"] if w["start_date"] <= f"{prefix}-31" and w["end_date"] >= f"{prefix}-01"]

        self._card(38, y, 520, 210, PALE_LAVENDER)
        self._section_label(S(lang, "personal_dates"), 54, y - 25)
        pdf.setFillColor(LAVENDER)
        pdf.setFont("Helvetica-Bold", 6.8)
        pdf.drawRightString(542, y - 25, S(lang, "month_dashboard", month=self.month_title(year, month)))
        self._link(f"month_{self.mk(year, month)}", 420, y - 34, 125, 16)
        cursor = y - 52
        if not focus:
            draw_wrapped(pdf, S(lang, "no_personal_month"), 54, cursor, 470, "Helvetica", 8.6, 12, MUTED)
            cursor -= 26
        for day, window in focus[:3]:
            stamp = date.fromisoformat(day)
            pdf.setFillColor(GOLD)
            pdf.setFont("Helvetica-Bold", 7.5)
            pdf.drawString(54, cursor, i18n.fmt_month_day(lang, stamp).upper())
            pdf.setFillColor(NAVY)
            label = i18n.personal_window_display(lang, window)
            pdf.setFont("Times-Bold", fit_text(label, "Times-Bold", 10, 420, 7.5))
            pdf.drawString(112, cursor, label)
            self._link(f"day_{day.replace('-', '_')}", 54, cursor - 6, 488, 20)
            cursor -= 24
        divider_y = cursor - 2
        pdf.setStrokeColor(LAVENDER)
        pdf.setLineWidth(0.5)
        pdf.line(54, divider_y, 542, divider_y)
        self._section_label(S(lang, "active_seasons"), 54, divider_y - 16)
        cursor = divider_y - 34
        for window in active[:3]:
            label = self._gantt_label(window)
            period = f"{i18n.fmt_month_day(lang, date.fromisoformat(window['start_date']))} - {i18n.fmt_month_day(lang, date.fromisoformat(window['end_date']))}"
            pdf.setFillColor(INK)
            pdf.setFont("Helvetica-Bold", 7)
            pdf.drawString(54, cursor, label)
            pdf.setFillColor(MUTED)
            pdf.setFont("Helvetica", 6.8)
            pdf.drawString(230, cursor, period)
            hint = self._window_hint(window)
            pdf.setFont("Helvetica", fit_text(hint, "Helvetica", 6.8, 200, 5.4))
            pdf.drawString(340, cursor, hint)
            cursor -= 15
        y -= 227
        sections = [
            (S(lang, "pm_q1"), PALE_GOLD),
            (S(lang, "pm_q2"), PALE_SAGE),
            (S(lang, "pm_q3"), CREAM),
        ]
        for heading, fill in sections:
            self._card(38, y, 520, 100, fill)
            self._section_label(heading, 54, y - 24, GOLD if fill == PALE_GOLD else LAVENDER)
            self._ruled_lines(54, y - 48, 488, 3, 18)
            y -= 111

    def _draw_personal_month_sample(self, spec: PageSpec) -> None:
        lang = self.lang
        year, month = spec.payload
        pdf = self.pdf
        y = self._page_title(spec.title, S(lang, "personal_month_eyebrow", name=S(lang, "profile_head_sample")))
        prefix = f"{year:04d}-{month:02d}"
        events = [event for event in self.sample["selected_2027_transits"] if event["date"].startswith(prefix)]
        self._card(38, y, 520, 135, PALE_LAVENDER)
        self._section_label(S(lang, "personal_dates"), 54, y - 25)
        pdf.setFillColor(LAVENDER)
        pdf.setFont("Helvetica-Bold", 6.8)
        pdf.drawRightString(542, y - 25, S(lang, "month_dashboard", month=self.month_title(year, month)))
        self._link(f"month_{self.mk(year, month)}", 420, y - 34, 125, 16)
        cursor = y - 54
        for event in events:
            stamp = date.fromisoformat(event["date"])
            pdf.setFillColor(GOLD)
            pdf.setFont("Helvetica-Bold", 7.5)
            pdf.drawString(54, cursor, i18n.fmt_month_day(lang, stamp).upper())
            pdf.setFillColor(NAVY)
            pdf.setFont("Times-Bold", 10.5)
            pdf.drawString(118, cursor, event["name"])
            self._link(f"day_{event['date'].replace('-', '_')}", 54, cursor - 8, 488, 24)
            cursor -= 31
        if not events:
            draw_wrapped(pdf, S(lang, "no_personal_month"), 54, cursor, 470, "Helvetica", 9, 12, MUTED)
        y -= 156
        sections = [
            (S(lang, "pm_q1"), PALE_GOLD),
            (S(lang, "pm_q2"), PALE_SAGE),
            (S(lang, "pm_q3"), CREAM),
        ]
        for heading, fill in sections:
            self._card(38, y, 520, 124, fill)
            self._section_label(heading, 54, y - 24, GOLD if fill == PALE_GOLD else LAVENDER)
            self._ruled_lines(54, y - 52, 488, 4, 19)
            y -= 141

    def draw_personal_transits(self, spec: PageSpec) -> None:
        lang = self.lang
        y = self._page_title(spec.title, S(lang, "timeline_eyebrow"))
        pdf = self.pdf
        start, end = spec.payload
        events = self.sample["selected_2027_transits"][start:end]
        draw_wrapped(pdf, S(lang, "timeline_intro"), 38, y, 520, "Helvetica", 9.2, 13, MUTED)
        y -= 52
        for index, event in enumerate(events):
            fill = PALE_LAVENDER if index % 2 == 0 else CREAM
            self._card(38, y, 520, 48, fill)
            stamp = date.fromisoformat(event["date"])
            pdf.setFillColor(LAVENDER)
            pdf.setFont("Helvetica-Bold", 7.2)
            pdf.drawString(51, y - 21, i18n.fmt_month_day(lang, stamp).upper())
            pdf.setFillColor(INK)
            pdf.setFont("Helvetica", fit_text(event["name"], "Helvetica", 8, 382, 6.5))
            pdf.drawString(112, y - 21, event["name"])
            pdf.setFillColor(MUTED)
            pdf.setFont("Helvetica", 6.5)
            pdf.drawRightString(544, y - 21, f"{event['time']} {self.tz}")
            y -= 54
        y -= 8
        self._section_label(S(lang, "observation_notes"), 38, y)
        self._ruled_lines(38, y - 22, 520, 5, 21)
        if spec.bookmark == "personal_transits":
            pdf.setFillColor(LAVENDER)
            pdf.setFont("Helvetica-Bold", 7.2)
            pdf.drawRightString(558, y, S(lang, "continue_timeline"))
            self._link("personal_transits_2", 430, y - 9, 128, 20)

    def draw_ai_prompt(self, spec: PageSpec) -> None:
        lang = self.lang
        y = self._page_title(S(lang, "ai_title"), S(lang, "ai_eyebrow"))
        pdf = self.pdf
        self._card(38, y, 520, 109, PALE_GOLD)
        self._section_label(S(lang, "privacy_first"), 54, y - 25, GOLD)
        draw_wrapped(pdf, S(lang, "privacy_body"), 54, y - 51, 486, "Helvetica", 9.2, 13.2, INK)
        y -= 130
        self._card(38, y, 520, 268, NAVY, NAVY)
        self._section_label(S(lang, "copyable_prompt"), 55, y - 25, GOLD)
        draw_wrapped(pdf, S(lang, "ai_prompt_text"), 55, y - 55, 485, "Courier", 8.2, 12.2, PALE_LAVENDER)
        y -= 291
        self._card(38, y, 520, 153, CREAM)
        self._section_label(S(lang, "questions_ask"), 54, y - 24)
        self._ruled_lines(54, y - 52, 488, 5, 21)

    def draw_notes(self, spec: PageSpec) -> None:
        lang = self.lang
        y = self._page_title(S(lang, "notes_title"), S(lang, "notes_eyebrow"))
        pdf = self.pdf
        pdf.setFillColor(MUTED)
        pdf.setFont("Helvetica-Oblique", 8.5)
        pdf.drawString(38, y, S(lang, "date_topic"))
        pdf.setStrokeColor(LINE)
        pdf.line(38 + stringWidth(S(lang, "date_topic"), "Helvetica-Oblique", 8.5) + 6, y - 2, 558, y - 2)
        self._ruled_lines(38, y - 37, 520, 24, 22)
        pdf.setFillColor(PALE_LAVENDER)
        for row in range(5):
            for col in range(4):
                pdf.circle(76 + col * 145, 84 + row * 128, 1.15, fill=1, stroke=0)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["prototype", "full", "personal"], default="prototype")
    parser.add_argument("--lang", choices=["en", "ja"], default="en")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not args.data.exists():
        raise SystemExit(f"Missing calculated transit data: {args.data}. Run compute_ephemeris.py first.")
    data = json.loads(args.data.read_text(encoding="utf-8"))
    if args.mode == "personal" and "personal" not in data:
        raise SystemExit("--mode personal needs a snapshot computed with --personal-yaml.")
    register_fonts(args.lang)
    label = data["metadata"].get("period_label", "2027")
    if args.output:
        output = args.output
    elif args.mode in {"prototype", "full"} and args.lang == "en":
        output = DEFAULT_OUTPUT_DIR / f"2027_astrology_transit_planner_{args.mode}.pdf"
    else:
        output = DEFAULT_OUTPUT_DIR / f"{label}_astrology_transit_planner_{args.mode}_{args.lang}.pdf"
    planner = Planner(data, output, args.mode, args.lang)
    planner.render()
    print(f"Wrote {output}")
    print(f"Pages: {len(planner.pages)}")


if __name__ == "__main__":
    main()
