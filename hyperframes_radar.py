# Radar (5 notícias) animado no HyperFrames (aprovado por Washington em 28/11/2026).
# O robô das redes chama gerar(); se der qualquer erro, o video.py volta para o modelo antigo (ffmpeg).
import html
import os
import shutil
import subprocess

import redes as R

L, A, FPS = 1080, 1920, 30
PROJETO = os.path.join(R.PASTA, "ensaio", "radar-hyperframes-projeto")
T_GANCHO, T_MATERIA, T_FINAL = 4.4, 5.0, 4.0
HF = ["npx", "-y", "hyperframes@latest"]


def log(t):
    print(t, flush=True)


def e(t):
    return html.escape(t, quote=True)


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

CSS_RADAR = """
.materia-foto { position: absolute; inset: 0; width: 1080px; height: 1920px; object-fit: cover;
                transform-origin: 50% 40%; }
.fume { position: absolute; inset: 0;
        background: linear-gradient(180deg, rgba(14,14,14,0) 0px, rgba(14,14,14,0) 700px,
                                    rgba(14,14,14,.55) 1050px, rgba(14,14,14,.92) 1500px, #0e0e0e 1920px); }
.bloco { position: absolute; left: 90px; right: 150px; bottom: 470px; }
.manchete { font-weight: 800; font-size: 80px; line-height: 1.12; margin-top: 24px; }
.manchete .lin { display: block; overflow: hidden; }
.manchete .lin span { display: inline-block; }
.rodape { position: absolute; left: 90px; right: 150px; top: 1520px; display: flex;
          justify-content: space-between; align-items: center; }
.rodape img { width: 300px; }
.rodape .cont { font-weight: 800; font-size: 36px; color: #ffcc00; }
.progresso { position: absolute; left: 0; top: 14px; height: 8px; background: rgba(255,204,0,.85); width: 0; }
.final-txt { position: absolute; left: 110px; right: 110px; top: 560px; }
.final-txt .f1 { font-weight: 700; font-size: 74px; line-height: 1.2; }
.final-txt .f2 { font-weight: 800; font-size: 150px; line-height: 1; margin-top: 50px; }
.final-txt .f3 { font-weight: 800; font-size: 280px; line-height: .95; color: #ffcc00; }
.final-txt .f4 { font-weight: 700; font-size: 56px; margin-top: 40px; }
.final-logo { position: absolute; left: 110px; top: 300px; width: 420px; }
.lojas-final { position: absolute; left: 110px; top: 1480px; width: 860px; height: 150px; overflow: hidden; }
"""


def linhas_manchete(texto, max_chars=19):
    """Quebra a manchete em linhas curtas, para cada linha entrar com animação."""
    linhas, atual = [], ""
    for p in texto.split():
        if atual and len(atual) + 1 + len(p) > max_chars:
            linhas.append(atual)
            atual = p
        else:
            atual = f"{atual} {p}".strip()
    if atual:
        linhas.append(atual)
    return linhas


