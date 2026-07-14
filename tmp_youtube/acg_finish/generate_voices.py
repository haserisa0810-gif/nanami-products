import json, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).parent
LINES = [
    "この線、何だと思います？",
    "実は、生まれた時間で変わる地図なんです。",
    "あなたにも、自分だけの地図があります。",
]
SPEAKER = 11  # VOICEVOX:玄野武宏

for i, text in enumerate(LINES):
    qurl = "http://127.0.0.1:50021/audio_query?" + urllib.parse.urlencode({"text": text, "speaker": SPEAKER})
    req = urllib.request.Request(qurl, method="POST")
    with urllib.request.urlopen(req) as response:
        query = json.load(response)
    query["speedScale"] = 1.12
    query["intonationScale"] = 1.05
    query["volumeScale"] = 0.92
    surl = "http://127.0.0.1:50021/synthesis?" + urllib.parse.urlencode({"speaker": SPEAKER})
    req = urllib.request.Request(surl, data=json.dumps(query).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req) as response:
        (ROOT / f"voice_{i}.wav").write_bytes(response.read())
    print(i, text)
