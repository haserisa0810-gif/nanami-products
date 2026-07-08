# ボイス占い（東北イタコ）フェーズ1

鑑定テキストを貼り付けると VOICEVOX の東北イタコの声で読み上げるローカル Web アプリ。
仕様: `../voice_uranai_phase1_spec.md`

## 起動手順

1. VOICEVOX ENGINE（Docker・CPU版）を起動:

   ```bash
   docker run --rm -p 50021:50021 voicevox/voicevox_engine:cpu-latest
   ```

   `http://localhost:50021/docs` が開ければ OK。

2. Flask アプリを起動:

   ```bash
   pip install flask requests
   python app.py
   ```

3. `http://localhost:5000/health` で `ok: true` と `itako_speaker_id` が返ることを確認。

4. `http://localhost:5000/tent` を開く（**本線**: 星詠みの天幕・声つきナナミVN）。
   左上の「声をきく」トグルをONにし、YAMLを貼って「星を視る」→ ナナミが東北イタコの声で鑑定を読み上げる。
   VOICEVOX未起動時はトグルが「声を準備中…」で無効化され、VNは無音で動作する。

   **CPU合成は遅い**: 1文あたり数秒〜十数秒かかる。トグルが「紡ぎ中…」の間は合成中なので、
   声を待ってからタップで進むこと。一度読んだ文はキャッシュされ、次のセリフは先読みされる。

5. `http://localhost:5000` は素の入力UI（口寄せの座）。鑑定テキストを貼って「聴く」。

VOICEVOX ENGINE の URL を変える場合は環境変数 `VOICEVOX_URL` で指定（既定 `http://localhost:50021`）。

## クレジット

音声合成: VOICEVOX:東北イタコ（画面下部に常時表示）
