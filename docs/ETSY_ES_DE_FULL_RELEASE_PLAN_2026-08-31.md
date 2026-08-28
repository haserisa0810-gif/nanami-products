# Etsy ES/DE FULL版 発売計画（2026-08-31）

## 1. 決定事項

- 2026年8月31日の発売対象は、Personalized Astrology Reading FULL版（`western_full` / `NP-WF`）のスペイン語版とドイツ語版である。
- FULL版には、出生図、トランジット、小惑星等のFULL版機能と1年Plannerを含む。
- FULL版にACG（Astrocartography）とBirth Chart Museumは含めない。
- Planner単体（`western-transit` / `NP-WBT`）は当面休止を継続する。
- NP-WBTはFULL版との差を購入者へ明確に伝えにくいため、新しいListing、下書き、再公開、販売導線の追加を行わない。
- Etsy下書きは、現在販売中の英語FULL版（NP-WF）を基礎に、スペイン語版とドイツ語版を別々に作成する。
- Etsyショップの既定言語に合わせ、Listingの通常欄（タイトル、説明、タグ）は英語を基準とし、`Spanish Edition` / `German Edition` を明記する。Etsyの手動翻訳欄を使う場合だけES/DE訳を追加する。
- 販売画像、アクセスPDF、購入後UI、生成されるPlannerは、販売する版の言語に合わせる。
- 下書き作成は公開承認ではない。公開は、内容確認とユーザーの別途明示承認後に行う。

## 2. 商品構成

| 商品 | SKU | 1年Planner | ACG | Museum | 今回の扱い |
|---|---|---:|---:|---:|---|
| FULL版 | NP-WF | 含む | 含まない | 含まない | ES/DE版を2026-08-31に発売予定 |
| Planner単体 | NP-WBT | 含む | 含まない | 含まない | 休止継続。下書き・再公開を行わない |
| ACG bundle | NP-ACG | 含む | 含む | 含まない | 今回のES/DE発売対象外 |

## 3. 休止中Planner単体の扱い

Planner単体の機能やSKUは削除しないが、当面は販売商品として扱わない。

- Etsyの休止中Listingを複製しない。
- 新しい言語版Listingや下書きを作らない。
- Nekoサンプル等からPlanner単体の購入CTAを出さない。
- Plannerのサンプルは、ACG bundleまたはFULL版に含まれる1年Planner体験の例として案内する。
- 「FULL版より安価なPlanner商品」として積極表示しない。

再開を検討する場合は、FULL版との機能差、価格差、対象購入者、商品説明を別途決定してから、新しい販売仕様として扱う。

## 4. Etsy下書き作成方針

作成する下書き:

- スペイン語 FULL版: `NP-WF-ES`
- ドイツ語 FULL版: `NP-WF-DE`

下書きでは既存の英語FULL版から、価格、デジタル商品の基本設定、画像構成、商品カテゴリー等を引き継ぐ。ただし、継承した内容をそのまま公開可とはみなさない。

言語別に確認・差し替えるもの:

- 英語の商品タイトル、説明、タグに、販売言語のEdition表記があること
- Etsyの手動翻訳欄を使用する場合のES/DE翻訳
- 販売画像内の可視テキスト
- 動画内の可視テキスト
- 購入後に配布するアクセスPDF
- PDF内の案内文、QRコード、URL、ファイル名
- 購入開始・引換URLの `lang=es` / `lang=de` と `provider=etsy`
- FULL版に1年Plannerを含むこと
- ACGとMuseumを含まないこと
- 購入者向けの免責、利用条件、デジタル商品の説明

## 5. URLと購入導線

候補URLは次を基準とする。

- スペイン語開始: `/start/western-full?lang=es&provider=etsy`
- スペイン語引換: `/redeem/western-full?lang=es&provider=etsy`
- ドイツ語開始: `/start/western-full?lang=de&provider=etsy`
- ドイツ語引換: `/redeem/western-full?lang=de&provider=etsy`
- スペイン語Neko日別AIサンプル: `/demo/neko/planner-ai?lang=es&date=2026-08-01`
- ドイツ語Neko日別AIサンプル: `/demo/neko/planner-ai?lang=de&date=2026-08-01`

