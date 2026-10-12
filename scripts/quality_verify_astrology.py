"""Read-only audit probes. FAIL is recorded, never repaired or hidden."""
from __future__ import annotations
import ast
import csv
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import sys
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, "C:/Users/haser/nanami-products/tmp/quality-independent-libs")
from lunar_python import Solar
from services import shichusuimei_calc as sc
from services import western_calc as wc
from services import western_core as core
from services import yaml_exporter as ye
from services.shichusuimei_structure import analyze_structure
from services.shichusuimei_year_selection import build_year_selection, YearSelectionError
from services.shichusuimei_year_extract_prototype import extract_annual
from services.transit_yaml import build_transit_only_yaml

OUT = ROOT / "docs/quality_audit_20261010"
ASOF = datetime(2026, 10, 10, 12, tzinfo=ZoneInfo("Asia/Tokyo"))
RESULTS = []

def record(name, passed, actual=None, expected=None, method="独立実装", **details):
    RESULTS.append(dict(id=name, status="PASS" if passed else "FAIL", actual=actual,
                        expected=expected, method=method, **details))

def check(name, fn, method="境界・整合性検証"):
    try:
        fn()
    except Exception as exc:
        RESULTS.append(dict(id=name, status="FAIL", method=method,
                            error=f"{type(exc).__name__}: {exc}"))

