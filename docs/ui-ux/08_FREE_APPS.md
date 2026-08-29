# 無料アプリ・公開デモ UI/UX仕様書

## 1. 位置づけ

無料アプリと公開デモは、有料商品の同梱物・機能一覧とは分離して案内する。有料商品から外した機能を削除するのではなく、既存利用者のURL互換を保ちながら無料体験として維持する。

## 2. Birth Chart Museum

- Birth Chart Museumは全有料商品から除外する。
- Museum機能そのものは削除せず、無料アプリとして残す。
- 既存URL `/birth-chart-museum`, `/birth-chart-museum/demo`, `/birth-chart-museum/demo/architecture`, `/house-tour`, `/house-tour-architecture` の互換を維持する。
- 有料商品の商品名、説明、販売画像、アクセスPDF、ZIP、README、購入導線でMuseumを含むように見せない。
- 無料Museumへのリンクを表示する場合は、「商品に含まれる」ではなく独立した無料体験であることを明記する。
- 将来の「無料で使えるアプリ一覧」ページは別仕様・別作業とする。それまでは既存URLを維持し、有料商品からの積極導線だけを外す。

## 3. Dream Skyその他の無料体験

- Dream Sky、Transit Flight、Astro Earth、旅行デモ等は、それぞれ無料・デモ・購入者限定の区分を画面上で明確にする。
- 保存済みチャートを読み込む機能では、対象データ、言語、戻り先を明示する。
- デモデータと購入者個人データを同じ表示に混在させない。
- 無料体験から有料商品へ案内する場合、実際の商品構成と公開中Listingだけを表示する。
- 休止中Planner単体、Museum同梱、未公開言語ListingへのCTAを出さない。

## 4. URL・データ互換

- 公開済みURLを変更する場合はredirectまたは互換ルートを用意する。
- 既存ブックマークから開いた利用者へ、単なる404ではなく現行の位置づけを案内する。
- 個人YAMLを扱う無料機能は、保存・ログ・外部送信の有無を機能ごとに明示する。
- 無料デモの固定サンプルは顧客データと分離し、実在顧客の情報を使用しない。

## 5. 言語

- 販売体験と接続する無料機能はJA / EN / ES / DEの選択言語を引き継ぐ。
- 4言語未対応の無料機能を有料商品の言語対応範囲として宣伝しない。
- 未翻訳時のfallbackを明示し、辞書キーや内部エラーを表示しない。

## 6. 受入テスト

### 自動テスト

- Museumの既存無料URLが200を返し、有料同梱表現を含まない。
- 有料商品、Neko、アクセスPDF、ZIP、READMEにMuseum同梱表現がない。
- デモと通常ルートで購入CTAの有無・文言が仕様どおり異なる。
- 固定サンプルが顧客データストアを参照しない。
- Transit Flight等の `load` URLが許可された入力だけを読み込む。
- 言語切替とエラーfallbackを確認する。

主なテスト: `tests/test_birth_chart_museum.py`, `tests/test_birth_chart_museum_demo.py`, `tests/test_house_tour.py`, `tests/test_house_tour_architecture.py`, `tests/test_transit_flight.py`, `tests/test_astro_earth.py`, `tests/test_travel_mvp.py`。

### 手動テスト

- 既存Museum URLをブックマークなし・Cookieなしで開く。
- 有料商品への誤った戻り導線がないことを確認する。
- PCとスマートフォンで3D初期化、操作説明、失敗時表示を確認する。
- 無料アプリ一覧を将来追加するとき、既存URLを移動・削除せず一覧から接続する。
