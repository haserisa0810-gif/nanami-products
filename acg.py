"""ACG 天空線 GeoJSON を出力する CLI。計算本体は services/acg_core.py。

使い方:
    # マンデン線（トランジット天体・対象日 12:00 UTC 基準）
    python acg.py --date 2026-07-02

    # ネイタル線（パーソナル ACG）
    python acg.py --birth-date 1990-01-15 --birth-time 08:30 --tz-offset 9

    # ファイル出力
    python acg.py --date 2026-07-02 -o mundane.geojson
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta, timezone

from services.acg_core import lines_to_geojson

# マンデン線の代表時刻（対象日の 03:00 UTC 固定 = 日本時間の正午時点の空）
MUNDANE_HOUR_UTC = 3


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ACG 天空線 GeoJSON 出力")
    parser.add_argument("--date", help="マンデン線の基準日 YYYY-MM-DD（省略時は今日）")
    parser.add_argument("--birth-date", help="ネイタル線の出生日 YYYY-MM-DD")
    parser.add_argument("--birth-time", default="12:00", help="出生時刻 HH:MM（既定 12:00）")
    parser.add_argument("--tz-offset", type=float, default=9.0, help="タイムゾーンオフセット時間（既定 9 = JST）")
    parser.add_argument("-o", "--output", help="出力ファイルパス（省略時は標準出力）")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    if args.birth_date:
        birth = date.fromisoformat(args.birth_date)
        hour, minute = (int(x) for x in args.birth_time.split(":"))
        local = datetime(
            birth.year, birth.month, birth.day, hour, minute,
            tzinfo=timezone(timedelta(hours=args.tz_offset)),
        )
        geojson = lines_to_geojson(local.astimezone(timezone.utc), natal=True)
    else:
        target = date.fromisoformat(args.date) if args.date else datetime.now(timezone.utc).date()
        dt_utc = datetime(target.year, target.month, target.day, MUNDANE_HOUR_UTC, tzinfo=timezone.utc)
        geojson = lines_to_geojson(dt_utc, natal=False)

    text = json.dumps(geojson, ensure_ascii=False)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text)
    else:
        sys.stdout.write(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
