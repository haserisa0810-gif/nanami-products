# Etsy ACG demo video

Silent 15-second product demo for the Etsy listing. The source screenshots were captured from the English UI at `https://chart.nanami-astro.com/acg` with a 540 x 1080 browser viewport, then rendered at 1080 x 2160 (1:2).

The demo uses `tests/fixtures/oda_nobunaga_yaml_v1.yaml`, a repository-managed historical-person test fixture. It does not use purchaser data, admin screens, credentials, or API keys.

## Rebuild

Python 3, Pillow, and ffmpeg with libx264 are required.

```powershell
python media/etsy-acg-demo/build_video.py --ffmpeg C:/path/to/ffmpeg.exe
```

Output: `media/etsy-acg-demo/etsy_acg_demo_15s.mp4`

The script also decodes the completed MP4 with ffmpeg and fails if the stream is invalid.

## Etsy target

- 15 seconds
- 1080 x 2160, 1:2 portrait
- MP4 / H.264 / yuv420p
- no audio stream
- under 100 MB
