# Chief Editor Neko サンプル UI/UX仕様書

## 1. 目的

Nekoサンプルは、購入前に鑑定結果、ACG、Planner、日別AI等の体験を確認する補助サンプルである。商品そのものや購入者への同梱物ではない。

## 2. 対象

- `GET /demo/neko`
- `GET /demo/neko/personal-edition.zip`
- `GET /demo/neko/planner.pdf`
- `GET /demo/neko/planner-ai`
- `GET /demo/neko/horoscope.svg`
- 正規データ `data/demo/chief_editor_neko.yaml`

## 3. データ・テンプレート設計

- JA / EN / ES / DEを別データ・別実装として複製しない。
- 1つの正規サンプルデータと共通テンプレートを使い、locale辞書と `lang` で表示を切り替える。
- 言語切替で人物、出生データ、計算結果、サンプル基準日は変えない。
- 新しい言語は辞書、日付書式、販売リンク設定、テストを追加して拡張する。
- 正規YAML内の日本語補助フィールドは維持し、非日本語の可視表示・AI用コピーだけから除外する。

## 4. 入口と導線

- `/demo/neko` は既存販売サンプル互換のため、`lang` 未指定または不正値で英語を既定とする。
- Etsy英語導線では必ず `?lang=en` を明示する。
- 国内向け導線では `?lang=ja` を明示する。
- ES / DEページは機能・テスト対象とする。該当言語の商品Listingが公開されるまで、無関係な購入リンクを先行表示しない。
- ページ内のACG、ZIP、Planner、日別AI、SVGは現在の `lang` を引き継ぐ。
- 配下URLへの直リンクはサイト共通fallbackが適用されるため、外部掲載URLでは必ず `lang` を付ける。

## 5. 商品表示

- Nekoは「このような体験になる」というサンプルであり、「Nekoデータが商品に含まれる」と表現しない。
- FULL版には1年Plannerが含まれることを示せるが、ACGを含むように見せない。
- ACG bundleにはACGと1年Plannerが含まれることを示せる。
- 休止中のPlanner単体を購入CTAとして表示しない。
- Museumカード、有料商品へのMuseum同梱表現、Museumアップセルを表示しない。
- 無料Museum機能への案内が必要な場合も、有料商品の内容とは明確に分離する。

## 6. 言語切替

- `JA / EN / ES / DE` の切替を表示する。
- 切替後はページタイトル、説明、カード、CTA、メタ情報、OGP、エラー、リンク先が同じ言語になる。
- 未公開言語の販売リンクは非表示にし、壊れたURLや別言語Listingへfallbackさせない。
- 言語を変えても同じ画面位置と情報構造をできる限り維持する。

## 7. メタ情報と購入前品質

- `<html lang>`, title, description, OGPを表示言語に合わせる。
- SNS共有時に日本語版OGPを英語・スペイン語・ドイツ語へ共用しない。
- サンプル画像・動画は実際の現行UIと商品構成に一致させる。
- 古いMuseum同梱表現、旧Activation方式、休止中Planner単体の購入CTAを販売サンプルへ残さない。

## 8. エラー仕様

- PlannerやZIP生成に失敗した場合、商品が購入できないように見せる曖昧な空白画面にしない。
- 無効な `date`、未対応 `lang`、未設定の販売URLを安全に処理する。
- 未設定の販売URLはリンク要素を表示しない。`#` や現在ページへの偽リンクを使わない。

## 9. 受入テスト

### 自動テスト

- 4言語が同じ正規データを使う。
- 4言語の見出し、カード、リンク、日別AI、メタ情報、OGPを検証する。
- 言語切替後の全リンクに同じ `lang` が付く。
- ES / DE販売URL未設定時に購入リンクが存在しない。
- 非日本語の可視UI・AI用コピーに不要な日本語補助フィールドが出ない。
- Museumカード、Planner単体販売CTA、商品に含まれない機能の表現がない。
- ZIP、Planner、SVGが正規サンプルから生成できる。

主なテスト: `tests/test_neko_demo.py`, `tests/test_planner_ai.py`, `tests/test_acg_locales.py`, `tests/test_multilingual_review_fixes.py`。

### 手動テスト

- 4言語を順番に切り替え、同じ猫・同じデータで表示だけが変わる。
- 各カードを開き、戻った後も選択言語が維持される。
- Etsy掲載用URLをシークレットウィンドウで開き、ログインや既存Cookieなしでも英語になる。
- SNSプレビューまたはOGP検査で、各言語の画像と説明を確認する。
