"""Render the full-screen 'pan' Reel style: fill 1080x1920 with the art and pan
top->bottom (tall art, face first) or pull back from the faces (wider art), eased, with the post's music track.
Usage: python render_pan.py <image> <track.wav> <out.mp4>"""
import subprocess, sys
from PIL import Image
img, wav, out = sys.argv[1:4]
w, h = Image.open(img).size
T = 12
ease = "(1-cos(PI*t/%d))/2" % T
if w / h <= 9 / 16:   # tall: fit width, pan down from the top (faces/hats are at the top)
    vf = (f"scale=2160:-2:flags=lanczos,fps=30,"
          f"crop=2160:3840:0:'(ih-3840)*{ease}',scale=1080:1920:flags=lanczos")
else:                 # wider than 9:16: open tight on the faces (upper third) and pull back to the full scene
    vf = ("scale=-2:3840:flags=lanczos,crop=2160:3840,"
          "zoompan=z='1.55-0.55*(1-cos(PI*on/359))/2':x='(iw-iw/zoom)/2':y='(ih-ih/zoom)*0.05':d=360:s=1080x1920:fps=30")
loop = ["-loop", "1", "-t", str(T)] if w / h <= 9 / 16 else []
cmd = ["ffmpeg", "-v", "error", "-y", *loop, "-i", img, "-i", wav,
       "-filter_complex", f"[0]{vf},format=yuv420p[v]", "-map", "[v]", "-map", "1:a",
       "-af", "loudnorm=I=-16:TP=-1.5,afade=t=in:d=0.6,afade=t=out:st=10.8:d=1.2,aresample=44100",
       "-c:v", "libx264", "-crf", "20", "-preset", "medium", "-c:a", "aac", "-b:a", "160k",
       "-t", str(T), "-movflags", "+faststart", out]
subprocess.run(cmd, check=True)
