# Reels do Áfricas Play: "Resumo do dia" (todo dia, 19h) e "Resumo da semana" com 8 notícias (domingo, 19h).
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

import requests
import urllib.request
from datetime import datetime, timedelta, timezone

from PIL import Image, ImageDraw, ImageEnhance

import redes as R

L, A = 1080, 1920            # vídeo em pé (9:16)
FPS = 30
DURACAO_GANCHO = 2.2         # tela de abertura (gancho dos primeiros segundos)
DURACAO_TELA = 4.2           # segundos por matéria: ~3,8 s de texto parado para dar tempo de ler (23/11)
TRANSICAO = 0.4
DURACAO_FINAL = 2.6          # tela final do Comente APP
BRILHO_MINIMO = 70           # abaixo disso (0 a 255) a foto é considerada escura
BRILHO_INUTIL = 25           # abaixo disso a foto está praticamente preta: não dá para clarear
PASTA_MUSICAS = os.path.join(R.PASTA, "musicas")
TRANSICOES = ["fade", "slideleft", "smoothleft", "circleopen", "slideup", "fadeblack", "wipeleft"]
ORDEM = {"breaking": 0, "alta": 1, "parceiro": 2, "nota7": 3}
DIAS_SEMANA = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]


def log(t):
    R.log(t)


# ---------------- Escolha das matérias ----------------
def data_sp(iso):
    return datetime.fromisoformat(iso).astimezone(R.FUSO_SP)


def escolher(posts, dias, quantas, agora_sp, excluir=()):
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
        if chave not in vistos and p.get("link") not in excluir:
            vistos.add(chave)
            unicas.append(p)
    return unicas[:quantas]


def brilho(img):
    return sum(img.convert("L").resize((64, 64)).getdata()) / 4096


