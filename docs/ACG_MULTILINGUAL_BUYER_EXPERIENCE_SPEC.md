# ACG 購入体験 多言語化仕様書

## 1. 文書情報

| 項目 | 内容 |
|---|---|
| 文書の目的 | ACG（アストロカートグラフィ）商品の英語化・多言語化について、商品判断、第三者レビュー、将来の安全なリリースに使える基準を定める |
| 対象リポジトリ | `nanami-products` |
| 対象ブランチ | `codex/neko-permanent-demo` |
| 確認時の基準 HEAD | `e4172dd06bbf` |
| 最終確認日 | 2026-08-28（JST） |
| 現在の状態 | ACG多言語表示、Neko親ページ・日別AIのJA/EN/ES/DE対応、有料Personal EditionのMuseum非同梱化をローカル実装・検証済み。無料Museum機能と既存URLは維持。最終販売URL、legacy/QA成果物の配布分離、差分分離は未完了。本番未デプロイ |
| 本番操作 | **禁止。ユーザーによる別ターンの明示承認があるまで、候補版作成、デプロイ、トラフィック変更、外部公開を行わない** |

この文書は、上記 HEAD そのものではなく、確認時点の未コミット作業ツリーを含む状態を記述する。多数の変更にACG対応以外の既存ユーザー作業も同居しているため、第三者レビュー・デプロイ前に「今回の対象差分」だけを分離する必要がある。

仕様書の承認は、本番デプロイの承認を意味しない。

### 1.1 改訂履歴

| 日付 | 区分 | 追加・変更事項 |
|---|---|---|
| 2026-08-27 | 初版 | ACG購入体験の英語化・多言語化、成果物管理、テスト、デプロイ承認ゲートを文書化 |
| 2026-08-27 | 商品構成追補 | ACG bundleとPlanner単体の包含関係、Museumの全有料商品からの除外、無料Museum機能・既存URLの維持を確定 |
| 2026-08-27 | **今回の追補** | Nekoサンプルの言語範囲を会話中に再検討し、最終的に1つの正規データと共通テンプレートによるJA/EN/ES/DEの4言語対応で確定 |
| 2026-08-27 | 販売方針追補 | 2026-08-31のES/DE発売対象をFULL版とし、Planner単体（NP-WBT）はFULL版との差を伝えにくいため休止継続。NekoからPlanner単体の積極的な販売導線を外す方針を確定 |
| 2026-08-27 | Etsy表示方針追補 | Etsy Listingの通常欄はショップ既定言語の英語を維持し、Edition名でES/DEを識別。販売画像、アクセスPDF、購入後UI、Plannerは販売言語へ合わせる方針を追加 |
| 2026-08-27 | Neko日別AI実装追補 | JA/EN/ES/DEの画面・AI依頼文・エラーをlocale化し、非日本語版の可視AIデータから日本語補助項目を除外。計算・保存データは変更せず、ローカル全テストを更新 |
| 2026-08-27 | Neko親ページ実装追補 | 親ページの完全なES/DE辞書、4言語メタ情報、商品構成表示、言語別販売URL設定、ES/DE公開前リンク非表示、Museumカード除去、購入者用日別AIテストを実装 |
| 2026-08-27 | 複数購入追補 | 別途承認されたEtsy/STORES/Payhip共通の複数購入対応を `docs/MULTI_PURCHASE_ORDER_ENTITLEMENTS_SPEC.md` に分離。注文番号単位から明細・数量単位の発行権へ拡張するローカル実装を記録。本番DB・デプロイは未変更 |
| 2026-08-28 | Museum有料導線除去 | 有料FULL版のコードPDF・README・ZIPからMuseum文言とアプリ同梱を除去。データZIPをYAML・AI相談文・専用URLへ整理し、無料Museumデモの旧購入CTAを無料版ダウンロードへ変更。無料機能と既存URLは維持 |

### 1.2 追加・変更事項: Nekoサンプルの4言語共通設計

Nekoサンプルの言語範囲は会話中に再検討した。検討途中の案は正式仕様とせず、次を最終決定とする。ACG本体、Planner、購入・引換フォーム、地図、3D地球儀、PDF、ZIP、OGP、販売素材の多言語対応方針も維持する。

- Chief Editor Neko／猫サンプルは `ja`、`en`、`es`、`de` の4言語に対応する。
- 4種類のサンプルデータやテンプレートを複製しない。`data/demo/chief_editor_neko.yaml` を正規サンプルデータとし、共通テンプレート、locale辞書、`lang` 切替で表示する。
- Etsyの標準導線では `lang=en` を明示し、英語版を既定・主要サンプルとして使う。国内向け導線では `lang=ja` を明示する。
- ES/DE版も機能・品質保証の対象とするが、対応言語の商品またはListingを公開するまで販売リンク要素を表示せず、無関係な販売導線へ先行露出させない。
- NekoはACG本体、Planner等の購入前体験を示す補助サンプルであり、商品同梱物ではない。商品内容の説明と混同させない。
- 新しい言語は、サンプルデータやページの複製ではなく、locale辞書と対応テストの追加で拡張する。
- Museumは引き続き全有料商品から除外し、無料アプリとして既存URLを維持する。Neko販売サンプルからMuseumへの商品導線を外すが、Museum機能そのものは削除しない。将来の無料アプリ一覧・ハブは別仕様・別作業である。

## 2. 非技術者向け要約

今回の目的は、Etsyから来た英語購入者が、購入開始から商品利用まで日本語UIに遭遇しない状態を作ることである。ただし、日本語版を廃止するのではなく、英語・日本語・将来の追加言語を同じ仕組みで安全に表示できるようにする。

変更は主に画面表示、文言辞書、言語パラメータの引継ぎ、販売素材の生成に限定した。占星術計算、注文確認、DBの基本構造は原則変更対象にしていない。

ローカルテストと素材確認は完了しているが、本番環境では未確認である。商品構造上はACG bundle、FULL版、Planner単体が別SKUとして存在するが、**2026-08-31のスペイン語・ドイツ語発売対象は1年Plannerを含むFULL版**とする。Planner単体（NP-WBT）はFULL版との差を購入者へ明確に伝えにくいため、当面は休止を継続し、新しいListingや下書きを作らない。Birth Chart Museumはすべての有料商品から外し、無料アプリとして機能と既存URLを維持する。Chief Editor Neko／猫サンプルは1つの正規データと共通テンプレートをJA/EN/ES/DEのlocale辞書で表示し、言語別Listingの公開状況に合わせて販売リンクだけを段階的に有効化する。現行生成コードはMuseum非同梱へ更新したが、旧成果物はlegacy/QAとして残るため配布対象の最終確認が必要であり、本番確認が終わるまで公開可とはしない。

## 3. 背景と目的

### 3.1 背景

英語のEtsy導線で `lang=en` を指定しても、次のような日本語露出が確認されていた。

- ACG商品の説明と特徴
- 注文・出生情報フォームの都道府県、補足、placeholder、title、入力エラー
- ACG地図から開く3D地球儀
- 地図レイヤーの「地図」表示、地理院地図名、APIエラー
- 共通の日本語OGP画像
- Nekoサンプルページ上の日本語版ZIP・Plannerカード
- Etsy販売画像・動画に写り込んだ日本語UI
- 旧仕様のPersonal Edition案内PDFや、配布対象が不明瞭な旧ZIP

### 3.2 目的

1. Etsyの英語導線では、購入者が操作する文言を英語に統一する。
2. 日本語文言を削除せず、`ja` と `en` を明示的に分離する。
3. 既存対応の `es`、`de` と将来言語を同じlocale設計へ載せられるようにする。
4. 既存の日本語既定動作とSTORES導線を維持する。
5. 占星術計算、注文検証、DB、生成コアへの変更を最小化する。
6. 現行の英語配布物と旧成果物を区別し、誤配布を防ぐ。

### 3.3 設計原則

- 表示文はlocale辞書へ置き、テンプレートへ直接埋め込む言語依存文を減らす。
- 座標解決などで必要な内部値は変更せず、表示ラベルだけを翻訳する。
- 言語はURLの `lang` で明示し、画面遷移・API呼出し・ダウンロードリンクへ引き継ぐ。
- 全サイトの既定言語を一括変更しない。Etsy専用URLで `lang=en&provider=etsy` を明示する。
- 日本語を削除して英語へ置換するのではなく、言語別に併存させる。
- 表示層の変更で済む箇所では、計算結果、注文状態、DB保存形式を変更しない。

