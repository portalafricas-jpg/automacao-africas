# Teste do HyperFrames (aprovado por Washington em 28/11/2026). NÃO PUBLICA NADA.
# Monta dois Reels da mesma matéria ("Agro e indústria na rota Brasil-África na Expo África Brasil"):
#   1) ATUAL: telas paradas do video.py (o jeito que o robô faz hoje);
#   2) NOVO: HTML animado renderizado pelo HyperFrames (gratuito, Apache 2.0), seguindo o manual-estilo-video.md.
# Os dois saem em -14 LUFS. Gera também a versão lado a lado, confere tudo e manda por e-mail para aprovação.

import html
import json
import os
import re
import shutil
import smtplib
import ssl
import subprocess
import sys
import unicodedata
from email.message import EmailMessage

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from PIL import Image, ImageEnhance, ImageFilter  # noqa: E402

import redes as R  # noqa: E402
import video as V  # noqa: E402

L, A, FPS = 1080, 1920, 30
SAIDA = os.path.join(RAIZ, "ensaio", "hyperframes")
PROJETO = os.path.join(RAIZ, "ensaio", "hyperframes-projeto")
MUSICA = os.path.join(RAIZ, "musicas", "afrobeat-1.mp3")
EMAIL = "portalafricas@gmail.com"
LIMITE_ANEXOS = 17 * 1024 * 1024   # o Gmail aceita 25 MB já convertidos; 17 MB de arquivo cabem com folga

MATERIA = {
    "titulo": "Agro e indústria na rota Brasil-África na Expo África Brasil",
    "categoria": "Mundo",
    "feed": os.path.join(RAIZ, "feeds", "mundo.xml"),
}
# Cada foto vem da pasta de origem com o nome da pessoa no arquivo; a conferência foto × nome usa isso.
PESSOAS = [
    {"nome": "Perez Ochieng", "arquivo": "perez-ochieng.jpg",
     "cargo": "CEO da Sacoma Global Foods Innovation", "pais": "QUÊNIA"},
    {"nome": "Fábio Guasti", "arquivo": "fabio-guasti.jpg",
     "cargo": "CEO da Zeepo Motors", "pais": "BRASIL"},
    {"nome": "Kupakwashe W. Midzi", "arquivo": "kupakwashe-midzi.jpg",
     "cargo": "Conselheiro de exportações da ZimTrade", "pais": "ZIMBÁBUE"},
]
PASTA_FOTOS = os.path.join(RAIZ, "assets", "materias", "expo")
CAPA = {"arquivo": "perez-ochieng.jpg", "pessoa": "Perez Ochieng"}  # mesma foto da capa da matéria, sem o resto do cartaz

# tempos do vídeo novo (segundos)
T_GANCHO, T_PESSOA, T_PAINEL, T_FINAL = 5.0, 3.8, 3.6, 4.4


def log(t):
    print(t, flush=True)


def slug(t):
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def rodar(cmd, **kw):
    log("$ " + " ".join(cmd))
    return subprocess.run(cmd, check=True, **kw)


# ---------------- Conferências ----------------
def conferir_fotos_nomes():
    """Foto de um com nome de outro não pode acontecer: cada arquivo tem de ter o nome da pessoa."""
    erros = []
    for p in PESSOAS:
        partes = [s for s in slug(p["nome"]).split("-") if len(s) > 1]
        if not all(s in p["arquivo"] for s in (partes[0], partes[-1])):
            erros.append(f"{p['arquivo']} não corresponde a {p['nome']}")
        if not os.path.exists(os.path.join(PASTA_FOTOS, p["arquivo"])):
            erros.append(f"foto não encontrada: {p['arquivo']}")
    # a capa da matéria é a foto da Perez Ochieng (conferido na pasta de origem)
    if not os.path.exists(os.path.join(PASTA_FOTOS, CAPA["arquivo"])):
        erros.append(f"capa não encontrada: {CAPA['arquivo']}")
    return erros


