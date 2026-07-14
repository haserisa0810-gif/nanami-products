# 生活感レイヤ（Lived-in props）

建築本体を壊さず、「人がさっきまで使っていた気配」を足すレイヤです。

## すぐ戻す（雰囲気が壊れたとき）

### A. 画面上（おすすめ）

Architecture Edition の HUD:

- **「生活感: ON/OFF」** チップ
- メニュー → **「生活感 ON/OFF（雰囲気を戻す）」**

OFF にすると小物だけ消え、**建築は残ります**（再読込不要）。

### B. URL

```text
/house-tour-architecture?lived_in=0
```

強制 OFF。ON に戻す: `?lived_in=1`

### C. localStorage

```js
localStorage.setItem("ht-arch-lived-in", "0"); // OFF
localStorage.setItem("ht-arch-lived-in", "1"); // ON
```

### D. コードを戻す（Git）

生活感はほぼこのファイルだけ:

```text
static/house-tour-architecture/js/life-props.js
```

`arch-builder.js` の `attachLivedInProps` 呼び出しを消せば完全に切り離せます。

```bash
git checkout HEAD -- static/house-tour-architecture/js/life-props.js
# または attachLivedInProps 行を削除
```

## 対象ハウス（v2 — 全12棟）

| ハウス | 生活感の核 |
|--------|------------|
| 1 玄関 | 鍵・鞄・傘立て・手紙 |
| 2 保管 | 仕分けノート・リスト・眼鏡・鍵 |
| 3 回廊 | 鞄・ボトル・手紙・通過の痕跡 |
| 4 邸宅 | カップ・写真・ノート・クッション |
| 5 劇場 | 袖の譜面・カップ・鞄 |
| **6 研究** | **厚め** — 机上一式・カレンダー・本棚 |
| 7 応接 | 二つのカップ・契約ノート・名札 |
| 8 金庫 | キャンドル・静かなノート（怖くしない） |
| 9 天文 | 研究ノート・ライト・眼鏡 |
| 10 塔 | 発表後のメモ・グラス・写真 |
| 11 サロン | 複数カップ・名札・ボウル |
| 12 休息 | スリッパ・お茶・キャンドル |

## 設計

- グループ名: `lived_in_props`
- 素材は `materials.js` を再利用
- 将来 glTF 差し替えは `life-props.js` 内の各小物関数だけ変えればよい