## 4. 対象範囲

### 4.1 対象

| 分類 | 対象 |
|---|---|
| 購入開始 | `/start/acg-bundle` の商品名、説明、特徴、注意事項 |
| 注文・引換 | `/redeem/acg-bundle`、`/personal-edition/activate` のUI、入力補助、都道府県表示、入力エラー |
| ACG地図 | `/acg` のUI、レイヤー名、CSS生成文、OGP、言語リンク、APIへのlang引継ぎ |
| 公開ACG API | `/api/acg/mundane`、`/api/acg/personal` の購入者向けエラー表示 |
| 3D地球儀 | `/acg/globe-demo` の画面文言、状態表示、ツールチップ、エラー、言語リンク |
| 購入前サンプル | `/demo/neko` を1つの正規データ・共通テンプレート・locale辞書でJA/EN/ES/DE表示し、言語別にリンクを制御 |
| 配布物 | Personal Edition ZIP、README、START-ACG方式の案内PDF、英語ファイル名 |
| 販売素材 | OGP、Etsy販売画像、ACG本体デモ動画、英語Etsy向けNeko動画、英語ソースフレーム |
| 配布管理 | `current-en` と旧 `Final` / `fixed` / 旧EN成果物の区別、Nekoが同梱物でなく補助サンプルであることの明示 |
| 品質保証 | ACG本体等とNekoのJA/EN/ES/DE回帰、可視誤言語検出、リンク・カード・メタ情報、画像・動画・PDF・ZIP確認 |

### 4.2 対象外

- 西洋占星術、ACGライン、天体位置、ハウス等の計算ロジック
- 初期のACG多言語化範囲としての注文番号の正当性確認方式、購入プロバイダ連携、使用済み判定。ただし、その後の別途明示依頼によりEtsy/STORES/Payhipの複数購入対応だけを追加実装した。詳細は `docs/MULTI_PURCHASE_ORDER_ENTITLEMENTS_SPEC.md` を正とする
- 初期のACG多言語化範囲としてのDBスキーマ、既存レコード、注文・チャートの永続化方式。ただし、上記複数購入対応の `order_entitlements` 追加だけは別仕様として扱う
- 本番データの追加、修正、削除、マイグレーション
- 管理画面、内部運用文書、開発コメントなど、購入者に表示されない日本語
- 地図・都市検索データに含まれる日本語の市区町村名・国名のローマ字化
- Museum機能、既存無料デモ、既存無料URLの物理削除
- 将来の「無料で使えるアプリ一覧」ページまたは無料アプリハブの設計・実装
- ES/DEの商品・Listingの公開と、それに伴うNeko販売リンクの有効化（別途公開判断後の作業）
- 本番デプロイ、候補版作成、Cloud Runトラフィック変更、Etsy等へのアップロード

### 4.3 確定した商品構成と販売状態

ACG商品とPlanner単体商品は別SKU・別商品である。包含関係は一方向とする。

```text
ACG bundle ⊃ 1年Planner
Planner単体 ⊄ ACG
```

| 商品 | ACG | 1年Planner | Birth Chart Museum | 販売方針 |
|---|---:|---:|---:|---|
| ACG bundle | 含む | **含む** | **含まない** | ACG商品として別管理 |
| FULL版（`western_full` / NP-WF） | 含まない | **含む** | **含まない** | 2026-08-31にES/DE版を発売予定 |
| Planner単体（`western-transit` / NP-WBT） | 含まない | 含む | **含まない** | **休止継続。当面、新規Listing・下書き・再公開を行わない** |
| その他の有料商品 | 商品ごとの仕様 | 商品ごとの仕様 | **含まない** | 商品ごとの承認に従う |

販売・表示上の要件:

- ACGの商品説明、販売画像、PDF、購入開始ページでは、1年Planner同梱を明記する。
- FULL版の商品説明、販売画像、PDF、購入開始ページでは、1年Planner同梱を各言語で明記する。FULL版にACGは含めない。
- Planner単体は技術上の別SKUとして保持するが、休止中の商品として扱い、販売中または発売予定の商品に見せない。
- 各言語のNekoページではPlannerの購入前サンプルを表示できるが、Planner単体の販売カード・購入CTAとして扱わない。ACG bundleおよびFULL版に含まれるPlanner体験の補助サンプルとして明示する。
- Nekoサンプル自体は購入前の補助体験であり、ACG bundleまたはPlannerの同梱物とは表現しない。
- Birth Chart Museumの名称、同梱案内、起動案内を、ACGを含むすべての有料商品の現行表面と現行配布物へ出さない。

Birth Chart Museum機能そのものは削除しない。無料で使える独立アプリとして残し、既存の無料デモ・機能URLは互換維持する。有料商品の購入導線、同梱説明、アップセル、販売素材からは積極的なMuseum導線を外す。将来は「無料で使えるアプリ一覧」ページまたは無料アプリハブへ掲載する構想とするが、そのハブは別仕様・別作業であり、今回のACG多言語化およびデプロイ範囲には含めない。

### 4.4 2026-08-31 ES/DE発売対象

- 発売対象はFULL版（`western_full` / NP-WF）のスペイン語版・ドイツ語版である。
- FULL版には出生図、トランジット、小惑星等のFULL版機能と1年Plannerを含む。ACGとMuseumは含めない。
- Etsy下書きは既存FULL版Listingを基礎に、ES/DEで別々に作成する。
- 休止中のPlanner単体Listing（NP-WBT）は基礎にせず、複製・再公開もしない。
- Etsyの通常欄（タイトル、説明、タグ）は英語を基準に、`Spanish Edition` / `German Edition` を明記する。手動翻訳欄を使う場合だけES/DE訳を追加する。
- ES/DE用のアクセスPDF、購入開始・引換URL、販売画像内テキスト、購入後UI、Plannerを言語別に確認する。
- 公開は下書きQAとデプロイ承認ゲートを通過した後に別途明示承認を受けて行う。

## 5. 許容例外

地図・都市検索データに含まれる日本語の市区町村名・国名は、商品UIの翻訳漏れとは扱わない。検索精度、座標解決、既存データ互換を優先し、そのまま保持する。

同様に、次の日本語は許容する。

- locale辞書内の `ja` 文言
- 都道府県や出生地を座標解決へ渡すための内部値
- JavaScript内の言語辞書・内部翻訳キー
- 購入者に見えないログ名、開発コメント、管理用メッセージ

ただし、英語画面のボタン、説明、エラー、README、メール相当の案内、ダウンロード名、販売画像へ日本語が表示される場合は許容しない。

## 6. 言語設計

### 6.1 対応言語

`SUPPORTED_LANGS` は次の4言語である。

- `ja`: 日本語
- `en`: 英語
- `es`: スペイン語
- `de`: ドイツ語

この4言語はACG本体だけでなくNekoサンプルにも適用する。Nekoは言語ごとの別ページ・別YAMLを持たず、同一の正規データと共通テンプレートをlocale辞書で切り替える。

### 6.2 `lang` の解決

- 共通の `_resolve_lang()` は、URLの `lang` を小文字化して解決する。
- `ja/en/es/de` 以外、または未指定の場合は、既存互換のため原則 `ja` を返す。
- `/acg` と `/acg/globe-demo` の未指定時は日本語を維持する。
- `/demo/neko` の入口だけは、既存の販売サンプルURL互換のため、`lang` 未指定または不正値のとき `en` を採用する。
- Etsy用Neko URLは既定値へ依存せず、必ず `/demo/neko?lang=en` とする。国内向けURLは `/demo/neko?lang=ja` とする。これにより、全サイトの既定言語を英語へ変更しない。
- NekoのZIP/PDF/日別AI等を直リンクし、`lang` を省略または不正値にした場合は、共通 `_resolve_lang()` による既存互換の `ja` を維持する。通常のNekoページは常に配下リンクへ有効な `lang` を付けるため、ページ内遷移では言語が分かれない。
- 既存の `/demo/neko` と配下URLは維持し、URLを言語別パスへ複製しない。

