# Reels do Áfricas Play: "Resumo do dia" (todo dia, 19h) e "A semana em 10 fatos" (domingo, 19h).
# Monta o vídeo com as fotos das matérias, manchetes, transições e música (ffmpeg, gratuito)
# e publica no Facebook (vídeo) e no Instagram (Reels). Aprovado em 23/11/2026.

import glob
import html
import io
import json
import os
import random
import re
import subprocess
import tempfile
import time
from datetime import datetime, timedelta, timezone

from PIL import Image, ImageDraw, ImageEnhance

import redes as R

L, A = 1080, 1920            # vídeo em pé (9:16)
FPS = 30
DURACAO_TELA = 4.0           # segundos por matéria
TRANSICAO = 0.6
DURACAO_FINAL = 4.0          # tela final do Comente APP
PASTA_MUSICAS = os.path.join(R.PASTA, "musicas")
TRANSICOES = ["fade", "slideleft", "smoothleft", "circleopen", "slideup", "fadeblack", "wipeleft"]
ORDEM = {"breaking": 0, "alta": 1, "parceiro": 2, "nota7": 3}
DIAS_SEMANA = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]


def log(t):
    R.log(t)


# ---------------- Escolha das matérias ----------------
def data_sp(iso):
    return datetime.fromisoformat(iso).astimezone(R.FUSO_SP)


def escolher(posts, dias, quantas, agora_sp):
    limite = agora_sp - timedelta(days=dias)
    if dias == 1:
        candidatas = [p for p in posts if p.get("tipo") != "reels" and p.get("publicado_em")
                      and R.dia_de_trabalho(data_sp(p["publicado_em"])) == R.dia_de_trabalho(agora_sp)]
    else:
        candidatas = [p for p in posts if p.get("tipo") != "reels" and p.get("publicado_em")
                      and data_sp(p["publicado_em"]) >= limite]
    vistos, unicas = set(), []
    for p in sorted(candidatas, key=lambda p: (ORDEM.get(p.get("prioridade"), 9), p["publicado_em"])):
        chave = R.normalizar(p["titulo"])
        if chave not in vistos:
            vistos.add(chave)
            unicas.append(p)
    return unicas[:quantas]


def foto_do_post(post):
    """Foto limpa da matéria: a guardada no registro ou, nas antigas, a imagem de compartilhamento da página."""
    url = post.get("foto") or ""
    if not url:
        try:
            pagina = R.baixar(post["link"]).decode("utf-8", errors="replace")
            achou = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', pagina) or \
                re.search(r'<meta[^>]+content="([^"]+)"[^>]+property="og:image"', pagina)
            url = html.unescape(achou.group(1)) if achou else ""
        except Exception:
            url = ""
    if not url:
        return None
    try:
        return Image.open(io.BytesIO(R.baixar(url))).convert("RGB")
    except Exception:
        return None


# ---------------- Telas ----------------
def tela_materia(foto, titulo, categoria, numero, total, cabecalho, data_txt):
    if foto is not None:
        img = R.cobrir(foto, L, A)
        img = ImageEnhance.Brightness(img).enhance(0.75)
        img = R.degrade_escuro(img, inicio=0.30)
    else:
        img = Image.new("RGB", (L, A), R.COR_FUNDO)
    d = ImageDraw.Draw(img)
    m = 90
    # faixa do topo
    d.rectangle((0, 0, L, 14), fill=R.COR_AMARELO)
    d.text((m, 150), cabecalho, font=R.fonte("extra", 58), fill=R.COR_AMARELO)
    d.text((m, 225), data_txt, font=R.fonte("media", 38), fill=R.COR_TEXTO)
    fc = R.fonte("extra", 46)
    cont = f"{numero}/{total}"
    d.text((L - m - d.textlength(cont, font=fc), 160), cont, font=fc, fill=R.COR_TEXTO)
    # manchete (dentro da área segura do Reels: longe da legenda e dos botões)
    f, linhas = R.caber(d, titulo, "forte", 84, L - 2 * m - 60, 520)
    passo = f.size * 1.18
    y = 1480 - len(linhas) * passo
    if categoria:
        fcat = R.fonte("extra", 36)
        txt = categoria.upper()
        w = d.textlength(txt, font=fcat)
        d.rounded_rectangle((m, y - 90, m + w + 40, y - 30), radius=10, fill=R.COR_AMARELO)
        d.text((m + 20, y - 85), txt, font=fcat, fill=R.COR_FUNDO)
    for linha in linhas:
        d.text((m, y), linha, font=f, fill=R.COR_TEXTO)
        y += passo
    R.colar_logo(img, m, 1560, 300)
    return img


