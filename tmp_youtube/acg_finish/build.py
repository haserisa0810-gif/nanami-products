from pathlib import Path
import math, subprocess, wave
import numpy as np

R = Path(__file__).parent
FF = Path(r"C:\tmp\acg-video-deps\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe")
SRC = Path(r"C:\Users\haser\dev\YouTube\ACG アストロカートグラフィ 動画\ACG_15s_neko_base.mp4")
OUT = R / "ACG_縦動画_完成版_15秒.mp4"

# Light original BGM: airy pulse, no external copyrighted material.
sr, duration = 44100, 15
t = np.arange(sr * duration) / sr
env = 0.55 + 0.45 * np.sin(2 * np.pi * 0.28 * t) ** 2
music = (0.055 * env * (np.sin(2*np.pi*110*t) + .45*np.sin(2*np.pi*165*t) + .25*np.sin(2*np.pi*220*t)))
for beat in np.arange(0, duration, .5):
    x = t - beat
    music += .055 * np.exp(-np.maximum(x,0)*16) * (x >= 0) * np.sin(2*np.pi*880*x)
music = np.clip(music, -.9, .9)
with wave.open(str(R / "bgm_original.wav"), "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
    w.writeframes((music * 32767).astype("<i2").tobytes())

font = r"C\:/Windows/Fonts/YuGothB.ttc"
closed = "[1:v]scale=1080:1920,setsar=1[closed]"
opened = "[2:v]scale=1080:1920,setsar=1[opened]"
filters = (
    "[0:v]trim=0:10.35,setpts=PTS-STARTPTS[v0];" + closed + ";" + opened + ";"
    "[opened][closed]overlay=enable='lt(mod(t,0.34),0.11)',trim=duration=3.15,setpts=PTS-STARTPTS," 
    f"drawtext=fontfile='{font}':text='nanami-astro 編集長':fontcolor=#F2C04B:fontsize=34:x=62:y=1240," 
    f"drawtext=fontfile='{font}':text='あなたにも、自分だけの地図があります。':fontcolor=white:fontsize=48:x=(w-text_w)/2:y=1320:box=1:boxcolor=#08142ACC:boxborderw=24[v1];"
    "[0:v]trim=13.50:15,setpts=PTS-STARTPTS," 
    f"drawtext=fontfile='{font}':text='AI占い for AI':fontcolor=white:fontsize=54:x=(w-text_w)/2:y=1450," 
    f"drawtext=fontfile='{font}':text='体験アプリ公開中':fontcolor=#D9C77A:fontsize=30:x=(w-text_w)/2:y=1530[v2];"
    "[v0][v1][v2]concat=n=3:v=1:a=0,format=yuv420p[v];"
    "[3:a]volume=.58[bg];[4:a]adelay=350|350[a0];[5:a]adelay=4050|4050[a1];[6:a]adelay=10380|10380[a2];"
    "[bg][a0][a1][a2]amix=inputs=4:duration=first:normalize=0,alimiter=limit=.94[a]"
)
cmd = [str(FF), "-y", "-i", str(SRC), "-loop", "1", "-i", str(R/"editor_closed.png"), "-loop", "1", "-i", str(R/"editor_open.png"),
       "-i", str(R/"bgm_original.wav"), "-i", str(R/"voice_0.wav"), "-i", str(R/"voice_1.wav"), "-i", str(R/"voice_2.wav"),
       "-filter_complex", filters, "-map", "[v]", "-map", "[a]", "-t", "15", "-r", "30", "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(OUT)]
subprocess.run(cmd, check=True)
print(OUT)