### 6.3 言語の引継ぎ

- `_lang_urls()` は既存のクエリを維持しつつ、選択言語だけを差し替える。
- ACG地図から3D地球儀へ移動するとき、現在の `lang` をURLへ付与する。
- ACG地図から `/api/acg/mundane`、`/api/acg/personal`、`/api/geocode` を呼ぶとき、現在の `lang` を付与する。
- NekoページのACG、ZIP、Planner PDF、日別AIリンクは、選択中の同じ `lang` を付与する。
- Nekoの言語切替は `ja/en/es/de` の4つを表示し、同じ正規サンプルのまま表示言語だけを変更する。
- Etsyでは英語Nekoリンクだけを有効にする。ES/DEのNekoページ自体はテスト可能にするが、対応言語の商品・Listing公開前は販売リンク要素を表示しない。
- Neko有料商品サンプルからMuseumカードとリンクを除去済み。独立した無料Museumデモは既存URLを維持し、有料購入CTAではなく無料版ZIPへ案内する。
- Etsyの標準英語入口は `lang=en&provider=etsy` を明示する。

### 6.4 既定言語と販売導線

- 日本語/STORESの既存URLを壊さないため、サイト全体の既定言語は日本語のままとする。
- Etsy販売ファイル内の開始URLは英語・Etsyプロバイダを明示する。
- 既存URLへ `lang` を付けない利用者は、Neko入口を除き従来どおり日本語になる。
- Neko入口だけは既存互換のため未指定時英語だが、販売導線では必ず `lang` を明示し、暗黙の既定値を商品言語の判定に使わない。

### 6.5 fallback方針

| 対象 | fallback |
|---|---|
| 共通Web画面 | 未対応・不正 `lang` は `ja` |
| ACG地図辞書 | 未対応言語は `ja` |
| 購入フォーム辞書 | 未対応言語は `ja` |
| ACG商品コピー | `ja/en/es/de` の明示コピーを持つ |
| 3D地球儀 | JA/ENは完全辞書。ES/DEは英語辞書を基礎に一部キーだけ翻訳 |
| Nekoページ本体 | 未指定・不正値はNeko固有の既定 `en`。正式対応するJA/EN/ES/DEは各言語の完全辞書を持ち、他言語へfallbackさせない |
| Neko配下のZIP/PDF/日別AI直リンク | 未指定・不正値は既存互換の `ja`。ページ内リンクは必ず有効な `lang` を付ける |

3D地球儀等でES/DEに英語を表示する箇所は、日本語混入を防ぐための段階的fallbackであり、完全翻訳ではない。一方、Nekoサンプルは4言語対応を完了条件とし、ES/DEを英語全文で代用しない。ES/DEの商品・Listingを公開する前には、Nekoを含む全購入者表面の内部翻訳QAを行う。外部ネイティブレビューは推奨する編集品質確認とし、公開責任者が必要性を判断する。

### 6.6 Neko販売リンクの公開条件

Nekoページの閲覧可否と、ページ内の販売リンク公開可否を分離する。

| 言語 | サンプル表示 | 販売リンク |
|---|---|---|
| `en` | 有効。Etsyの主要サンプル | 英語Etsy Listingへ有効化 |
| `ja` | 有効。国内向けサンプル | 国内向けの対応商品導線へ有効化 |
| `es` | 有効。機能・テスト対象 | スペイン語商品・Listing公開まではリンク要素を非表示 |
| `de` | 有効。機能・テスト対象 | ドイツ語商品・Listing公開まではリンク要素を非表示 |

販売リンクの有効化はlocale辞書へURLを直接混在させず、言語別の商品公開設定または明示的なリンク設定で制御する。新しい言語の追加時も、正規サンプルデータを複製せず、辞書、リンク公開設定、テストを追加する。

### 6.7 内部値と表示ラベルの分離

都道府県は次の構造でテンプレートへ渡す。

```text
value = 東京都   # 座標解決・既存フォーム・保存互換に使う
label = Tokyo    # en/es/de画面で購入者へ表示する
```

日本語画面では `value` と `label` は同じ日本語になる。非日本語画面では47都道府県を英字ラベルで表示する。これにより、既存の `services.location` の解決キーや保存済みデータを変更しない。

## 7. 機能別変更仕様

### 7.1 ACG商品コピー

`acg_bundle` の商品説明と特徴を `PRODUCT_COPY` に追加し、英語開始ページが日本語の `PRODUCT_CONFIG` へ戻らないようにした。ES/DEにも同じ商品単位のコピーを用意した。

主要ファイル:

- `services/site_locales.py`
- `routes.py`
- `templates/start_western_full.html`

### 7.2 注文・引換フォーム

- 注文番号、氏名、都市、海外出生地、緯度・経度のplaceholderとtitleをlocale化した。
- 都道府県の内部値と表示ラベルを分離した。
- 出生時刻精度、国内外出生地、座標、タイムゾーン等の入力エラーをlocale化した。
- 座標計算、都道府県解決、注文確認のコア処理は維持した。

主要ファイル:

- `services/buyer_input_locales.py`
- `services/birth_time.py`
- `routes.py`
- `templates/redeem_western_full.html`
- `templates/personal_edition_activate.html`

### 7.3 ACG公開APIエラー

エラー応答を次の形へ整理した。

```json
{
  "ok": false,
  "error_code": "date_format",
  "error": "Enter the date in YYYY-MM-DD format."
}
```

- `error_code` は言語に依存しない識別子である。
- `error` は `lang` に応じた表示文である。
- 日本語では既存クライアントとの互換のため、元の日本語エラー文を維持する。
- 成功時のGeoJSON、計算処理、YAML保存方針は変更しない。

主要ファイル:

- `services/acg_locales.py`
- `routes.py`
- `templates/acg_map.html`

既知の制約として、現在のエラー分類は内部例外文の部分一致に依存する。内部例外文が将来変更されると `input_invalid` へ分類される可能性がある。長期的には計算/API層が型付きエラーコードを直接返す設計が望ましい。

### 7.4 ACG地図

- 画面文、惑星名、線種、検索、AI向けコピーをlocale辞書から取得する。
- CSSの `content: "地図"` をlocale別の `Map` 等へ変更した。
- 地理院レイヤー名・帰属表示をlocale化した。
- locale別OGPを選択する。
- 3D地球儀リンクとAPI呼出しへ `lang` を引き継ぐ。
- 未指定 `lang` の日本語既定を維持する。

主要ファイル:

- `services/acg_locales.py`
- `templates/acg_map.html`
- `routes.py`
- `static/ogp_acg_en.jpg`
- `static/ogp_acg_es.jpg`
- `static/ogp_acg_de.jpg`

### 7.5 3D地球儀

- 画面タイトル、説明、操作、ロード結果、エラー、ツールチップ、シミュレーション状態を辞書化した。
- ACG地図から選択中の `lang` を引き継ぐ。
- JA/EN/ES/DEの言語切替を表示する。
- 計算デモそのものは変更せず、表示層だけを切り替える。

主要ファイル:

- `services/acg_globe_locales.py`
- `templates/acg_globe_demo.html`
- `routes.py`

### 7.6 Nekoサンプル