def tela_final():
    img = Image.new("RGB", (L, A), R.COR_FUNDO)
    d = ImageDraw.Draw(img)
    m = 110
    d.rectangle((0, 0, L, 14), fill=R.COR_AMARELO)
    R.colar_logo(img, m, 260, 460)
    fm = R.fonte("forte", 66)
    d.text((m, 560), "Quer ler as matérias", font=fm, fill=R.COR_TEXTO)
    d.text((m, 640), "completas?", font=fm, fill=R.COR_TEXTO)
    d.text((m, 780), "Comente", font=R.fonte("extra", 150), fill=R.COR_TEXTO)
    d.text((m, 940), "APP", font=R.fonte("extra", 260), fill=R.COR_AMARELO)
    fp = R.fonte("media", 46)
    y = 1250
    for linha in ["e receba os links no direct.", "Quem tem o app abre na matéria;", "quem não tem baixa grátis."]:
        d.text((m, y), linha, font=fp, fill=R.COR_CINZA)
        y += 64
    w1 = R.botao_loja(d, m, 1480, "DISPONÍVEL NO", "Google Play", 1.0)
    R.botao_loja(d, m + w1 + 30, 1480, "BAIXAR NA", "App Store", 1.0)
    return img


# ---------------- Montagem do vídeo (ffmpeg) ----------------
def montar_video(telas, musica, saida):
    pasta = tempfile.mkdtemp()
    entradas, filtros, duracoes = [], [], []
    for i, (img, dur) in enumerate(telas):
        caminho = os.path.join(pasta, f"t{i}.png")
        img.save(caminho)
        entradas += ["-i", caminho]
        quadros = int(dur * FPS)
        filtros.append(
            f"[{i}:v]scale={int(L * 1.12)}:{int(A * 1.12)},"
            f"zoompan=z='min(zoom+0.0007,1.10)':d={quadros}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":s={L}x{A}:fps={FPS},setsar=1,format=yuv420p[v{i}]")
        duracoes.append(dur)
    atual, offset = "v0", 0.0
    for i in range(1, len(telas)):
        offset += duracoes[i - 1] - TRANSICAO
        trans = TRANSICOES[(i - 1) % len(TRANSICOES)]
        filtros.append(f"[{atual}][v{i}]xfade=transition={trans}:duration={TRANSICAO}:offset={offset:.2f}[x{i}]")
        atual = f"x{i}"
    total = sum(duracoes) - TRANSICAO * (len(telas) - 1)
    n = len(telas)
    filtros.append(f"[{n}:a]atrim=0:{total:.2f},afade=t=in:d=0.5,afade=t=out:st={total - 1.8:.2f}:d=1.8,"
                   f"volume=0.85[a]")
    cmd = (["ffmpeg", "-y", "-v", "error"] + entradas + ["-i", musica, "-filter_complex", ";".join(filtros),
           "-map", f"[{atual}]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
           "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
           "-t", f"{total:.2f}", saida])
    subprocess.run(cmd, check=True)
    return total


def fazer_video(posts, semana, agora_sp, saida):
    """Monta o vídeo. Devolve (lista de matérias usadas, duração) ou (None, 0) se não houver material."""
    escolhidas = escolher(posts, 7 if semana else 1, 10 if semana else 5, agora_sp)
    if len(escolhidas) < (5 if semana else 3):
        log(f"Reels: só {len(escolhidas)} matérias; o vídeo fica para a próxima.")
        return None, 0
    if semana:
        cabecalho = "A SEMANA EM 10 FATOS"
        data_txt = f"{(agora_sp - timedelta(days=6)).strftime('%d/%m')} a {agora_sp.strftime('%d/%m/%Y')}"
    else:
        cabecalho = "RESUMO DO DIA"
        data_txt = f"{DIAS_SEMANA[agora_sp.weekday()].capitalize()}, {agora_sp.strftime('%d/%m/%Y')}"
    telas = []
    for i, p in enumerate(escolhidas, 1):
        telas.append((tela_materia(foto_do_post(p), p["titulo"], p.get("categoria", ""), i, len(escolhidas),
                                   cabecalho, data_txt), DURACAO_TELA))
    telas.append((tela_final(), DURACAO_FINAL))
    faixas = sorted(glob.glob(os.path.join(PASTA_MUSICAS, "noticias-*.mp3" if semana else "afrobeat-*.mp3"))) or \
        sorted(glob.glob(os.path.join(PASTA_MUSICAS, "*.mp3")))
    if not faixas:
        raise RuntimeError("nenhuma música na pasta musicas")
    musica = random.choice(faixas)
    duracao = montar_video(telas, musica, saida)
    log(f"Reels montado: {len(escolhidas)} matérias, {duracao:.0f}s, música {os.path.basename(musica)}")
    return escolhidas, duracao


def legenda(escolhidas, semana, agora_sp):
    if semana:
        topo = "📅 A semana em 10 fatos: as notícias pretas que marcaram a semana no Áfricas Play."
    else:
        topo = f"🎬 Resumo do dia: as notícias pretas que marcaram este {DIAS_SEMANA[agora_sp.weekday()]}, " \
               f"{agora_sp.strftime('%d/%m')}."
    lista = "\n".join(f"{i}. {p['titulo']}" for i, p in enumerate(escolhidas, 1))
    tags = "#ÁfricasPlay #NotíciasPretas #CulturaNegra " + ("#SemanaEm10Fatos" if semana else "#ResumoDoDia")
    return f"{topo}\n\n{lista}\n\n👉🏿 Quer ler as matérias completas? Comente APP que a gente te manda os links no direct.\n\n{tags}"


# ---------------- Publicação ----------------
def publicar_video(caminho, texto, token, pagina, ig):
    with open(caminho, "rb") as f:
        r = R.meta("POST", f"{pagina}/videos", token, {"description": texto, "published": "true"},
                   {"source": ("reels.mp4", f, "video/mp4")}, tentativas=1)
    video_fb = r["id"]
    fonte_url, inicio = "", time.time()
    while time.time() - inicio < 300:
        info = R.meta("GET", video_fb, token, {"fields": "source,status"})
        fonte_url = info.get("source") or ""
        if fonte_url:
            break
        time.sleep(10)
    if not fonte_url:
        raise R.ErroMeta("o Facebook não liberou o endereço do vídeo a tempo; o Instagram fica para a próxima")
    c = R.meta("POST", f"{ig}/media", token, {"media_type": "REELS", "video_url": fonte_url, "caption": texto,
                                                "share_to_feed": "true"})["id"]
    R.esperar_container(c, token, limite=420)
    midia = R.meta("POST", f"{ig}/media_publish", token, {"creation_id": c})["id"]
    try:
        link = R.meta("GET", midia, token, {"fields": "permalink"}).get("permalink", "")
    except R.ErroMeta:
        link = ""
    return video_fb, midia, link


def fazer_e_publicar(posts, semana, token, pagina, ig):
    agora_sp = R.agora_sp()
    saida = os.path.join(tempfile.mkdtemp(), "reels.mp4")
    escolhidas, _ = fazer_video(posts, semana, agora_sp, saida)
    if not escolhidas:
        return None
    texto = legenda(escolhidas, semana, agora_sp)
    video_fb, midia, link = publicar_video(saida, texto, token, pagina, ig)
    titulo = ("A semana em 10 fatos" if semana else "Resumo do dia") + f" {agora_sp.strftime('%d/%m')}"
    log(f"REELS PUBLICADO: {titulo} {link}")
    return {"tipo": "reels", "titulo": titulo, "link": "https://www.africas.com.br",
            "links": [{"titulo": p["titulo"], "link": p["link"]} for p in escolhidas],
            "ig_media": midia, "ig_link": link, "fb_post": video_fb, "prioridade": "reels",
            "publicado_em": datetime.now(timezone.utc).isoformat()}


def teste(semana=False):
    """Só monta o vídeo (não publica) e guarda em ensaio/reels-teste.mp4."""
    posts = R.ler_json(R.ARQ_POSTS, [])
    os.makedirs(R.PASTA_ENSAIO, exist_ok=True)
    saida = os.path.join(R.PASTA_ENSAIO, "reels-semana-teste.mp4" if semana else "reels-teste.mp4")
    escolhidas, dur = fazer_video(posts, semana, R.agora_sp(), saida)
    if escolhidas:
        print(legenda(escolhidas, semana, R.agora_sp()))


if __name__ == "__main__":
    import sys
    teste(semana="semana" in sys.argv)