def montar_html(escolhidas, fotos_pil, youtube=False):
    if os.path.isdir(PROJETO):
        shutil.rmtree(PROJETO)
    pasta = os.path.join(PROJETO, "assets")
    os.makedirs(pasta)
    for tipo in ("extra", "forte", "media"):
        shutil.copy(R.caminho_fonte(tipo), os.path.join(pasta, f"poppins-{tipo}.ttf"))
    shutil.copy(R.ARQ_LOGO, os.path.join(pasta, "logo.png"))
    for i, img in enumerate(fotos_pil):
        R.cobrir(img, L, A).save(os.path.join(pasta, f"m{i}.jpg"), quality=92)   # rosto centralizado
    total_m = len(escolhidas)

    cenas, tl = [], []
    t = 0.0
    # Gancho: igual ao aprovado (foto nítida em cima, preto leve, gancho grande, zoom leve), com mais movimento
    cenas.append(f"""
    <img id="capa" class="clip foto-topo" src="./assets/m0.jpg" data-start="0" data-duration="{T_GANCHO}" data-track-index="1" style="object-position:50% 30%; z-index:1" />""")
    cenas.append(f"""
    <div id="c-gancho" class="clip" style="z-index:2" data-start="0" data-duration="{T_GANCHO}" data-track-index="0">
      <div class="preto-leve"></div>
      <div class="barra"></div>
      <img class="logo" src="./assets/logo.png" alt="Áfricas Play" />
      <div class="gancho" style="top:1000px">
        <div id="g1" class="l g1" style="font-size:140px">{total_m} NOTÍCIAS</div>
        <div id="g2" class="l g2" style="font-size:140px">PRETAS</div>
        <div id="g3" class="l g3" style="font-size:90px">que você precisa saber</div>
      </div>
    </div>""")
    tl += [f'tl.fromTo("#capa", {{scale: 1.0}}, {{scale: 1.06, duration: {T_GANCHO}, ease: "none"}}, 0);',
           'tl.from("#g1", {y: 70, opacity: 0, duration: 0.55, ease: "power3.out"}, 0.35);',
           'tl.from("#g2", {y: 70, opacity: 0, duration: 0.55, ease: "power3.out"}, 0.55);',
           'tl.from("#g3", {y: 40, opacity: 0, duration: 0.5, ease: "power2.out"}, 0.9);']
    t += T_GANCHO
    for i, p in enumerate(escolhidas):
        ini = round(t, 2)
        cat = (p.get("categoria") or "Notícia").upper()
        lins = "".join(f'<span class="lin"><span id="h{i}_{j}">{e(x)}</span></span>'
                       for j, x in enumerate(linhas_manchete(p.get("curta") or p["titulo"])))
        cenas.append(f"""
    <img id="f{i}" class="clip materia-foto" src="./assets/m{i}.jpg" alt="{e(p['titulo'])}" data-start="{ini}" data-duration="{T_MATERIA}" data-track-index="1" style="z-index:1" />
    <div id="c-m{i}" class="clip" data-start="{ini}" data-duration="{T_MATERIA}" data-track-index="0" style="z-index:2">
      <div class="fume"></div>
      <div class="barra"></div>
      <div class="bloco">
        <span id="s{i}" class="selo">{e(cat)}</span>
        <div id="m{i}" class="manchete">{lins}</div>
      </div>
      <div class="rodape"><img src="./assets/logo.png" alt="Áfricas Play" /><span class="cont">RADAR  ·  {i + 1}/{total_m}</span></div>
    </div>""")
        tl += [f'tl.fromTo(["#c-m{i}", "#f{i}"], {{clipPath: "inset(0 0 0 100%)"}}, {{clipPath: "inset(0 0 0 0%)", '
               f'duration: 0.45, ease: "power3.inOut"}}, {ini});',
               f'tl.fromTo("#f{i}", {{scale: 1.08}}, {{scale: 1.0, duration: {T_MATERIA}, ease: "none"}}, {ini});',
               f'tl.from("#s{i}", {{x: -60, opacity: 0, duration: 0.4, ease: "power3.out"}}, {ini + 0.4});',
               f'tl.from("#m{i}", {{y: 60, opacity: 0, duration: 0.5, ease: "power3.out"}}, {ini + 0.5});']
        t += T_MATERIA
    if youtube:   # no YouTube não há direct: os links ficam na descrição
        l1, l2, l3, l4 = "Quer ler as matérias completas?", "Links na", "descrição", "Baixe o app Áfricas Play"
    else:
        l1, l2, l3, l4 = "Quer ler as matérias completas?", "Comente", "APP", "Receba os links no direct."
    # Tela final: Comente APP (o funil do Radar continua) e os selos das lojas em carrossel
    ini = round(t, 2)
    meio = ini + T_FINAL / 2
    cenas.append(f"""
    <div id="c-final" class="clip" data-start="{ini}" data-duration="{T_FINAL}" data-track-index="0">
      <div class="barra"></div>
      <img id="fl" class="final-logo" src="./assets/logo.png" alt="Áfricas Play" />
      <div class="final-txt">
        <div id="fa" class="f1">{l1}</div>
        <div id="fb" class="f2">{l2}</div>
        <div id="fc" class="f3">{l3}</div>
        <div id="fd" class="f4">{l4}</div>
      </div>
      <div class="lojas-final">
        <div id="loja-g" class="loja"><span class="s1">DISPONÍVEL NO</span><span class="s2">Google Play</span></div>
        <div id="loja-a" class="loja"><span class="s1">BAIXAR NA</span><span class="s2">App Store</span></div>
      </div>
    </div>""")
    tl += [f'tl.fromTo("#c-final", {{opacity: 0}}, {{opacity: 1, duration: 0.4}}, {ini});',
           f'tl.from("#fl", {{y: -40, opacity: 0, duration: 0.4}}, {ini + 0.1});',
           f'tl.from("#fa", {{y: 40, opacity: 0, duration: 0.45, ease: "power3.out"}}, {ini + 0.25});',
           f'tl.from("#fb", {{x: -80, opacity: 0, duration: 0.4, ease: "power3.out"}}, {ini + 0.45});',
           f'tl.from("#fc", {{x: -80, opacity: 0, duration: 0.4, ease: "power3.out"}}, {ini + 0.6});',
           f'tl.from("#fd", {{opacity: 0, duration: 0.4}}, {ini + 0.9});',
           f'tl.fromTo("#loja-g", {{x: 900}}, {{x: 0, duration: 0.5, ease: "power3.out"}}, {ini + 0.8});',
           f'tl.fromTo("#loja-a", {{x: 900}}, {{x: 900, duration: 0.01}}, {ini});',
           f'tl.to("#loja-g", {{x: -900, duration: 0.5, ease: "power3.in"}}, {meio + 0.2});',
           f'tl.to("#loja-a", {{x: 0, duration: 0.5, ease: "power3.out"}}, {meio + 0.45});']
    t += T_FINAL
    total = round(t, 2)

    pagina = f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8" />
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>{CSS}{CSS_RADAR}</style>
</head>
<body>
<div id="root" data-composition-id="radar" data-start="0" data-duration="{total}" data-width="{L}" data-height="{A}">
  {''.join(cenas)}
