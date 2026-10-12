# 注文処理：隔離PostgreSQL・アプリSMTP検証（2026-10-11）

商品コード・注文処理の公開判断は**保留を継続**する。実PostgreSQLの13件と、アプリから隔離TLS SMTPサーバーへ送信する4件は成功した。外部メールサーバーを経由した運営テスト宛先への実配信は、SMTP設定が未提供のため未実施。占術商品の計算精度・海外販売の判断とは分ける。

## 実施結果と限界

| 検証 | 結果 | 範囲 |
|---|---|---|
| 隔離PostgreSQL：通知再送・同時発行・未知コード・ロールバック等 | PASS：従来7件 | 実DB・架空Payhip通知。実販売サイトとの照合ではない |
| 隔離PostgreSQL：管理者承認・古い版・同時承認・原本保護等 | PASS：追加6件 | 実トランザクション・実ロック。ブラウザ操作は未実施 |
| アプリSMTP：SSL／STARTTLS、認証、451失敗から再送、DB保存 | PASS：2件 | `smtplib`をモックせず、TLS SMTPサーバーと実DBを使用 |
| アプリSMTP：4並列の通知処理 | PASS：2件 | SSL／STARTTLS各1件。通知1通・試行1回を確認 |
| 修正後の通常の全体回帰 | PASS：2179件、161 subtests | 17 SKIP、5653 warnings、118.67秒。実DB／SMTPの17件はこの実行では未設定でSKIP |
| 外部メールサーバー経由での運営テスト宛先への到達 | 未実施 | SMTPホスト・送信元・認証情報が未設定 |
| 以前のGmail到達 | この検証の対象外 | Gmail連携による送信は、アプリSMTPの実配信として数えない |
| 本番DB・購入履歴・発行済み原本・本番メール | 対象外 | 接続・書き込み・メール送信を行わない |

通知先は運営者だけであり、購入者へのメール送信はこの機能の対象ではない。SMTP検証の宛先には予約済みの `.invalid` ドメインを使用し、外部配送を行わず試験サーバー内で捕捉した。

## 実DBで発見した不整合と修正

初回の13件は**8成功・5失敗**。`PURCHASE_EVIDENCE_REQUIRED`により、正常な再通知の候補を管理者が承認できなかった。通知解析の`purchase_evidence`は「確認した購入明細フィールド名のリスト」だが、`save_candidate()`は`is True`で比較しており、正常なリストを未検証の`false`として保存していた。

`services/order_holds.py`の保存境界だけを修正し、非空のフィールド名リストを検証済みの真偽値へ変換する。既存の真偽値入力も維持し、文字列・数値・空リスト・不正なリスト要素は検証済みにしない。承認時の商品・SKU・数量・入金・保留理由・既存権限・確認版の検査は維持した。新機能を追加したものではない。

正常／未知コードについてSTORES・Payhip・Etsyの実解析処理から保存・承認検査まで通す6件、不正な根拠値を拒否する7件を追加。承認の限定回帰は39成功。修正後の実DB13件は全て成功した。初回の失敗を消さず、以下に保存した。

- [初回ログ](postgres-initial-failures.txt)／[初回JUnit](postgres-initial-failures.xml)
- [修正後：実DB13件＋TLS SMTP4件のログ](postgres-smtp-results.txt)／[JUnit](postgres-smtp-results.xml)
- [機械可読の検証記録](evidence.json)

## 隔離環境

Windowsの実行制御を変更せず、利用可能なCloud Shellの既設PostgreSQL 16.15を使用した。通常のクラウドDBへ接続せず、`/tmp/np-order-verify-20261011/pgdata`に新しい一時クラスタと専用DBを作成し、ランダムポートの`127.0.0.1`だけで待ち受けた。SCRAM認証の使い捨て秘密値は遠隔の権限制限ファイルで保持し、成果物へ保存していない。

転送したのは関連Pythonモジュール・試験コードだけで、`.env`、本番接続文字列、購入者データを転送していない。試験プロセスから`DATABASE_URL`と運用メール環境変数を除外し、専用の`TEST_ORDER_DATABASE_URL`を明示。各テストはUUID付き専用スキーマを作成・終了時に削除する。Cloud ShellへのSSHでは`--authorize-session`を使用せず、WindowsのGCP認証を試験プロセスへ転送していない。