全サイトの既定言語は変更しない。Etsyの各言語ListingとアクセスPDFから、該当言語を明示したURLへ接続する。
Neko日別AIサンプルも `lang` を必須とし、画面、コピー文、AI依頼文、エラーを同じ言語で表示する。非日本語版では、正規サンプルデータ内の日本語補助項目（例: `sign_ja`）を画面へ出さない。元データと占星術計算結果は変更しない。

## 6. 公開前チェックリスト

- [ ] 英語のタイトル、説明、タグに `Spanish Edition` / `German Edition` が明記され、別言語を通常欄へ混在させていない。
- [ ] Etsyの手動翻訳欄を使用する場合は、ES/DE訳を校正した。
- [ ] ListingのSKUが `NP-WF-ES` / `NP-WF-DE` である。
- [ ] FULL版に1年Plannerを含むことが明確である。
- [ ] ACGとMuseumを含むように見える表現がない。
- [ ] Planner単体の販売商品・追加購入を案内していない。
- [ ] 販売画像と動画に別言語・旧商品構成が混入していない。
- [x] スペイン語・ドイツ語の販売画像を、それぞれ実際の同言語Planner PDFから生成した。
- [x] JA/EN/ES/DEのFULL版アクセスPDFを言語別に生成し、ES/DEへ英語版PDFを流用しない構成にした。
- [x] 4言語PDFのQRコード、クリック可能URL、可視URLが正しい `lang` と `provider=etsy` を持つことを確認した。
- [x] 添付ファイル名が `nanami_western_full_ETSY_{JA|EN|ES|DE}.pdf` となり、言語と商品を正しく示す。
- [ ] 価格、数量、デジタル商品設定、返品・免責表示を確認した。
- [ ] テスト注文だけを使い、開始、引換、生成、Planner取得まで候補環境で確認した。
- [ ] `NP-WF-ES` / `NP-WF-DE` の数量2、および同一注文で複数商品を購入した場合に、明細・数量分の発行権が作られることを候補環境で確認した。詳細は `docs/MULTI_PURCHASE_ORDER_ENTITLEMENTS_SPEC.md` を参照する。
- [x] NekoのES/DE販売リンクは、URL未設定の公開前状態では非表示になる。
- [ ] ES/DE FULL版Listingの公開時に、`NEKO_SHOP_URL_ES` / `NEKO_SHOP_URL_DE`へ該当Listing URLを設定してリンク先を確認する。
- [x] Neko日別AIのES/DE画面、コピー文、AI依頼文、エラーが選択言語になり、非日本語版に `sign_ja` 等の可視日本語が出ないことをローカルテストした。
- [ ] 本番反映とEtsy公開について、ユーザーの明示承認を得た。

## 7. 現在の状態と残る判断

