# ボイス占いアプリ 指示書（フェーズ1: 鑑定テキスト直貼り版・ローカル一体型）

## 0. この指示書の目的

鑑定テキストを貼り付けると、東北イタコの声（VOICEVOX）で読み上げるローカルWebアプリを作る。
Cloud Run化・Chart URL入力・MCP連携は本フェーズのスコープ外（フェーズ2以降）。
まず「テキストを貼る → 東北イタコの声が鳴る」を最短で完成させる。

---

## 1. スコープ

### やること（フェーズ1）
- ローカルで VOICEVOX ENGINE（Docker）を起動する
- Flask アプリを立て、ブラウザUIから鑑定テキストを受け取る
- Flask が VOICEVOX ENGINE の `/audio_query` → `/synthesis` を叩き、東北イタコ音声(wav)を返す
- ブラウザで音声を再生する
- 画面に「VOICEVOX:東北イタコ」のクレジットを常時表示する

### やらないこと（本フェーズ対象外）
- Cloud Run へのデプロイ
- Chart URL 入力・YAML取得・Fable5による鑑定生成（フェーズ2）
- MCP連携の橋渡しツール（フェーズ2）
- 章分割合成・複数キャラ切替（将来検討）

---

## 2. 全体構成

```
ブラウザ (index.html)
  │  鑑定テキストをPOST
  ▼
Flask (app.py)  http://localhost:5000
  │  /audio_query?speaker=<itako_id>   （クエリ生成）
  │  /synthesis?speaker=<itako_id>     （音声合成）
  ▼
VOICEVOX ENGINE (Docker)  http://localhost:50021
  │  wav
  ▼
Flask が wav をブラウザに返す → <audio> で再生
```

ポイント: ブラウザから VOICEVOX ENGINE を直叩きしない。必ず Flask を経由する（将来のCORS・課金・規約管理を一箇所に寄せるため）。

---

## 3. 環境・前提

- OS: ローカル開発機（Windows/Mac/Linuxいずれか）
- Docker が使えること
- Python 3.10+ / Flask
- VOICEVOX ENGINE 公式Dockerイメージ `voicevox/voicevox_engine`（CPU版で可）

### VOICEVOX ENGINE 起動（CPU版）
```
docker run --rm -p 50021:50021 voicevox/voicevox_engine:cpu-latest
```
起動後 `http://localhost:50021/docs` でOpenAPI仕様が見えることを確認する。

---

## 4. 実装タスク

### タスク1: 東北イタコの speaker ID を取得する
- ENGINE起動後、`GET http://localhost:50021/speakers` を叩く
- レスポンスJSONから「東北イタコ」を探し、使用スタイル（例: ノーマル）の `styles[].id` を取得する
- 取得したIDを `app.py` の定数 `ITAKO_SPEAKER_ID` に設定する
- 注意: IDはバージョンで変わりうるので、ハードコードせず起動時に名前解決してもよい（下の推奨実装参照）

### タスク2: Flask バックエンド（app.py）
エンドポイント `POST /speak` を実装する。

- 入力: JSON `{ "text": "<鑑定テキスト>" }`
- 処理:
  1. `text` が空ならエラーを返す
  2. `POST http://localhost:50021/audio_query?speaker=<ITAKO_SPEAKER_ID>&text=<text>` でクエリJSON取得
  3. 必要なら話速等を調整（`speedScale` 等。初期値はデフォルトのまま）
  4. `POST http://localhost:50021/synthesis?speaker=<ITAKO_SPEAKER_ID>` にクエリJSONを送り wav 取得
  5. wav を `audio/wav` で返す
- 例外処理: ENGINE未起動・タイムアウト時は 503 と分かりやすいメッセージ

補助エンドポイント `GET /health`: ENGINEに到達できるか確認して返す。