- `data/demo/chief_editor_neko.yaml` を唯一の正規サンプルデータとし、JA/EN/ES/DEで複製しない。
- `templates/neko_demo.html` を共通テンプレートとし、`services/neko_demo_locales.py` の4言語辞書と `lang` で購入者向け文言、カード、メタ情報を切り替える。
- 1ページ内へ複数言語のZIP/Plannerカードを同時表示せず、選択中言語のカードだけを出す。
- ACG、ZIP、Planner、日別AIのリンクへ同じ `lang` を付与し、同一セッションの購入前体験で言語を維持する。
- 日別AIページはJA/EN/ES/DEで、title、description、見出し、説明、コピーボタン、コピー完了文、注意事項、AI依頼文、日付・期間・生成エラーを選択言語へ揃える。
- 非日本語の日別AI用テキストでは、正規YAML内の `sign_ja` 等 `*_ja` 補助項目を表示用データから再帰的に除外する。正規サンプルYAML、保存済みチャート、計算結果のデータ構造は変更しない。日本語版では従来どおり日本語補助項目を保持する。
- 未指定・不正値のNekoページ入口は既存どおり英語とする。Etsyは `/demo/neko?lang=en`、国内向けは `/demo/neko?lang=ja` を明示する。
- JA/EN/ES/DEの言語切替を表示する。新しい言語は辞書とテストの追加で拡張し、サンプルデータ・テンプレートは複製しない。
- Plannerカードは、ACG bundleおよびFULL版に含まれる1年Planner体験の購入前サンプルとして表示する。休止中のPlanner単体（NP-WBT）を販売中の商品として見せず、購入CTAも出さない。
- Nekoサンプルは購入前の補助サンプルであり、商品ZIP等への同梱を意味しないことを各言語で明示する。
- ENでは `NEKO_SHOP_URL_EN`、JAでは `NEKO_SHOP_URL_JA`、ESでは `NEKO_SHOP_URL_ES`、DEでは `NEKO_SHOP_URL_DE` を使用する。URL未設定時は販売リンク要素自体を表示しない。ENだけは既存互換のため `ETSY_SHOP_URL` を既定値として継承する。ES/DEは対応FULL版Listing公開時に同じ言語のURLを設定する。
- `services/neko_demo_locales.py` はJA/EN/ES/DEで同一キー集合の完全辞書を持つ。ES/DEを英語全文へfallbackさせない。
- Museumプレビューカードとリンクは有料商品向けNeko販売サンプルから除去した。Museumの無料機能・既存URLは維持し、回帰テスト対象とする。
- `<html lang>`、ページタイトル、description、OGP等のメタ情報も選択言語へ合わせる。
- OGP画像に文字を含む場合は言語別画像を選択する。文字を含まない共通画像を使う場合は画像共有を許容するが、OGP title・description・localeは必ず選択言語へ切り替える。

主要ファイル:

- `services/neko_demo_locales.py`
- `services/planner_ai.py`
- `templates/neko_demo.html`
- `templates/planner_ai_day.html`
- `routes.py`

### 7.7 OGP・販売画像・動画

- locale別OGPをスクリプト生成する。
- Etsyメイン画像内のUIを英語化した。
- ACGデモ動画とEtsy向けNeko動画を英語化し、元の日本語キャプチャは削除せず、英語正規化フレームを別ディレクトリへ出力する。
- 動画は音声なしの15秒MP4として再生成する。
- Neko動画は英語Etsy向けの補助素材であり、Nekoサンプルの4言語Web対応とは別に管理する。ES/DE Listing公開前にES/DE動画を必須とはしないが、英語動画をES/DE商品へ流用する場合は別途販売判断と翻訳QAを必要とする。

主要ファイル:

- `scripts/build_acg_ogp.py`
- `scripts/build_etsy_acg_conversion_main.py`
- `media/etsy-acg-demo/build_video.py`
- `scripts/build_etsy_acg_neko_video.py`
- `media/etsy-acg-demo/frames-en/`

販売動画は既存キャプチャへ英語オーバーレイを適用している。現在のWeb UIからブラウザ自動撮影する方式ではないため、将来UIが変わった場合はキャプチャの更新が必要である。

### 7.8 PDF・ZIP

- 英語のアクセスコードサンプルPDFを、旧Museum/start script前提から現行 `START-ACG.html` 方式へ更新した。このPDFにはMuseum表記がない。
- 現行英語配布物を `output/acg/current-en/` へ明確な `CURRENT` 名で生成する。
- NekoサンプルZIPは同じ正規YAMLから言語別に生成し、選択言語のREADMEと `START-ACG.html` を含む。Neko固有データを言語別に複製しない。
- Neko ZIP、Planner PDF等は購入前サンプル成果物であり、販売商品の同梱物一覧へ含めない。
- 古い `Final`、`fixed`、非 `CURRENT` 成果物は削除せず、legacy/QAとして配布禁止にした。
- `output/pdf/nanami_acg_premium_bundle_etsy_en.pdf` はMuseum表記を除去し、1年Planner同梱を明記した2ページ版へ再生成・検証済み。
- 有料FULL版のPersonal Edition ZIPはMuseumアプリを含めず、`ASTROLOGY-DATA.yaml`、`AI-PROMPT.txt`、locale別README、専用鑑定ページURLだけを格納する。既存ユーザーがすでに保存した旧ZIPは変更しない。
- FULL版アクセスコードPDFのJA/EN/ES/DEサンプルを `output/pdf/personal-edition-full-current/` に再生成し、Museum表記0、4ページ、Planner案内、QR・クリックURLを確認した。日本語版はNoto Sans JPをPDFへ埋め込み、閲覧環境に日本語フォントがなくても本文が欠落しない生成方式とする。

主要ファイル:

- `scripts/build_personal_edition_acg_sample_pdf.py`
- `scripts/build_acg_distribution_artifacts.py`
- `docs/ACG_DISTRIBUTION_ARTIFACTS.md`
- `output/pdf/personal-edition-acg-access-code-sample-en.pdf`

## 8. データ互換性・後方互換性

| 項目 | 方針 |
|---|---|
| 日本語都道府県値 | 変更しない。英語等は表示ラベルだけ変更 |
| 保存済み出生地 | 変更しない。移行不要 |
| 占星術YAML | 計算構造を変更しない |
| ACG GeoJSON | 成功応答を変更しない |
| APIエラー | `error_code` を追加。JAの既存 `error` 文は維持 |
| `/acg` 未指定言語 | 日本語を維持 |
| 既存JA/STORES URL | 維持 |
| Etsy URL | `lang=en&provider=etsy` を明示 |
| 既存ユーザーのZIP | 自動更新・削除しない |
| 旧配布物 | 残すが、再配布しない |
| DB | スキーマ変更・データ変更なし |

既存ユーザーへすでに渡したファイルは変化しない。変更が反映されるのは、将来このコードから生成されるページ・PDF・ZIP・販売素材である。

## 9. 生成物と配布管理

### 9.1 現行英語成果物とNeko言語別サンプル

| 生成物 | 出力先 | 生成方法 |
|---|---|---|
| Etsy自動アクセスZIP | `output/acg/current-en/nanamiastro-ACG-Premium-Bundle-Automatic-Access-EN-CURRENT.zip` | `python scripts/build_acg_distribution_artifacts.py` |
| Neko ACGサンプルZIP（英語スナップショット） | `output/acg/current-en/Chief-Editor-Neko-Personal-Edition-ACG-Sample-EN-CURRENT.zip` | 同上。同じ正規YAMLから言語別に生成する購入前サンプルであり、商品同梱物ではない |
| Personal EditionサンプルPDF | `output/pdf/personal-edition-acg-access-code-sample-en.pdf` | `python scripts/build_personal_edition_acg_sample_pdf.py` |
| EtsyアクセスガイドPDF | `output/pdf/nanami_acg_premium_bundle_etsy_en.pdf` | `python scripts/build_etsy_acg_access_pdf.py`。Museum表記0・1年Planner同梱を確認済み |
| FULL版コードPDF（JA/EN/ES/DE QA） | `output/pdf/personal-edition-full-current/` | `python scripts/build_personal_edition_full_sample_pdfs.py`。`python scripts/qa_personal_edition_full_artifacts.py` で4ページ・Museum表記0・Planner・リンクを検査 |
| locale別OGP | `static/ogp_acg_{en,es,de}.jpg` | `python scripts/build_acg_ogp.py` |
| Etsyメイン画像 | `output/etsy/acg-conversion/01-personalized-acg-premium-bundle.jpg` | `python scripts/build_etsy_acg_conversion_main.py` |
| ACGデモ動画 | `media/etsy-acg-demo/etsy_acg_demo_15s.mp4` | `python media/etsy-acg-demo/build_video.py --ffmpeg <path>` |
| Neko動画 | `output/video/etsy-acg/neko-chart-companion-demo-15s.mp4` | `python scripts/build_etsy_acg_neko_video.py` |

`output/` は `.gitignore` 対象である。ローカルに生成物が存在しても、コミット・別環境・デプロイ成果物へ自動的に含まれるとは限らない。配布前には生成スクリプトを正として再生成し、ファイル内容を確認する。

