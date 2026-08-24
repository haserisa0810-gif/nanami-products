---
title: Nanami Knowledge Hub 運用ガイド
kind: playbook
status: active
tags: [knowledge, product, operations]
owner: nanami-products
updated_at: 2026-08-20
---

# Nanami Knowledge Hub

このディレクトリは、`nanami-products` の開発知識と、別フォルダにある
`nanami-content` の運用知識を、混在させずに横断検索するための入口です。

## 情報の分け方

| collection | 内容 | 正本の場所 |
|---|---|---|
| `product` | アプリ仕様、計算仕様、販売導線、デプロイ手順 | `nanami-products` |
| `operations` | SNS、YouTube、Pinterest、販売運用 | `nanami-content` |
| `operations_after_action` | 公開後の結果、障害、振り返り | `nanami-content/knowledge/after_action` |
| `operations_archive` | 会話の引き継ぎ、過去の知識アーカイブ | `nanami-content/archives` |

DBに入った後も `collection`、`kind`、`status`、`source_path` を保持するため、
検索結果は横断できますが、原本同士は混ざりません。

## 作った後の話をどう扱うか

会話や思いつきを自動で正式ナレッジにはしません。

1. 未整理の内容は `nanami-content/knowledge/inbox/` に保存する
2. 実施結果は `knowledge/after_action/` に記録する
3. 繰り返し使う結論だけを `operations/` または `decisions/` へ昇格する
4. 古くなった原本は削除せず `status: superseded` または `archived` にする

通常のカタログ・DB同期では `inbox` を除外します。これにより、会話ログや途中の
アイデアが正式な運用ルールとしてAIに渡る事故を防ぎます。

## コマンド

```powershell
# 構成とメタデータの検証（DBへは接続しない）
.\.venv\Scripts\python.exe scripts\knowledge_sync.py validate

# GitHubでレビューできる索引を生成
.\.venv\Scripts\python.exe scripts\knowledge_sync.py catalog

# ローカル横断検索
.\.venv\Scripts\python.exe scripts\knowledge_sync.py search "Etsy 注文"

# DB同期予定だけ表示。本番DBは変更しない
.\.venv\Scripts\python.exe scripts\knowledge_sync.py sync-db
```

本当にDBへ反映するときだけ、`DATABASE_URL`を設定した環境で明示的に
`sync-db --apply`を実行します。本番DBへの初回適用は、通常のデプロイとは分けて
承認・バックアップ確認を行ってください。

運用側の場所が標準配置と異なる場合は、`NANAMI_CONTENT_ROOT`環境変数、または
各コマンドの`--content-root`で指定できます。

## メタデータ

新しい正式ナレッジは、Markdown先頭に次のfront matterを付けます。

```yaml
---
title: Etsy注文取込の運用手順
kind: playbook
status: active
tags: [etsy, order, operations]
owner: nanami-astro
updated_at: 2026-08-20
---
```

`status`は`draft`、`active`、`superseded`、`archived`のいずれかです。
テンプレートは運用側の`knowledge/_templates/`にあります。
