"""Reproduce reviewer findings and broaden offline boundary/product checks."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import sys
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from itertools import combinations
from unittest.mock import patch
import yaml

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,"C:/Users/haser/nanami-products/tmp/quality-independent-libs")
from lunar_python import Solar
from lunar_python.util import LunarUtil
from services import shichusuimei_calc as sc, yaml_exporter as ye
from services import western_core as core
from services.api_calc import calc_western_api
from services.asteroid_provider import fetch_asteroids
from services.long_term_transit_yaml import build_long_term_transits_yaml, build_ai_long_term_transits_yaml
from services.light_yaml import build_light_astrology_yaml
from services.chart_svg import build_horoscope_svg_from_yaml
from scripts.quality_verify_astrology import independent_angles_and_cusps

OUT=ROOT/"docs/quality_audit_20261010"
R=[]
def add(name,status,actual=None,expected=None,method="実行再現",**extra):
    R.append(dict(id=name,status=status,actual=actual,expected=expected,method=method,**extra))
def boolean(name,condition,**kw):add(name,"PASS" if condition else "FAIL",**kw)

def main():
    # All expectations are external implementation, mathematical relationships,
    # or explicit output/input contracts, not a pasted copy of application tables.
    for branch,expected in LunarUtil.ZHI_HIDE_GAN.items():
        boolean("hidden_members:"+branch,set(sc.HIDDEN_STEMS[branch])==set(expected),actual=sc.HIDDEN_STEMS[branch],expected=expected,method="lunar_python独立蔵干表（構成員の照合）")
        if sc.HIDDEN_STEMS[branch]!=expected:
            add("hidden_order:"+branch,"未実施",actual=sc.HIDDEN_STEMS[branch],expected=expected,method="並び順に方式差。固定0.3/0.1重みへの影響は方式として要評価")
    for i in range(10):
        dt=datetime(2000,1,7,12)+timedelta(days=i)
        day=Solar.fromYmd(dt.year,dt.month,dt.day).getLunar().getDayInGanZhi()
        for hour in range(1,23,2):
            ec=Solar.fromYmdHms(dt.year,dt.month,dt.day,hour,0,0).getLunar().getEightChar();ec.setSect(2)
            expected=ec.getTimeDiShi().replace("长生","長生").replace("冠带","冠帯").replace("临官","建禄").replace("养","養").replace("绝","絶")
            branch=ec.getTimeZhi()
            boolean(f"stage:{day[0]}:{branch}",sc.twelve_fortune(day[0],branch)==expected,actual=sc.twelve_fortune(day[0],branch),expected=expected,method="lunar_python独立十二運表（陰干・土の方式を統一）")
            actual=sc.hour_kanshi_from_day_stem_and_time(day[0],dt.replace(hour=hour),"Asia/Tokyo")
            boolean(f"hour:{day}:{hour}",actual==ec.getTime(),actual=actual,expected=ec.getTime(),method="lunar_python五鼠遁、日替わり境界を避ける")
    for i,j in combinations(range(12),2):
        a,b=sc.BRANCHES[i],sc.BRANCHES[j]
        item=lambda name,branch:dict(name=name,kanshi="甲"+branch,stem="甲",branch=branch)
        got={r["type"] for r in sc._branch_pair_relations(item("a",a),item("b",b))}
        for label,expected in [("clash",j-i==6),("six_harmony",(i+j)%12==1),("harm",(i+j)%12==7)]:
            boolean(f"branch_geometry:{a}{b}:{label}",(label in got)==expected,method="12地支の対向・鏡映関係から独立構成")
    asof=datetime(2026,10,10,12,tzinfo=ZoneInfo("Asia/Tokyo"))
    calc=sc.calc_shichusuimei_from_payload(dict(year=1990,month=5,day=15,hour=12,gender="unknown"),as_of=asof)
    add("gender_unknown_female_default","FAIL",actual={"input_gender":calc["input"]["raw"].get("gender"),"daiun_gender":calc["normalized_data"]["daiun"].get("gender"),"direction":calc["normalized_data"]["daiun"]["direction"]},expected="未指定の性別を確定させない。API/管理者/ライブラリ経路",reviewer="F4")
    strength=sc._calc_strength_score(sc.Pillars4("庚午","壬午","甲子","甲子"))
    add("strength_output_month_neutral","FAIL",actual=strength["breakdown"][0],expected="木→火の洩気関係を明示（点数の正解自体は未検証）",reviewer="F5")
    try:
        calc=sc.calc_shichusuimei_from_payload(dict(year=1950,month=7,day=15,hour=13,minute=30,gender="female"),as_of=asof)
        dt=datetime(1950,7,15,13,30,tzinfo=ZoneInfo("Asia/Tokyo"))
        add("pre1970_windows_current_runtime","PASS",actual={"offset":str(dt.utcoffset()),"hour_pillar":calc["normalized_data"]["pillars"]["hour"],"daiun_count":len(calc["normalized_data"]["daiun"]["items"])},expected="計算が完了する",reviewer="F9: 当環境Python3.14では再現しない")
        add("shichu_dst_policy","未実施",actual={"civil_hour":13,"standard_hour":12,"dst":str(dt.dst())},expected="流派・採用時刻の方針確定が必要。時計時刻を使うことは確認済み",reviewer="F6（方式差）")
    except Exception as exc:add("pre1970_windows_current_runtime","FAIL",str(exc),reviewer="F9")
    unknown=yaml.safe_load((OUT/"sample_western_unknown.yaml").read_text(encoding="utf-8"))
    transit=unknown["systems"]["western"]["transit"]
    values=[b.get("natal_house") for day in transit["daily"] for b in day["transiting_bodies"].values()]
    add("unknown_transit_natal_house","FAIL" if any(v is not None for v in values) else "PASS",actual={"non_null":sum(v is not None for v in values),"total":len(values),"sample":values[:10]},expected="仮置きハウスを確定値に使わない。出生図側の暫定情報と照合が必要",reviewer="F7")
    # Inspect request contract only; no actual provider request or key is sent.
    class Fake:
        def raise_for_status(self):pass
        def json(self):return {"planets":[]}
    sent={}
    def capture(*a,**kw):sent.update(kw.get("json") or {});return Fake()
    with patch("services.asteroid_provider._get_api_key",return_value="fictional-not-a-key"),patch("services.asteroid_provider.requests.post",side_effect=capture):
        fetch_asteroids(dict(year=2024,month=1,day=1,hour=12,tz_offset_hours=-5,lat=40.71,lng=-74),["Ceres"])
    add("freeastro_timezone_contract","未実施",actual={"sent_keys":sorted(sent),"offset_sent":"tz_offset_hours" in sent},expected="受信サービスの既定タイムゾーン未確認。送信にoffsetがないことのみ確認",reviewer="F8")
    for field,value in [("birth_date","not-a-date"),("birth_date","2023-02-29"),("birth_time","24:00"),("lat",100)]:
        payload=dict(birth_date="1990-05-15",birth_time="12:30",birth_place="東京都",lat=35.68,lon=139.76)
        payload[field]=value
        response,status=calc_western_api(payload)
        boolean(f"api_invalid:{field}:{value}",status==400,actual=dict(http_status=status,response=response),expected="不正な入力にHTTP400（API契約）")
    dt=datetime(2024,11,3,1,30,tzinfo=ZoneInfo("America/New_York"))
    add("DST_ambiguous_fold","FAIL",actual={"default_utc":dt.astimezone(timezone.utc).isoformat(),"other_utc":dt.replace(fold=1).astimezone(timezone.utc).isoformat()},expected="1時間異なる2候補を区別するUIまたは明示。現実装にはfold指定なし")
    base=yaml.safe_load((OUT/"sample_western_basic.yaml").read_text(encoding="utf-8"))
    natal=base["systems"]["western"]["natal"]
    longterm=ye._build_long_term_transit_block(start_date=asof,days=365,lat=35.68,lng=139.76,pref_name="東京都",
        tz_name="Asia/Tokyo",natal_bodies=natal["bodies"],natal_houses=natal["houses"])
    longdoc=deepcopy(base);longdoc["systems"]["western"]["transit_long_term"]=longterm
    full=build_long_term_transits_yaml(doc=longdoc);ai=build_ai_long_term_transits_yaml(doc=longdoc)
    (OUT/"sample_long_term_transits.yaml").write_text(full,encoding="utf-8")
    (OUT/"sample_long_term_transits_ai.yaml").write_text(ai,encoding="utf-8")
    boolean("long_term_parse",isinstance(yaml.safe_load(full),dict) and isinstance(yaml.safe_load(ai),dict),actual={"samples":len(longterm["samples"]),"days":365},method="実計算・実商品用exporter。ピーク精度は週次近似")
    text=(OUT/"sample_western_full.yaml").read_text(encoding="utf-8")
    light=build_light_astrology_yaml(text)
    (OUT/"sample_western_light.yaml").write_text(light,encoding="utf-8")
    boolean("western_light_parse",isinstance(yaml.safe_load(light),dict),method="既存Light生成経路")
    svg=build_horoscope_svg_from_yaml(text)
    import xml.etree.ElementTree as ET
    root=ET.fromstring(svg)
    boolean("western_svg_parse",root.tag.endswith("svg"),method="実商品SVG生成・XML解析（目視は未実施）")
    (OUT/"sample_western.svg").write_text(svg,encoding="utf-8")
    src=Path("C:/Users/haser/dev/nanami-astro")
    for name in ["services/western_core.py","tests/test_western_core_golden.py","tests/fixtures/western_core_golden.json"]:
        a=(src/name).read_bytes();b=(ROOT/name).read_bytes()
        boolean("source_sync_content:"+name,a.replace(b"\r\n",b"\n")==b.replace(b"\r\n",b"\n"),actual={"source_sha256":hashlib.sha256(a).hexdigest(),"products_sha256":hashlib.sha256(b).hexdigest(),"byte_equal":a==b},method="nanami-astro正本と改行正規化後の比較。同期コマンドのrawハッシュ失敗と区別")
    (OUT/"followup_probe_results.json").write_text(json.dumps(R,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
    print({s:sum(x["status"]==s for x in R) for s in ["PASS","FAIL","未実施"]},flush=True)

if __name__=="__main__":main()
