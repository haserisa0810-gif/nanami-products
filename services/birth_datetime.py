"""Resolve a civil birth time without conflating it with a pillar calendar day.

No solar-time correction and no fallback to UTC. Ambiguous DST times require
an explicit fold/offset or an already aware instant; nonexistent times fail.
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class BirthDatetimeError(ValueError):
    pass


def resolve_birth_datetime(
    birth: datetime, tz_name: str, *, fold: int | None = None,
    utc_offset_hours: float | None = None,
) -> datetime:
    if not isinstance(tz_name, str) or not tz_name.strip():
        raise BirthDatetimeError("出生地のIANAタイムゾーンを指定してください。UTCへ自動補完しません。")
    try:
        tz = ZoneInfo(tz_name)
    except (ValueError, ZoneInfoNotFoundError) as exc:
        raise BirthDatetimeError("出生地のIANAタイムゾーンを確認してください。") from exc
    if fold is not None and (type(fold) is not int or fold not in (0, 1)):
        raise BirthDatetimeError("birth_foldは0または1で指定してください。")
    aware = birth.tzinfo is not None
    local = birth.astimezone(tz) if aware else birth.replace(tzinfo=tz)
    wall = local.replace(tzinfo=None)
    candidates = []
    for choice in (0, 1):
        candidate = wall.replace(tzinfo=tz, fold=choice)
        back = candidate.astimezone(timezone.utc).astimezone(tz)
        if back.replace(tzinfo=None) == wall and back.fold == choice:
            candidates.append(candidate)
    if not candidates:
        raise BirthDatetimeError("出生時刻が夏時間切替などにより存在しません。現地日時を確認してください。")
    if aware:
        candidates = [c for c in candidates if c.astimezone(timezone.utc) == local.astimezone(timezone.utc)]
    if fold is not None:
        candidates = [c for c in candidates if c.fold == fold]
    if utc_offset_hours is not None:
        if isinstance(utc_offset_hours, bool):
            raise BirthDatetimeError("出生当時のUTCオフセットを数値で指定してください。真偽値は使用できません。")
        try:
            offset = float(utc_offset_hours)
        except (ValueError, TypeError) as exc:
            raise BirthDatetimeError("出生当時のUTCオフセットを数値で指定してください。") from exc
        candidates = [c for c in candidates if abs(c.utcoffset().total_seconds() / 3600 - offset) < 1e-9]
    if not candidates:
        raise BirthDatetimeError("指定したUTCオフセット・foldと出生地の日時が一致しません。")
    if len(candidates) > 1:
        raise BirthDatetimeError("出生時刻が夏時間終了により重複します。birth_foldまたは出生当時のUTCオフセットを指定してください。")
    return candidates[0]