def fotos_da_pagina(link):
    """Outras fotos oficiais da própria matéria (compartilhamento no Facebook e no X)."""
    try:
        pagina = R.baixar(link).decode("utf-8", errors="replace")
    except Exception:
        return []
    urls = re.findall(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', pagina) + \
        re.findall(r'<meta[^>]+content="([^"]+)"[^>]+property="og:image"', pagina) + \
        re.findall(r'<meta[^>]+name="twitter:image"[^>]+content="([^"]+)"', pagina)
    # só as fotos declaradas da própria matéria (as imagens soltas da página podem ser de outras matérias)
    vistos, saida = set(), []
    for u in urls:
        u = html.unescape(u)
        if u not in vistos and "logo" not in u.lower() and "icon" not in u.lower():
            vistos.add(u)
            saida.append(u)
    return saida[:6]


def abrir(url):
    try:
        img = Image.open(io.BytesIO(R.baixar(url))).convert("RGB")
        return img if img.width >= 400 and img.height >= 250 else None
    except Exception:
        return None


def nomes_no_titulo(titulo):
    """Nomes próprios do título (ex.: "Gaby Amarantos"), para buscar uma foto livre da pessoa."""
    return re.findall(r"[A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wáéíóúâêôãõç]+(?: (?:d[aeo]s? )?[A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wáéíóúâêôãõç]+)+", titulo)


def foto_similar(post):
    """Foto livre parecida: a da pessoa citada no título (Wikipédia, licença livre)."""
    try:
        import robo
    except Exception:
        return None
    for nome in nomes_no_titulo(post["titulo"]):
        try:
            achou = robo.foto_da_pessoa(nome)
        except Exception:
            achou = None
        if achou and achou[0]:
            img = abrir(achou[0])
            if img is not None and brilho(img) >= BRILHO_INUTIL:
                log(f"Reels: foto quase preta trocada por foto livre de {nome}")
                return img
    return None


def foto_do_post(post):
    """Foto da matéria. Se for escura, procura outra foto mais clara na própria matéria;
    se não houver, clareia a melhor que tiver."""
    candidatas = [post["foto"]] if post.get("foto") else []
    melhor, melhor_brilho = None, -1
    for tentativa in range(2):
        for url in candidatas:
            img = abrir(url)
            if img is None:
                continue
            b = brilho(img)
            if b >= BRILHO_MINIMO:
                return img
            if b > melhor_brilho:
                melhor, melhor_brilho = img, b
        if tentativa == 0:
            candidatas = [u for u in fotos_da_pagina(post["link"]) if u not in candidatas]
    if melhor is None or melhor_brilho < BRILHO_INUTIL:
        similar = foto_similar(post)
        if similar is not None:
            return similar if brilho(similar) >= BRILHO_MINIMO else \
                ImageEnhance.Brightness(similar).enhance(min(1.9, (BRILHO_MINIMO + 20) / max(brilho(similar), 15)))
        log(f"Reels: sem foto legível; matéria fica fora do vídeo: {post['titulo'][:50]}")
        return None
    fator = min(1.9, (BRILHO_MINIMO + 20) / max(melhor_brilho, 15))
    log(f"Reels: foto escura ({melhor_brilho:.0f}) clareada em {fator:.1f}x: {post['titulo'][:50]}")
    return ImageEnhance.Contrast(ImageEnhance.Brightness(melhor).enhance(fator)).enhance(1.08)


# ---------------- Telas ----------------
def fundo_foto(foto, escurecer=0.85, inicio=0.30):
    img = R.cobrir(foto, L, A)
    img = ImageEnhance.Brightness(img).enhance(escurecer)
    return R.degrade_escuro(img, inicio=inicio)


FERRAMENTA_MANCHETES = {
    "name": "manchetes_curtas",
    "description": "Manchetes curtas para ler em 3 segundos no Reels, na mesma ordem dos títulos recebidos.",
    "input_schema": {"type": "object", "properties": {"manchetes": {"type": "array", "items": {"type": "string"}}},
                     "required": ["manchetes"]},
}
INSTRUCAO_MANCHETES = (
    "Você é editor do portal Áfricas (jornalismo negro). Para cada título, escreva uma manchete curta para um "
    "vídeo de Reels, lida em 3 segundos: no máximo 8 palavras e 50 caracteres. Mantenha o fato principal, o nome "
    "da pessoa ou do lugar quando houver, e não invente nada que não esteja no título. Português do Brasil, "
    "tom direto e popular, sem emoji, sem ponto final. Nunca use 'escravo' (use 'escravizado').")


def manchetes_curtas(titulos):
    """Pede ao Claude manchetes de até 8 palavras. Se der erro, usa os títulos originais."""
    chave = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    if not chave:
        return titulos
    try:
        corpo = json.dumps({
            "model": R.MODELO, "max_tokens": 800, "system": INSTRUCAO_MANCHETES,
            "messages": [{"role": "user", "content": "\n".join(f"{i}. {t}" for i, t in enumerate(titulos, 1))}],
            "tools": [FERRAMENTA_MANCHETES], "tool_choice": {"type": "tool", "name": "manchetes_curtas"},
        }).encode("utf-8")
        req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=corpo, headers={
            "x-api-key": chave, "anthropic-version": "2023-06-01", "content-type": "application/json"})
        with urllib.request.urlopen(req, timeout=90) as r:
            resposta = json.loads(r.read().decode("utf-8"))
        for bloco in resposta.get("content", []):
            if bloco.get("type") == "tool_use":
                curtas = bloco["input"].get("manchetes", [])
                if len(curtas) == len(titulos):
                    return [c.strip() if c.strip() and len(c) <= 70 else t for c, t in zip(curtas, titulos)]
    except Exception as e:
        log(f"Reels: manchetes curtas falharam ({e}); usando os títulos originais.")
    return titulos


def tela_gancho(foto, semana, total, data_txt):
    """Primeiro quadro: a promessa do vídeo em letras grandes, legível sem som."""
    if foto is not None:
        img = fundo_foto(foto, escurecer=0.6, inicio=0.10)
    else:
        img = Image.new("RGB", (L, A), R.COR_FUNDO)
    d = ImageDraw.Draw(img)
    m = 90
    d.rectangle((0, 0, L, 14), fill=R.COR_AMARELO)
    if semana:
        linhas = [(f"{total} NOTÍCIAS", R.COR_AMARELO, 140), ("PRETAS", R.COR_AMARELO, 140),
                  ("que marcaram", R.COR_TEXTO, 96), ("a semana", R.COR_TEXTO, 96)]
    else:
        linhas = [(f"{total} NOTÍCIAS", R.COR_AMARELO, 140), ("PRETAS", R.COR_AMARELO, 140),
                  ("que você precisa", R.COR_TEXTO, 96), ("saber hoje", R.COR_TEXTO, 96)]
    y = 540
    for texto, cor, tam in linhas:
        f = R.fonte("extra", tam)
        while d.textlength(texto, font=f) > L - 2 * m and tam > 50:
            tam -= 4
            f = R.fonte("extra", tam)
        d.text((m, y), texto, font=f, fill=cor)
        y += tam * 1.15
    d.text((m, y + 30), data_txt, font=R.fonte("media", 44), fill=R.COR_CINZA)
    R.colar_logo(img, m, 1560, 300)
    return img


def fume(img, topo, forca=0.55):
    """Degradê suave: começa transparente bem acima da manchete e escurece aos poucos até o pé da tela.
    Sem faixa sólida, para a foto continuar aparecendo (ajuste pedido em 23/11)."""
    mascara = Image.new("L", (1, A))
    inicio = max(0, topo - 520)
    for y in range(A):
        v = 0.0 if y < inicio else ((y - inicio) / (A - inicio)) ** 1.15
        mascara.putpixel((0, y), int(255 * forca * v))
    preto = Image.new("RGB", (L, A), R.COR_FUNDO)
    return Image.composite(preto, img, mascara.resize((L, A)))


def tela_materia(foto, titulo, categoria, numero, total, cabecalho, data_txt):
    categoria = categoria or "Notícia"
    img = R.cobrir(foto, L, A) if foto is not None else Image.new("RGB", (L, A), R.COR_FUNDO)
    d = ImageDraw.Draw(img)
    m = 90
    # manchete (dentro da área segura do Reels: longe da legenda e dos botões)
    f, linhas = R.caber(d, titulo, "forte", 84, L - 2 * m - 60, 520)
    passo = f.size * 1.18
    y = 1480 - len(linhas) * passo
    img = fume(img, int(y - 110))
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, L, 14), fill=R.COR_AMARELO)
    fcat = R.fonte("extra", 36)
    txt = categoria.upper()
    w = d.textlength(txt, font=fcat)
    d.rounded_rectangle((m, y - 90, m + w + 40, y - 30), radius=10, fill=R.COR_AMARELO)
    d.text((m + 20, y - 85), txt, font=fcat, fill=R.COR_FUNDO)
    for linha in linhas:
        d.text((m, y), linha, font=f, fill=R.COR_TEXTO, stroke_width=3, stroke_fill=(0, 0, 0))
        y += passo
    # rodapé: logo + "RESUMO DO DIA · 1/5"
    R.colar_logo(img, m, 1560, 300)
    frod = R.fonte("extra", 34)
    rodape = f"{cabecalho}  ·  {numero}/{total}"
    d.text((L - m - d.textlength(rodape, font=frod), 1568), rodape, font=frod, fill=R.COR_AMARELO)
    return img