使用環境：Python 3.12、PostgreSQL 16.15、psycopg2-binary 2.9.13、pytest 9.1.1、aiosmtpd 1.4.6。SQL実行ではアプリの本番スキーマを使用しない。

終了時に試験スキーマが0件であることを確認し、専用PostgreSQLを停止、使い捨ての認証ファイルを削除した。[終了記録](cleanup.json)。停止した一時クラスタと秘密値を含まない検証資料はCloud Shellの`/tmp`に残し、他の環境やファイルは削除していない。

SMTPのテスト証明書を試験プロセスだけで信頼し、アプリ側の証明書検証を無効化していない。認証時にTLSソケットであることも確認した。SSLの2ケースではaiosmtpdがSTARTTLS専用フラグを見て5件の警告を出すが、サーバー自体が暗号化接続のみ受け付ける構成である。この警告をゼロと報告しない。

環境の概要は[Cloud Shellの説明](https://docs.cloud.google.com/shell/docs/launching-cloud-shell)、[SSHの認証転送仕様](https://docs.cloud.google.com/sdk/gcloud/reference/cloud-shell/ssh)、[aiosmtpdのSSLサーバー仕様](https://aiosmtpd.aio-libs.org/en/latest/controller.html)に対応する。

## 再実行

隔離PostgreSQLと使い捨て認証情報を環境変数で用意し、次を実行する。接続先はloopbackに限定し、DSNのクエリ指定も拒否する。SMTP試験には試験環境だけに`aiosmtpd`と`openssl`が必要。アプリ本体の依存は増やしていない。

```text
TEST_ORDER_DATABASE_URL=<isolated loopback PostgreSQL DSN>
TEST_ORDER_SMTP_INTEGRATION=1
python -m pytest tests/test_purchase_notifications_postgres.py tests/test_order_notifications_smtp_postgres.py -q -p no:cacheprovider --tb=short
```

接続未設定の場合はSKIPでありPASSではない。通常のローカル全体回帰と、明示設定して実行した実DB／SMTP試験を合算して一つのテスト合格数にはしない。

## 残る公開前確認

1. 運営通知のSMTP設定をローカル環境変数または秘密設定ファイルで指定する。秘密値はチャット・Gitへ記録しない。
2. 運営者のテスト宛先だけにアプリから送信し、外部サーバー経由の到達・宛先・本文・失敗再送・DB履歴を確認する。
3. 本番向けDDL適用・候補版と旧コードの切り替え手順を別途確認する。本番DB操作・push・デプロイは今回実施していない。

SMTPが成功を返した後にDBコミットが失敗した場合、メールだけが再送される可能性は残る。今回確認したのは通常の同時処理・SMTP失敗再送であり、外部メール配送のexactly-onceを保証する結果ではない。

## Gitの整理

同じブランチ`codex/astrology-prompt-separation`に履歴を追加し、既存履歴は書き換えていない。作業ファイルの内容を保持して占術修正と注文処理を切り分けた。元のルートcheckoutは変更していない。

- `86f0c05`：占術別指示文・現地暦日・日替わり・性別未指定の先行修正。29ファイルの独立したコミット状態で1971件の回帰テスト成功。
- `f8656b9`：共通商品台帳、明細検証、保留の管理者承認、SMTP・実DB試験。21ファイル。上記の修正後全体回帰と隔離環境試験を確認済み。
- 続く検証資料のコミット：先行する品質監査・独立レビュー・注文通知の調査と、本報告・証跡をまとめる。過去の未実施・失敗結果を現在の成功結果で書き換えず、時点を区別する。

push・候補版デプロイ・本番切り替え・本番DDL適用は実施していない。ローカルのコミット完了は公開許可を意味しない。

実装コミットの`git diff --check`は成功。資料コミットでは、先行レビューの行番号付き入力・依頼文・パッチ・pytest原ログの11ファイルに空白警告がある。独立レビューの入力ハッシュと原ログを維持するため、その既存の空白を整形せず保存した。警告が実装や今回の報告書から出ていないことを確認しており、資料全体の空白検査を成功とは記録しない。
