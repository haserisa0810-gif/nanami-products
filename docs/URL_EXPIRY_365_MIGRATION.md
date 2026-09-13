# 発行URLの365日化・既存データ移行手順

- 決定日: 2026-09-13（RETENTION-01 / PLANNER-01）。新規・発行済みの通常URLが対象。
- 状態: ローカル実装・全回帰テスト・隔離PostgreSQLでの移行/復旧検証済み。本番コード切替・期限UPDATE・復旧操作は未実施。
- リリース範囲の仕様・運用: [配布物仕様](ui-ux/07_DELIVERY_ARTIFACTS.md)、[本番安全](PRODUCTION_SAFETY.md)、[AGENTS.md](../AGENTS.md)。
- 実行ファイル: [migrate_chart_expiry_365.py](../scripts/migrate_chart_expiry_365.py)。`init_db`は呼ばない。

## 対象と期限の計算

通常の新規URLは元の発行日時から365日（365×24時間）。MCP、WebのNULL補完、DB保存既定値、
Add-onも同じ定数を使う。明示期限があるURLの閲覧はその期限を優先するため、コード切替だけでは
旧90日の明示期限は延びない。既存データには次の移行を行う。

| 保存状態 | 移行時の扱い |
|---|---|
| `charts`または`transit_addon_links`だけに存在 | `max(created_at + 365日, 既存expires_at)`。NULLは発行日時で補完 |
| 両表に同じtokenが存在 | 両表の最も早い`created_at + 365日`と、両側の既存明示期限の最大値を両表へ設定 |
| `charts.options.expires_policy = no_expiry` | 同じtokenの両表を除外。期限のある行が併存すれば異常件数として表示 |
| 90日で失効したが新しい期限前 | URLは再び利用できる。移行日から365日にはしない |
| 既存期限が365日より長い | 短縮しない。画面の具体的な期限を優先し、案内は「通常365日」とする |
| 作成日時欠損・不正日時・重複行 | 不明な期限を推測せず適用を停止 |
| 削除済み生成データ | 復元しない。注文や使用済み枠を再発行可能へ戻さない |

対象は両表の`expires_at`のみ。注文・発行権・引換記録・有効化コード・APIキー・API snapshots、
GCSのオブジェクトとライフサイクルは変更しない。期限切れ削除と週次運用は後続段階。

## 本番の事前集計（2026-09-13 17:51 JST）

chiefがユーザーの読取調査依頼の範囲で独立したSQL集計を行った。DBは
`transaction_read_only=on` / `repeatable read`、時点は2026-09-13T08:51:24.420944Z。
当時の本番リビジョンは`nanami-products-00554-lag`。tokenや顧客データは取得せず、件数だけを返した。

| 集計 | 件数 |
|---|---:|
| `charts` / `transit_addon_links` | 290 / 48行 |
| 重複を除いたURL / 通常URL / 無期限URL | 302 / 281 / 21 |
| 変更予定の`charts` / Add-on | 237 / 48行（合計285行） |
| 通常URLの期限NULL補完 | 85行 |
| 再び有効になるURL | 182 |
| 移行後も失効したままのURL | 0 |
| 365日より長い既存期限を維持するURL | 32 |
| 両表の作成日時差 / 期限差 | 0 / 0 |
| 作成日時欠損 / 無期限と明示期限の併存 | 0 / 0 |

