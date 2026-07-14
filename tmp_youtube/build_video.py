from pathlib import Path
import math, wave, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parent
W, H, FPS, DUR = 1080, 1920, 30, 15.0
FFMPEG = Path(r"C:\tmp\youtube-video-deps\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe")
BG = ROOT / "keyart.png"

LINES = [
    (0.35, 3.00, "mio", "鑑定モード、私の恋愛傾向まで分かるんだ。"),
    (3.25, 7.05, "mio", "ルナ、片思いの彼に、どうアプローチすればいい？"),
    (7.25, 12.20, "luna", "まず短い会話を増やして。彼の好きな話題から、自然に誘ってみて。"),
    (12.35, 14.75, "mio", "わかった。今日、話しかけてみる！"),
]

def font(size, bold=False):
    name = "YuGothB.ttc" if bold else "YuGothM.ttc"
    return ImageFont.truetype(str(Path(r"C:\Windows\Fonts") / name), size)

def synth_music(path):
    sr = 44100
    n = int(DUR * sr)
    t = np.arange(n) / sr
    y = np.zeros(n, dtype=np.float64)
    chords = [(261.63,329.63,392.00),(220.00,261.63,329.63),(174.61,220.00,261.63),(196.00,246.94,293.66)]
    for i in range(n):
        beat = int((i/sr)/3.75) % 4
        local = (i/sr) % 3.75
        env = min(1.0, local*3) * max(0.15, 1-local/4.3)
        for f in chords[beat]:
            y[i] += math.sin(2*math.pi*f*t[i]) * 0.018 * env
        y[i] += math.sin(2*math.pi*(880 if int(t[i]*2)%2==0 else 987.77)*t[i]) * 0.004
    y *= np.linspace(1, .25, n)
    pcm = np.int16(np.clip(y, -1, 1)*32767)
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(pcm.tobytes())

def load_amp(path):
    with wave.open(str(path),'rb') as w:
        sr=w.getframerate(); raw=w.readframes(w.getnframes())
    a=np.frombuffer(raw,dtype=np.int16).astype(float)/32768
    return sr,a

def wrap(draw, text, f, maxw):
    lines=[]; cur=""
    for c in text:
        if draw.textbbox((0,0),cur+c,font=f)[2] > maxw and cur:
            lines.append(cur); cur=c
        else: cur+=c
    if cur: lines.append(cur)
    return lines

def rounded_label(im, xy, text, fill, f):
    d=ImageDraw.Draw(im,'RGBA'); x,y=xy
    box=d.textbbox((0,0),text,font=f); tw=box[2]
    d.rounded_rectangle((x,y,x+tw+46,y+62),22,fill=fill)
    d.text((x+23,y+7),text,font=f,fill="white",stroke_width=1,stroke_fill=(0,0,0,50))