NekoのJA/EN/ES/DEページ、ZIP、Planner PDF、日別AIは、言語別にデータを保管する方式ではなく、同一の `data/demo/chief_editor_neko.yaml` から動的または再現可能に生成する。`current-en` のZIPは英語Etsy向けの確認用スナップショットであり、NekoがACG bundleへ同梱されることを意味しない。将来、ES/DE Listingを公開する場合も、正規データを複製せず、同じ生成経路とlocale辞書を使う。

`docs/ACG_DISTRIBUTION_ARTIFACTS.md` はMuseum表記を除去してQA済みのEtsyアクセスガイドPDFを現行候補として列挙する。旧 `Final` / `fixed` / 非 `CURRENT` 成果物は引き続き配布対象外とする。

### 9.2 確認時の成果物スナップショット

次のSHA-256は2026-08-27確認時点のローカル成果物に対するものであり、再生成すれば変わる可能性がある。

| 生成物 | SHA-256 |
|---|---|
| `static/ogp_acg_en.jpg` | `69DBC419314BAAD4DC2CCCFC6747BFD2CCC520044A0F90F49E65EBB592FE6EEC` |
| `static/ogp_acg_es.jpg` | `AAF28BC19C2899BC942F374155F53FA2CA1284616A9C01E0FAC64978C38DB33E` |
| `static/ogp_acg_de.jpg` | `738663878CBBE55F8E7AECB51FF4E3923B5537890E78AE756B13B646FAC29442` |
| `personal-edition-acg-access-code-sample-en.pdf` | `02096D29AD93585BB4602B8C10B1A187B8014219DF17BD1E341BB5F9223D460A` |
| `etsy_acg_demo_15s.mp4` | `CD73780905D55A29BEAD00E6E5A4C171F612DF4704346493266528E3A0ACD300` |
| Etsyメイン画像 | `5359F0C68FE4EA684BE3E6671D4FA84AF1B5741E84DC942D7724C2D82888313A` |
| Neko動画 | `56B102E64E82E1F9C5916B153F9206036222F0008443EFAD500B93F23256641B` |
| Etsy自動アクセスZIP | `A0B9EB2EE27865ECB8F13CC763EA730432B2A1AEBBA9375D046E45DFAB72847C` |
| Neko ACGサンプルZIP | `60193CB24393726F52239E5BD7879065BE6DCDF9D820093148A43226016D4A98` |

### 9.3 legacy/QA成果物

次の条件に該当するものは、確認なしに英語商品へアップロードしない。

- 名前に `Final` または `fixed` が含まれる。
- `output/` 内で `CURRENT` を含まない旧ACG ZIP。
- 旧Museum/start script方式を前提とするファイル。
- `EN` と書かれていても、可視日本語検出または目視確認を通していないもの。

削除は行わない。既存ユーザーの再現、QA、比較のため保存し、現行配布物とはディレクトリと名前で分離する。

## 10. テストと検証

### 10.1 自動テスト

実行条件:

```powershell
.venv\Scripts\python.exe -m pytest tests -q --basetemp .pytest_tmp\acg-i18n-full-20260827
```

初回監査時の結果:

- `568 passed`
- `140 subtests passed`
- 失敗なし

この結果はNekoのES/DEが英語fallbackだった時点の実装確認であり、今回確定したNeko 4言語完全辞書と販売リンク制御の合格証跡ではない。仕様承認後の追加実装後に全件を再実行し、下記のNeko受入条件を追加で満たす必要がある。

Neko日別AIの4言語化追加後（2026-08-27）の結果:

- `575 passed`
- `140 subtests passed`
- 失敗なし

この追加結果は、日別AIページのJA/EN/ES/DE表示、ES/DEエラー、言語別AI依頼文、非日本語版での可視日本語除外、日本語版の後方互換を含む。当時未完了だったNeko親ページとMuseum導線は、その後の追補実装で対応した。

Neko親ページと購入者用日別AIの追加実装後（2026-08-27）の結果:

- 関連テスト: `61 passed`
- 全テスト: `588 passed`
- `140 subtests passed`
- 失敗なし

この結果には、親ページの完全なJA/EN/ES/DE辞書、選択言語のリンク引継ぎ、canonical/OGPメタ情報、ES/DEの販売URL未設定時のリンク非表示、Museumカード非表示と無料Museum URL互換、商品構成表示、購入者用 `/chart/{token}/planner-ai` の4言語表示・拒否エラー、表示用日本語除外の非破壊性、秘密チャートtokenのログマスクが含まれる。

有料Personal EditionのMuseum非同梱化後（2026-08-28）の最新結果:

- 全テスト: `613 passed`
- `141 subtests passed`
- 失敗なし
- FULL版コードPDFのJA/EN/ES/DE各4ページについて、Museum表記0、Planner案内、発行リンク・QR、全ページレンダリングを確認

本番未デプロイ、最終販売URL未承認、legacy/QA成果物の最終配布分離未完了であるため、この結果だけで公開可とはしない。

### 10.2 可視日本語検出

`tests/test_acg_english_buyer_surfaces.py` で次を確認する。

- 英語Etsy開始ページの商品説明・特徴が英語である。
- 英語引換フォームとPersonal Editionフォームの可視都道府県が英字である。
- 内部 `value="東京都"` は互換性のため残る。
- 英語の出生時刻エラーが英語である。
- ACG APIが同一 `error_code` と言語別表示文を返す。
- 英語ACG地図・3D地球儀の可視HTMLに日本語がない。
- locale別OGPが1200×630で存在する。
- 未指定 `/acg` が日本語のままである。
- 英語の自動アクセスZIP、README、`START-ACG.html` の購入者可視部分に日本語がない。
- NekoのJA/EN/ES/DEページで、可視テキスト、カード、リンク先、`<html lang>`、title、description、OGP等のメタ情報が選択言語と一致する。
- Nekoの各言語ページに他言語の可視文言が混入せず、同一の正規サンプルデータを参照する。
- Neko日別AIの非日本語ページでは、画面とtextareaの双方に日本語がなく、`sign_ja` 等の日本語補助項目が購入者へ露出しない。日本語ページでは従来の日本語補助項目を維持する。

検出では `script` と `style` の内容を可視テキストから除外する。locale辞書、内部日本語値、許容済みの都市・地名データを誤検出しないためである。

### 10.3 素材確認

- OGP: EN/ES/DEを1200×630でレンダリングし目視確認。
- Etsyメイン画像: 英語UI、英語YAML例、Map表示を目視確認。
- ACG動画: 7枚の英語正規化ソースフレームを確認し、ffmpegで15秒MP4を再読込してデコードエラーがないことを確認。
- Neko動画: 英語Etsy向け3枚の英語正規化ソースフレームを確認し、ffmpegで再読込してデコードエラーがないことを確認。Webサンプルの4言語対応とは別の販売素材QAとして扱う。
- `personal-edition-acg-access-code-sample-en.pdf`: 4ページ、`START-ACG.html` 記載、旧 `Birth Chart Museum` 記載なし、抽出テキストに日本語なしを確認。Popplerで全4ページを画像化し目視確認。
- `nanami_acg_premium_bundle_etsy_en.pdf`: 2ページ、Museum表記0、1年Planner同梱、英語Etsy引換URLの可視URL・クリックリンク・QRを確認。
- `personal-edition-full-current/*.pdf`: JA/EN/ES/DE各4ページ、Museum表記0、1年Planner案内、各言語の発行URL・QRを抽出と全ページレンダリングで確認。
- ZIP: 現行英語README、開始ファイル、言語別リンク、ファイル名を確認。

画像・動画についてはOCRによる自動日本語検出を導入していない。今回の保証はソース生成処理、代表フレームの目視、動画デコード確認による。

### 10.4 Neko 4言語の受入テスト計画

`ja/en/es/de` をパラメータ化し、少なくとも次を各言語で検証する。

