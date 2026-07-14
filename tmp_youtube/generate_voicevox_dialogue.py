import json
import urllib.parse
import urllib.request
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BASE = "http://127.0.0.1:50021"

# VOICEVOX: 冥鳴ひまり (14), VOICEVOX: 九州そら (16)
LINES = [
    ("voice_mio_0.wav", "鑑定モード、私の恋愛傾向まで分かるんだ。", 14, 1.38, 0.03),
    ("voice_mio_1.wav", "ルナ、片思いの彼に、どうアプローチすればいい？", 14, 1.42, 0.03),
    ("voice_luna_0.wav", "まず短い会話を増やして。彼の好きな話題から、自然に誘ってみて。", 16, 1.72, -0.02),
    ("voice_mio_2.wav", "わかった。今日、話しかけてみる！", 14, 1.38, 0.04),
]

def post(path, params, payload=None):
    url = BASE + path + "?" + urllib.parse.urlencode(params)
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    if body is not None:
        req.add_header("Content-Type", "application/json; charset=utf-8")
    with urllib.request.urlopen(req, timeout=120) as res:
        return res.read()

for filename, text, speaker, speed, pitch in LINES:
    query = json.loads(post("/audio_query", {"text": text, "speaker": speaker}))
    query["speedScale"] = speed
    query["pitchScale"] = pitch
    query["intonationScale"] = 1.10 if speaker == 14 else 1.03
    query["volumeScale"] = 1.0
    wav_bytes = post("/synthesis", {"speaker": speaker}, query)
    out = ROOT / filename
    out.write_bytes(wav_bytes)
    with wave.open(str(out), "rb") as w:
        duration = w.getnframes() / w.getframerate()
    print(f"{filename}: {duration:.2f}s")