def medir(caminho):
    """Durações de imagem e som, volume integrado (LUFS) e silêncios."""
    sond = json.loads(subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-of", "json", caminho],
        capture_output=True, text=True, check=True).stdout)
    dur = {s["codec_type"]: float(s.get("duration", 0)) for s in sond["streams"]}
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", caminho, "-af",
                        "ebur128=peak=true,silencedetect=n=-45dB:d=0.8", "-f", "null", "-"],
                       capture_output=True, text=True)
    txt = r.stderr
    lufs = re.findall(r"I:\s+(-?[\d.]+) LUFS", txt)
    silencios = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", txt)]
    return {"imagem": dur.get("video", 0), "som": dur.get("audio", 0),
            "lufs": float(lufs[-1]) if lufs else None, "silencios": silencios}


def conferir_video(nome, caminho):
    m = medir(caminho)
    problemas = []
    if abs(m["imagem"] - m["som"]) > 0.15:
        problemas.append(f"imagem ({m['imagem']:.2f}s) e som ({m['som']:.2f}s) com durações diferentes")
    if m["lufs"] is None or abs(m["lufs"] + 14) > 1.0:
        problemas.append(f"volume fora de -14 LUFS ({m['lufs']})")
    meio = [s for s in m["silencios"] if 0.3 < s < m["imagem"] - 2.5]
    if meio:
        problemas.append(f"silêncio no meio do vídeo em {meio}")
    log(f"Conferência {nome}: imagem {m['imagem']:.2f}s, som {m['som']:.2f}s, volume {m['lufs']} LUFS, "
        f"problemas: {problemas or 'nenhum'}")
    return m, problemas


# ---------------- Fotos ----------------
def preparar_foto(arquivo, destino, largura=L, altura=None):
    """Nitidez e contraste antes de ampliar (manual, item 5)."""
    img = Image.open(os.path.join(PASTA_FOTOS, arquivo)).convert("RGB")
    # as fotos de divulgação trazem restos do texto do cartaz nas bordas: recorta 10% de cada lado
    w, h = img.size
    img = img.crop((int(w * 0.10), 0, int(w * 0.90), h))
    img = R.melhorar_foto(img)
    if altura:
        img = R.cobrir(img, largura, altura)
    else:
        img = img.resize((largura, int(img.height * largura / img.width)), Image.LANCZOS)
    img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=60, threshold=3))
    img = ImageEnhance.Contrast(img).enhance(1.05)
    img.save(destino, quality=92)
    return img


