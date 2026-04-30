# nanami-products デプロイ手順

## 初回デプロイ

```bash
cd ~/dev/nanami-products

gcloud run deploy nanami-products \
  --source . \
  --region asia-northeast1 \
  --allow-unauthenticated
```

## 動作確認

```text
/healthz
/admin/yaml/new
```

## 注意

- 現状は管理者用フォームに認証なしです。URLを公開する前に、Cloud Run の URLを表に出さないか、簡易認証を追加してください。
- `/tmp/nanami_products.db` に保存するため、Cloud Run再起動で消える可能性があります。販売運用前に Cloud SQL / Firestore / Cloud Storage 保存へ変更推奨です。
- まずはテスト販売・手動発行用の最小版です。
