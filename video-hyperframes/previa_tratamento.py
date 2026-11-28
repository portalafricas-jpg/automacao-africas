# Prévia do tratamento de foto + Radar novo (28/11/2026). NÃO PUBLICA NADA.
# Gera: 1) antes × depois de cada foto do Radar de hoje; 2) o Radar novo no HyperFrames com as fotos tratadas.
import glob
import io
import os
import random
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from PIL import Image, ImageDraw  # noqa: E402

import redes as R  # noqa: E402
import video as V  # noqa: E402
import hyperframes_radar  # noqa: E402

SAIDA = os.path.join(RAIZ, "ensaio", "previa-tratamento")


def antigo(post):
    """Como era: foto principal, recorte no meio e só nitidez."""
    img = V.abrir(post["foto"]) if post.get("foto") else None
    if img is None:
        return None
    esc = max(1080 / img.width, 1920 / img.height)
    img = img.resize((int(img.width * esc) + 1, int(img.height * esc) + 1), Image.LANCZOS)
    x, y = (img.width - 1080) // 2, (img.height - 1920) // 2
    return img.crop((x, y, x + 1080, y + 1920))


def main():
    os.makedirs(SAIDA, exist_ok=True)
    posts = R.ler_json(R.ARQ_POSTS, [])
    agora = R.agora_sp()
    escolhidas, fotos, pares = [], [], []
    for p in V.escolher(posts, 1, 9, agora):
        if len(escolhidas) == 5:
            break
        nova = V.foto_do_post(p)
        if nova is None:
            continue
        nova = R.melhorar_foto(nova)
        escolhidas.append(p)
        fotos.append(nova)
        pares.append((antigo(p), R.cobrir(nova, 1080, 1920), p["titulo"]))
    # quadro antes × depois
    lado = 360
    quadro = Image.new("RGB", (2 * lado + 30, len(pares) * (640 + 60)), (14, 14, 14))
    d = ImageDraw.Draw(quadro)
    f = R.fonte("forte", 24)
    for i, (a, b, t) in enumerate(pares):
        y = i * 700
        d.text((10, y + 8), t[:58], font=f, fill=(255, 204, 0))
        if a is not None:
            quadro.paste(a.resize((lado, 640)), (0, y + 50))
        quadro.paste(b.resize((lado, 640)), (lado + 30, y + 50))
        d.text((10, y + 652), "ANTES", font=f, fill=(255, 255, 255))
        d.text((lado + 40, y + 652), "DEPOIS", font=f, fill=(255, 255, 255))
    quadro.save(os.path.join(SAIDA, "fotos-antes-depois.jpg"), quality=88)
    curtas = V.manchetes_curtas([p["titulo"] for p in escolhidas])
    escolhidas = [dict(p, curta=c) for p, c in zip(escolhidas, curtas)]
    musica = random.choice(sorted(glob.glob(os.path.join(RAIZ, "musicas", "afrobeat-*.mp3"))))
    dur = hyperframes_radar.gerar(escolhidas, fotos, musica, os.path.join(SAIDA, "radar-novo-tratado.mp4"))
    print(f"Prévia pronta: {len(escolhidas)} matérias, {dur:.1f}s", flush=True)


if __name__ == "__main__":
    main()
