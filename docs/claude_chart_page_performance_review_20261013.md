# Claude Code 発行ページ高速化の最終レビュー

固定差分のレビュー。ツール・編集・テスト実行なし。

## レビュー結果

結論: 合意した設計の意図通りに実装されており、既存動作を壊す確定的な欠陥は見当たりません。1点、実装前提の確認を推奨する箇所があります。差分起因の既存不具合（regression）は見つかりませんでした。

### 確認推奨（中優先度）：chart_doc 多重利用による汚染リスク
- `routes.py:6354-6358` で `chart["prompt_text"]` を `parsed_doc=chart_doc` 付きで構築後、同じ `chart_doc` が `extract_birth_time_notice`（6373-6375）、`_chart_share_yaml_text`（6378）、`share_prompt_text` の再利用判定（6379-6383）、`chart_companion_prompt` 判定（6462-6467）で再利用されます。
- 差分前は `fallback_doc=chart_doc` は例外時のみ使われ、成功時の `prompt_doc` は毎回新規parseされた別オブジェクトでした。差分後は成功時にも**同一オブジェクト参照**が `build_prompt_for_doc`（9390）/`legacy_reading_prompt`（9377）に渡ります。
- `legacy_reading_prompt`（shichusuimei_editions.py）はread-onlyと確認できましたが、`build_prompt_for_doc` の実装は本レビュー資料に含まれておらず、in-place変更の有無は未確認です。変更するなら、最初のprompt構築後に `birth_time_notice`・共有YAML・companion判定が意図せず変わる可能性があります。
- 最小修正案: `build_prompt_for_doc` が非破壊であることをコードで確認する。確証がなければ `routes.py:6356` と `6381` の `parsed_doc=chart_doc` を `parsed_doc=copy.deepcopy(chart_doc)` に変更する（速度は落ちるが安全側）。
- 既存テスト（`test_parsed_prompt_preserves_legacy_and_current_branches`）は単発呼び出し後の非破壊は`deepcopy`比較で確認済みですが、ルート内で複数消費者をまたいだ非破壊は明示的に検証されていません。

### 他の観点は良好
- **原文/軽量版の取り違え**: `share_yaml_text == chart["yaml_text"]` の厳密一致で分岐。西洋軽量版（`has_yaml_mode_selector`系）は`build_light_astrology_yaml`で別文字列になるため自動的に別parseが保たれる。
- **legacy/FULLのプロンプト変化**: `_chart_prompt_for_yaml_text`内の分岐ロジック自体は無変更。parsed_doc有無で`prompt_doc`取得方法のみ変化。
- **安全なローダーのフォールバック**: `getattr(yaml, "CSafeLoader", yaml.SafeLoader)`はグローバル非変更、C拡張なし環境で正しくSafeLoaderへ。SafeConstructorはCSafeLoader/SafeLoaderで共通実装のため構築結果・alias同一性は同等（テストで確認）。
- **不正YAML**: parsed_doc未指定時は従来通りtry/exceptでfallback_docへ後退、安全性の後退なし。
- **HTML**: `FULL_YAML_INLINE = SHARE_YAML`化はJinja側の文字列完全一致判定（JSONエンコード前比較）であり、内容が異なる場合は旧来通り個別埋め込みされる（`test_distinct_share_and_full_strings_are_not_deduplicated`で確認）。宣言順序もSHARE_YAMLが先。DLエンドポイント・ZIP・保存YAML（CRLF含む）は別経路で確認済み。
- **計測**: `prompt_build_ms`新設のみで既存計測区間に影響なし。

差分のスコープ外にある既存の個別`yaml.safe_load`呼び出し（`_chart_share_yaml_text`や`_chart_prompt_text`内）は今回の高速化対象外であり、今回の欠陥ではありません。

## Reviewed SHA256

```json
{
  "routes.py": "1b270e7121f1c417c6526924b27b234fdde099a02147938cb73d3437a0378a97",
  "templates/chart_page.html": "5c4f8f4a25a49aed4797e7e674c0dd8d2e5acb2cabdca6e7f57eae8232bd0def",
  "tests/test_chart_page_display_performance.py": "9ddf49e0b5983839d5fac406fae396dcb9853912348abfc7e49fa4216e79e7ee"
}
```