def save():
    OUT.mkdir(parents=True, exist_ok=True)
    doc = dict(as_of=ASOF.isoformat(), python=sys.version, swiss_ephemeris=wc.swe.version,
        lunar_python=importlib.metadata.version("lunar-python"), results=RESULTS)
    (OUT / "new_verification_results.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

def baseline():
    sources = [ROOT / "routes.py", ROOT / "config.py", ROOT / "requirements.txt"]
    for folder in ("services", "templates", "static"):
        sources += [p for p in (ROOT / folder).rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    path = OUT / "application_source_baseline.json"
    if path.exists():
        previous = json.loads(path.read_text(encoding="utf-8"))
        record("application_source_unchanged", hashes == previous, method="SHA256（検証開始時と比較）",
               changed_files=[n for n in hashes if hashes[n] != previous.get(n)])
    else:
        path.write_text(json.dumps(hashes, indent=2), encoding="utf-8")

def days_and_tables():
    for y,m,d in [(1900,1,1),(1975,9,15),(1990,5,15),(2000,1,7),(2024,2,29),(2026,10,10)]:
        expected = Solar.fromYmd(y,m,d).getLunar().getDayInGanZhi()
        for zone in ["Asia/Tokyo", "UTC", "Europe/London", "America/New_York", "Australia/Sydney"]:
            actual = sc.day_kanshi_from_birth(datetime(y,m,d,12), zone, False)
            record(f"day:{y}-{m}-{d}:{zone}", actual == expected, actual, expected,
                   method="lunar_python 1.4.8の独立干支計算（暦日0時切替）")
    for h in (0,1,22,23):
        dt = datetime(2000,1,7,h,30)
        next_day = dt.date() + timedelta(days=h>=23)
        expected = Solar.fromYmd(next_day.year,next_day.month,next_day.day).getLunar().getDayInGanZhi()
        actual = sc.day_kanshi_from_birth(dt, "Asia/Tokyo", True)
        record(f"day_boundary_23:{h:02}:30", actual==expected, actual, expected,
               method="23時切替というUI選択の期待。内部実装の1時切替とは区別")
    god_names = {0:("比肩","劫財"),1:("食神","傷官"),2:("偏財","正財"),
                 3:("偏官","正官"),4:("偏印","印綬")}
    stems = "甲乙丙丁戊己庚辛壬癸"
    for i,a in enumerate(stems):
        for j,b in enumerate(stems):
            expected=god_names[((j//2)-(i//2))%5][(i-j)%2]
            record(f"ten_god:{a}:{b}", sc.ten_god(a,b)==expected, sc.ten_god(a,b), expected,
                   method="五行の相生相剋と陰陽から独立構成した100組")
    for offset in range(60):
        dt = datetime(2000,1,7,12) + timedelta(days=offset)
        lunar = Solar.fromYmdHms(dt.year,dt.month,dt.day,12,0,0).getLunar()
        day=lunar.getDayInGanZhi()
        ec=lunar.getEightChar()
        ec.setSect(2)
        expected=ec.getDayXunKong()
        actual=sc.kubo_from_day_kanshi(day)["empty_branches"]
        record(f"kubo:{day}", "".join(actual)==expected, actual,expected, method="lunar_python全60旬空")
        expected_stage=ec.getTimeDiShi().replace("长生","長生").replace("冠带","冠帯").replace("临官","建禄").replace("养","養").replace("绝","絶")
        actual_stage=sc.twelve_fortune(day[0], "午")
        record(f"twelve:{day}:午", actual_stage==expected_stage, actual_stage,expected_stage,
               method="lunar_pythonの日干×午支。陰干逆行・火土同根方式")
    # Independent Gregorian JD from ordinal; no Swiss call for expectation.
    for dt in [datetime(2000,1,1,12,tzinfo=timezone.utc),datetime(2024,2,29,tzinfo=timezone.utc)]:
        expected=dt.date().toordinal()+1721424.5+(dt.hour*3600+dt.minute*60+dt.second)/86400
        actual=sc.julian_day(dt)
        record(f"jd:{dt.isoformat()}", abs(actual-expected)<1e-8, actual,expected,method="Gregorian ordinal→JDの独立算術")

def solar_terms():
    # Published by NAOJ, rounded to minute; tolerate 60 seconds.
    entries=[(285,1,5,17,23),(315,2,4,5,2),(345,3,5,22,59),(15,4,5,3,40),
             (45,5,5,20,49),(75,6,6,0,48),(105,7,7,10,57),(135,8,7,20,43),
             (165,9,7,23,41),(195,10,8,15,29),(225,11,7,18,52),(255,12,7,11,53)]
    for lon,m,d,h,mi in entries:
        expected=datetime(2026,m,d,h,mi,tzinfo=ZoneInfo("Asia/Tokyo"))
        actual=sc._find_solar_longitude_crossing(target_lon_deg=lon,approx_dt_utc=expected.astimezone(timezone.utc))
        diff=(actual-expected).total_seconds()
        record(f"naoj_jie:{lon}", abs(diff)<=60,actual,expected,method="国立天文台2026暦要項（秒差、許容60秒）",seconds_error=diff)
        before=sc.year_month_pillars(actual-timedelta(minutes=2),"Asia/Tokyo")[:2]
        after=sc.year_month_pillars(actual+timedelta(minutes=2),"Asia/Tokyo")[:2]
        record(f"jie_switch:{lon}", before[1]!=after[1] and ((before[0]!=after[0])==(lon==315)),
               dict(before=before,after=after),method="外部節気時刻近傍での年柱/月柱切替")

def payload(lat=35.68,lng=139.76,**kw):
    return dict(year=2024,month=4,day=8,hour=18,minute=0,birth_time="18:00",
                tz_offset_hours=0,lat=lat,lng=lng,include_asteroids=False,
                include_chiron=False,include_lilith=False,include_vertex=False,**kw)

def circular(a,b): return abs((a-b+180)%360-180)

def independent_angles_and_cusps(dt,lat,lng):
    jd=dt.date().toordinal()+1721424.5+(dt.hour*60+dt.minute)/1440
    t=(jd-2451545)/36525
    theta=math.radians((280.46061837+360.98564736629*(jd-2451545)+.000387933*t*t-t*t*t/38710000+lng)%360)
    eps=math.radians(23+26/60+(21.448-46.815*t-.00059*t*t+.001813*t*t*t)/3600)
    phi=math.radians(lat)
    mc=math.degrees(math.atan2(math.sin(theta),math.cos(theta)*math.cos(eps)))%360
    asc=(math.degrees(math.atan2(-math.cos(theta),math.sin(theta)*math.cos(eps)+math.tan(phi)*math.sin(eps)))+180)%360
    def resid(lon, n):
        lam=math.radians(lon)
        ra=math.atan2(math.sin(lam)*math.cos(eps),math.cos(lam))
        dec=math.asin(math.sin(eps)*math.sin(lam))
        sda=math.acos(-math.tan(phi)*math.tan(dec))
        ha=(theta-ra+math.pi)%(2*math.pi)-math.pi
        target={11:-sda/3,12:-2*sda/3,2:-sda-(math.pi-sda)/3,3:-sda-2*(math.pi-sda)/3}[n]
        return ha-target
    cusps={1:asc,4:(mc+180)%360,7:(asc+180)%360,10:mc}
    for n in (11,12,2,3):
        for lo in range(360):
            hi=lo+1
            a,b=resid(lo,n),resid(hi,n)
            if a*b<=0 and abs(a-b)<.5:
                for _ in range(45):
                    mid=(lo+hi)/2
                    c=resid(mid,n)
                    if a*c<=0:hi=mid
                    else:lo,a=mid,c
                cusps[n]=(lo+hi)/2%360
                cusps[(n+5)%12+1]=(cusps[n]+180)%360
                break
    return asc,mc,cusps

def western_independent():
    dt=datetime(2024,4,8,18,tzinfo=timezone.utc)
    for lat,lng,label in [(35.68,139.76,"Tokyo"),(-33.87,151.21,"Sydney"),(51.51,-.12,"London"),(64.15,-21.94,"Reykjavik")]:
        actual=wc.calc_western_from_payload(payload(lat,lng))
        asc,mc,cusps=independent_angles_and_cusps(dt,lat,lng)
        for key,expected in [("asc",asc),("mc",mc)]:
            record(f"angle_geometry:{label}:{key}",circular(actual["angles"][key],expected)<.03,actual["angles"][key],expected,
                   method="GMST・平均黄道傾斜の独立球面式（真/平均差を考慮し0.03度許容）")
        for house,expected in cusps.items():
            got=actual["houses"][house-1]["lon"]
            record(f"placidus_geometry:{label}:{house}",circular(got,expected)<.03,got,expected,
                   method="赤経/赤緯の半日弧を三等分する独立数値解、0.03度許容")
    for body,command in {"Sun":"10","Moon":"301","Mercury":"199","Venus":"299","Mars":"499",
                         "Jupiter":"599","Saturn":"699","Uranus":"799","Neptune":"899","Pluto":"999"}.items():
        params=dict(format="json",COMMAND=command,EPHEM_TYPE="OBSERVER",CENTER="500@399",
            START_TIME="2024-04-08 18:00",STOP_TIME="2024-04-09 18:00",STEP_SIZE="1 d",QUANTITIES="31",
            CSV_FORMAT="YES",EXTRA_PREC="YES",APPARENT="AIRLESS")
        cache=OUT / f"horizons_{body}.json"
        if cache.exists() and json.loads(cache.read_text(encoding="utf-8"))["parameters"]==params:
            data=json.loads(cache.read_text(encoding="utf-8"))["response"]
        else:
            response=requests.get("https://ssd.jpl.nasa.gov/api/horizons.api",params=params,timeout=45)
            response.raise_for_status()
            data=response.json()
            cache.write_text(json.dumps(dict(parameters=params,response=data),indent=2),encoding="utf-8")
        text=data.get("result","")
        if "$$SOE" not in text:raise ValueError(data.get("error") or "Horizons has no ephemeris")
        rows=list(csv.reader(text.split("$$SOE")[1].split("$$EOE")[0].strip().splitlines()))
        expected=float(rows[0][3]); later=float(rows[1][3]); speed=(later-expected+180)%360-180
        actual=wc.calc_western_from_payload(payload())
        item=next(x for x in actual["planets"] if x["name"]==body)
        record(f"JPL_longitude:{body}",circular(item["lon"],expected)<=.02,item["lon"],expected,
               method="JPL Horizons DE系、地心視黄経（平均/真黄道差含み0.02度許容）",degrees_error=circular(item["lon"],expected))
        record(f"JPL_retrograde:{body}",item["retrograde"]==(speed<0),item["retrograde"],speed<0,
               method="JPL独立黄経の翌日差分（留付近は対象外）")
    for case in [dict(lat=69.65,lng=18.96),dict(lat=-75,lng=0)]:
        try:
            wc.calc_western_from_payload(payload(**case))
            record(f"high_latitude:{case['lat']}",True,method="生成例外の確認（精度検証ではない）")
        except Exception as exc:
            record(f"high_latitude:{case['lat']}",False,str(exc),"明示的な利用制限または適切なエラー応答",method="高緯度生成の例外")
    cases=[(0,0,1,1,True),(0,0,359,-1,True),(10,0,180,1,True),(10,0,190,1,False)]
    # Opposition can approach through 180 degrees; finite difference is the oracle.
    for a,sa,b,sb,_ in cases:
        for aspect in (0,60,90,120,180):
            initial=abs(circular(a,b)-aspect)
            later=abs(circular(a+sa*1e-4,b+sb*1e-4)-aspect)
            if initial<1e-6 or initial>{0:8,60:4,90:6,120:6,180:8}[aspect]:continue
            expected=later<initial
            got=core.aspect_applying(a,sa,b,sb,aspect)
            record(f"aspect_finite_diff:{a}:{b}:{aspect}",got==expected,got,expected,method="微小時間後の幾何学的オーブ差（ライブラリ不使用）")

def structures_and_timing():
    for accuracy in ("exact","unknown","approximate"):
        p=dict(year=1990,month=5,day=15,hour=12,minute=30,gender="female",birth_time_accuracy=accuracy)
        calc=sc.calc_shichusuimei_from_payload(p,as_of=ASOF)
        (OUT / f"shichu_engine_{accuracy}.json").write_text(json.dumps(calc,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
        nd=calc["normalized_data"];struct=nd["structural_analysis"]
        useful=struct["useful_god_analysis"]
        record(f"structure:useful_selected_with_method:{accuracy}",
               useful["definitive_useful_god"]==useful["useful_god_selection"]["useful_god"]
               and useful["definitive_basis"]=="general_fuyi_with_climate_priority_v1",
               method="明示した一般的な取り方（扶抑基本・厳寒酷暑は調候優先）で一つ選ぶ契約。流派共通の正解ではない")
        screens=struct["interactions"]["combination_screening"]
        record(f"structure:no_element_change:{accuracy}",all(not x["confirmed"] and not x["element_change_applied"] for x in screens),method="合化を適用しない出力契約")
        for index,item in enumerate(nd["daiun"]["items"]):
            if index:
                prev=nd["daiun"]["items"][index-1]
                step=1 if nd["daiun"]["direction"]=="forward" else -1
                expected=(sc.KANSHI_60.index(prev["kanshi"])+step)%60
                record(f"daiun_sequence:{accuracy}:{index}",sc.KANSHI_60.index(item["kanshi"])==expected,method="60干支の連続性・順逆整合性")
        for annual in nd["annual_forecasts"]["items"]:
            start=datetime.fromisoformat(annual["period_start"]);end=datetime.fromisoformat(annual["period_end"])
            expected=[]
            for item in nd["daiun"]["items"]:
                a=datetime.fromisoformat(item["approx_start_at"]);b=datetime.fromisoformat(item["approx_end_at"])
                if max(start,a)<min(end,b):expected.append(item["index"])
            actual=[x["index"] for x in annual["daiun_contexts"]]
            record(f"daiun_intersection:{accuracy}:{annual['effective_year']}",actual==expected,actual,expected,method="暦上の半開区間の独立交差判定（起運近似そのものの精度は未確認）")
    for year in ("甲","乙"):
        for gender in ("male","female"):
            expected="forward" if (year=="甲")== (gender=="male") else "reverse"
            actual=sc._daiun_direction_from_year_stem(year,gender)
            record(f"direction:{year}:{gender}",actual==expected,actual,expected,method="陽男陰女順行、陰男陽女逆行の採用規則")
    for zone,local in [("America/New_York",datetime(2024,3,10,2,30)),("America/New_York",datetime(2024,11,3,1,30))]:
        attached=local.replace(tzinfo=ZoneInfo(zone));back=attached.astimezone(timezone.utc).astimezone(ZoneInfo(zone))
        nonexistent=back.replace(tzinfo=None)!=local
        actual=ye.build_product_yaml(title="Fictional DST test",birth_date=local.date().isoformat(),birth_time=local.strftime("%H:%M"),
            prefecture="東京都",tz_name=zone,birth_lat=40.71,birth_lng=-74.0,include_asteroids=False,include_transit=False)
        record(f"DST:{local.isoformat()}", not nonexistent, dict(input=local.isoformat(),utc=attached.astimezone(timezone.utc).isoformat(),roundtrip=back.isoformat()),
               "不存在時刻は拒否または明示。重複時刻のfold選択UIは未実装",method="ZoneInfoの往復による独立存在判定・生成実行")

def products_and_selection():
    # Do not invoke any external asteroid provider. Document the resulting gaps.
    os.environ.pop("FREEASTRO_API_KEY",None)
    args=dict(title="Quality audit fictional A",birth_date="1990-05-15",birth_time="12:30",prefecture="東京都",gender="female")
    configs={}
    for node in ast.parse((ROOT/"routes.py").read_text(encoding="utf-8-sig")).body:
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=="PRODUCT_CONFIG" for t in node.targets):configs=ast.literal_eval(node.value)
    (OUT/"product_catalog.json").write_text(json.dumps(configs,ensure_ascii=False,indent=2),encoding="utf-8")
    products={}
    for name,options in {"western_basic":(False,False,False),"western_full":(True,False,True),"western_asteroids":(True,False,False),
        "western_transit":(False,False,True),"acg_bundle":(True,False,True),"shichu_full":(False,True,False),"combined_admin":(True,True,True)}.items():
        a,s,t=options
        text,prompt,doc=ye.build_product_yaml(**args,include_asteroids=a,include_shichusuimei=s,include_transit=t)
        products[name]=(text,prompt,doc)
    for name,fn in [("western_asteroids_addon",ye.build_asteroid_addon_yaml),("western_31days_transit_addon",ye.build_31days_transit_addon_yaml),("shichu_fortune_cycles_addon",ye.build_shichu_fortune_cycles_addon_yaml)]:
        products[name]=fn(**args)
    products["transit_only"]=build_transit_only_yaml(event_name="Fictional event",event_date="2024-04-08",event_time="18:00",
        location_name="Tokyo",latitude=35.68,longitude=139.76,timezone_name="UTC")
    for name,(text,prompt,doc) in products.items():
        (OUT/f"sample_{name}.yaml").write_text(text,encoding="utf-8")
        (OUT/f"sample_{name}_ai.txt").write_text(prompt+"\n\n```yaml\n"+text+"\n```\n",encoding="utf-8")
        record(f"yaml_roundtrip:{name}",yaml.safe_load(text)==doc,method="実際の生成YAMLをsafe_load、アンカー解決を含む")
        record(f"no_internal_paths:{name}",not any(x in text for x in ["C:\\Users\\","searched_ephe_dirs:","resolved_ephe_dir:","env_sweph_ephe_path:"]),method="生成商品データの診断情報検査")
    full=products["shichu_full"][0]
    source=yaml.safe_load(full);nd=source["systems"]["shichusuimei"]["normalized_data"]
    available=[i["effective_year"] for i in nd["annual_forecasts"]["items"]]
    for years in [[],[available[0]],[available[0],available[1]],[available[0],available[-1]]]:
        mode="selected" if years else "basic"
        result=build_year_selection(full,dict(mode=mode,years=years))
        doc=yaml.safe_load(result["yaml_text"]);out_nd=doc["common"]["systems"]["shichusuimei"]["normalized_data"]
        selected=doc.get("selected_base_forecasts",[])
        expected=[x for x in nd["annual_forecasts"]["items"] if x["effective_year"] in years]
        record(f"selection_years:{years}",selected==expected,method="保存済み年別データの値・配置を比較（再計算なし）")
        record(f"selection_daiun:{years}",out_nd["daiun"]==nd["daiun"],method="全大運の保存値比較")
        if years==[available[0]]:
            (OUT/"sample_shichu_selected_ai.txt").write_text(result["ai_text"],encoding="utf-8")
    original=full.replace("\n","\r\n")
    record("complete_original",build_year_selection(original,dict(mode="complete",years=[]))["yaml_text"]==original,method="原本の改行を含む文字列一致")
    try:
        build_year_selection(full,dict(mode="selected",years=[available[-1]+1]))
        record("selection_out_of_range",False,method="未収録年拒否")
    except YearSelectionError:record("selection_out_of_range",True,method="未収録年拒否")
    (OUT/"selection_available_years.json").write_text(json.dumps(available),encoding="utf-8")

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    baseline()
    for name,fn in [("day_tables",days_and_tables),("solar_terms",solar_terms),("western_independent",western_independent),
                    ("structures_timing",structures_and_timing),("products_selection",products_and_selection)]:
        print("Running "+name,flush=True)
        check(name,fn)
        save()
        print({s:sum(x["status"]==s for x in RESULTS) for s in ["PASS","FAIL"]},flush=True)
    baseline();save()
    print("Audit complete; FAIL entries are findings, not corrected.",flush=True)
    return 0

if __name__=="__main__":raise SystemExit(main())
