# Ferramentas de vídeo que rodam no GitHub (internet liberada):
# 1) transcrição da fala com tempo de cada palavra (faster-whisper)
# 2) máscara da pessoa (para letras passando por trás da cabeça) com MediaPipe
import glob, json, os, subprocess, urllib.request
import cv2, numpy as np
ENT, SAI = "video-ferramentas/entrada", "video-ferramentas/saida"
os.makedirs(SAI, exist_ok=True)
MODELO = "/tmp/selfie.tflite"
if not os.path.exists(MODELO):
    urllib.request.urlretrieve("https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_segmenter/float16/latest/selfie_segmenter.tflite", MODELO)
from faster_whisper import WhisperModel
import mediapipe as mp
whisper = WhisperModel("small", device="cpu", compute_type="int8")

def transcrever(v, base):
    segs, _ = whisper.transcribe(v, language="pt", word_timestamps=True, vad_filter=True)
    out, srt = [], []
    for i, s in enumerate(segs, 1):
        out.append({"inicio": round(s.start, 2), "fim": round(s.end, 2), "texto": s.text.strip(),
                    "palavras": [{"p": w.word.strip(), "i": round(w.start, 2), "f": round(w.end, 2)} for w in (s.words or [])]})
        t = lambda x: f"{int(x//3600):02d}:{int(x%3600//60):02d}:{int(x%60):02d},{int(x*1000%1000):03d}"
        srt.append(f"{i}\n{t(s.start)} --> {t(s.end)}\n{s.text.strip()}\n")
    json.dump(out, open(f"{SAI}/{base}_fala.json", "w"), ensure_ascii=False, indent=1)
    open(f"{SAI}/{base}_fala.srt", "w").write("\n".join(srt))

def mascara(v, base):
    BaseOptions = mp.tasks.BaseOptions
    opts = mp.tasks.vision.ImageSegmenterOptions(base_options=BaseOptions(model_asset_path=MODELO),
            running_mode=mp.tasks.vision.RunningMode.VIDEO, output_confidence_masks=True)
    seg = mp.tasks.vision.ImageSegmenter.create_from_options(opts)
    cap = cv2.VideoCapture(v); fps = cap.get(cv2.CAP_PROP_FPS) or 30
    tmp = f"/tmp/{base}_mask.avi"; wr = None; n = 0
    while True:
        ok, fr = cap.read()
        if not ok: break
        img = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(fr, cv2.COLOR_BGR2RGB))
        r = seg.segment_for_video(img, int(n * 1000 / fps)); n += 1
        m = (r.confidence_masks[0].numpy_view() * 255).astype(np.uint8)
        m = cv2.GaussianBlur(m, (7, 7), 0)
        if wr is None: wr = cv2.VideoWriter(tmp, cv2.VideoWriter_fourcc(*"MJPG"), fps, (m.shape[1], m.shape[0]), False)
        wr.write(m)
    wr.release(); cap.release()
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmp, "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p", f"{SAI}/{base}_mascara.mp4"], check=True)

for v in sorted(glob.glob(f"{ENT}/*.mp4")):
    base = os.path.splitext(os.path.basename(v))[0]
    if os.path.exists(f"{SAI}/{base}_fala.json"): continue
    print("processando", base)
    transcrever(v, base)
    mascara(v, base)
print("fim")