- 2026-08-27確認時点で、英語FULL版（NP-WF）はEtsyで販売中、Planner単体（NP-WBT）は休止中である。
- NP-WBTを元にしたコピー画面で入力を開始したことはあるが、コピー確定ボタンを押しておらず、Planner単体の新規下書きは作成していない。
- スペイン語FULL版の販売画像7枚を `output/etsy/western-full-es/listing-images/` に生成済みである。実際のスペイン語Planner PDFからページを抽出し、メイン画像、年表示、月相・出生図、トランジット・月間カレンダーに加え、スペイン語本文を読み取りやすい接写画像3枚を掲載した。
- 画像生成元のスペイン語Plannerサンプルは `output/etsy/western-full-es/planner-sample/neko-editor-transit-planner-2026-2027-es.pdf`。432ページ、主要見出しのスペイン語表示、日本語文字0件を確認済みである。
- ドイツ語FULL版の販売画像7枚を `output/etsy/western-full-de/listing-images/` に生成済みである。メイン画像、年表示、月相・出生図、トランジット・月間カレンダー、ドイツ語本文の接写3枚で構成する。ACGまたはMuseumが含まれるように見える文言は使用しない。
- ドイツ語画像の生成元は `output/etsy/western-full-de/planner-sample/neko-editor-transit-planner-2026-2027-de.pdf`。正規サンプルデータから生成した432ページの実Plannerで、PDF抽出テキストの日本語文字0件、Museum表記0件を確認した。販売画像は `scripts/build_etsy_wf_german_images.py` で同じページから再生成できる。
- FULL版のEtsyデジタル商品へ添付する2ページのアクセスPDFをJA/EN/ES/DEで生成した。正規成果物は `output/pdf/etsy-western-full/`、Etsy作業用の同一コピーは `output/etsy/western-full/` に置く。各PDFは該当言語の `/redeem/western-full?lang={lang}&provider=etsy` へ接続し、31日トランジットと12か月Plannerを案内する。PDF内にMuseum名称は表示しない。
- ここでいう「アクセスPDF」は、購入直後にEtsyからダウンロードして注文番号入力ページを開くための案内書であり、購入者ごとに生成される鑑定結果、Planner PDF、旧Personal EditionコードPDFとは別物である。
- 現行のEtsy FULL注文番号方式では、Etsy添付物としてREADMEまたはPersonal Edition ZIPを配布しない。別経路のPersonal EditionコードPDF／購入者別ZIPについても、将来またはサポート用途で使った場合にMuseumを同梱しないよう修正済みである。FULL版ZIPは計算済みYAML、AI相談文、locale別README、専用鑑定ページURLだけを含む。無料Museumアプリと既存URLは別機能として維持する。
- Neko日別AIページはJA/EN/ES/DEの表示辞書へ統合し、ES/DEの画面文言、コピー完了文、注意事項、AI依頼文、入力エラーをローカル実装・検証済みである。非日本語版のAI用テキストから `*_ja` 補助項目を表示時だけ除外し、日本語版と正規サンプルデータは維持している。
- Neko親ページもJA/EN/ES/DEの完全辞書へ更新し、選択言語のACG・ZIP・Planner・日別AIへ接続する。ES/DE販売URLは未設定時に非表示となり、Museumカードと有料商品向け導線は除去済みである。
- 上記画像とPDFはローカル生成物であり、Etsyへは未アップロード・未保存・未公開である。ES/DE文面は用語・導線・商品構成の内部QAを行ったが、外部の職業翻訳者／ネイティブ校正者による証明は取得していない。これは推奨する編集品質確認であり、自動的な技術的公開禁止条件とはしない。公開責任者が現行文面を承認するか、外部校正へ回すかを公開前に決定する。
- 出生地の選択肢は、英語版の曖昧な `Domestic / International` を `Japan / Outside Japan` に変更した。JA/ES/DEも日本を明示する。フォーム送信値の `domestic` は日本の都道府県入力を表す内部互換値として維持し、購入者向けラベルには表示しない。
- ES/DE FULL版の最終価格は未確定である。下書き作成時は英語FULL版の設定を仮継承できるが、公開前に承認する。
- ES/DEの販売画像とアクセスPDFはローカル目視確認済みである。Etsyへ添付する直前にファイル選択を再確認し、動画を使う場合は別途同言語・同商品構成で確認する。
- アプリ側の本番デプロイと本番購入フロー確認は未実施である。候補版作成、本番昇格、Etsy公開はそれぞれ別の承認ゲートとする。
- Etsy/STORES/Payhip共通の複数購入対応はローカル実装済みだが、本番DBの `order_entitlements` 作成と実通知メールによる候補環境確認は未実施である。この確認が終わるまでES/DE Listingを公開しない。
- 2026-08-28の最新ローカル全テスト結果は `613 passed, 141 subtests passed`。本番URLは未デプロイの旧表示のままであり、この結果だけで公開可とはしない。

## 8. 公開禁止条件

次のいずれかが残る場合は公開しない。

- ES/DEの購入者向け画面または配布物に誤言語が残る。
- FULL版とPlanner単体の違いが誤解される。
- ACGまたはMuseumが同梱されるように見える。
- 英語用アクセスPDFや誤ったURLが添付されている。
- 候補環境の購入・引換・生成テストが完了していない。
- ユーザーの明示的な公開承認がない。
