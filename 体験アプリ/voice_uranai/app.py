"""ボイス占いアプリ フェーズ1: 鑑定テキストを東北イタコ(VOICEVOX)で読み上げるローカルWebアプリ。

前提: VOICEVOX ENGINE が http://localhost:50021 で起動していること。
  docker run --rm -p 50021:50021 voicevox/voicevox_engine:cpu-latest

起動: python app.py → http://localhost:5000
"""
import io
import os

import requests
from flask import Flask, jsonify, request, send_file

app = Flask(__name__)

VOICEVOX_URL = os.environ.get("VOICEVOX_URL", "http://localhost:50021")
ITAKO_NAME = "東北イタコ"
ITAKO_STYLE = "ノーマル"  # 使用スタイル。聴き比べて変更可
_itako_speaker_id = None


def resolve_itako_id():
    """起動時に東北イタコのspeaker IDを名前解決する（IDはENGINEバージョンで変わりうるため）。"""
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


@app.route("/")
def index():
    return send_file(os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html"))


@app.route("/tent")
def tent():
    """星詠みの天幕（声つきナナミVN）。voiceBase="" のまま同一オリジンで /speak に到達する。"""
    return send_file(os.path.join(os.path.dirname(os.path.abspath(__file__)), "hoshiyomi-no-yoru.html"))


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
