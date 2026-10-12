"""Compare to protected before snapshots; never reads/writes customer storage."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from services import shichusuimei_calc as new
from services import yaml_exporter as exporter
OUT=ROOT/"docs/shichusuimei_engine_fix_20261011"

def before(relative,name):
    code=(OUT/"before"/relative).read_text(encoding="utf-8-sig")
    spec=importlib.util.spec_from_loader(name,loader=None)
    module=importlib.util.module_from_spec(spec)
    module.__file__=str(ROOT/relative)  # Same ephemeris files, unchanged calculations.
    sys.modules[name]=module
    exec(compile(code,module.__file__,"exec"),module.__dict__)
    return module

old=before("services/shichusuimei_calc.py","_shichu_before_fix")
old_exporter=before("services/yaml_exporter.py","_exporter_before_fix")
now=datetime(2026,10,11,12,tzinfo=ZoneInfo("Asia/Tokyo"))
oracle=json.loads((ROOT/"tests/fixtures/shichusuimei/overseas_calendar_reference.json").read_text(encoding="utf-8"))["cases"]
rows=[]
for c in oracle:
    if c["day_boundary_hour"]!=0:continue
    dt=datetime.fromisoformat(c["local"])
    a=old.day_kanshi_from_birth(dt,c["timezone"],False)
    b=new.day_kanshi_from_birth(dt,c["timezone"],day_boundary_hour=0)
    rows.append(dict(local=c["local"],timezone=c["timezone"],before=a,after=b,independent_expected=c["day"],after_matches=b==c["day"]))

def comparable(value):
    if isinstance(value,dict):
        return {k:comparable(v) for k,v in value.items()
                if k not in {"generated_at","daiun_direction_status"}
                and not (k=="status" and v=="determined_direction_approx_timing")}
    if isinstance(value,list):return [comparable(v) for v in value]
    return value

japanese=[]
for y,m,d,h,minute,gender in [(1990,5,15,12,30,"female"),(2000,1,7,8,0,"male"),(2024,2,29,20,41,"female")]:
    for late in (False,True):
        payload=dict(year=y,month=m,day=d,hour=h,minute=minute,gender=gender)
        a=old.calc_shichusuimei_from_payload(payload,as_of=now,day_change_at_23=late)
        b=new.calc_shichusuimei_from_payload(payload,as_of=now,day_change_at_23=late)
        japanese.append(dict(payload=payload,day_change_at_23=late,
            normalized_data_unchanged_except_new_status=comparable(a["normalized_data"])==comparable(b["normalized_data"])))

boundaries=[]
for h in (0,1,22,23):
    for late in (False,True):
        dt=datetime(2000,1,7,h,30)
        a=old.pillars_day_hour(dt,day_change_at_23=late)
        b=new.pillars_day_hour(dt,day_change_at_23=late)
        boundaries.append(dict(local=dt.isoformat(),day_change_at_23=late,before=dict(day=a.day,hour=a.hour),after=dict(day=b.day,hour=b.hour)))

western=[]
for title,zone,date,time,lat,lng in [("Fictional Tokyo","Asia/Tokyo","2000-01-07","12:30",35.68,139.76),
                                 ("Fictional Los Angeles","America/Los_Angeles","2000-01-07","23:30",34.05,-118.24)]:
    for combined in (False,True):
        args=dict(title=title,birth_date=date,birth_time=time,prefecture="東京都",tz_name=zone,birth_lat=lat,birth_lng=lng,
                  gender="female",include_shichusuimei=combined,include_transit=True,transit_days=1,include_asteroids=False)
        with patch.object(new,"calc_shichusuimei_from_payload",old.calc_shichusuimei_from_payload):
            a=old_exporter.build_product_yaml(**args)[2]
        b=exporter.build_product_yaml(**args)[2]
        western.append(dict(timezone=zone,combined=combined,western_block_unchanged=comparable(a["systems"]["western"])==comparable(b["systems"]["western"])))

baseline=json.loads((ROOT/"docs/quality_audit_20261010/application_source_baseline.json").read_text(encoding="utf-8"))
changed=[name.replace("\\","/") for name,sha in baseline.items() if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=sha]
result=dict(p0_isolated_rule00_comparison=rows,
            p0_summary=dict(cases=len(rows),before_mismatch=sum(r["before"]!=r["independent_expected"] for r in rows),after_mismatch=sum(not r["after_matches"] for r in rows)),
            japanese_daytime_regression=japanese,japanese_boundary_changes=boundaries,western_regression=western,
            changed_application_files=changed,
            western_engine_sources_unchanged=all(n not in changed for n in ("services/western_calc.py","services/western_core.py")))
(OUT/"before_after_verification.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps({k:v for k,v in result.items() if k not in {"p0_isolated_rule00_comparison","japanese_boundary_changes"}},ensure_ascii=False,indent=2))
assert result["p0_summary"]["after_mismatch"]==0
assert all(r["normalized_data_unchanged_except_new_status"] for r in japanese)
assert all(r["western_block_unchanged"] for r in western)
assert result["western_engine_sources_unchanged"]
