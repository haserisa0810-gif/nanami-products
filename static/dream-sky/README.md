# Dream Sky v0

Birth Sky の姉妹作品。**出生時の空に、ハウスという夢の重力を重ねる。**

- URL: `/dream-sky/`
- Birth Sky / Chart Sphere / 星の和音は変更しない

## チャート

| 方法 | 内容 |
|------|------|
| 既定 | **ねこ編集長**（固定サンプル） |
| **YAML** | 画面下 **Chart / YAML** → nanami-products の western natal を貼る |
| 復元 | 同一ブラウザの `sessionStorage`（`ds-last-yaml`） |

クライアント内のみ。再計算・サーバー送信なし。

## 空間（v0）

- 第4 · 第5 · 第12 のみ
- そのハウスにいる天体（太陽・月・土星・海王星など）で光・粒子が変わる

## 開き方

```bash
cd natal-sphere-planetarium
python -m http.server 8765
# http://127.0.0.1:8765/dream-sky/
```
