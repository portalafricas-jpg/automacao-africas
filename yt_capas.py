"""Troca a capa (miniatura) de vídeos do canal. Uso: python yt_capas.py pasta  (cada arquivo ID_DO_VIDEO.jpg)"""
import sys, os, requests, youtube
H = {"Authorization": "Bearer " + youtube.token()}
pasta = sys.argv[1]
for nome in sorted(os.listdir(pasta)):
    if not nome.endswith(".jpg"):
        continue
    vid = nome[:-4]
    with open(os.path.join(pasta, nome), "rb") as f:
        r = requests.post("https://www.googleapis.com/upload/youtube/v3/thumbnails/set",
                          headers={**H, "Content-Type": "image/jpeg"}, params={"videoId": vid}, data=f.read(), timeout=60)
    print(vid, "OK" if r.status_code == 200 else f"ERRO {r.status_code} {r.text[:200]}")
