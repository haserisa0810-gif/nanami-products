# 本番操作の安全ルール

## 原則

本番はデフォルトで読み取り専用です。デプロイ、本番トラフィック変更、本番 DB の書き込み・DDL・削除は、ユーザーがそのターンで対象操作を明示した場合だけ実行します。
デプロイスクリプトの既定対象は Cloud Run サービス `nanami-products`、プロジェクト `nanami-astro`、リージョン `asia-northeast1` に固定しています。

## デプロイ手順

1. 必要な変更だけをコミットする。
2. テストを通す。
3. 対象ブランチを upstream に push する。
4. `git status --short` が空であることを確認する。追跡外ファイルも残さない。
5. `powershell -ExecutionPolicy Bypass -File .\scripts\deploy_candidate.ps1` で候補版を作る。この処理は全テストを再実行し、候補版を 0% 配信で作成する。
6. 表示、主要リンク、主要 API を候補 URL でスモークテストする。
7. 本番切り替えの明示承認を別途受ける。
8. `powershell -ExecutionPolicy Bypass -File .\scripts\promote_candidate.ps1 -Revision <revision> -Confirm "PROMOTE:<revision>"` で 100% に切り替える。
9. 本番 URL でも同じスモークテストを行う。

ガードが停止した場合は、その理由を解消します。ガードを迂回して `gcloud run deploy` や `gcloud run services update-traffic` を直接実行しません。

## 本番 DB

デプロイ承認は、本番 DB の直接操作を含みません。DDL、マイグレーション、UPDATE、DELETE、手動データ修正には、対象・影響・復旧方法を示した別の明示承認が必要です。