### タスク3: フロントUI（index.html）
- テキストエリア（鑑定テキスト貼り付け用）
- 「聴く」ボタン → `/speak` にPOST → 返ってきたwavを `<audio>` で再生
- ローディング表示（合成中の待ち時間があるため必須）
- 画面下部に固定でクレジット表示: `VOICEVOX:東北イタコ`
- HTMLの `<form>` は使わず、ボタンの `onClick` で処理する

---

## 5. 推奨実装（参考コード）

### app.py
```python
import requests
from flask import Flask, request, send_file, jsonify
import io

app = Flask(__name__)

VOICEVOX_URL = "http://localhost:50021"
ITAKO_NAME = "東北イタコ"
ITAKO_STYLE = "ノーマル"  # 使用スタイル。聴き比べて変更可
_itako_speaker_id = None


def resolve_itako_id():
    """起動時に東北イタコのspeaker IDを名前解決する。"""
    global _itako_speaker_id
    if _itako_speaker_id is not None:
        return _itako_speaker_id
    res = requests.get(f"{VOICEVOX_URL}/speakers", timeout=10)
    res.raise_for_status()
    for sp in res.json():
        if sp.get("name") == ITAKO_NAME:
            for st in sp.get("styles", []):
                if st.get("name") == ITAKO_STYLE:
                    _itako_speaker_id = st["id"]
                    return _itako_speaker_id
            # スタイル名が違う場合は先頭スタイルを使う
            _itako_speaker_id = sp["styles"][0]["id"]
            return _itako_speaker_id
    raise RuntimeError("東北イタコが見つかりません。ENGINEのバージョンを確認してください。")


@app.route("/health")
def health():
    try:
        sid = resolve_itako_id()
        return jsonify({"ok": True, "itako_speaker_id": sid})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 503


@app.route("/speak", methods=["POST"])
def speak():
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "textが空です"}), 400
    try:
        sid = resolve_itako_id()
        q = requests.post(
            f"{VOICEVOX_URL}/audio_query",
            params={"speaker": sid, "text": text},
            timeout=30,
        )
        q.raise_for_status()
        query = q.json()
        # 話速調整したい場合はここで query["speedScale"] = 1.0 など
        syn = requests.post(
            f"{VOICEVOX_URL}/synthesis",
            params={"speaker": sid},
            json=query,
            timeout=120,
        )
        syn.raise_for_status()
        return send_file(
            io.BytesIO(syn.content),
            mimetype="audio/wav",
            as_attachment=False,
            download_name="uranai.wav",
        )
    except requests.exceptions.ConnectionError:
        return jsonify({"error": "VOICEVOX ENGINEに接続できません。Dockerを起動してください。"}), 503
    except requests.exceptions.Timeout:
        return jsonify({"error": "合成がタイムアウトしました。テキストが長すぎる可能性があります。"}), 504
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
```

### index.html（Flaskの static/ か templates/ に置く。単体で開いてもOK）
```html
<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ボイス占い（東北イタコ）</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 640px; margin: 2rem auto; padding: 0 1rem; }
    textarea { width: 100%; height: 200px; font-size: 1rem; padding: .5rem; box-sizing: border-box; }
    button { font-size: 1.1rem; padding: .6rem 1.4rem; margin-top: .8rem; cursor: pointer; }
    #status { margin-top: .8rem; color: #666; min-height: 1.4em; }
    #credit { margin-top: 2rem; padding-top: 1rem; border-top: 1px solid #ccc; color: #888; font-size: .85rem; }
    audio { width: 100%; margin-top: 1rem; }
  </style>
</head>
<body>
  <h1>ボイス占い（東北イタコ）</h1>
  <p>鑑定テキストを貼り付けて「聴く」を押してください。</p>
  <textarea id="text" placeholder="ここに鑑定テキストを貼り付け"></textarea>
  <button id="speakBtn">聴く</button>
  <div id="status"></div>
  <audio id="player" controls hidden></audio>
  <div id="credit">VOICEVOX:東北イタコ</div>

  <script>
    const btn = document.getElementById('speakBtn');
    const status = document.getElementById('status');
    const player = document.getElementById('player');

    btn.addEventListener('click', async () => {
      const text = document.getElementById('text').value.trim();
      if (!text) { status.textContent = 'テキストを入力してください'; return; }
      btn.disabled = true;
      status.textContent = '合成中…（数十秒かかることがあります）';
      player.hidden = true;
      try {
        const res = await fetch('/speak', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text })
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.error || ('HTTP ' + res.status));
        }
        const blob = await res.blob();
        player.src = URL.createObjectURL(blob);
        player.hidden = false;
        player.play();
        status.textContent = '完了';
      } catch (e) {
        status.textContent = 'エラー: ' + e.message;
      } finally {
        btn.disabled = false;
      }
    });
  </script>
</body>
</html>
```