# Chamadas da tela final: trocam a cada dia, para o vídeo não ficar com cara de robô.
CHAMADAS_FINAIS = [
    ("Quer ler as matérias", "completas?", "Receba os links no direct."),
    ("Quer saber mais?", "", "Os links chegam no seu direct."),
    ("Ficou curioso?", "", "A gente manda no seu direct."),
    ("Quer ler tudo?", "", "Receba os links no direct."),
]


def tela_final(variante=None):
    if variante is None:
        variante = datetime.now(R.FUSO_SP).timetuple().tm_yday % len(CHAMADAS_FINAIS)
    l1, l2, rodape = CHAMADAS_FINAIS[variante]
    img = Image.new("RGB", (L, A), R.COR_FUNDO)
    d = ImageDraw.Draw(img)
    m = 110
    d.rectangle((0, 0, L, 14), fill=R.COR_AMARELO)
    R.colar_logo(img, m, 300, 420)
    fm = R.fonte("forte", 74)
    y = 600
    for linha in (l1, l2):
        if linha:
            d.text((m, y), linha, font=fm, fill=R.COR_TEXTO)
            y += 90
    y += 40
    d.text((m, y), "Comente", font=R.fonte("extra", 150), fill=R.COR_TEXTO)
    d.text((m, y + 160), "APP", font=R.fonte("extra", 280), fill=R.COR_AMARELO)
    d.text((m, y + 500), rodape, font=R.fonte("forte", 56), fill=R.COR_TEXTO)
    w1 = R.botao_loja(d, m, 1500, "DISPONÍVEL NO", "Google Play", 1.0)
    R.botao_loja(d, m + w1 + 30, 1500, "BAIXAR NA", "App Store", 1.0)
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


