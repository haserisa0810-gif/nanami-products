from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

import yaml

from services.yaml_exporter import build_product_yaml


@dataclass(frozen=True)
class NoteTransitCampaign:
    campaign_id: str
    label: str
    start_date: date
    end_date: date
    enabled: bool

    @property
    def target_month(self) -> str:
        return self.start_date.strftime("%Y-%m")

    @property
    def days(self) -> int:
        return (self.end_date - self.start_date).days + 1


NOTE_TRANSIT_CAMPAIGNS: dict[str, NoteTransitCampaign] = {
    "2026-07": NoteTransitCampaign(
        campaign_id="note-2026-07",
        label="2026年7月 note特典",
        start_date=date(2026, 7, 1),
        end_date=date(2026, 8, 7),
        enabled=True,
    ),
}


def get_note_transit_campaign(target_month: str) -> NoteTransitCampaign | None:
    return NOTE_TRANSIT_CAMPAIGNS.get((target_month or "").strip())


def build_note_transit_yaml(
    *,
    campaign: NoteTransitCampaign,
    source_doc: dict[str, Any],
    calculation_args: dict[str, Any],
) -> str:
    start_datetime = datetime(
        campaign.start_date.year,
        campaign.start_date.month,
        campaign.start_date.day,
        tzinfo=ZoneInfo(str(calculation_args.get("tz_name") or "Asia/Tokyo")),
    )
    _full_yaml_text, _prompt_text, full_doc = build_product_yaml(
        **calculation_args,
        include_asteroids=False,
        include_shichusuimei=False,
        include_transit=True,
        transit_start_date=start_datetime,
        transit_days=campaign.days,
        data_role="addon",
    )
    western = ((full_doc.get("systems") or {}).get("western") or {})
    transit = western.get("transit")
    if not isinstance(transit, dict) or not transit:
        raise ValueError("固定期間のトランジットデータを生成できませんでした。")

    period = transit.get("period") or {}
    if period.get("start_date") != campaign.start_date.isoformat():
        raise ValueError("トランジット開始日がキャンペーン設定と一致しません。")
    expected_end_date = campaign.end_date.isoformat()
    generated_end_date = period.get("end_date")
    if generated_end_date and generated_end_date != expected_end_date:
        raise ValueError("トランジット終了日がキャンペーン設定と一致しません。")
    period["end_date"] = expected_end_date
    period["target_month"] = campaign.target_month

    source_product = source_doc.get("product") or {}
    source_options = source_product.get("options") or {}
    doc = {
        "version": "nanami-products-yaml-addon-v1",
        "meta": {
            **(full_doc.get("meta") or {}),
            "product_type": "western_note_transit_addon",
            "data_role": "addon",
            "addon_type": "western_note_transit",
            "campaign_id": campaign.campaign_id,
            "target_month": campaign.target_month,
            "source_product_type": source_options.get("product_type") or source_product.get("type"),
        },
        "campaign": {
            "id": campaign.campaign_id,
            "label": campaign.label,
            "target_month": campaign.target_month,
            "start_date": campaign.start_date.isoformat(),
            "end_date": campaign.end_date.isoformat(),
        },
        "base": {
            "target_system": "western",
            "merge_path": "systems.western.transit",
            "compatible_with": ["western_basic", "western_full", "personal_ai_astrology_yaml_natal"],
        },
        "product": {
            "type": "western_note_transit_addon",
            "label": f"{campaign.label} トランジット追加",
            "options": {
                "addon": True,
                "western_natal": False,
                "asteroids": False,
                "transit": True,
                "transit_days": campaign.days,
                "shichusuimei": False,
                "campaign_id": campaign.campaign_id,
                "target_month": campaign.target_month,
            },
        },
        "generated_at": full_doc.get("generated_at"),
        "calculation": full_doc.get("calculation") or {},
        "birth_time": full_doc.get("birth_time") or {},
        "interpretation_flags": full_doc.get("interpretation_flags") or {},
        "assets": {
            "yaml_addon": {
                "available": True,
                "merge_path": "systems.western.transit",
            },
            "horoscope_svg": {"available": False},
            "shichusuimei_svg": {"available": False},
        },
        "input": full_doc.get("input") or {},
        "usage_note": {
            "for_ai": "これはnote特典の月固定トランジット追加データです。元の基本版またはFULL版データと一緒にAIへ渡してください。",
            "merge_instruction": "systems.western.transit を、同じ出生情報で作成済みのYAMLへ追加する想定です。",
        },
        "systems": {
            "western": {
                "natal": None,
                "asteroids": None,
                "transit": transit,
            },
            "shichusuimei": None,
        },
    }
    return yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=120)