- ページ本体、ACGカード、ZIPカード、Plannerカード、日別AIカード、免責・補足文が対象言語で表示される。
- ACG、ZIP、Planner PDF、日別AI、言語切替のリンクへ正しい `lang` が引き継がれる。
- `<html lang>`、title、meta description、OGP title/description/image、canonicalまたは代替言語情報が仕様どおりである。
- 対象言語以外の可視テキストが混入しない。固有名詞、内部locale辞書、許容済み地名データは誤言語検出から除外する。
- JA/EN/ES/DEが同じ正規YAMLを使用し、言語ごとのYAML・テンプレート複製が存在しない。
- ENは英語Etsy販売リンク、JAは国内向け対応リンクを表示する。
- ES/DEは対応商品・Listingの公開設定が無効な間、販売リンク要素を表示しない。公開設定を有効にしたテスト条件では、同じ言語のListingだけへ接続する。
- Nekoが購入前サンプルであり、商品同梱物として表示されない。PlannerカードはACG bundle／FULL版に含まれる体験の例であり、Planner単体の販売カードや購入CTAになっていない。
- Museumカード・同梱表記・有料商品向け導線がなく、Museumの既存無料URL自体は回帰テストで維持される。
- `/demo/neko` の未指定・不正 `lang` は英語、配下の直リンク未指定・不正 `lang` は既存互換の日本語となる。Nekoページ内リンクは必ず有効な `lang` を持つ。

## 11. 既知の制約・残るリスク・追加実装事項

### 11.1 本番未検証

- 本番デプロイは実施していない。
- Cloud Run候補URL、本番URL、実際のEtsyリンク、実購入フローでは未検証である。
- 本番環境の環境変数、キャッシュ、CDN、DB、外部注文連携との組合せは未確認である。

### 11.2 確定商品仕様と現状差分

商品責任者の判断により、次を正とする。

- ACG bundleとPlanner単体は別SKU・別商品。
- ACG bundleには1年Plannerを含む。
- Planner単体にはACGを含まない。
- 2026-08-31のスペイン語・ドイツ語発売対象はFULL版（NP-WF）であり、FULL版には1年Plannerを含むがACGは含めない。
- Planner単体（NP-WBT）はFULL版との差を購入者へ明確に伝えにくいため休止を継続し、新規Listing、下書き、再公開を行わない。
- Birth Chart Museumは、ACG bundle、Planner単体、その他の有料商品には含めない。
- すべての有料商品の現行商品名、配布名、案内、購入導線、PDF、販売画像・動画からMuseum名称と同梱を示唆する表現を外す。
- Museum機能そのものは無料アプリとして維持し、既存の無料デモ・機能URLも互換維持する。
- 将来の無料アプリ一覧・ハブは別仕様・別作業とし、今回の実装・デプロイ範囲には含めない。

このうち、ACGへのPlanner同梱は商品コピーとEtsyメイン画像に反映済みである。Neko親ページについても、4言語辞書、Plannerの位置づけ、休止中NP-WBTへのCTA非表示、言語別販売リンク設定、ES/DE公開前非表示、メタ情報、Museumカード除去を実装・テスト済みである。Personal Editionの共通引換見出し、ACG/FULLダウンロード名、有料FULL版のPDF・README・ZIPからMuseum名称と同梱アプリを除去し、有料Personal Editionの結果画面から無料Museumへの積極的なダウンロード導線も除去した。無料アプリ本体と既存URLは維持する。残る差分は次のとおりである。

- 2026-08-31発売予定のES/DE FULL版Listing URLは未確定である。`NEKO_SHOP_URL_ES` / `NEKO_SHOP_URL_DE` は未設定のままにし、公開前はNekoから販売リンクを表示しない。
- ENの最終Etsy Listing URLとJAの国内向け販売先URLの承認が残る。ENは既存互換のEtsyショップURL、JAは未設定・非表示である。
- `scripts/build_etsy_acg_access_pdf.py` と生成済み `nanami_acg_premium_bundle_etsy_en.pdf` は修正・QA済み。現行候補は `docs/ACG_DISTRIBUTION_ARTIFACTS.md` に記載したものに限定する。
- `services/personal_edition_delivery.py`、`services/personal_edition_code_pdf.py` の有料FULL分岐はMuseum非同梱へ修正済み。無料Museum ZIP、無料デモ、既存URLは別分岐として維持する。
- 無料Museumデモの旧Personal Edition購入CTAは無料版ZIPへの案内へ変更済み。旧販売先環境変数は内部互換のため残るが、購入者画面では参照しない。
- 旧 `Final` / `fixed` / `BirthChartMuseum-*` 成果物が `output/` に残る。これらはlegacy/QAとして保持できるが、現行ACG商品へ配布してはならない。

FULL版の現行Etsy注文番号方式については、購入直後に配布するものは入力フォームへ案内するアクセスPDFであり、Personal EditionコードPDF／購入者別データZIPとは別経路である。JA/EN/ES/DEのアクセスPDFを `output/pdf/etsy-western-full/` に生成し、各言語の `/redeem/western-full?lang={lang}&provider=etsy` へ接続した。現行FULL ListingにREADMEを直接添付する設計ではないが、将来またはサポート用途でPersonal Edition経路を使ってもMuseumを同梱しないよう共通生成コードを修正済みである。

ES/DE FULL版のPlanner販売画像は、言語だけを画像編集したモックではなく、正規Nekoサンプルデータから実生成した各言語の432ページPlanner PDFを撮影素材として作る。DE版は `output/etsy/western-full-de/planner-sample/` の実PDFと `scripts/build_etsy_wf_german_images.py` を生成元とし、7枚を `output/etsy/western-full-de/listing-images/` に出力する。画像内では31日トランジット、12か月Planner、NP-WF-DEを明示し、ACGとMuseumを同梱物として表示しない。

#### 仕様承認後の実装予定

1. **完了:** `routes.py` のACG Personal Editionダウンロード名を `nanamiastro-ACG-Premium-Bundle-Personal-Edition-{LANG}.zip` へ変更し、FULL版も `nanamiastro-FULL-Personal-Edition-{LANG}.zip` とした。
2. **完了:** `scripts/build_etsy_acg_access_pdf.py` のMuseum項目を削除し、1年Planner同梱を維持したPDFを再生成した。
3. **完了:** `docs/ACG_DISTRIBUTION_ARTIFACTS.md` はMuseum表記のない再生成済みPDFだけを現行配布候補とする。
4. **完了:** `services/neko_demo_locales.py` に完全なES/DE辞書を追加し、JA/EN/ES/DEの同一キー集合をテストした。正規YAMLやテンプレートは複製していない。
5. **完了:** `templates/neko_demo.html` と関連ルートで4言語の可視テキスト、カード、リンク、title、description、canonical、OGPを選択言語へ一致させた。
6. **完了:** NekoページへACG BundleとFULL版のPlanner同梱、NP-WBT休止、Nekoが購入前サンプルで商品同梱物ではないことを4言語で追加した。
7. **実装完了・URL承認待ち:** Neko販売リンクを言語別環境変数へ分離し、未設定言語では要素を非表示にした。ES/DE URLはListing公開時まで未設定とする。NP-WBTへの販売CTAは表示しない。
8. **完了:** Nekoページ・ZIP・Planner・日別AI・ACGリンクの `lang` 維持とfallbackをテストした。
9. **完了:** Neko有料商品サンプルからMuseumプレビューと導線を除去し、無料Museumの既存URL回帰テストを維持した。
10. ACG開始ページ、販売画像、PDF、README、ZIP名、ダウンロードヘッダーにMuseum名称がないことを自動テストする。
11. FULL版の開始ページ、販売素材、PDF、READMEで「1年Planner同梱・ACG非同梱」が明確であること、および休止中のPlanner単体（NP-WBT）が販売中・発売予定として露出しないことをテストする。
12. その他の有料商品についても、商品名、販売説明・画像、PDF、配布ファイル名、購入導線を横断監査し、Museum同梱または付属を示唆する表現を除去する。
13. **完了:** `services/personal_edition_delivery.py` と `services/personal_edition_code_pdf.py` の有料商品分岐からMuseum文言・アプリ同梱を切り離し、FULL版データZIPと4言語PDFを再生成した。無料Museum生成分岐は保持した。
14. **完了（ローカル）:** `/birth-chart-museum`、`/birth-chart-museum/demo`、無料ZIPダウンロードの互換を回帰テストし、デモ内の旧購入CTAだけを無料版ダウンロードへ変更した。本番確認は未実施。
15. `output/` の旧Museum名成果物は削除せずlegacy/QAのまま隔離し、新しい現行成果物を再生成する。物理削除は別承認とする。
16. 将来の無料アプリ一覧・ハブは別仕様として起票し、今回のACG変更には含めない。
17. 上記変更後に全テスト、4言語の誤言語検出、リンク・カード・メタ情報、PDF抽出、ZIP内容、画像・動画を再検証する。
18. **完了（ローカル）:** 有料Personal Editionのチャート結果画面から無料Museumダウンロードボタンを除去し、無料Museumの独立デモ・ZIP URLの回帰テストは維持した。

