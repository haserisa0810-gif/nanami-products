import json,urllib.parse,urllib.request,wave
from pathlib import Path
R=Path(__file__).parent;B='http://127.0.0.1:50021'
L=[(.3,'頑張っても評価されなくて。転職すべきかな。',11,1.55,-.03),(3.2,'生まれ持った配置では、丁寧に積み上げるタイプ。',16,1.75,-.01),(6.6,'でも成果が伝わりにくい傾向も。今の星なら、まず報告の仕方を一緒に整えましょう。',16,2.05,-.01),(12.15,'まず、伝え方から変えてみます。',11,1.5,-.02)]
def post(p,ps,q=None):
 u=B+p+'?'+urllib.parse.urlencode(ps);b=None if q is None else json.dumps(q,ensure_ascii=False).encode();r=urllib.request.Request(u,data=b,method='POST');r.add_header('Content-Type','application/json');return urllib.request.urlopen(r,timeout=120).read()
for i,(st,text,sp,speed,pitch) in enumerate(L):
 q=json.loads(post('/audio_query',{'text':text,'speaker':sp}));q.update(speedScale=speed,pitchScale=pitch,intonationScale=1.06);p=R/f'voice_{i}.wav';p.write_bytes(post('/synthesis',{'speaker':sp},q))
 with wave.open(str(p),'rb') as w:print(i,round(w.getnframes()/w.getframerate(),2))