def make_frames():
    scene_paths=[BG,ROOT/'scene2_question.png',ROOT/'scene3_advice.png',ROOT/'scene4_resolve.png']
    scenes=[]
    for scene_path in scene_paths:
        src=Image.open(scene_path).convert('RGB')
        scale=max(W/src.width,H/src.height)
        still=src.resize((round(src.width*scale),round(src.height*scale)),Image.Resampling.LANCZOS)
        still=still.crop(((still.width-W)//2,(still.height-H)//2,(still.width+W)//2,(still.height+H)//2))
        scenes.append(still)
    amps={}
    for _,_,who,_ in LINES:
        p=ROOT/f"voice_{who}_{sum(1 for k in amps if k.startswith(who))}.wav"
    voice_files=sorted(ROOT.glob('voice_*.wav'))
    for p in voice_files: amps[p.stem]=load_amp(p)
    out=ROOT/'frames'; out.mkdir(exist_ok=True)
    titlef=font(60,True); smallf=font(32,True); subf=font(47,True)
    occurrence={'mio':0,'luna':0}
    line_keys=[]
    for a,b,who,txt in LINES:
        line_keys.append(f"voice_{who}_{occurrence[who]}"); occurrence[who]+=1
    for fi in range(int(DUR*FPS)):
        t=fi/FPS
        active=None
        for idx,(a,b,who,txt) in enumerate(LINES):
            if a<=t<=b:
                active=(idx,a,b,who,txt); break
        # Four purpose-built stills. Each shot is completely stable; only
        # a short crossfade at scene boundaries creates cinematic motion.
        boundaries=[0.0,3.15,7.15,12.25]
        scene_idx=max(i for i,boundary in enumerate(boundaries) if t>=boundary)
        fr=scenes[scene_idx]
        if scene_idx>0:
            fade=(t-boundaries[scene_idx])/0.22
            if fade<1.0:
                fr=Image.blend(scenes[scene_idx-1],fr,max(0.0,fade))
        fr=fr.convert('RGBA')
        d=ImageDraw.Draw(fr,'RGBA')
        # Dark readability gradients.
        overlay=Image.new('RGBA',(W,H),(0,0,0,0)); od=ImageDraw.Draw(overlay)
        for yy in range(300): od.rectangle((0,yy,W,yy+1),fill=(9,4,28,int(155*(1-yy/300))))
        for yy in range(420): od.rectangle((0,H-420+yy,W,H-419+yy),fill=(9,4,28,int(40+150*yy/420)))
        fr=Image.alpha_composite(fr,overlay); d=ImageDraw.Draw(fr,'RGBA')
        # Header and mode indicator.
        d.text((54,48),"AI占い for AI",font=titlef,fill="white",stroke_width=3,stroke_fill=(45,16,80,180))
        mode="占い鑑定モード" if t < 3.15 else "相談モード"
        rounded_label(fr,(58,130),mode,(116,70,210,225) if t<3.15 else (20,165,190,225),smallf)
        # Active line and speaker treatment. No artificial mouth layer.
        if active:
            idx,a,b,who,txt=active; key=line_keys[idx]
            # Speaker tag and subtitle bubble.
            speaker="ミオ" if who=='mio' else "AI占い師 ルナ"
            color=(183,110,230,245) if who=='mio' else (31,185,207,245)
            rounded_label(fr,(58,1460),speaker,color,smallf)
            lines=wrap(d,txt,subf,940)
            top=1542
            d.rounded_rectangle((42,top-22,1038,top+len(lines)*68+22),30,fill=(10,7,30,210),outline=(255,255,255,60),width=2)
            for li,s in enumerate(lines):
                bb=d.textbbox((0,0),s,font=subf); tx=(W-(bb[2]-bb[0]))//2
                d.text((tx,top+li*68),s,font=subf,fill='white',stroke_width=3,stroke_fill=(20,8,35,220))
        # End-card accent.
        if t>14.0:
            alpha=int(230*min(1,(t-14)/.45))
            d.rounded_rectangle((190,1760,890,1860),40,fill=(93,49,180,alpha),outline=(255,255,255,alpha//2),width=2)
            msg="占いを、次の一歩に。"
            bb=d.textbbox((0,0),msg,font=subf); d.text(((W-bb[2])/2,1780),msg,font=subf,fill=(255,255,255,alpha))
        fr.convert('RGB').save(out/f"f{fi:04d}.jpg",quality=91,subsampling=0)

def mux():
    # Each TTS clip is placed at its scripted start; music remains subtle.
    inputs=['-framerate',str(FPS),'-i',str(ROOT/'frames/f%04d.jpg'),'-i',str(ROOT/'music.wav')]
    filters=[]; mix=['[1:a]volume=0.28[m]']
    occurrence={'mio':0,'luna':0}
    idx=2
    for start,end,who,text in LINES:
        vf=ROOT/f"voice_{who}_{occurrence[who]}.wav"; occurrence[who]+=1
        inputs += ['-i',str(vf)]
        delay=round(start*1000)
        filters.append(f"[{idx}:a]adelay={delay}|{delay},volume=1.25[v{idx}]")
        mix.append(f"[v{idx}]"); idx+=1
    filters=['[1:a]volume=0.28[m]']+filters+["[m]"+''.join(mix[1:])+f"amix=inputs={len(LINES)+1}:duration=first:normalize=0,alimiter=limit=0.95[a]"]
    cmd=[str(FFMPEG),'-y']+inputs+['-filter_complex',';'.join(filters),'-map','0:v','-map','[a]','-t',str(DUR),'-c:v','libx264','-preset','medium','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-movflags','+faststart',str(ROOT/'AI占いforAI_15秒縦動画.mp4')]
    subprocess.run(cmd,check=True)

if __name__=='__main__':
    synth_music(ROOT/'music.wav'); make_frames(); mux()