def fazer_video(posts, semana, agora_sp, saida, excluir=(), turno="noite"):
    """Monta o vídeo. Devolve (lista de matérias usadas, duração) ou (None, 0) se não houver material."""
    quantas = 8 if semana else 5
    escolhidas, fotos = [], []
    for p in escolher(posts, 7 if semana else 1, quantas + 4, agora_sp, excluir):
        if len(escolhidas) == quantas:
            break
        foto = foto_do_post(p)
        if foto is not None:
            escolhidas.append(p)
            fotos.append(foto)
    if len(escolhidas) < (5 if semana else 3):
        log(f"Reels: só {len(escolhidas)} matérias; o vídeo fica para a próxima.")
        return None, 0
    if semana:
        cabecalho = "RADAR DA SEMANA"
        data_txt = f"{(agora_sp - timedelta(days=6)).strftime('%d/%m')} a {agora_sp.strftime('%d/%m/%Y')}"
    else:
        cabecalho = "RADAR DO MEIO-DIA" if turno == "meio" else "RADAR"
        data_txt = f"{DIAS_SEMANA[agora_sp.weekday()].capitalize()}, {agora_sp.strftime('%d/%m/%Y')}"
    telas = [(tela_gancho(fotos[0], semana, len(escolhidas), data_txt), DURACAO_GANCHO)]
    curtas = manchetes_curtas([p["titulo"] for p in escolhidas])
    for i, (p, foto, curta) in enumerate(zip(escolhidas, fotos, curtas), 1):
        log(f"Reels {i}: {curta}")
        telas.append((tela_materia(foto, curta, p.get("categoria", ""), i, len(escolhidas),
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


def legenda(escolhidas, semana, agora_sp, turno="noite"):
    if semana:
        topo = f"📅 A semana em {len(escolhidas)} notícias: as notícias pretas que marcaram a semana no Áfricas Play."
    elif turno == "meio":
        topo = f"☀️ Radar do meio-dia: as notícias pretas desta manhã de {DIAS_SEMANA[agora_sp.weekday()]}, " \
               f"{agora_sp.strftime('%d/%m')}."
    else:
        topo = f"🎬 Resumo do dia: as notícias pretas que marcaram este {DIAS_SEMANA[agora_sp.weekday()]}, " \
               f"{agora_sp.strftime('%d/%m')}."
    lista = "\n".join(f"{i}. {p['titulo']}" for i, p in enumerate(escolhidas, 1))
    tags = "#ÁfricasPlay #NotíciasPretas #CulturaNegra " + ("#ResumoDaSemana" if semana else "#ResumoDoDia")
    return f"{topo}\n\n{lista}\n\n👉🏿 Quer ler as matérias completas? Comente APP que a gente te manda os links no direct.\n📲 Manda pra quem precisa saber.\n\n{tags}"


# ---------------- Publicação ----------------
def publicar_instagram(caminho, texto, token, ig):
    """Envio direto do arquivo ao Instagram (upload resumível, o caminho oficial para Reels)."""
    tamanho = os.path.getsize(caminho)
    c = R.meta("POST", f"{ig}/media", token, {"media_type": "REELS", "upload_type": "resumable", "caption": texto,
                                                "share_to_feed": "true", "thumb_offset": "800"})
    with open(caminho, "rb") as f:
        r = requests.post(c["uri"], data=f.read(), timeout=300, headers={
            "Authorization": f"OAuth {token}", "offset": "0", "file_size": str(tamanho)})
    if r.status_code >= 300:
        raise R.ErroMeta(f"o envio do vídeo ao Instagram falhou ({r.status_code}: {r.text[:200]})")
    inicio = time.time()
    while time.time() - inicio < 600:
        info = R.meta("GET", c["id"], token, {"fields": "status_code,status"})
        st = info.get("status_code")
        if st == "FINISHED":
            break
        if st in ("ERROR", "EXPIRED"):
            raise R.ErroMeta(f"o Instagram recusou o vídeo ({info.get('status', st)})")
        time.sleep(10)
    else:
        raise R.ErroMeta("o Instagram demorou demais para processar o vídeo")
    midia = R.meta("POST", f"{ig}/media_publish", token, {"creation_id": c["id"]})["id"]
    try:
        link = R.meta("GET", midia, token, {"fields": "permalink"}).get("permalink", "")
    except R.ErroMeta:
        link = ""
    return midia, link


def publicar_facebook(caminho, texto, token, pagina):
    with open(caminho, "rb") as f:
        r = R.meta("POST", f"{pagina}/videos", token, {"description": texto, "published": "true"},
                   {"source": ("reels.mp4", f, "video/mp4")}, tentativas=1)
    return r["id"]


def fazer_e_publicar(posts, semana, token, pagina, ig, estado=None, hoje=None, turno="noite", excluir=()):
    """Instagram primeiro; o Facebook só depois que o Instagram der certo, e uma vez por dia (sem duplicar)."""
    estado = estado if estado is not None else {}
    agora_sp = R.agora_sp()
    saida = os.path.join(tempfile.mkdtemp(), "reels.mp4")
    escolhidas, _ = fazer_video(posts, semana, agora_sp, saida, excluir, turno)
    if not escolhidas:
        return None
    texto = legenda(escolhidas, semana, agora_sp, turno)
    midia, link = publicar_instagram(saida, texto, token, ig)
    titulo = ("Resumo da semana" if semana else "Radar do meio-dia" if turno == "meio" else "Resumo do dia") + f" {agora_sp.strftime('%d/%m')}"
    log(f"REELS PUBLICADO: {titulo} {link}")
    video_fb = ""
    chave_fb = "reels_fb_dia" if turno == "noite" else f"reels_fb_{turno}"
    if estado.get(chave_fb) != hoje:
        try:
            video_fb = publicar_facebook(saida, texto, token, pagina)
            estado[chave_fb] = hoje
            log("Reels publicado também no Facebook.")
        except Exception as e:
            log(f"Reels no Facebook falhou: {e}")
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
