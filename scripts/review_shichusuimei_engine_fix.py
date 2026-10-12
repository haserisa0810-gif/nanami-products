"""Exact Opus re-review of fixed source + before/after diff and counterexamples."""
import difflib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import quality_claude_audit as audit

OUT=ROOT/"docs/shichusuimei_engine_fix_20261011"
FILES=["services/birth_datetime.py","services/shichusuimei_calc.py","services/shichusuimei_annual_report.py",
       "services/yaml_exporter.py","services/api_calc.py","services/prompt_builder.py","services/shichu_chart.py",
       "tests/test_shichusuimei_overseas_engine.py","scripts/build_shichusuimei_independent_cases.py"]
parts=["""# 四柱推命0.5.0 修正の独立再レビュー
実モデルはclaude-opus-5-5のみ。別モデルに切替えない。
この固定ソースと修正前差分をレビューし、既存テスト合格を計算正確性の根拠にしない。
前回P0=UTC offset<=0の日柱+1、P1=1時/23時のUIと実装不一致、P1=unknownの女性補完。
新仕様は現地時計時刻: 1時(標準)は0時台前日、23時は23時台翌日、0時は明示指定のみ暦日。
年/月柱はUTC天文時刻、日/時柱は現地暦日/時計時刻。真太陽時と流派変更は対象外。
UTC±、DST重複/不存在、日付変更線、子刻、年末を独立した式・表・手計算で検証し、反例を具体化する。
unknownは大運未確定(items空)、命式・原局×流年は保持。確定性別の全大運・構造分析の互換性も確認。
旧保存原本は再計算・書換えない。旧booleanの実規則でaddonを作る。日柱が変わる旧海外原本は統合拒否。
日柱アンカーや節気を記憶のみで確定しない。渡された独立参照手法の独立性と限界を批判的に確認する。
模擬でコード実行/外部照合したと書かない。今回ツールは無効。未検証を明記。
出力: 対象、独立検証した式/条件、各P0/P1の解決判定、追加P0-P3、根拠・行・最小反例、方式差、未検証、公開判断。
ローカルのみ。DB・顧客資料・認証キーは渡していない。修正案のみでソース編集はしない。
"""]
for relative in FILES+["routes.py","templates/redeem_shichu.html","API_CALC_SPEC.md"]:
    oldpath=OUT/"before"/relative
    if oldpath.exists():
        old=oldpath.read_text(encoding="utf-8-sig")
        new=(ROOT/relative).read_text(encoding="utf-8-sig")
        parts.append("\n## 修正前からの差分 "+relative+"\n```diff\n"+"".join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile="before/"+relative,tofile="after/"+relative))+"\n```\n")
    elif relative.startswith("templates/"):
        parts.append("\n## 現在のUI（全体）\n"+(ROOT/relative).read_text(encoding="utf-8"))
oracle=json.loads((ROOT/"tests/fixtures/shichusuimei/overseas_calendar_reference.json").read_text(encoding="utf-8"))
parts.append("\n## 独立参照fixtureのメタデータ\n"+json.dumps(oracle["reference"],ensure_ascii=False))
examples=[c for c in oracle["cases"] if c["local"] in {"2000-01-07T00:59:00","2000-01-07T23:30:00"}]
parts.append("\n## 独立参照の代表反例（生成器から、エンジン期待値のコピーではない）\n"+json.dumps(examples,ensure_ascii=False,indent=2))
parts.append("\n## 立春独立資料\n国立天文台2026暦要項: 2026-02-04 05:02 JST (2026-02-03 20:02 UTC)。年/月は2分前=乙巳/己丑、2分後=丙午/庚寅。掲載時刻は分丸め、厳密秒でない。\n")
(OUT/"claude_review_request.md").write_text("\n".join(parts),encoding="utf-8")
audit.OUT=OUT
audit.FILES=FILES
if __name__=="__main__":raise SystemExit(audit.main())
