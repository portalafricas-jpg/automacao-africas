# Teste do Radar (5 notícias) com HyperFrames, pedido por Washington em 28/11/2026. NÃO PUBLICA NADA.
# Escolhe as matérias do dia do mesmo jeito que o robô do Radar (video.py), monta:
#   1) ATUAL: o Radar como sai hoje (telas paradas);
#   2) NOVO: o mesmo Radar, com as mesmas matérias, fotos, manchetes e música, animado no HyperFrames.
# Os dois em -14 LUFS, lado a lado, conferidos e enviados por e-mail para aprovação.

import html
import os
import random
import shutil
import smtplib
import ssl
import subprocess
import sys
from email.message import EmailMessage

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)
sys.path.insert(0, AQUI)

from PIL import ImageEnhance, ImageFilter  # noqa: E402

import redes as R  # noqa: E402
import video as V  # noqa: E402
import teste_hyperframes as T  # noqa: E402

L, A, FPS = 1080, 1920, 30
SAIDA = os.path.join(RAIZ, "ensaio", "radar-hyperframes")
PROJETO = os.path.join(RAIZ, "ensaio", "radar-hyperframes-projeto")
T_GANCHO, T_MATERIA, T_FINAL = 4.4, 5.0, 4.0

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


def log(t):
    print(t, flush=True)


def e(t):
    return html.escape(t, quote=True)


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


def salvar_foto(img, destino):
    img = R.cobrir(img, L, A)
    img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=50, threshold=3))
    ImageEnhance.Contrast(img).enhance(1.04).save(destino, quality=92)


class MusicaFixa:
    """Guarda a música sorteada pelo Radar atual, para o novo usar a mesma."""
    escolhida = None

    def choice(self, seq):
        MusicaFixa.escolhida = random.choice(seq)
        return MusicaFixa.escolhida

    def __getattr__(self, nome):
        return getattr(random, nome)


def fazer_atual(posts, agora):
    V.random = MusicaFixa()
    bruto = os.path.join(SAIDA, "atual-bruto.mp4")
    escolhidas, dur = V.fazer_video(posts, False, agora, bruto)
    if not escolhidas:
        raise SystemExit("Hoje não há matérias suficientes para o Radar.")
    final = os.path.join(SAIDA, "radar-atual.mp4")
    T.normalizar_volume(bruto, final)
    os.remove(bruto)
    return escolhidas, final


