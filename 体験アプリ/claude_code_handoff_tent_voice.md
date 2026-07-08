# Claude Code 指示書 — 声つき「星詠みの天幕」統合・ローカル完成

## 0. 前提（この指示書だけで着手できるように）

これは西洋占星術のWebアプリ群の一部。すでに以下ができている：

1. **ボイス占いアプリ（Flask）** — 鑑定テキストを受け取り、VOICEVOX ENGINE の東北イタコ音声(wav)を返す。エンドポイントは `POST /speak`（JSON `{text}` → wav）と `GET /health`（東北イタコの speaker ID を返す）。すでに実機で動作確認済み（health が `{"ok":true,"itako_speaker_id":109}` を返す）。
2. **星詠みの天幕（声つき版）** — `hoshiyomi-no-yoru.html`。ビジュアルノベル形式で占い師「ナナミ」が喋る。YAMLをローカル解釈して鑑定文を生成（`buildLocalReading`）、1文ずつタイプ表示する。今回この HTML に**声レイヤー**を追加済みで、ナナミのセリフ表示のたびに上記 `/speak` を叩いて東北イタコ声で読み上げる。VOICEVOX未起動時は自動で無音フォールバックする。

**このタスクのゴール：** 星詠みの天幕（声つきナナミ）を本線とし、Flask から同一オリジンで配信して、ブラウザで開けば「ナナミが東北イタコの声で鑑定を読む」状態をローカルで確実に動かす。Cloud Run化はスコープ外（次フェーズ）。

---

## 1. スコープ

### やること
- Flask アプリ（既存の `/speak`・`/health` を持つ `app.py`）に、`hoshiyomi-no-yoru.html` を配信するルートを足す
- 星詠みの天幕を Flask と**同一オリジン**で開けるようにする（`voiceBase=""` のまま `/speak` に到達できる状態）
- VOICEVOX:東北イタコ のクレジットを星詠みの天幕の画面内に常時表示する（声を使う以上、表記は必須）
- ローカルでエンドツーエンド動作確認（YAML貼付 → ナナミが鑑定を喋る）

### やらないこと（次フェーズ）
- Cloud Run へのデプロイ
- Chart URL 入力・MCP連携・Fable5 での鑑定生成（現状はローカル `buildLocalReading` を使う）
- 口寄せの座UI版（`index.html`／御神鏡）の本線化 ※下の「別案」参照

---

## 2. 受け取るファイル

作業ディレクトリ（例：`体験アプリ/voice_uranai/`）に以下がある想定：

- `app.py` — Flask。`/speak`・`/health` 実装済み。VOICEVOX_URL は環境変数で上書き可。
- `hoshiyomi-no-yoru.html` — 声つきナナミ本体（本線）。
- `index.html` — ボイス占いの素の入力UI（口寄せの座・御神鏡の装飾版）。**別案として温存**。本線では使わない。
- `README.md` — 起動手順。

`hoshiyomi-no-yoru.html` 冒頭の設定行：
```js
const voiceBase = "";   // 同一オリジン配信ならこのまま。別ポートなら "http://localhost:5000"
```
同一オリジン配信にするので、この値は `""` のままでよい。

---

## 3. 実装タスク

### タスク1: Flask に星詠みの天幕の配信ルートを足す
`app.py` に以下を追加する（既存の `/speak`・`/health`・`GET /` は変更しない）。

- ルート `GET /tent` で `hoshiyomi-no-yoru.html` を返す（`send_file` または `render_template` 相当）
- 既存トップ `GET /`（素の入力UI）はそのまま残す。トップから `/tent` へのリンクを1つ足してもよい（任意）

配置方針はどちらでも可：
- `hoshiyomi-no-yoru.html` をアプリと同じ階層に置き、`send_file("hoshiyomi-no-yoru.html")` で返す
- もしくは `static/` に置いて静的配信

**重要：** 星詠みの天幕は `voiceBase=""` で `/speak`・`/health` を叩く。つまり天幕を配信する Flask が `/speak` も持っている（＝同一オリジン）ことが前提。だから既存の `/speak` を持つ `app.py` から配信するのが正しい。別サーバーで静的配信しないこと（CORSと設定が増える）。