これは同じ期限ポリシーによる`WITH`＋`SELECT`の独立集計であり、この移行スクリプトの実DB実行結果ではない。
集計は[Neon HTTPSのread-only batch](https://github.com/neondatabase/serverless/blob/main/src/httpQuery.ts)を利用した。
以前のTCP接続はタイムアウトしており、psycopg2を使う本スクリプトの本番接続・UPDATE・復旧SQLは未検証。
承認された接続可能な管理環境で実行する。適用時には発行件数が変わり得るため、上記件数を固定条件にはしない。

## リリースの順序

1. 対象変更をレビューし、隔離した非本番DBでdry run・apply・restoreを検証する。実DB未検証を解消してから本番へ進む。
2. 所定の承認後、必要な変更をcommit・pushし、cleanな状態から`deploy_candidate.ps1`で0%候補版を作る。候補の期限・ZIP・Plannerを確認する。
3. 本番切替の別承認後、`promote_candidate.ps1`で365日を新規発行するコードへ切り替える。旧リビジョンの処理中リクエストが終了したことを確認する。
4. 本番DB移行の別承認を受け、下記dry runで今回の対象件数・欠損・無期限を再確認する。
5. 保護した復旧台帳の保存先を指定してapplyする。失敗したら復旧台帳と件数を確認するまで再試行しない。
6. apply直後の独立dry runで`changed_rows=0`、無期限件数・長い既存期限の維持を確認する。旧コードによる遅延保存が疑われる場合は終了確認後に再集計し、残件があれば新しい台帳で再適用する。
7. 新規発行と延長した旧URLを確認し、候補/本番リビジョン・実行時刻・集計結果を記録する。個別URL、token、顧客情報をログへ残さない。
8. 配布ガイドを再生成してPDF全ページの表示・リンク・QRを確認し、外部販売ページ/配布PDFの差替えを別途行う。

既存移行を旧90日コード稼働中に先に済ませると、その後の新規発行が90日のまま残り得るため、
新規発行コードを先に切り替える。切替直後から移行完了までは、旧明示期限が一時的に残る。
NULLの旧期限はコード切替時点で365日補完になる。**延長・確認の完了前にcleanupを実行しない。**
本作業でcleanupの不整合、30日猶予、週次ジョブを実装したことにはしない。

## 実行例と安全機構

以下は承認後の管理者用例。資格情報をコマンドや`.env`に記載せず、承認された環境で`DATABASE_URL`を設定する。
スクリプトはenvファイルを読み込まない。接続先を秘密値を表示せず確認できなければ接続しない。

```powershell
# 既定: SELECTのみ。repeatable read・read-only transaction、集計のみ出力。
python -B scripts/migrate_chart_expiry_365.py

# 本番DBの対象・影響・復旧方法について別の承認後にだけ実行。
# 事前に管理者専用の非同期フォルダを用意し、毎回未使用の台帳名を指定する。
python -B scripts/migrate_chart_expiry_365.py --apply --confirm EXTEND_ISSUED_URLS_TO_365_DAYS --backup C:/Users/haser/work/staging/private-expiry-recovery/expiry-before-APPROVED-RUN.json
```

- dry runはSELECTだけで終了時rollback。UPDATEしてrollbackする方式ではない。対象行やURLを出力しない。
- apply/restoreはtransaction advisory lockと両表の行ロックを使い、全件を同じトランザクションで更新する。旧期限と作成日時の一致をUPDATE条件にも入れる。
- DB接続10秒、SQL60秒、行ロック待機5秒、Windows ACL処理15秒の上限を設ける。途中例外でrollbackする。
- apply前に旧期限（NULL含む）・新期限・元の作成日時・token・表名、および同tokenの両表の更新後状態を復旧台帳へ書き、flush/fsyncしてからUPDATEする。未変更の相方と相方が存在しない状態も保全し、台帳の上書きは拒否する。
- 更新後に同じトランザクションで再集計し、残り変更候補0を確認してcommit。2回目に変更対象がなければUPDATEも台帳作成もしない。
- apply/restore時の全行ロックは現在の小規模DB向け。件数が大きくなった場合は実行窓と処理時間を見直す。新しい行の追加まではロックしないため、切替と独立再集計が必要。
- 無期限行に別表の明示期限がある等の異常が出た場合は、そのURLを除外して集計する。運用では異常の扱いを確認してからapplyへ進む。

## 復旧台帳と戻し方

台帳にはURLアクセスに使えるtokenが含まれる。秘密として扱い、チャット、メール、Issue、Git、クラウド同期へ
添付・貼付しない。保存先は**管理者専用のフォルダで、OneDriveおよび全リポジトリの外**を選ぶ。
スクリプトは既知のOneDriveルートと本リポジトリ内への保存を拒否する。他リポジトリへの配置は管理者が避ける。
ファイルは排他的に空で作成し、Unixでは0600、Windowsでは継承を切った実行ユーザーのみのDACLを設定してから
内容を書き込む。権限設定失敗時は空ファイルを残してDBをrollbackする。空ファイルを成功した台帳と扱わない。
保存に失敗した場合も、既存台帳を上書きせず、状態を確認して新しいパスを使う。

```powershell
# 復旧操作について承認後、同じ接続先・同じ台帳で実行する。
python -B scripts/migrate_chart_expiry_365.py --restore C:/Users/haser/work/staging/private-expiry-recovery/expiry-before-APPROVED-RUN.json --confirm RESTORE_ISSUED_URL_EXPIRIES
```

restoreはDB接続先のhost/port/dbnameのハッシュと台帳のチェックサムを確認し、対象行の作成日時と現在の期限が
台帳の更新後の値に一致する場合だけ旧期限へ戻す。新しい無期限ポリシー、別の期限変更、削除、同tokenの再作成、
別DB、台帳の破損を検出した場合は全体を停止する。接続先のホスト名が変わった場合も自動でガードを外さない。
同tokenの未変更だった相方も比較し、移行後の相方追加・削除・期限変更があれば復旧を停止する。
全表のINSERTを止めるテーブルロックは使わないため、復旧の実行中は同tokenを追加する手動操作や
別の移行処理を停止しておく。トランザクション開始後の新しい相方のINSERTは、同じsnapshotからは検出できない。
チェックサムは偶発的破損の検出用であり、台帳のアクセス制御の代わりではない。

通信がcommit直後に切れると、成功表示がなくてもDB側がcommit済みの可能性がある。台帳を保持し、別承認の読取確認で
現在値を確認してから再試行/復旧を判断する。apply前に残った台帳は「commit済み」の証明にはならない。
restoreは繰返し強制適用しない。既に旧値へ戻った行があれば現在値不一致で停止する。

**DBだけの復旧ではURLの挙動を完全には戻せない。** NULLへ戻した旧行は365日コードでは365日補完される。
90日の挙動へ戻す必要がある場合はコードの切戻しも別途判断する。新コード稼働中に発行したURLはこの台帳の対象外であり、
それらまで一律に短縮しない。台帳は復旧可能期間中、管理者の保護された保管先で維持し、必要終了後に管理者が安全に廃棄する。

## 検証と未実施事項

- [移行テスト](../tests/test_migrate_chart_expiry_365.py): 合成行・偽cursorでread-only、両表整合、延長/NULL/無期限/長期限、二回目0件、途中rollback、復旧と変更検知、ACL失敗時の空台帳を検証。
- [365日回帰](../tests/test_url_expiry_365.py): Web/MCP/DB保存の基準、Add-onと365日の境界、4言語ZIP、期限内のPlanner繰返し・月更新・無期限を検証。
- DB/外部通信をimport前から遮断してローカル検証。Windows asyncioの標準socketpair内部IPCだけを許可し、DB接続・通常のsocket接続は拒否。
- リリース基点は現行本番の`a314ca69fe`（購入者エラーの多言語化）。この基点に365日差分だけを適用した全suite: **690 passed、149 subtests passed**（2026-09-13）。既存作業ツリーの未公開変更は含めない。
- 新しく初期化したlocalhost専用PostgreSQL 17.11で、合成データを使った実SQLの8項目がPASS。read-onlyの不変、2表目の失敗で全体rollback、advisory lock競合の拒否、行ロックtimeout、期限だけのapply、二回目0件、未変更の相方が変わった際のrestore拒否、NULLを含む完全復旧を確認。試験用サーバーは停止済み。
- 実PostgreSQL試験で使用した移行コードとリリース版は同一。本番DBの接続資格情報は使用していない。
- commit直後の通信切断試験、本番接続/apply/restore、デプロイ後の候補確認、配布PDFの実ファイル再生成/全ページ検査、外部販売ページとPDF差替えは未実施。候補版の確認後、本番切替と既存期限移行は別の承認で進める。
