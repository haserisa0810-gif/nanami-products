from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import hashlib
import hmac


@dataclass(frozen=True)
class NoteTransitCampaign:
    campaign_id: str
    access_key_hash: str
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
        access_key_hash="29289964758539427b12262c43e0371ac82e5f7b0017ab2dc82e4468bf7b9a3a",
        label="2026年7月 note特典",
        start_date=date(2026, 7, 1),
        end_date=date(2026, 8, 7),
        enabled=True,
    ),
}


def get_note_transit_campaign(target_month: str) -> NoteTransitCampaign | None:
    return NOTE_TRANSIT_CAMPAIGNS.get((target_month or "").strip())


def get_note_transit_campaign_by_access_key(access_key: str) -> NoteTransitCampaign | None:
    candidate_hash = hashlib.sha256((access_key or "").strip().encode("utf-8")).hexdigest()
    for campaign in NOTE_TRANSIT_CAMPAIGNS.values():
        if hmac.compare_digest(candidate_hash, campaign.access_key_hash):
            return campaign
    return None