### タスク2: クレジット表示を天幕に追加
`hoshiyomi-no-yoru.html` の画面内に「VOICEVOX:東北イタコ」を常時見える形で足す。VN画面下部か、設定/情報の小さな表記で可。既存の金色テーマ（`#d9b35e` / `#e8c15e`）に合わせる。声を鳴らす公開物なので、この表記は受入基準に含める。

### タスク3: 動作確認
下記「4. 動作確認手順」を通す。

---

## 4. 動作確認手順

1. VOICEVOX ENGINE 起動：
   `docker run --rm -p 50021:50021 voicevox/voicevox_engine:cpu-latest`
   → `http://localhost:50021/docs` が見えること
2. Flask 起動：`python3 app.py`
3. `http://localhost:5000/health` → `{"ok":true,"itako_speaker_id":...}` を確認
4. `http://localhost:5000/tent` を開く → ナナミのVNが表示される
5. 「声をきく」トグルが有効になっている（＝health到達成功）ことを確認
6. 「星を視てもらう」→ サンプルYAML（下記）を貼付 → 「星を視る」
7. ナナミが鑑定を1文ずつ表示し、**同時に東北イタコの声で読み上げる**ことを確認
8. トグルOFFで無音・文字送りのみになることを確認
9. VOICEVOX ENGINE を止めた状態で `/tent` を開き、トグルが「声を準備中」で無効化され、VNは無音で正常動作することを確認（クラッシュしない）

---

## 5. 受入基準

- [ ] `GET /tent` で声つきナナミが表示される（同一オリジン、`voiceBase=""`のまま）
- [ ] YAML貼付 → ナナミが鑑定を喋る（文字送りと音声が同期）
- [ ] 声トグルON/OFFが効く。OFFで無音・文字送り継続
- [ ] VOICEVOX未起動時：トグル無効化＋VNは無音で正常動作（クラッシュしない）
- [ ] 「VOICEVOX:東北イタコ」クレジットが画面内に常時表示される
- [ ] 既存の `/speak`・`/health`・`GET /`（素の入力UI）は無改変で従来通り動く

---

## 6. 声レイヤーの内部仕様（改修時の参照用・すでに実装済み）

`hoshiyomi-no-yoru.html` 内 `voice` オブジェクトが音声を管理する。触る必要が出た時のために要点：

- `voice.probe()` … 起動時に `GET /health` を叩き、到達可否でトグルを有効化／「声を準備中」無効化
- `typeWrite(text, cb)` 内で `voice.speak(text)` を呼ぶ … これが唯一の接続点。ナナミが喋る文字＝読み上げ文字
- `voice.speak` … `clean()` で `✦▸▼` 等の記号を除去 → `/speak` で wav取得 → 再生。同一文は `cache` で再取得しない
- ON中にセリフが変わると前の音声を `stop()` してから次を鳴らす
- 合成失敗は握りつぶしてVN進行を止めない（無音フォールバック）

**改修の原則：** `buildLocalReading` とVN進行ロジックは触らない。音声は上に乗った任意レイヤーで、剥がしても元のVNが動く設計を維持する。

---

## 7. 次フェーズの布石（今は作らない）

- **Chart URL / MCP連携：** 現状の鑑定文はブラウザ内 `buildLocalReading`（YAML直接解釈）。次フェーズで「Chart URL入力 → MCP/APIでYAML取得 → Fable5で鑑定生成」に差し替える余地がある。その場合も、生成した鑑定文を今の表示＋`voice.speak` に流す形にすれば声レイヤーは再利用できる。
- **Cloud Run化：** Flask＋VOICEVOX ENGINE をCloud Run化。ENGINEは内部URLで参照し、ブラウザから直叩きさせない。`voiceBase` は同一オリジンのまま運用。クレジット表示は公開版でも必須。
- **口寄せの座UI（index.htmlの装飾版・御神鏡）：** 別デザインのボイス占い入口として温存。本線が固まった後、統合するか別ページとして残すか判断する。

---

## 別案（本線を変える場合）

もし本線を「星詠みの天幕」ではなく素のボイス占いUI（口寄せの座・御神鏡＝装飾版 `index.html`）にしたい場合は、タスク1で `/tent` の代わりに装飾版 `index.html` を `GET /` に据える。ただし推奨は星詠みの天幕：ナナミの姿・口調・YAMLローカル鑑定・分身AI生成がすでに揃っており、「占い師が喋る」体験が一番完成しているため。
