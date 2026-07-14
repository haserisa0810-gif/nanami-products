import json,urllib.parse,urllib.request,wave
from pathlib import Path
R=Path(__file__).parent;B='http://127.0.0.1:50021'
L=[(0.3,'AIに、生年月日だけ渡して占わせていませんか？',11,1.55,-.03),(2.95,'情報が、足りません。',16,2.2,-.01),(4.35,'AI占い for AIは違います。計算ファースト。',11,1.62,-.03),(7.35,'理解しました！',16,1.42,.01),(8.65,'鑑定モードなら。',11,1.4,-.03),(9.85,'仕事運では、発信力がポイントですね。',16,1.7,-.01),(12.9,'恋愛のことで相談できますか？',14,1.45,.02),(15.05,'もちろんです。占術データをもとに、一緒に考えます。',16,2.05,-.01),(18.7,'無料で試せる体験アプリもあります。',11,1.48,-.03),(21.25,'鑑定モードも、相談モードも。AI占い for AI。',11,1.58,-.03)]
def post(p,ps,q=None):
 u=B+p+'?'+urllib.parse.urlencode(ps);b=None if q is None else json.dumps(q,ensure_ascii=False).encode();r=urllib.request.Request(u,data=b,method='POST');r.add_header('Content-Type','application/json');return urllib.request.urlopen(r,timeout=120).read()
for i,(st,text,sp,speed,pitch) in enumerate(L):
 q=json.loads(post('/audio_query',{'text':text,'speaker':sp}));q.update(speedScale=speed,pitchScale=pitch,intonationScale=1.06);p=R/f'voice_{i:02}.wav';p.write_bytes(post('/synthesis',{'speaker':sp},q))
 with wave.open(str(p),'rb') as w:print(i,round(w.getnframes()/w.getframerate(),2))
