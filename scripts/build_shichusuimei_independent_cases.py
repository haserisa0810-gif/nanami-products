"""Build an offline oracle with lunar-python, not the production engine.

No import of application calculation code. IANA offsets below are explicit
reference data for the four dates; UTC expectations do not reuse ZoneInfo.
"""
import json
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, "C:/Users/haser/nanami-products/tmp/quality-independent-libs")
from lunar_python import Solar

stems = "甲乙丙丁戊己庚辛壬癸"
branches = "子丑寅卯辰巳午未申酉戌亥"
zones = {"Asia/Tokyo": [9]*4, "Asia/Seoul": [9]*4,
         "Europe/London": [0,0,1,0], "America/New_York": [-5,-5,-4,-5],
         "America/Los_Angeles": [-8,-8,-7,-8], "Pacific/Honolulu": [-10]*4,
         "Australia/Sydney": [11,11,10,11], "UTC": [0]*4,
         "Pacific/Kiritimati": [14]*4, "Pacific/Pago_Pago": [-11]*4}
dates = [(2000,1,7), (2024,2,29), (2024,7,1), (2024,12,31)]
times = [(0,0),(0,59),(1,0),(1,1),(22,59),(23,0),(23,30),(23,59)]
rows = []
for zone, offsets in zones.items():
    for (y,m,d), offset in zip(dates,offsets):
        for h, minute in times:
            wall = datetime(y,m,d,h,minute)
            local = wall.replace(tzinfo=timezone(timedelta(hours=offset)))
            utc = local.astimezone(timezone.utc)
            bj = utc.astimezone(timezone(timedelta(hours=8)))
            ec = Solar.fromYmdHms(bj.year,bj.month,bj.day,bj.hour,bj.minute,0).getLunar().getEightChar()
            for boundary in (0,1,23):
                date = wall.date()
                if boundary == 1 and h == 0: date -= timedelta(days=1)
                if boundary == 23 and h == 23: date += timedelta(days=1)
                day = Solar.fromYmd(date.year,date.month,date.day).getLunar().getDayInGanZhi()
                branch = ((h+1)//2)%12
                # Five-mouse rule, independently expressed as an arithmetic cycle.
                hour = stems[(stems.index(day[0])%5*2+branch)%10]+branches[branch]
                rows.append(dict(local=wall.isoformat(),timezone=zone,offset_hours=offset,
                    utc=utc.isoformat(),day_boundary_hour=boundary,effective_date=date.isoformat(),
                    day=day,hour=hour,year=ec.getYear(),month=ec.getMonth()))
doc = dict(reference=dict(library="lunar_python",version="1.4.8",source="https://github.com/6tail/lunar-python",
           term_source="https://eco.mtk.nao.ac.jp/koyomi/yoko/2026/rekiyou262.html",
           calendar="Gregorian civil date, selected 00/01/23 boundary; no true solar time",
           year_month="Independent lunar-python EightChar at same instant in UTC+8; outside term boundary",
           hour="Five-mouse cyclic formula based on selected civil-date stem and local two-hour branch"),cases=rows)
path=ROOT/"tests/fixtures/shichusuimei/overseas_calendar_reference.json"
path.write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding="utf-8")
print(f"Saved {len(rows)} independent cases to {path}")
