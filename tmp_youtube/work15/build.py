from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import wave,subprocess,numpy as np
R=Path(__file__).parent;W,H,FPS,D=1080,1920,30,15;F=Path(r'C:\tmp\youtube-video-deps\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe')
B=[0,3.1,6.5,12.0];L=[(.3,'主人公','頑張っても評価されなくて。転職すべきかな。'),(3.2,'AI占い師 ルナ','生まれ持った配置では、丁寧に積み上げるタイプ。'),(6.6,'AI占い師 ルナ','でも成果が伝わりにくい傾向も。今の星なら、まず報告の仕方を一緒に整えましょう。'),(12.15,'主人公','まず、伝え方から変えてみます。')]
def ft(n,b=0):return ImageFont.truetype(r'C:\Windows\Fonts\YuGothB.ttc' if b else r'C:\Windows\Fonts\YuGothM.ttc',n)
def fit(im):
 s=max(W/im.width,H/im.height);im=im.resize((round(im.width*s),round(im.height*s)),Image.Resampling.LANCZOS);return im.crop(((im.width-W)//2,(im.height-H)//2,(im.width+W)//2,(im.height+H)//2)).convert('RGBA')
S=[fit(Image.open(R/f'scene{i}.png')) for i in range(1,5)];dur=[]
for i in range(4):
 with wave.open(str(R/f'voice_{i}.wav'),'rb') as w:dur.append(w.getnframes()/w.getframerate())
O=R/'frames';O.mkdir(exist_ok=True);sf=ft(43,1);tf=ft(54,1);mf=ft(31,1)
def wrap(d,x,f,m):
 a=[];c=''
 for z in x:
  if d.textbbox((0,0),c+z,font=f)[2]>m and c:a.append(c);c=z
  else:c+=z
 return a+[c]
for k in range(D*FPS):
 t=k/FPS;si=max(i for i,b in enumerate(B) if t>=b);im=S[si].copy()
 if si and t-B[si]<.18:im=Image.blend(S[si-1],im,(t-B[si])/.18)
 d=ImageDraw.Draw(im,'RGBA');d.rectangle((0,0,W,215),fill=(8,4,28,155));d.rectangle((0,1430,W,H),fill=(8,4,28,185));d.text((50,45),'AI占い for AI',font=tf,fill='white')
 labs=['仕事の悩み','出生図＋仕事傾向','現在のトランジット','次の一歩'];lab=labs[si];bb=d.textbbox((0,0),lab,font=mf);d.rounded_rectangle((52,120,94+bb[2],180),20,fill=(37,160,190,235));d.text((72,130),lab,font=mf,fill='white')
 ac=None
 for i,(st,who,tx) in enumerate(L):
  if st<=t<=st+dur[i]:ac=(who,tx)
 if ac:
  who,tx=ac;ls=wrap(d,tx,sf,940);d.text((52,1475),who,font=mf,fill=(255,220,150));d.rounded_rectangle((38,1530,1042,1560+64*len(ls)),28,fill=(8,4,28,225),outline=(100,210,230,160),width=2)
  for j,x in enumerate(ls):bb=d.textbbox((0,0),x,font=sf);d.text(((W-bb[2])/2,1550+j*64),x,font=sf,fill='white')
 if t>13.7:
  f=ft(34,1);x='答えを決めつけず、合う行動を一緒に。';bb=d.textbbox((0,0),x,font=f);d.rounded_rectangle((90,1760,990,1860),28,fill=(91,48,175,235));d.text(((W-bb[2])/2,1790),x,font=f,fill='white')
 im.convert('RGB').save(O/f'f{k:04}.jpg',quality=91)
sr=44100;n=D*sr;t=np.arange(n)/sr;y=sum(np.sin(2*np.pi*f*t)*.01 for f in (174.6,220,261.6));pcm=np.int16(y*32767)
with wave.open(str(R/'music.wav'),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(sr);w.writeframes(pcm.tobytes())
ins=['-framerate',str(FPS),'-i',str(O/'f%04d.jpg'),'-i',str(R/'music.wav')];fs=['[1:a]volume=.2[m]'];pads=['[m]']
for i,(st,_,_) in enumerate(L):ins+=['-i',str(R/f'voice_{i}.wav')];q=round(st*1000);fs.append(f'[{i+2}:a]adelay={q}|{q},volume=1.15[v{i}]');pads.append(f'[v{i}]')
fs.append(''.join(pads)+f'amix=inputs={len(pads)}:duration=first:normalize=0,alimiter=limit=.95[a]')
subprocess.run([str(F),'-y']+ins+['-filter_complex',';'.join(fs),'-map','0:v','-map','[a]','-t','15','-c:v','libx264','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-movflags','+faststart',str(R/'AI占いforAI_仕事編_15秒.mp4')],check=True)
