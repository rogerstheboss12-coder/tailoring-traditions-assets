import sys, torch, numpy as np, scipy.io.wavfile
from transformers import AutoProcessor, MusicgenForConditionalGeneration
PROMPTS = [
 "1940s big band swing ballad, crooner era orchestra, lush strings, muted trumpet melody, brushed drums, walking upright bass, warm vintage recording, instrumental",
 "upbeat 1940s swing big band, bright brass section, clarinet lead, swinging hi-hat, walking bass, vintage ballroom recording, instrumental",
 "1950s Las Vegas lounge swing, smooth saxophone, finger snaps, jazz piano, upright bass, cocktail hour, warm analog recording, instrumental",
 "romantic 1940s orchestral pop ballad, sweeping strings, soft french horn, gentle harp, slow tempo, vintage crooner backing track, instrumental",
 "mid-tempo 1950s swing with big band horns, punchy trombones, swinging ride cymbal, confident and classy, vintage recording, instrumental",
 "smoky late night jazz club trio 1940s, brushed snare, upright bass, mellow piano, soft muted trumpet, vintage vinyl warmth, instrumental",
 "1950s doo-wop era slow ballad backing, soft saxophone, gentle piano triplets, upright bass, warm vintage recording, instrumental",
 "jaunty 1930s swing, stride piano, clarinet and trumpet, banjo rhythm, upright bass, old-time dance hall recording, instrumental",
 "elegant 1940s cocktail piano jazz, solo piano with soft upright bass and brushes, sophisticated hotel lounge, vintage recording, instrumental",
 "breezy 1950s swing with vibraphone, muted trumpet, light bongos, upright bass, poolside resort mood, warm analog recording, instrumental",
 "bold 1950s big band swing intro, brass fanfare, driving rhythm section, saxophone section riffs, glamorous, vintage recording, instrumental",
 "tender 1940s string orchestra serenade, solo violin melody, soft woodwinds, slow romantic waltz feel, vintage film soundtrack recording, instrumental",
]
i = int(sys.argv[1]); secs = float(sys.argv[2])
proc = AutoProcessor.from_pretrained("facebook/musicgen-small")
model = MusicgenForConditionalGeneration.from_pretrained("facebook/musicgen-small")
torch.manual_seed(1000 + i)
inp = proc(text=[PROMPTS[i]], padding=True, return_tensors="pt")
audio = model.generate(**inp, do_sample=True, guidance_scale=3.0, max_new_tokens=int(secs * 50))
sr = model.config.audio_encoder.sampling_rate
a = audio[0, 0].float().numpy(); a = a / max(1e-6, np.abs(a).max()) * 0.9
scipy.io.wavfile.write(f"track_{i:02d}.wav", sr, (a * 32767).astype(np.int16))
print("wrote", i, len(a) / sr)