### 11.3 ES/DEの完全性

- ACG地図、入力フォーム、主要エラーにはES/DE辞書がある。
- 3D地球儀は一部だけES/DEで、残りは英語fallbackである。
- Neko親ページと日別AIのES/DE完全辞書は実装済みであり、英語全文fallbackは使用しない。
- ES/DEの用語・導線・商品構成は内部QAを行う。外部の職業翻訳者／ネイティブ校正は推奨する編集品質確認とし、自動的な技術的公開禁止条件にはしない。公開責任者が現行文面を承認するか、外部校正へ回すかを公開前に決定する。

### 11.4 APIエラー分類

内部日本語例外文の部分一致で公開 `error_code` を決める箇所がある。内部文言変更時に分類が劣化するリスクがある。今回、計算コアへ手を入れない方針を優先した結果である。

### 11.5 古いQA成果物とpytest収集

リポジトリ直下で単に `pytest -q` を実行すると、`output/` と `tmp/` に残る過去のpytest複製物や依存物まで収集し、重複テスト・権限エラーが発生する。正規テストは `pytest tests -q` として対象を限定し、書込み可能な `--basetemp` を指定する。

旧QA成果物は今回削除していない。将来、保存方針を決めた上で、pytest設定の `testpaths = tests` や `norecursedirs = output tmp work` を検討できるが、本仕様作成時点ではコード変更しない。

### 11.6 未分離の作業ツリー

確認時点で多数の未コミット変更があり、ACG対応と他機能が同居している。現状のままではデプロイガードが停止するため、誤って本番へ出る可能性は低い。一方で、レビュー時に無関係な変更を混ぜる危険があるため、専用コミットまたは専用ブランチへ差分を分離する必要がある。

### 11.7 ロールバック手段

現行 `promote_candidate.ps1` は「現在のpush済みコミットに対応するcandidate」だけを本番へ昇格するガードであり、任意の旧revisionへ戻す汎用ロールバックスクリプトではない。本番昇格前に、直前revisionへ戻す承認済み手順を用意し、実行権限と担当者を確認する必要がある。

## 12. デプロイ前チェックリストと承認ゲート

以下は順序どおりに実施する。1項目でも未完了なら次へ進まない。

### Gate 1: 仕様・商品判断

- [ ] 本仕様書をユーザーが承認した。
- [x] ACG bundleには1年Plannerを含むと決定した。
- [x] Planner単体にはACGを含めないと決定した。
- [x] 2026-08-31のスペイン語・ドイツ語発売対象をFULL版（NP-WF）と決定した。
- [x] Planner単体（NP-WBT）は休止を継続し、新規Listing、下書き、再公開を行わないと決定した。
- [x] MuseumをACG bundle、Planner単体、その他すべての有料商品から除外すると決定した。
- [x] 現行ACGダウンロードファイル名から旧Museum表記を外すと決定した。
- [x] Museum機能そのものと既存無料デモ・機能URLは維持すると決定した。
- [x] 将来の無料アプリ一覧・ハブは別仕様・別作業と決定した。
- [x] Nekoサンプルを1つの正規データ・共通テンプレート・locale辞書でJA/EN/ES/DE対応すると決定した。
- [x] Etsyでは英語Neko、国内では日本語Nekoを使い、ES/DE販売リンクは対応Listing公開まで有効化しないと決定した。
- [x] Nekoサンプルは購入前の補助サンプルであり商品同梱物ではないと決定した。
- [ ] NekoのEN用Etsy販売先URLとJA用国内販売先URLを確定した。
- [ ] Etsyで実際に配布するZIP、PDF、画像、動画を確定した。

### Gate 2: 第三者レビュー

- [x] Claude Codeによる読み取り専用の第三者レビューを実施し、「条件付き承認」の報告を受けた。
- [ ] 表示層以外のコア変更が混入していないことを確認した。
- [ ] JA/STORES、EN/Etsy、ES、DEのfallbackと互換性を確認した。
- [ ] Nekoの正規データ一元化、4言語辞書、販売リンク公開条件が設計どおりであることを確認した。
- [ ] セキュリティ、個人情報、注文検証への影響がないことを確認した。

### Gate 3: 差分分離と再検証

- [ ] ACG対象差分だけを専用コミットへ分離した。
- [ ] `git status --short` が空である。
- [ ] upstreamへpush済みで、HEADとupstreamが一致している。
- [x] 2026-08-28に `pytest tests -q --ignore=tests/test_multilingual_review_fixes.py` を書込み可能な `--basetemp` で再実行し、`606 passed + 149 subtests passed` を確認した。除外ファイルは現環境に `pypdf` がないためで、別途PDF QAゲートとして残す。
- [ ] 英語販売成果物を再生成し、ハッシュ・寸法・内容を再確認した。
- [ ] ACG側の全表面でPlanner同梱が明確で、Museum表記がないことを確認した。
- [ ] FULL版の全表面で1年Planner同梱・ACG非同梱が明確であることを確認した。
- [ ] 休止中のPlanner単体（NP-WBT）が販売中・発売予定として表示されず、販売CTAも存在しないことを確認した。
- [ ] その他の有料商品の全表面でもMuseum同梱を示す表記・導線がないことを確認した。
- [ ] Museumの既存無料デモ・機能URLの互換性を確認した。
- [ ] NekoのJA/EN/ES/DEで、可視文言、リンク、カード、メタ情報、誤言語混入を検証した。
- [ ] NekoのES/DE販売リンクが対応Listing公開前は露出せず、EN/JAは正しい販売先へ接続することを確認した。
- [ ] Nekoが商品同梱物と誤認されないことを4言語で確認した。
- [ ] 旧legacy/QA成果物を配布対象から外した。

### Gate 4: ロールバック準備

- [ ] 現在本番で100%配信中のrevision名を記録した。
- [ ] 直前revisionへ戻す手順を文書化し、実行可能性を確認した。
- [ ] DB変更がないことを再確認した。
- [ ] ロールバック後も、切替中に消費された注文状態は自動では戻らないことを理解した。

### Gate 5: 候補環境

- [ ] ユーザーが候補版作成を明示承認した。
- [ ] `scripts/deploy_candidate.ps1` だけを使い、0%トラフィックで候補版を作成した。
- [ ] 候補URLで以下をスモークテストした。
  - [ ] `/start/acg-bundle?lang=en&provider=etsy`
  - [ ] `/redeem/acg-bundle?lang=en&provider=etsy`
  - [ ] `/personal-edition/activate?lang=en`
  - [ ] `/acg?lang=en`
  - [ ] `/acg/globe-demo?lang=en`
  - [ ] `/demo/neko?lang=ja`
  - [ ] `/demo/neko?lang=en`
  - [ ] `/demo/neko?lang=es`
  - [ ] `/demo/neko?lang=de`
  - [ ] `/demo/neko` の既定英語と、配下直リンクの既存fallback日本語
  - [ ] EN/JAのNeko販売リンク先と、FULL版Listing公開前のES/DE販売リンク非露出
  - [ ] `/start/western-full?lang=es&provider=etsy`
  - [ ] `/redeem/western-full?lang=es&provider=etsy`
  - [ ] `/start/western-full?lang=de&provider=etsy`
  - [ ] `/redeem/western-full?lang=de&provider=etsy`
  - [ ] 休止中のNP-WBTへ購入導線が出ないこと
  - [ ] `/api/acg/mundane?...&lang=en`
  - [ ] `/api/acg/personal?lang=en`
  - [ ] JA未指定/STORES導線
  - [ ] ES/DEの主要表示とfallback
