# 共通商品台帳の導入（第1段階）

実装先: `tmp/prompt-separation` / `codex/astrology-prompt-separation`。ルートの別ブランチには適用していない。
既存の未コミット変更を保持し、対象既存ファイルの作業前コピーを `tmp/product-catalog-before/` に保存した。コミット・push・デプロイ・本番DB操作・商品公開・価格変更は未実施。

## 商品台帳

`services/product_catalog.py` を唯一の商品コード→内部商品キー対応表とする。商品コード全体を抽出し、正規化後の完全一致で照合する。商品名の「Full」「Basic」「四柱」「追加」などから商品を推測しない。

| 有効コード | 内部商品キー |
|---|---|
| NP-ACG | acg_bundle |
| NP-WBA | western_asteroids |
| NP-WBT | western_transit |
| NP-WB | western_basic |
| NP-WF | western_full |
| NP-WA | western_asteroids_addon |
| NP-AA | western_asteroids_addon |
| NP-WT | western_31days_transit_addon |
| NP-TA | western_31days_transit_addon |
| NP-SF | shichu_fortune_cycles_addon |
| NP-SC | shichu |
| NP-TY | transit_yaml |

AA・TAは有効コードであり、旧コードへの格下げやWA・WTへの書き換えは行わない。Payhipの選択肢4件（WB・WF・AA・TA）、表示ラベル、内部キーを維持し、台帳から生成する。

上記12コード以外に、**このチェックアウトで既存実装されていた** NP-WL（`western_long_term_transits_addon`）とNP-APIを維持した。WLは `routes.py` のaddon選択、基本データ検証、長期データ生成、保存・発行経路および既存回帰テストで確認した。販売サイトの現行設定や本番適用状況の確認とは別である。APIの既存プラン修飾は正確なNP-APIコードがある場合に限り維持する。

NP-SB・NP-SFULL・NP-SY05・NP-SY10・NP-SY20は予約情報のみ。照合表、Payhip選択肢、商品生成、購入権限には登録していない。NP-SCは単一の四柱推命商品であり、年選択の`basic`モードは販売商品Basicへの対応ではない。

## 注文・発行への接続

- STORES・Etsy・Payhip・ココナラのメール取込は同じ照合処理を使用する。Gumroadの厳格照合も同じ台帳を使用し、従来どおりWB・WFのみに限定する。
- 既存の大文字小文字・区切り表記の正規化、JA/EN/ES/DEの言語付きSKU、数量・明細キーの保持を継続する。言語サフィックスでフォームの言語を制限しない。
- `NP-SFULL`、`NP-SF2`、`NP-WF-BOGUS`等を短い有効コードに切り詰めない。未知のコードを含む同一商品行では、併記された有効コードにも自動的に振り分けない。
- 複数種類の商品がある注文では代表商品を決めつけず、既存の明細別発行権を使用する。正確に識別できた別の明細は購入済みの商品に限って利用できる。未分類の明細から発行権を推測生成しない。
- 通常注文で商品種別が未分類・未登録の場合、発行前にエラーで停止する。addonの旧注文経路でも、注文消込・チャート保存の前に停止する。
- 保存済みの既知の商品種別を持つ旧注文はSKUがなくても利用できる。SKUがある発行権は、登録コードと保存済み内部キーの整合を消込前に検査する。
- 明示的な`reusable`・`test`・`permanent`の既存テスト注文の方針は維持する。通常購入へ同じ例外を適用しない。

コードを含まないEtsyの商品名や「テスト」からの推測発行も停止した。これまで商品名だけで自動分類していた**新たな取込通知**は、コードまたは将来の外部ID対応が必要になる。すでに分類済みの旧購入データを自動再分類・上書きする実装はない。

## 外部商品ID

`ChannelProductBinding` と `resolve_channel_product_id()` により、販売チャネル＋外部商品IDを共通商品コードへ完全一致で対応付けられる。チャネルをまたぐ同じIDは別扱いとし、競合設定・未登録コードの対応は拒否する。

今回は実在のSTORES/Etsy商品IDを設定しておらず、API連携やDBテーブルを新設していない。実際のIDを確認した後、チャネルアダプターからこの処理へ接続する。注文ID・SKU・明細キーは外部商品IDの代用として登録しない。

## 変更ファイル

- `services/product_catalog.py`（新規）: 台帳、完全一致照合、SKU正規化、外部ID対応インターフェース。
- `services/stores_mail_sync.py`: 分散したコード対応・商品名推測を共通照合へ置換。
- `routes.py`: Payhip選択肢の生成、通常注文・addonの未分類停止、Gumroad厳格照合の共通化。
- `services/pg_store.py`: 消込・保存前の識別検査、複数商品注文の選択明細を結果に保持。
- `services/site_locales.py`: 未確認商品のエラー文言（日本語・英語・スペイン語・ドイツ語）。
- `tests/test_product_catalog.py`（新規）: 固定した既存12コードを期待値にした3チャネル互換、未知コード、言語SKU、数量・複数商品、外部ID、消込前停止。
- `tests/test_order_intake_and_redeem.py`、`tests/test_unverified_product_warning.py`: 推測発行・警告だけの通過を停止する新仕様に期待値を変更。

計算エンジン、YAML生成、年選択モード、保存済み完全原本、価格、購入履歴のデータは今回編集していない。

## 検証

- 最終の関連回帰テスト: **184 PASS、29サブテストPASS**（1.34秒）。DB・注文照合はモックで、本番へ接続していない。
- 全体回帰テスト: **2039 PASS、160サブテストPASS**（147.61秒）。既存ライブラリの非推奨警告あり。
- `git diff --check`: PASS。
- 実販売サイトからの購入・実際の通知再取込: 未実施。

全体回帰テストの実行開始後にSKUのスペース区切り対応、重複・末尾区切りの不正SKU拒否、チャートpayloadのない複数商品addonの結果保持を追加した。最終の関連テストにはこれらの変更および不正な保存済みSKUの消込停止を含む。全体テストと最終の関連テストを区別し、件数を加算しない。

実行コマンド（チェックアウトをカレントディレクトリにする）:

```powershell
python -m pytest tests -q -p no:cacheprovider --tb=short
python -m pytest tests/test_product_catalog.py tests/test_stores_product_code_coverage.py tests/test_order_intake_and_redeem.py tests/test_unverified_product_warning.py tests/test_multi_purchase_entitlements.py tests/test_addon_idempotency.py tests/test_addon_generate_product_mismatch.py -q -p no:cacheprovider --tb=short
```

## 残る確認

公開前に、実際の通知へ共通コードが収録されることと、STORES/Etsyの外部商品ID・SKU設定を確認する必要がある。コードなし通知の自動発行は停止する仕様のため、当該商品の通知形式を確認し、必要なら正確な外部ID対応を設定する。

過去に誤った商品種別で分類済みの注文については、この変更だけで発見・修復できるとは保証しない。特にSKUが保存されていない旧注文は、注文実績の個別照合が必要。自動変更は行わない。

四柱推命Basic/Fullの独立販売、流年5/10/20年の有効化は第2段階で、商品仕様・内部キー・権限・発行内容を定義した後に扱う。
