"""Render a 'detail' Reel: the full scene, then close-ups (tie, coat, shoes...) with a slow push-in,
dissolving between shots. Usage:
  python render_detail.py <image> <track.wav> <out.mp4> '<json list of [cx, cy, width] in image px>' [bottom_trim_frac]"""
import json, subprocess, sys, tempfile, os
from PIL import Image
img, wav, out, boxes = sys.argv[1:5]
trim = float(sys.argv[5]) if len(sys.argv) > 5 else 0.0
boxes = json.loads(boxes)
im = Image.open(img).convert("RGB")
W, H = im.size
H_use = int(H * (1 - trim))
SEG, XF = 3.0, 0.5
tmp = tempfile.mkdtemp()

def region(cx, cy, w):
    h = w * 16 / 9
    if h > H_use: h = H_use; w = h * 9 / 16
    if w > W: w = W; h = w * 16 / 9
    x = min(max(cx - w / 2, 0), W - w); y = min(max(cy - h / 2, 0), H_use - h)
    return int(x), int(y), int(w), int(h)

# shot 1: the whole scene (fit height, centered 9:16 crop); then each close-up
shots = [region(W / 2, H_use / 2, H_use * 9 / 16)] + [region(*b) for b in boxes]
clips = []
for i, (x, y, w, h) in enumerate(shots):
    crop = im.crop((x, y, x + w, y + h)).resize((2160, 3840), Image.LANCZOS)
    p = os.path.join(tmp, f"s{i}.png"); crop.save(p); clips.append(p)

n = len(clips); frames = int(SEG * 30)
inputs, chains = [], []
for i, p in enumerate(clips):
    inputs += ["-i", p]
    z = "1.0+0.06*on/%d" % frames if i else "1.0+0.04*on/%d" % frames
    chains.append(f"[{i}]zoompan=z='{z}':x='(iw-iw/zoom)/2':y='(ih-ih/zoom)/2':d={frames}:s=1080x1920:fps=30,setpts=PTS-STARTPTS[v{i}]")
cur, t = "v0", SEG - XF
for i in range(1, n):
    chains.append(f"[{cur}][v{i}]xfade=transition=fade:duration={XF}:offset={t:.2f}[x{i}]")
    cur = f"x{i}"; t += SEG - XF
total = SEG * n - XF * (n - 1)
filt = ";".join(chains) + f";[{cur}]format=yuv420p[v]"
cmd = ["ffmpeg", "-v", "error", "-y", *inputs, "-i", wav, "-filter_complex", filt, "-map", "[v]", "-map", f"{n}:a",
       "-af", f"loudnorm=I=-16:TP=-1.5,afade=t=in:d=0.6,afade=t=out:st={total-1.2:.2f}:d=1.2,aresample=44100",
       "-c:v", "libx264", "-crf", "20", "-preset", "medium", "-c:a", "aac", "-b:a", "160k",
       "-t", f"{total:.2f}", "-movflags", "+faststart", out]
subprocess.run(cmd, check=True)
print(f"{out}: {n} shots, {total:.1f}s")