- [ ] テスト専用データだけを使い、実顧客の注文番号・出生情報を使用していない。

### Gate 6: 本番昇格

- [ ] 候補版のrevisionとスモーク結果をユーザーへ提示した。
- [ ] ユーザーがそのターンで本番昇格を明示承認した。
- [ ] 承認対象revisionだけを `scripts/promote_candidate.ps1` で昇格した。
- [ ] 本番URLで同じスモークテストを行った。

**現在は第三者レビューの条件付き承認を受け、Gate 3へ進む前の仕様・差分整理段階である。候補版作成を含む以後の操作は禁止されている。**

## 13. ロールバック方針

### 13.1 候補版が0%トラフィックの場合

- 本番トラフィックは変更しない。
- 候補版の不具合を修正し、新しい候補版を作る。
- 問題のある候補を本番へ昇格しない。

### 13.2 本番昇格後の場合

1. 新規購入・引換への影響を確認する。
2. 必要なら新revisionへのトラフィックを停止し、記録済みの直前revisionへ100%戻す。
3. 現行スクリプトは汎用rollbackに対応しないため、事前にレビュー・承認したロールバック手順だけを使う。
4. アプリのロールバックとDBデータ修正を分ける。DBを直接変更しない。
5. 切替中に使用済みとなった注文や生成済みURLは、アプリを戻しても自動で巻き戻らない。個別対応が必要な場合は別承認を取る。

今回の変更にはDBマイグレーションがないため、基本の復旧単位はCloud Run revisionである。

## 14. 本番監視項目

次は本番昇格が承認された将来時点の監視案であり、現在監視を開始したという意味ではない。

- `/health` の成功率と応答時間
- `/start/acg-bundle`、`/redeem/acg-bundle`、`/personal-edition/activate` の4xx/5xx率
- `/api/acg/mundane`、`/api/acg/personal` の5xx率、`error_code` 別件数
- Etsy注文確認の成功・失敗・再試行率
- ZIP/PDF生成失敗、生成時間、ダウンロード失敗
- 英語画面に日本語が見えるという問い合わせ
- 注文番号が使用済みになったが成果物を取得できない問い合わせ
- OGP、画像、動画、ZIPの404
- GSI/OpenStreetMap等、外部タイル・地理検索依存の障害
- JA/STORES導線の利用率・エラー率がリリース前から悪化していないこと

ログへ注文番号、出生情報、YAML本文などの機密データを追加してはならない。

## 15. 差分の区分

### 15.1 今回のACG仕様に直接対応する新規ファイル

- `services/acg_locales.py`
- `services/acg_globe_locales.py`
- `services/buyer_input_locales.py`
- `services/neko_demo_locales.py`
- `scripts/build_acg_distribution_artifacts.py`
- `scripts/build_acg_ogp.py`
- `scripts/build_personal_edition_acg_sample_pdf.py`
- `docs/ACG_DISTRIBUTION_ARTIFACTS.md`
- `static/ogp_acg_en.jpg`
- `static/ogp_acg_es.jpg`
- `static/ogp_acg_de.jpg`
- `media/etsy-acg-demo/frames-en/`
- `tests/test_acg_english_buyer_surfaces.py`

### 15.2 今回のACG対応で変更した、またはACG関連hunkを含む既存ファイル

- `routes.py`
- `services/birth_time.py`
- `services/site_locales.py`
- `templates/acg_map.html`
- `templates/acg_globe_demo.html`
- `templates/redeem_western_full.html`
- `templates/personal_edition_activate.html`
- `templates/neko_demo.html`
- `media/etsy-acg-demo/build_video.py`
- `media/etsy-acg-demo/etsy_acg_demo_15s.mp4`
- `scripts/build_etsy_acg_conversion_main.py`
- `scripts/build_etsy_acg_neko_video.py`
- `output/pdf/personal-edition-acg-access-code-sample-en.pdf`
- `tests/test_acg_map_template.py`
- `tests/test_neko_demo.py`

これらの一部は作業開始時点ですでに変更されていたため、ファイル全体を今回変更として扱ってはならない。第三者レビューでは、ACGに関係するhunkだけを抽出して確認する。

### 15.3 関連するが、既存変更と混在しており今回差分として一括評価できない依存ファイル

- `services/common_access_package.py`
- `services/geocoding_service.py`
- `services/personal_edition_code_pdf.py`
- `services/personal_edition_delivery.py`
- `services/prompt_builder.py`
- `services/yaml_exporter.py`
- `static/acg_interpretations_es.json`
- `static/acg_interpretations_de.json`

今回の生成・テストはこれらを利用しているが、現在の未コミット差分全体をACG英語化だけの成果とはみなさない。

### 15.4 明確に今回のACG仕様レビュー対象外とする既存ユーザー変更

- `love_edition/`
- `services/addon_prompt_locales.py`
- `services/companion_locales.py`
- `services/prompt_locales.py`
- `services/planner/` 配下の変更
- `services/planner_ai.py`
- `services/planner_delivery.py`
- `services/planner_export.py`
- `services/transit_yaml.py`
- ACG以外のstart/redeem/addon/chart/plannerテンプレート変更
- ACG以外のplanner、holiday、love edition等のテスト変更

これらは削除・上書き・巻き戻しを行わず、ACG専用コミットへ混ぜない。

## 16. ユーザー確認項目

技術詳細をすべて読まなくても、確定事項と残る承認ゲートを次の欄で確認できる。

- [x] Etsy英語導線は英語表示、日本語/STORES導線は従来どおり日本語とする。
- [x] 地図・都市検索データ内の日本語地名は許容する。
- [x] ACG bundleとPlanner単体は別SKU・別商品とする。
- [x] ACG bundleには1年Plannerを含める。
- [x] Planner単体にはACGを含めない。
- [x] 2026-08-31のスペイン語・ドイツ語発売対象は、1年Plannerを含むFULL版（NP-WF）とする。
- [x] Planner単体（NP-WBT）はFULL版との差を伝えにくいため休止を継続し、新規Listing、下書き、再公開を行わない。
- [x] NekoのPlanner表示はACG bundle／FULL版に含まれる体験のサンプルとして扱い、Planner単体の販売カード・購入CTAとして扱わない。
- [x] Nekoサンプルは1つの正規データと共通テンプレートをlocale辞書で切り替え、JA/EN/ES/DEの4言語に対応する。
- [x] Etsyでは `lang=en` の英語Nekoを主要サンプルにし、国内向けは `lang=ja` を使う。
- [x] ES/DEのNeko機能は実装・テストするが、FULL版Listing公開前は販売リンクを露出せず、公開後は同じ言語のFULL版へ接続する。
- [x] Nekoは購入前体験を示す補助サンプルであり、商品同梱物ではない。
- [x] 新しいNeko対応言語は、サンプルデータの複製ではなく辞書とテストの追加で拡張する。
- [x] ACG bundle、Planner単体、その他すべての有料商品からBirth Chart Museumを外す。
- [x] 有料商品の同梱物、商品名、販売説明・画像、PDF、配布ファイル名、購入導線でMuseumを含むように見せない。
- [x] 現行ACGダウンロード名から旧 `BirthChartMuseum` 表記を外す。
- [x] Museum機能と既存の無料デモ・機能URLは、無料アプリとして維持する。
- [x] 将来の「無料で使えるアプリ一覧」またはハブは別仕様・別作業とし、今回は実装しない。
- [x] JA/EN/ES/DEのFULL版EtsyアクセスPDFを言語別に用意し、該当言語の引換URLへ接続する。
- [x] ES/DEの内部翻訳QAを行い、外部ネイティブ校正は公開責任者が必要性を判断する編集ゲートとする。
- [x] 旧 `Final` / `fixed` / 非 `CURRENT` 成果物を英語商品へ使わない。
- [x] 第三者レビューは、秘密情報と無関係な変更を除外して今回のACG差分に限定して実施した。
- [x] 本仕様を承認しても、本番デプロイは別の明示承認があるまで行わない。
- [ ] NekoのEN用Etsy販売先URLとJA用国内販売先URLを承認する。
- [ ] Etsyで実際に配布するZIP、PDF、画像、動画の最終セットを承認する。
- [ ] 本仕様書の内容を最終承認する。