---

## 6. 動作確認手順

1. `docker run --rm -p 50021:50021 voicevox/voicevox_engine:cpu-latest` でENGINE起動
2. `http://localhost:50021/docs` が見えることを確認
3. `pip install flask requests` → `python app.py`
4. ブラウザで `http://localhost:5000/health` を開き `ok: true` と itako_speaker_id が返ることを確認
5. トップページでテキストを貼り「聴く」→ 東北イタコの声で再生されることを確認

---

## 7. 受入基準（フェーズ1完了条件）

- [ ] VOICEVOX ENGINE(Docker)がローカルで起動している
- [ ] `/health` が東北イタコのspeaker IDを返す
- [ ] 鑑定テキストを貼り「聴く」で東北イタコ音声が再生される
- [ ] ENGINE未起動時にUIへ分かるエラーが出る（クラッシュしない）
- [ ] 画面に「VOICEVOX:東北イタコ」クレジットが常時表示される
- [ ] 200〜300字程度の要約鑑定テキストが実用的な待ち時間で合成される

---

## 8. 動作確認用サンプルテキスト（約230字・要約鑑定）

```
長谷川リサさんの今日を視ます。あなたは自分を出す力と、
引いて見る目を両方持つ人。積み上げで効くタイプです。
今日は人との距離感の調整日。急がず、確かめながら進めて。
朝は頭が冴える時間。方針出しやメモに向きます。
昼は人と関わる流れ。連絡や相談はこの時間に。
夜は気持ちが落ち着き、噛み合う時間。振り返りに使って。
明後日は動きが出やすい日。伝えたいことは、その日に。
```

---

## 9. 次フェーズの布石（今は作らない・設計だけ意識）

- フェーズ2: Chart URL入力欄を追加 → MCP/APIでYAML取得 → Fable5で「要約4ブロック（つかみ／今日のテーマ／朝昼夜／締め）」を生成 → その出力を本フェーズの `/speak` にそのまま流す。だから `/speak` の入力インターフェイス（textを受けてwavを返す）はフェーズ2でも変えない設計にしておく。
- フェーズ3: VOICEVOX ENGINEとFlaskをCloud Run化。ENGINEは内部URLで参照し、ブラウザから直叩きさせない構成を維持する。クレジット表示は公開版でも必須。

## 10. 要約生成ルール（フェーズ2でFable5に渡す用・今はメモ）

添付鑑定プロンプトの縛りを継承する:
- 計算値（天体位置・ハウス・アスペクト・トランジット）は変更しない
- today.selected_date を基準日にする
- 断定しすぎず傾向・活かし方で表現する
音声用の追加制約:
- 1ブロック1〜2文、話し言葉、東北イタコの口調（「視ます」「視えます」等を効かせる）
- 全体で200〜300字に収める
- 構成は4ブロック固定: (1)つかみ=natalの核 (2)今日のテーマ=today最タイトのアスペクト1本 (3)朝昼夜=moon_timepoints各1文 (4)締め=next_few_daysの動きやすい日1つ
