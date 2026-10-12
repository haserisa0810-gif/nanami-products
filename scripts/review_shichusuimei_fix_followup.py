"""Exact-model follow-up, retaining the first report and reviewing final guards."""
import difflib
import json
import re
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import quality_claude_audit as audit

BASE = ROOT / "docs/shichusuimei_engine_fix_20261011"
final = "--final" in sys.argv
if final:
    sys.argv.remove("--final")
OUT = BASE / ("claude_final" if final else "claude_followup")
OUT.mkdir(exist_ok=True)
source = (BASE / "independent_review_input.md").read_text(encoding="utf-8")
parts = ["""# Opus 5.5最終保護差分の再確認
前回の実レビュー原文と、その後の対応差分を提示する。元の3件の新規計算判定は前回の固定ソースレビューを参照する。
今回は前回の指摘に対する保護の十分性を独立に確認し、追加の実在する反例だけを出す。
ツール無効。実行や外部照合をしたと主張しない。実モデルclaude-opus-5-5のみ。
変更: 旧原本の年レポートは保存日柱を変更せず、旧offset<=0/不明なら疑義flag。旧unknown->female大運はlegacy_female_imputedで参照用。
四柱/複合APIのみ1.1を識別し仕様変更を告知、西洋単独1.0維持。nullable timezoneと有効tz_nameのalias回帰保護。
旧addon日柱はnormalized/top-level/summaryの順に照合し、不足は拒否。旧offsetは保存値を引継ぐ。
foldは国内も指定可。日本1949重複時刻はresolverで確認。Windows負timestampの既存Q06は今回未修正として公開リスクに残す。
時干規則をtime_contextに明記。文字列のbooleanはエンジンでは拒否、UIはboolean、API day_boundaryは時間enumで別型である。
大運未確定の告知は日本語基本フォームと日本語addonフォームに明記。外部販売ページと外国語告知はこの修正で未確定、公開課題として残す。
呼出元をrgで確認: 運用上の直接呼出元はyaml_exporterのみ。API/admin/buyerはそこを通る。日運や相性の別エンジン呼出元は存在しない。scriptsは検証専用。
order使用済み登録は生成後に実行する既存順序。保存済み原本の自動修正はしない。
出力: 対応のPASS/FAIL/未検証、根拠と最小反例、残る公開条件。モデル単体でコード実行済みと言わない。
""", (BASE / "independent_review.md").read_text(encoding="utf-8")]
if final:
    parts = [parts[0], """## 最終の対応事項
2回目のOpus指摘を反映: N1 timezoneの非文字列false/0/[]/{}は400拒否しraw自体をZoneInfoで検証。
旧女性補完flagは元inputにgenderキーが存在する場合だけ付け、欠落を補完済みと断定しない。
旧日柱疑義をinterpretation_flagsにも明記。API変更履歴は日柱/unknown/必須timezone/新エラーを含める。
実生成関数をモックしない旧JST addon統合テストと西洋/トランジットAPI版1.0の回帰テストを追加。
外部販売ページ・外国語告知・旧原本の救済/返金/再発行・Windows1970以前は未解決事項として明示し、今回の公開はしない。
新規3件と追加保護のコードを最終確認する。未提示箇所への条件付き推測と、実在する反例を区別する。
"""]
for name in ("services/shichusuimei_calc.py", "services/api_calc.py", "services/shichusuimei_annual_report.py", "tests/test_shichusuimei_overseas_engine.py"):
    block = re.search(r"\n## " + re.escape(name) + r"\n```text\n(.*?)\n```", source, re.S)
    if block:
        previous = "\n".join(re.sub(r"^\d+: ", "", line) for line in block.group(1).splitlines())
        current = (ROOT / name).read_text(encoding="utf-8-sig")
        parts.append("\n## 前回からの差分 " + name + "\n```diff\n" + "".join(difflib.unified_diff(previous.splitlines(True), current.splitlines(True), fromfile="round1/" + name, tofile="final/" + name)) + "\n```\n")
routes = (ROOT / "routes.py").read_text(encoding="utf-8-sig")
start = routes.index("def _addon_args_from_base_doc(")
end = routes.index("ASTEROID_ADDON_CHART_PROMPT", start)
parts.append("\n## routes：旧原本の引数と検証・生成\n" + routes[start:end])
parts.append("\n## 生成成功後の注文使用登録\n" + "\n".join(routes.splitlines()[8880:8905]))
parts.append("\n## 日本語addon告知\n" + "\n".join((ROOT / "templates/addon_form.html").read_text(encoding="utf-8").splitlines()[18:31]))
parts.append("\n## API変更履歴\n" + "\n".join((ROOT / "API_CALC_SPEC.md").read_text(encoding="utf-8").splitlines()[:17]))
parts.append("\n## 国内も利用可能な夏時間fold欄\n" + "\n".join((ROOT / "templates/redeem_shichu.html").read_text(encoding="utf-8").splitlines()[161:170]))
(OUT / "claude_review_request.md").write_text("\n".join(parts), encoding="utf-8")
audit.OUT = OUT
audit.FILES = ["services/birth_datetime.py", "services/api_calc.py", "services/shichusuimei_annual_report.py"]
if __name__ == "__main__":
    raise SystemExit(audit.main())
