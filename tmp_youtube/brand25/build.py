from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import wave,subprocess,numpy as np
R=Path(__file__).parent;W,H,FPS,D=1080,1920,30,25;F=Path(r'C:\tmp\youtube-video-deps\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe')
B=[0,4.25,8.45,12.7,18.5];L=[(.3,'編集長','AIに、生年月日だけ渡して占わせていませんか？'),(2.95,'AI','情報が、足りません。'),(4.35,'編集長','AI占い for AIは違います。計算ファースト。'),(7.35,'AI','理解しました！'),(8.65,'編集長','鑑定モードなら。'),(9.85,'AI','仕事運では、発信力がポイントですね。'),(12.9,'相談者','恋愛のことで相談できますか？'),(15.05,'AI','もちろんです。占術データをもとに、一緒に考えます。'),(18.7,'編集長','無料で試せる体験アプリもあります。'),(21.25,'編集長','鑑定モードも、相談モードも。AI占い for AI。')]
def ft(n,b=0):return ImageFont.truetype(r'C:\Windows\Fonts\YuGothB.ttc' if b else r'C:\Windows\Fonts\YuGothM.ttc',n)
def fit(im):
 s=max(W/im.width,H/im.height);im=im.resize((round(im.width*s),round(im.height*s)),Image.Resampling.LANCZOS);return im.crop(((im.width-W)//2,(im.height-H)//2,(im.width+W)//2,(im.height+H)//2)).convert('RGBA')
S=[fit(Image.open(R/f'scene{i}.png')) for i in range(1,6)];dur=[]
for i in range(len(L)):
 with wave.open(str(R/f'voice_{i:02}.wav'),'rb') as w:dur.append(w.getnframes()/w.getframerate())
O=R/'frames';O.mkdir(exist_ok=True);sf=ft(43,1);tf=ft(54,1);mf=ft(34,1)
def wrap(d,x,f,m):
 a=[];c=''
 for z in x:
  if d.textbbox((0,0),c+z,font=f)[2]>m and c:a.append(c);c=z
  else:c+=z
 return a+[c]
for k in range(D*FPS):
 t=k/FPS;si=max(i for i,b in enumerate(B) if t>=b);im=S[si].copy()
 if si and t-B[si]<.18:im=Image.blend(S[si-1],im,(t-B[si])/.18)
 d=ImageDraw.Draw(im,'RGBA');d.rectangle((0,0,W,220),fill=(2,9,25,150));d.rectangle((0,1430,W,H),fill=(2,7,22,175));d.text((50,45),'AI占い for AI',font=tf,fill='white')
 labs=['情報不足','計算ファースト','鑑定モード','相談モード','体験アプリ'];lab=labs[si];bb=d.textbbox((0,0),lab,font=mf);d.rounded_rectangle((52,120,96+bb[2],180),20,fill=(22,135,180,235));d.text((74,128),lab,font=mf,fill='white')
 ac=None
 for i,(st,who,tx) in enumerate(L):
  if st<=t<=st+dur[i]:ac=(who,tx)
 if ac:
  who,tx=ac;ls=wrap(d,tx,sf,940);d.rounded_rectangle((38,1530,1042,1560+64*len(ls)),28,fill=(2,7,22,225),outline=(220,175,65,180),width=2)
  d.text((55,1475),who,font=mf,fill=(255,220,135))
  for j,x in enumerate(ls):bb=d.textbbox((0,0),x,font=sf);d.text(((W-bb[2])/2,1550+j*64),x,font=sf,fill='white')
 if t>22.2:
  f=ft(35,1);x='計算ファースト。AIが読みやすい占術データ。';bb=d.textbbox((0,0),x,font=f);d.rounded_rectangle((60,1740,1020,1860),30,fill=(3,12,35,235),outline=(220,175,65,220),width=3);d.text(((W-bb[2])/2,1780),x,font=f,fill=(255,235,185))
 im.convert('RGB').save(O/f'f{k:04}.jpg',quality=91)
sr=44100;n=D*sr;t=np.arange(n)/sr;y=sum(np.sin(2*np.pi*f*t)*.01 for f in (130.8,196,261.6));pcm=np.int16(y*32767)
with wave.open(str(R/'music.wav'),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(sr);w.writeframes(pcm.tobytes())
ins=['-framerate',str(FPS),'-i',str(O/'f%04d.jpg'),'-i',str(R/'music.wav')];fs=['[1:a]volume=.2[m]'];pads=['[m]']
for i,(st,_,_) in enumerate(L):ins+=['-i',str(R/f'voice_{i:02}.wav')];q=round(st*1000);fs.append(f'[{i+2}:a]adelay={q}|{q},volume=1.15[v{i}]');pads.append(f'[v{i}]')
fs.append(''.join(pads)+f'amix=inputs={len(pads)}:duration=first:normalize=0,alimiter=limit=.95[a]')
subprocess.run([str(F),'-y']+ins+['-filter_complex',';'.join(fs),'-map','0:v','-map','[a]','-t','25','-c:v','libx264','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-movflags','+faststart',str(R/'AI占いforAI_ブランド紹介_25秒.mp4')],check=True)
