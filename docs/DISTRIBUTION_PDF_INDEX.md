# 配布PDF配置一覧

## 目的

販売サイトへ添付するPDFと、QA用サンプル・販売画像用PDFを取り違えないための配置ルールです。

## 現行の配布用PDF

| 販売元・商品 | 正規フォルダ | 備考 |
|---|---|---|
| STORES（基本版・トランジット・FULL・四柱推命・アドオン） | `output/pdf/distribution/stores/` | 購入者へ配布する現行PDF。各PDFに `provider=stores` のリンクを収録 |
| Etsy FULL版（JA/EN/ES/DE） | `output/pdf/etsy-western-full/` | Etsy Listingへ添付する注文番号入力案内PDF |
| Etsy ACG bundle（EN） | `output/pdf/nanami_acg_premium_bundle_etsy_en.pdf` | Etsy ACG Listing用 |
| ココナラ（販売終了） | `output/pdf/nanami_*_coconala.pdf` | 過去購入者の引換・サポート専用Legacy PDF。新規販売には使用しない |

## 配布しないPDF

| 種別 | フォルダ・ファイル | 扱い |
|---|---|---|
| Personal Edition FULLサンプル | `output/pdf/personal-edition-full-current/` | コード発行・表示確認用。Etsy/STORESへ添付しない |
| Personal Edition ACGサンプル | `output/pdf/personal-edition-acg-access-code-sample*.pdf` | サポート・QA用。通常配布しない |
| Planner販売画像の元PDF | `output/etsy/*/planner-sample/` | 販売画像作成用。アクセス案内PDFではない |
| 旧成果物 | `output/legacy/`、`output/` 内の `Final` / `fixed` / Museum名を含む成果物 | legacy/QA扱い。現行商品へ配布しない |

## STORESの5冊

| ファイル | 商品 |
|---|---|
| `nanami_western_basic_stores.pdf` | ホロスコープ基本版 |
| `nanami_western_transit_stores.pdf` | ホロスコープ基本版＋トランジット |
| `nanami_western_full_stores.pdf` | ホロスコープFULL版 |
| `nanami_shichu_stores.pdf` | 四柱推命版 |
| `nanami_addon_stores.pdf` | アドオンデータ |

## 再生成

```powershell
python scripts/build_marketplace_product_guides.py --marketplace stores
```

生成先は `output/pdf/distribution/stores/` です。各PDFは日本語ページと英語ページを含み、リンク先では `provider=stores` を明示します。

## 配布前確認

- 対象商品のPDFであること
- URLとQRコードが `provider=stores` になっていること
- FULL版には1年Plannerが含まれ、ACGとMuseumは含まれないこと
- Personal Editionの `SAMPLE` コードPDFではないこと
- 旧 `Final` / `fixed` / Museum名成果物ではないこと