def normalizar_volume(entrada, saida):
    """-14 LUFS em duas passadas (medir e aplicar), o padrão do Instagram e do YouTube."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", entrada, "-af",
                        "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True, check=True)
    dados = json.loads(r.stderr[r.stderr.rindex("{"):r.stderr.rindex("}") + 1])
    filtro = ("loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={input_i}:measured_TP={input_tp}:"
              "measured_LRA={input_lra}:measured_thresh={input_thresh}:offset={target_offset}:linear=true"
              ).format(**dados)
    rodar(["ffmpeg", "-y", "-v", "error", "-i", entrada, "-c:v", "copy", "-af", filtro, "-ar", "48000",
           "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", saida])


# ---------------- 1) Reels ATUAL (motor do video.py) ----------------
def fazer_atual():
    capa = R.melhorar_foto(Image.open(os.path.join(PASTA_FOTOS, CAPA["arquivo"])).convert("RGB"))
    cab = "EXPO ÁFRICA BRASIL"
    total = len(PESSOAS)
    telas = [(V.tela_materia(capa, "Agro e indústria na rota Brasil-África", "Mundo", 1, total + 1, cab, ""),
              V.DURACAO_GANCHO)]
    for i, p in enumerate(PESSOAS, 2):
        foto = R.melhorar_foto(Image.open(os.path.join(PASTA_FOTOS, p["arquivo"])).convert("RGB"))
        telas.append((V.tela_materia(foto, f"{p['nome']}, {p['cargo']}", p["pais"].capitalize(), i,
                                     total + 1, cab, ""), V.DURACAO_TELA))
    telas.append((V.tela_final(0), V.DURACAO_FINAL))
    bruto = os.path.join(SAIDA, "atual-bruto.mp4")
    V.montar_video(telas, MUSICA, bruto)
    final = os.path.join(SAIDA, "reels-atual.mp4")
    normalizar_volume(bruto, final)
    os.remove(bruto)
    return final


# ---------------- 2) Reels NOVO (HyperFrames) ----------------
CSS = """
@font-face { font-family: 'Poppins'; font-weight: 800; src: url('./assets/poppins-extra.ttf'); }
@font-face { font-family: 'Poppins'; font-weight: 700; src: url('./assets/poppins-forte.ttf'); }
@font-face { font-family: 'Poppins'; font-weight: 500; src: url('./assets/poppins-media.ttf'); }
html, body { margin: 0; background: #0e0e0e; }
#root { position: relative; width: 1080px; height: 1920px; overflow: hidden; background: #0e0e0e;
        font-family: 'Poppins', sans-serif; color: #fff; }
.clip { position: absolute; inset: 0; overflow: hidden; }
.barra { position: absolute; left: 0; top: 0; width: 1080px; height: 14px; background: #ffcc00; z-index: 9; }
.logo { position: absolute; left: 90px; top: 70px; width: 300px; z-index: 9; }
.foto-topo { position: absolute; left: 0; top: 0; width: 1080px; height: 1250px; object-fit: cover;
             transform-origin: 50% 35%; }
.preto-leve { position: absolute; inset: 0;
              background: linear-gradient(180deg, rgba(30,27,25,0) 0px, rgba(30,27,25,0) 760px,
                                          rgba(30,27,25,.85) 1080px, #1e1b19 1250px, #1e1b19 1920px); }
.selo { display: inline-block; background: #ffcc00; color: #0e0e0e; font-weight: 800; font-size: 36px;
        padding: 6px 22px; border-radius: 10px; letter-spacing: 1px; }
.gancho { position: absolute; left: 90px; right: 140px; top: 930px; }
.gancho .l { font-weight: 800; line-height: 1.05; text-transform: uppercase; }
.g1 { font-size: 108px; margin-top: 26px; }
.g2 { font-size: 108px; color: #ffcc00; }
.g3 { font-size: 66px; font-weight: 700 !important; text-transform: none !important; margin-top: 22px; }
.pessoa-foto { position: absolute; left: 0; top: 0; width: 1080px; height: 1350px; object-fit: cover;
               object-position: 50% 20%; transform-origin: 50% 30%; }
.degrade { position: absolute; inset: 0;
           background: linear-gradient(180deg, rgba(14,14,14,0) 0px, rgba(14,14,14,0) 820px,
                                       rgba(14,14,14,.9) 1200px, #0e0e0e 1350px, #0e0e0e 1920px); }
.cartao { position: absolute; left: 90px; right: 140px; top: 1150px; }
.cartao .nome { font-weight: 800; font-size: 86px; line-height: 1.04; margin-top: 22px; }
.cartao .cargo { font-weight: 700; font-size: 46px; line-height: 1.2; color: #ffcc00; margin-top: 16px; }
.traco { width: 140px; height: 10px; background: #ffcc00; margin-top: 26px; transform-origin: 0 50%; }
.palavra-fundo { position: absolute; left: 0; top: 330px; white-space: nowrap; font-weight: 800;
                 font-size: 260px; color: rgba(255,255,255,.07); letter-spacing: 6px; }
.painel { position: absolute; left: 90px; right: 140px; top: 560px; }
.painel .p1 { font-weight: 800; font-size: 170px; line-height: 1; color: #ffcc00; margin-top: 30px; }
.painel .p2 { font-weight: 800; font-size: 74px; line-height: 1.12; margin-top: 26px; }
.painel .p3 { font-weight: 700; font-size: 48px; line-height: 1.3; margin-top: 40px; color: #ddd; }
.caixa-app { position: absolute; left: 90px; right: 90px; top: 520px; border: 6px solid #ffcc00;
             border-radius: 34px; padding: 60px 56px 70px; background: #141414; }
.caixa-app .a1 { font-weight: 800; font-size: 132px; line-height: 1; }
.caixa-app .a2 { font-weight: 800; font-size: 132px; line-height: 1; color: #ffcc00; }
.caixa-app .a3 { font-weight: 700; font-size: 50px; margin-top: 30px; }
.lojas { position: relative; height: 150px; margin-top: 54px; overflow: hidden; }
.loja { position: absolute; left: 0; top: 0; height: 132px; padding: 0 44px; border-radius: 22px;
        background: #000; border: 4px solid #c8c8c8; display: flex; flex-direction: column;
        justify-content: center; }
.loja .s1 { font-weight: 500; font-size: 28px; color: #c8c8c8; }
.loja .s2 { font-weight: 800; font-size: 50px; line-height: 1.1; }
.site { position: absolute; left: 90px; top: 1330px; font-weight: 800; font-size: 64px; color: #fff; }
.site b { color: #ffcc00; }
"""


def e(t):
    return html.escape(t, quote=True)


def montar_html():
    """Escreve o projeto do HyperFrames: um index.html com as cenas e a linha do tempo GSAP."""
    if os.path.isdir(PROJETO):
        shutil.rmtree(PROJETO)
    pasta = os.path.join(PROJETO, "assets")
    os.makedirs(pasta)
    for tipo in ("extra", "forte", "media"):
        shutil.copy(R.caminho_fonte(tipo), os.path.join(pasta, f"poppins-{tipo}.ttf"))
    shutil.copy(R.ARQ_LOGO, os.path.join(pasta, "logo.png"))
    preparar_foto(CAPA["arquivo"], os.path.join(pasta, "capa.jpg"), L, 1250)
    for i, p in enumerate(PESSOAS):
        preparar_foto(p["arquivo"], os.path.join(pasta, f"pessoa{i}.jpg"), L, 1350)

    cenas, tl = [], []
    t = 0.0
    # Cena 1: gancho (foto nítida em cima, preto leve embaixo, gancho grande, zoom bem leve)
    cenas.append(f"""
    <div id="c-gancho" class="clip" data-start="{t}" data-duration="{T_GANCHO}" data-track-index="0">
      <img id="capa" class="foto-topo" src="./assets/capa.jpg" />
      <div class="preto-leve"></div>
      <div class="barra"></div>
      <img id="logo" class="logo" src="./assets/logo.png" alt="Áfricas Play" />
      <div class="gancho">
        <span id="g-selo" class="selo">EXPO ÁFRICA BRASIL</span>
        <div id="g1" class="l g1">Agro e indústria</div>
        <div id="g2" class="l g2">Brasil–África</div>
        <div id="g3" class="l g3">o que você precisa saber</div>
      </div>
    </div>""")
    tl += [f'tl.fromTo("#capa", {{scale: 1.0}}, {{scale: 1.06, duration: {T_GANCHO}, ease: "none"}}, {t});',
           f'tl.from("#g-selo", {{x: -60, opacity: 0, duration: 0.45, ease: "power3.out"}}, {t + 0.2});',
           f'tl.from("#g1", {{y: 70, opacity: 0, duration: 0.55, ease: "power3.out"}}, {t + 0.35});',
           f'tl.from("#g2", {{y: 70, opacity: 0, duration: 0.55, ease: "power3.out"}}, {t + 0.55});',
           f'tl.from("#g3", {{y: 40, opacity: 0, duration: 0.5, ease: "power2.out"}}, {t + 0.9});']
    t += T_GANCHO
    # Cenas 2 a 4: quem está na mesa (foto × nome conferidos)
    for i, p in enumerate(PESSOAS):
        ini = round(t, 2)
        cenas.append(f"""
    <div id="c-p{i}" class="clip" data-start="{ini}" data-duration="{T_PESSOA}" data-track-index="0">
      <img id="f{i}" class="pessoa-foto" src="./assets/pessoa{i}.jpg" alt="{e(p['nome'])}" />
      <div class="degrade"></div>
      <div id="w{i}" class="palavra-fundo">{e(p['pais'])}</div>
      <div class="cartao">
        <span id="s{i}" class="selo">{e(p['pais'])}</span>
        <div id="n{i}" class="nome">{e(p['nome'])}</div>
        <div id="t{i}" class="traco"></div>
        <div id="k{i}" class="cargo">{e(p['cargo'])}</div>
      </div>
    </div>""")
        tl += [f'tl.fromTo("#c-p{i}", {{clipPath: "inset(0 0 0 100%)"}}, {{clipPath: "inset(0 0 0 0%)", '
               f'duration: 0.45, ease: "power3.inOut"}}, {ini});',
               f'tl.fromTo("#f{i}", {{scale: 1.08}}, {{scale: 1.0, duration: {T_PESSOA}, ease: "none"}}, {ini});',
               f'tl.fromTo("#w{i}", {{x: 200}}, {{x: -260, duration: {T_PESSOA}, ease: "none"}}, {ini});',
               f'tl.from("#s{i}", {{x: -60, opacity: 0, duration: 0.4, ease: "power3.out"}}, {ini + 0.4});',
               f'tl.from("#n{i}", {{y: 60, opacity: 0, duration: 0.5, ease: "power3.out"}}, {ini + 0.5});',
               f'tl.from("#t{i}", {{scaleX: 0, duration: 0.4, ease: "power2.out"}}, {ini + 0.75});',
               f'tl.from("#k{i}", {{y: 30, opacity: 0, duration: 0.45, ease: "power2.out"}}, {ini + 0.85});']
        t += T_PESSOA
    # Cena 5: o painel (sem data dentro do vídeo; data só na legenda de cada rede)
    ini = round(t, 2)
    cenas.append(f"""
    <div id="c-painel" class="clip" data-start="{ini}" data-duration="{T_PAINEL}" data-track-index="0">
      <div class="barra"></div>
      <div id="w-painel" class="palavra-fundo" style="top:1300px">INDÚSTRIA · AGRO · MÁQUINAS</div>
      <div class="painel">
        <span id="p-selo" class="selo">EXPO ÁFRICA BRASIL</span>
        <div id="p1" class="p1">PAINEL 2</div>
        <div id="p2" class="p2">Indústria, agronegócio, equipamentos e manufatura</div>
        <div id="p3" class="p3">Quênia, Moçambique, Zimbábue e Brasil<br/>InvestSP, São Paulo</div>
      </div>
    </div>""")
    tl += [f'tl.fromTo("#c-painel", {{clipPath: "inset(100% 0 0 0)"}}, {{clipPath: "inset(0% 0 0 0)", '
           f'duration: 0.45, ease: "power3.inOut"}}, {ini});',
           f'tl.fromTo("#w-painel", {{x: 100}}, {{x: -700, duration: {T_PAINEL}, ease: "none"}}, {ini});',
           f'tl.from("#p-selo", {{x: -60, opacity: 0, duration: 0.4, ease: "power3.out"}}, {ini + 0.35});',
           f'tl.from("#p1", {{scale: 0.6, opacity: 0, duration: 0.55, ease: "back.out(1.6)"}}, {ini + 0.45});',
           f'tl.from("#p2", {{y: 50, opacity: 0, duration: 0.5, ease: "power3.out"}}, {ini + 0.75});',
           f'tl.from("#p3", {{y: 30, opacity: 0, duration: 0.45, ease: "power2.out"}}, {ini + 1.05});']
    t += T_PAINEL
    # Cena 6: tela final BAIXE O APP, selos das lojas em carrossel, app.africas.com.br
    ini = round(t, 2)
    cenas.append(f"""
    <div id="c-final" class="clip" data-start="{ini}" data-duration="{T_FINAL}" data-track-index="0">
      <div class="barra"></div>
      <div class="caixa-app" id="caixa">
        <div id="a1" class="a1">BAIXE</div>
        <div id="a2" class="a2">O APP</div>
        <div id="a3" class="a3">Áfricas Play, app oficial da Expo África Brasil</div>
        <div class="lojas">
          <div id="loja-g" class="loja"><span class="s1">DISPONÍVEL NO</span><span class="s2">Google Play</span></div>
          <div id="loja-a" class="loja"><span class="s1">BAIXAR NA</span><span class="s2">App Store</span></div>
        </div>
      </div>
      <div id="site" class="site">app.<b>africas</b>.com.br</div>
    </div>""")
    meio = ini + T_FINAL / 2
    tl += [f'tl.fromTo("#c-final", {{opacity: 0}}, {{opacity: 1, duration: 0.4}}, {ini});',
           f'tl.from("#caixa", {{scale: 0.9, opacity: 0, duration: 0.5, ease: "back.out(1.4)"}}, {ini + 0.15});',
           f'tl.from("#a1", {{x: -80, opacity: 0, duration: 0.4, ease: "power3.out"}}, {ini + 0.35});',
           f'tl.from("#a2", {{x: -80, opacity: 0, duration: 0.4, ease: "power3.out"}}, {ini + 0.5});',
           f'tl.from("#a3", {{opacity: 0, duration: 0.4}}, {ini + 0.7});',
           f'tl.fromTo("#loja-g", {{x: 900}}, {{x: 0, duration: 0.5, ease: "power3.out"}}, {ini + 0.8});',
           f'tl.fromTo("#loja-a", {{x: 900}}, {{x: 900, duration: 0.01}}, {ini});',
           f'tl.to("#loja-g", {{x: -900, duration: 0.5, ease: "power3.in"}}, {meio + 0.2});',
           f'tl.to("#loja-a", {{x: 0, duration: 0.5, ease: "power3.out"}}, {meio + 0.45});',
           f'tl.from("#site", {{y: 40, opacity: 0, duration: 0.45, ease: "power2.out"}}, {ini + 1.0});']
    t += T_FINAL
    total = round(t, 2)

    pagina = f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8" />
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>{CSS}</style>
</head>
<body>
<div id="root" data-composition-id="reels" data-start="0" data-duration="{total}" data-width="{L}" data-height="{A}">
  {''.join(cenas)}
</div>
<script>
  window.__timelines = window.__timelines || {{}};
  document.fonts.ready.then(function () {{
    const tl = gsap.timeline({{ paused: true }});
    {chr(10).join('    ' + x for x in tl)}
    tl.to({{}}, {{duration: 0.01}}, {total - 0.01});
    window.__timelines.reels = tl;
  }});
</script>
</body>
</html>
"""
    with open(os.path.join(PROJETO, "index.html"), "w", encoding="utf-8") as f:
        f.write(pagina)
    log(f"Projeto HyperFrames montado: {total}s")
    return total


def fazer_novo():
    total = montar_html()
    hf = ["npx", "-y", "hyperframes@latest"]
    subprocess.run(hf + ["doctor"], cwd=PROJETO)
    subprocess.run(hf + ["lint"], cwd=PROJETO)
    mudo = os.path.join(SAIDA, "novo-mudo.mp4")
    rodar(hf + ["render", "--output", mudo, "--fps", str(FPS), "--quality", "high"], cwd=PROJETO)
    bruto = os.path.join(SAIDA, "novo-bruto.mp4")
    rodar(["ffmpeg", "-y", "-v", "error", "-i", mudo, "-i", MUSICA, "-filter_complex",
           f"[1:a]atrim=0:{total},afade=t=in:d=0.5,afade=t=out:st={total - 1.8}:d=1.8[a]",
           "-map", "0:v", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
           "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "aac", "-b:a", "160k", "-t", str(total), bruto])
    final = os.path.join(SAIDA, "reels-novo-hyperframes.mp4")
    normalizar_volume(bruto, final)
    os.remove(bruto)
    os.remove(mudo)
    return final


# ---------------- Lado a lado ----------------
def lado_a_lado(atual, novo):
    fonte = R.caminho_fonte("extra")
    da, dn = medir(atual)["imagem"], medir(novo)["imagem"]
    total = max(da, dn)
    saida = os.path.join(SAIDA, "comparacao-lado-a-lado.mp4")

    def rotulo(txt):
        return (f"drawbox=x=0:y=0:w=iw:h=70:color=black@0.75:t=fill,"
                f"drawtext=fontfile={fonte}:text='{txt}':fontcolor=0xFFCC00:fontsize=40:x=(w-tw)/2:y=14")
    filtro = (f"[0:v]scale=540:960,tpad=stop_mode=clone:stop_duration={total - da + 0.1:.2f},{rotulo('ATUAL')}[a];"
              f"[1:v]scale=540:960,tpad=stop_mode=clone:stop_duration={total - dn + 0.1:.2f},{rotulo('NOVO (HyperFrames)')}[b];"
              f"[a][b]hstack=inputs=2[v]")
    rodar(["ffmpeg", "-y", "-v", "error", "-i", atual, "-i", novo, "-filter_complex", filtro,
           "-map", "[v]", "-map", "1:a", "-c:v", "libx264", "-preset", "veryfast", "-crf", "24",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-t", f"{dn:.2f}", saida])
    return saida


# ---------------- E-mail ----------------
def enviar_email(arquivos, relatorio):
    senha = (os.environ.get("GMAIL_SENHA_APP") or "").replace(" ", "").strip()
    if not senha:
        log("Sem GMAIL_SENHA_APP: e-mail não enviado.")
        return False
    msg = EmailMessage()
    msg["From"] = f"Robô de vídeo · Áfricas Play <{EMAIL}>"
    msg["To"] = EMAIL
    msg["Subject"] = "Prévia para aprovação: Reels atual × Reels novo (HyperFrames)"
    anexados, fora, soma = [], [], 0
    escolhidos = []
    for c in arquivos:
        tam = os.path.getsize(c)
        if soma + tam <= LIMITE_ANEXOS:
            escolhidos.append(c)
            anexados.append(os.path.basename(c))
            soma += tam
        else:
            fora.append(os.path.basename(c))
    corpo = [
        "Olá, Washington.",
        "",
        "Segue o teste do HyperFrames com a matéria \"Agro e indústria na rota Brasil-África na Expo África Brasil\" (Mundo).",
        "Nada foi publicado. É só a prévia para você comparar.",
        "",
        "Anexos:",
        "- comparacao-lado-a-lado.mp4: os dois juntos (esquerda: atual; direita: novo).",
        "- reels-novo-hyperframes.mp4: o vídeo novo, em tamanho de Reels.",
        "- reels-atual.mp4: o vídeo do jeito que o robô faz hoje.",
    ]
    if fora:
        corpo += ["", "Não couberam no e-mail (estão guardados no GitHub, galho midia, pasta ensaio/hyperframes): "
                  + ", ".join(fora)]
    corpo += ["", "Conferência automática:"] + relatorio + [
        "",
        "Para aprovar, é só responder \"sim\" na conversa com o Claude. Se quiser ajustes, diga o que mudar.",
        "",
        "Robô de vídeo do Áfricas Play",
    ]
    msg.set_content("\n".join(corpo))
    for c in escolhidos:
        with open(c, "rb") as f:
            msg.add_attachment(f.read(), maintype="video", subtype="mp4", filename=os.path.basename(c))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context(), timeout=120) as smtp:
        smtp.login(EMAIL, senha)
        smtp.send_message(msg)
    log(f"E-mail enviado para {EMAIL} com: {', '.join(anexados)}")
    return True


def main():
    os.makedirs(SAIDA, exist_ok=True)
    erros_fotos = conferir_fotos_nomes()
    if erros_fotos:
        raise SystemExit("Foto × nome com problema: " + "; ".join(erros_fotos))
    log("Foto × nome: conferido (" + ", ".join(f"{p['arquivo']} = {p['nome']}" for p in PESSOAS)
        + f"; capa {CAPA['arquivo']} = {CAPA['pessoa']})")

    atual = fazer_atual()
    novo = fazer_novo()
    comp = lado_a_lado(atual, novo)

    relatorio = ["- Foto × nome: conferido. " + "; ".join(f"{p['nome']} = {p['arquivo']}" for p in PESSOAS) + "."]
    tudo_ok = True
    for nome, c in (("Reels atual", atual), ("Reels novo", novo)):
        m, prob = conferir_video(nome, c)
        tudo_ok = tudo_ok and not prob
        relatorio.append(f"- {nome}: {m['imagem']:.1f} s de imagem e {m['som']:.1f} s de som, volume {m['lufs']} LUFS"
                         + (". Tudo certo." if not prob else ". ATENÇÃO: " + "; ".join(prob)))
    with open(os.path.join(SAIDA, "relatorio.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(relatorio) + "\n")
    log("\n".join(relatorio))
    enviar_email([comp, novo, atual], relatorio)
    if not tudo_ok:
        log("ATENÇÃO: a conferência achou problema (detalhes acima e no e-mail).")


if __name__ == "__main__":
    main()