</div>
<script>
  window.__timelines = window.__timelines || {{}};
  document.fonts.ready.then(function () {{
    const tl = gsap.timeline({{ paused: true }});
    {chr(10).join('    ' + x for x in tl)}
    tl.to({{}}, {{duration: 0.01}}, {total - 0.01});
    window.__timelines.radar = tl;
  }});
</script>
</body>
</html>
"""
    with open(os.path.join(PROJETO, "index.html"), "w", encoding="utf-8") as f:
        f.write(pagina)
    log(f"Projeto do Radar montado: {total}s, {total_m} matérias")
    return total




def gerar(escolhidas, fotos_pil, musica, saida, youtube=False):
    """Monta o Radar no HyperFrames, põe a música e deixa o volume em -14 LUFS. Devolve a duração."""
    total = montar_html(escolhidas, fotos_pil, youtube)
    mudo = saida + ".mudo.mp4"
    subprocess.run(HF + ["render", "--output", mudo, "--fps", str(FPS), "--quality", "high"], cwd=PROJETO,
                   check=True, timeout=600)
    bruto = saida + ".bruto.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", mudo, "-i", musica, "-filter_complex",
                    f"[1:a]atrim=0:{total},afade=t=in:d=0.5,afade=t=out:st={total - 1.8}:d=1.8[a]",
                    "-map", "0:v", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
                    "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "aac", "-b:a", "160k", "-t", str(total), bruto],
                   check=True)
    volume_14(bruto, saida)
    for f in (mudo, bruto):
        try:
            os.remove(f)
        except OSError:
            pass
    return total


def volume_14(entrada, saida):
    """-14 LUFS (padrão do Instagram e do YouTube), em duas passadas."""
    import json
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", entrada, "-af",
                        "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True, check=True)
    d = json.loads(r.stderr[r.stderr.rindex("{"):r.stderr.rindex("}") + 1])
    filtro = ("loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={input_i}:measured_TP={input_tp}:"
              "measured_LRA={input_lra}:measured_thresh={input_thresh}:offset={target_offset}:linear=true").format(**d)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", entrada, "-c:v", "copy", "-af", filtro, "-ar", "48000",
                    "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", saida], check=True)