def montar_html(escolhidas):
    if os.path.isdir(PROJETO):
        shutil.rmtree(PROJETO)
    pasta = os.path.join(PROJETO, "assets")
    os.makedirs(pasta)
    for tipo in ("extra", "forte", "media"):
        shutil.copy(R.caminho_fonte(tipo), os.path.join(pasta, f"poppins-{tipo}.ttf"))
    shutil.copy(R.ARQ_LOGO, os.path.join(pasta, "logo.png"))
    fotos = []
    for i, p in enumerate(escolhidas):
        img = R.melhorar_foto(V.foto_do_post(p))   # a mesma foto que o Radar atual usou
        salvar_foto(img, os.path.join(pasta, f"m{i}.jpg"))
        fotos.append(p.get("foto") or p["link"])
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
    # Tela final: Comente APP (o funil do Radar continua) e os selos das lojas em carrossel
    ini = round(t, 2)
    meio = ini + T_FINAL / 2
    cenas.append(f"""
    <div id="c-final" class="clip" data-start="{ini}" data-duration="{T_FINAL}" data-track-index="0">
      <div class="barra"></div>
      <img id="fl" class="final-logo" src="./assets/logo.png" alt="Áfricas Play" />
      <div class="final-txt">
        <div id="fa" class="f1">Quer ler as matérias completas?</div>
        <div id="fb" class="f2">Comente</div>
        <div id="fc" class="f3">APP</div>
        <div id="fd" class="f4">Receba os links no direct.</div>
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
<style>{T.CSS}{CSS_RADAR}</style>
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
    return total, fotos


def fazer_novo(escolhidas):
    total, fotos = montar_html(escolhidas)
    musica = MusicaFixa.escolhida or T.MUSICA
    hf = ["npx", "-y", "hyperframes@latest"]
    subprocess.run(hf + ["lint"], cwd=PROJETO)
    mudo = os.path.join(SAIDA, "novo-mudo.mp4")
    T.rodar(hf + ["render", "--output", mudo, "--fps", str(FPS), "--quality", "high"], cwd=PROJETO)
    bruto = os.path.join(SAIDA, "novo-bruto.mp4")
    T.rodar(["ffmpeg", "-y", "-v", "error", "-i", mudo, "-i", musica, "-filter_complex",
             f"[1:a]atrim=0:{total},afade=t=in:d=0.5,afade=t=out:st={total - 1.8}:d=1.8[a]",
             "-map", "0:v", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
             "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "aac", "-b:a", "160k", "-t", str(total), bruto])
    final = os.path.join(SAIDA, "radar-novo-hyperframes.mp4")
    T.normalizar_volume(bruto, final)
    os.remove(bruto)
    os.remove(mudo)
    return final, fotos, os.path.basename(musica)


def lado_a_lado(atual, novo):
    fonte = R.caminho_fonte("extra")
    da, dn = T.medir(atual)["imagem"], T.medir(novo)["imagem"]
    total = max(da, dn)
    saida = os.path.join(SAIDA, "radar-lado-a-lado.mp4")

    def rotulo(txt):
        return (f"drawbox=x=0:y=0:w=iw:h=70:color=black@0.75:t=fill,"
                f"drawtext=fontfile={fonte}:text='{txt}':fontcolor=0xFFCC00:fontsize=40:x=(w-tw)/2:y=14")
    filtro = (f"[0:v]scale=540:960,tpad=stop_mode=clone:stop_duration={total - da + 0.1:.2f},{rotulo('ATUAL')}[a];"
              f"[1:v]scale=540:960,tpad=stop_mode=clone:stop_duration={total - dn + 0.1:.2f},{rotulo('NOVO')}[b];"
              f"[a][b]hstack=inputs=2[v]")
    T.rodar(["ffmpeg", "-y", "-v", "error", "-i", atual, "-i", novo, "-filter_complex", filtro,
             "-map", "[v]", "-map", "1:a", "-c:v", "libx264", "-preset", "veryfast", "-crf", "24",
             "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-t", f"{total:.2f}", saida])
    return saida


def enviar_email(arquivos, relatorio, escolhidas):
    senha = (os.environ.get("GMAIL_SENHA_APP") or "").replace(" ", "").strip()
    if not senha:
        log("Sem GMAIL_SENHA_APP: e-mail não enviado.")
        return
    msg = EmailMessage()
    msg["From"] = f"Robô de vídeo · Áfricas Play <{T.EMAIL}>"
    msg["To"] = T.EMAIL
    msg["Subject"] = "Prévia para aprovação: Radar atual × Radar novo (HyperFrames)"
    escolhidos, fora, soma = [], [], 0
    for c in arquivos:
        tam = os.path.getsize(c)
        if soma + tam <= T.LIMITE_ANEXOS:
            escolhidos.append(c)
            soma += tam
        else:
            fora.append(os.path.basename(c))
    corpo = ["Olá, Washington.", "",
             "Segue o teste do Radar (5 notícias) com o visual novo do HyperFrames, com as matérias de hoje.",
             "Nada foi publicado. É só a prévia para você comparar.", "",
             "Para assistir: toque no anexo para abrir o vídeo (o Gmail mostra só a imagem parada até abrir).", "",
             "Anexos:",
             "- radar-lado-a-lado.mp4: os dois juntos (esquerda: atual; direita: novo).",
             "- radar-novo-hyperframes.mp4: o Radar novo, em tamanho de Reels.",
             "- radar-atual.mp4: o Radar do jeito que sai hoje.", "",
             "Matérias do teste:"] + [f"- {p.get('curta') or p['titulo']} ({p.get('categoria', '')})" for p in escolhidas]
    if fora:
        corpo += ["", "Não couberam no e-mail (estão no GitHub, galho midia, pasta ensaio/radar-hyperframes): "
                  + ", ".join(fora)]
    corpo += ["", "Conferência automática:"] + relatorio + [
        "", "Para aprovar, é só responder \"sim\" na conversa com o Claude.", "", "Robô de vídeo do Áfricas Play"]
    msg.set_content("\n".join(corpo))
    for c in escolhidos:
        with open(c, "rb") as f:
            msg.add_attachment(f.read(), maintype="video", subtype="mp4", filename=os.path.basename(c))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context(), timeout=120) as smtp:
        smtp.login(T.EMAIL, senha)
        smtp.send_message(msg)
    log(f"E-mail enviado para {T.EMAIL}")


def main():
    os.makedirs(SAIDA, exist_ok=True)
    posts = R.ler_json(R.ARQ_POSTS, [])
    agora = R.agora_sp()
    escolhidas, atual = fazer_atual(posts, agora)
    novo, fotos, musica = fazer_novo(escolhidas)
    comp = lado_a_lado(atual, novo)
    relatorio = ["- Fotos: cada notícia usa a foto da própria matéria, a mesma nos dois vídeos:"]
    relatorio += [f"  {i}. {p.get('curta') or p['titulo']}: {f}" for i, (p, f) in enumerate(zip(escolhidas, fotos), 1)]
    relatorio.append(f"- Música: {musica} (a mesma nos dois).")
    for nome, c in (("Radar atual", atual), ("Radar novo", novo)):
        m, prob = T.conferir_video(nome, c)
        relatorio.append(f"- {nome}: {m['imagem']:.1f} s de imagem e {m['som']:.1f} s de som, volume {m['lufs']} LUFS"
                         + (". Tudo certo." if not prob else ". ATENÇÃO: " + "; ".join(prob)))
    with open(os.path.join(SAIDA, "relatorio.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(relatorio) + "\n")
    log("\n".join(relatorio))
    enviar_email([comp, novo, atual], relatorio, escolhidas)


if __name__ == "__main__":
    main()
