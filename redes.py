# Robô das redes sociais do Áfricas Play
# Lê o RSS geral do site, escolhe o que vai para as redes, monta o carrossel
# (capa do site + frase de destaque + chamada para o app) e escreve as legendas.
#
# MODO "ensaio": não publica nada. Salva tudo na pasta "ensaio" para aprovação.
# MODO "publicar": publica no Instagram (carrossel + story) e no Facebook (álbum + link no 1º comentário).

import html
import io
import time
import json
import random
from urllib.parse import urlparse
import os
import re
import textwrap
import unicodedata
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

try:
    import requests
except ImportError:  # só o modo publicar precisa
    requests = None

# ---------------- Configuração ----------------
RSS_SITE = "https://www.africas.com.br/noticias.xml"
MODO = os.environ.get("MODO_REDES", "ensaio")
MODELO = "claude-haiku-5-5"
NOTA_MINIMA_REDES = 8          # matérias do robô: só nota 8, 9 ou 10 (breaking entra sempre)
LIMITE_POR_RODADA = 5          # no ensaio, no máximo 5 matérias por rodada
JANELA_PRIMEIRA_VEZ_HORAS = 24 # na primeira rodada, só olha as últimas 24 horas
FUSO_SP = ZoneInfo("America/Sao_Paulo")

PASTA = os.path.dirname(os.path.abspath(__file__))
PASTA_ESTADO = os.path.join(PASTA, "estado")
ARQ_PUBLICADAS = os.path.join(PASTA_ESTADO, "publicadas.json")   # registro do robô do portal
ARQ_REDES = os.path.join(PASTA_ESTADO, "redes.json")             # registro do robô das redes
PASTA_ENSAIO = os.path.join(PASTA, "ensaio")
PASTA_FONTES = os.path.join(PASTA, "fontes-redes")

# Identidade visual aprovada em 22/11/2026: fundo preto, texto branco,
# destaque em amarelo (o das etiquetas de editoria do site) e vermelho só no breaking.
COR_FUNDO = (14, 14, 14)
COR_TEXTO = (255, 255, 255)
COR_AMARELO = (255, 204, 0)
COR_VERMELHO = (220, 30, 38)
COR_CINZA = (200, 200, 200)

# Chamada da Fase 1. Quando o "comente APP" estiver ligado (Fase 2), troca aqui.
CHAMADA_INSTAGRAM = "👉🏿 Quer ler a matéria completa? Comente APP que a gente te manda o link no direct."
CHAMADA_FACEBOOK = "👉🏿 Leia a matéria completa: {link}"
LIMITE_LEGENDA = 700           # trava de segurança: o corpo da legenda nunca passa disso
VERSAO_ENSAIO = 3              # mudou a versão: o ensaio refaz as matérias das últimas 24 horas

# ---------------- Regras da publicação (aprovadas em 22/11/2026) ----------------
API_META = "https://graph.facebook.com/v26.0/"
FEED_MAXIMO_DIA = 14          # carrosséis no feed por dia
FEED_MINIMO_DIA = 10          # abaixo disso, a nota 7 entra para completar o dia
STORIES_MAXIMO_DIA = 30
STORIES_POR_RODADA = 1        # 1 por rodada (15 min) e cota proporcional ao horário: não esgota cedo (24/11)
STORIES_INICIO, STORIES_FIM = 7, 23  # os 30 stories se espalham das 7h às 23h
INTERVALO_FEED_MIN = 45       # minutos entre um post de feed e outro (breaking não espera)
# Carrosséis concentrados nos horários de maior alcance (aprovado em 24/11): (início, fim, quantos)
JANELAS_FEED = [((7, 0), (9, 0), 2), ((9, 0), (13, 0), 3), ((13, 0), (18, 0), 4), ((18, 0), (22, 0), 5)]  # tarde: 1 por hora (24/11)
HORA_INICIO = (7, 0)          # publica das 7h...
HORA_FIM = (0, 30)            # ...até 0h30; de madrugada, só breaking
VALIDADE_FILA_HORAS = 12      # matéria que espera mais que isso na fila sai dela (notícia velha)
ARQ_POSTS = os.path.join(PASTA_ESTADO, "posts-redes.json")   # o que foi publicado (usado pelo comente APP)
PRIORIDADE = {"breaking": 0, "parceiro": 1, "alta": 2, "nota7": 3}  # colunistas e assessorias à frente da nota 8 (23/11)
HORA_REELS = 19               # Resumo do dia (domingo: Resumo da semana), a partir das 19h
REELS_MEIO_DIA = 12 * 60 + 30   # Radar do meio-dia, a partir das 12h30 (aprovado em 23/11)
REELS_LIGADO = True           # ligado em 23/11/2026, aprovado pelo Washington

# Instagram de quem assina as matérias (preencher quando chegar a lista da equipe).
AUTORES_INSTAGRAM = {
    # "Thays Andrade": "@usuario",
}
HASHTAG_FIXA = "#ÁfricasPlay"
ARQ_LOGO = os.path.join(PASTA, "AP_500_140_negativo.png")   # logo para fundo escuro (envio de 22/11/2026)

NS = {
    "media": "http://search.yahoo.com/mrss/",
    "social": "urn:3wcontrol:rss:social:1",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "dc": "http://purl.org/dc/elements/1.1/",
}

FONTES_WEB = {
    "forte": "https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-Bold.ttf",
    "extra": "https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-ExtraBold.ttf",
    "media": "https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-Medium.ttf",
}
FONTES_LOCAIS = {
    "forte": "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf",
    "extra": "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf",
    "media": "/usr/share/fonts/truetype/google-fonts/Poppins-Medium.ttf",
}
FONTE_RESERVA = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def log(texto):
    print(texto, flush=True)


# ---------------- Arquivos ----------------
def ler_json(caminho, padrao):
    try:
        with open(caminho, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return padrao


def salvar_json(caminho, dados):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=1)


def baixar(url, timeout=40):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (robo-africas-redes)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


# ---------------- Fontes das letras ----------------
_CACHE_FONTES = {}


def caminho_fonte(tipo):
    destino = os.path.join(PASTA_FONTES, os.path.basename(FONTES_WEB[tipo]))
    if os.path.exists(destino):
        return destino
    if os.path.exists(FONTES_LOCAIS[tipo]):
        return FONTES_LOCAIS[tipo]
    try:
        os.makedirs(PASTA_FONTES, exist_ok=True)
        dados = baixar(FONTES_WEB[tipo])
        with open(destino, "wb") as f:
            f.write(dados)
        return destino
    except Exception as e:
        log(f"Aviso: não baixou a fonte {tipo} ({e}); usando a reserva.")
        return FONTE_RESERVA


def fonte(tipo, tamanho):
    chave = (tipo, tamanho)
    if chave not in _CACHE_FONTES:
        _CACHE_FONTES[chave] = ImageFont.truetype(caminho_fonte(tipo), tamanho)
    return _CACHE_FONTES[chave]


# ---------------- Artes ----------------
def quebrar(desenho, texto, tipo, tamanho, largura_max):
    """Quebra o texto em linhas que cabem na largura, medindo palavra por palavra."""
    f = fonte(tipo, tamanho)
    linhas, atual = [], ""
    for palavra in texto.split():
        teste = (atual + " " + palavra).strip()
        if desenho.textlength(teste, font=f) <= largura_max:
            atual = teste
        else:
            if atual:
                linhas.append(atual)
            atual = palavra
    if atual:
        linhas.append(atual)
    return f, linhas


def caber(desenho, texto, tipo, tamanho_max, largura_max, altura_max, entrelinha=1.18):
    for tamanho in range(tamanho_max, 30, -2):
        f, linhas = quebrar(desenho, texto, tipo, tamanho, largura_max)
        if len(linhas) * tamanho * entrelinha <= altura_max:
            return f, linhas
    return quebrar(desenho, texto, tipo, 30, largura_max)


def cobrir(foto, largura, altura):
    """Recorta a foto para preencher o tamanho, sem distorcer."""
    img = foto.convert("RGB")
    escala = max(largura / img.width, altura / img.height)
    img = img.resize((int(img.width * escala) + 1, int(img.height * escala) + 1), Image.LANCZOS)
    x = (img.width - largura) // 2
    y = (img.height - altura) // 2
    return img.crop((x, y, x + largura, y + altura))


def degrade_escuro(img, inicio=0.25, forca=0.92):
    """Escurece a parte de baixo da foto, para o texto ficar legível."""
    largura, altura = img.size
    mascara = Image.new("L", (1, altura))
    for y in range(altura):
        t = max(0.0, (y / altura - inicio) / (1 - inicio))
        mascara.putpixel((0, y), int(255 * min(1.0, t * 1.25) * forca))
    mascara = mascara.resize((largura, altura))
    preto = Image.new("RGB", (largura, altura), COR_FUNDO)
    return Image.composite(preto, img, mascara)


def assinatura(desenho, largura, altura, escala):
    f = fonte("forte", int(30 * escala))
    texto = "ÁFRICAS PLAY"
    w = desenho.textlength(texto, font=f)
    desenho.text(((largura - w) / 2, altura - int(78 * escala)), texto, font=f, fill=COR_AMARELO)


def tela_foto(foto, frase, autor, credito, tamanho):
    """Telas extras do carrossel: foto do corpo da matéria com outra frase de impacto (layout diferente da
    tela 2: barra amarela ao lado da frase, foto mais clara) e o crédito pequeno no canto."""
    largura, altura = tamanho
    escala = largura / 1080
    img = cobrir(foto, largura, altura)
    img = ImageEnhance.Brightness(img).enhance(0.8)
    img = degrade_escuro(img, inicio=0.45 if frase else 0.8)
    d = ImageDraw.Draw(img)
    margem = int(140 * escala)
    if frase:
        f, linhas = caber(d, frase, "forte", int(64 * escala), largura - 2 * margem - int(40 * escala), altura * 0.3)
        passo = f.size * 1.18
        altura_autor = int(60 * escala) if autor else 0
        y0 = altura - int(150 * escala) - len(linhas) * passo - altura_autor
        d.rectangle((margem, y0 + int(6 * escala), margem + int(10 * escala), y0 + len(linhas) * passo), fill=COR_AMARELO)
        y = y0
        for linha in linhas:
            d.text((margem + int(36 * escala), y), linha, font=f, fill=COR_TEXTO, stroke_width=2, stroke_fill=(0, 0, 0))
            y += passo
        if autor:
            fa, la = quebrar(d, autor, "media", int(34 * escala), largura - 2 * margem)
            d.text((margem + int(36 * escala), y + int(14 * escala)), la[0], font=fa, fill=COR_AMARELO)
    fc = fonte("media", int(26 * escala))
    texto = f"Foto: {credito}"
    d.text((largura - margem - d.textlength(texto, font=fc), altura - int(70 * escala)), texto, font=fc,
           fill=COR_CINZA, stroke_width=1, stroke_fill=(0, 0, 0))
    return seta_mais(img, ("esquerda", "direita"))


def tela_destaque(frase, autor, foto, tamanho, breaking=False):
    """Tela 2: foto original escurecida, com a frase forte da matéria entre aspas."""
    largura, altura = tamanho
    escala = largura / 1080
    if foto is not None:
        img = cobrir(foto, largura, altura)
        img = ImageEnhance.Brightness(img).enhance(0.55)
        img = degrade_escuro(img, inicio=0.15)
    else:
        img = Image.new("RGB", (largura, altura), COR_FUNDO)
    d = ImageDraw.Draw(img)
    margem = int(140 * escala)  # espaço para as setas laterais
    if breaking:
        fb = fonte("extra", int(40 * escala))
        d.rounded_rectangle((margem, margem, margem + d.textlength("URGENTE", font=fb) + int(50 * escala),
                             margem + int(70 * escala)), radius=int(14 * escala), fill=COR_VERMELHO)
        d.text((margem + int(25 * escala), margem + int(10 * escala)), "URGENTE", font=fb, fill=COR_TEXTO)
    area_alt = altura * 0.42
    f, linhas = caber(d, frase, "forte", int(78 * escala), largura - 2 * margem, area_alt)
    passo = f.size * 1.18
    bloco = len(linhas) * passo
    y0 = altura - int(300 * escala) - bloco
    if autor:  # aspas só quando é fala de alguém
        aspas = fonte("extra", int(220 * escala))
        d.text((margem - int(8 * escala), y0 - int(190 * escala)), "“", font=aspas, fill=COR_AMARELO)
    else:
        d.rectangle((margem, y0 - int(50 * escala), margem + int(90 * escala), y0 - int(38 * escala)), fill=COR_AMARELO)
    y = y0
    for linha in linhas:
        d.text((margem, y), linha, font=f, fill=COR_TEXTO)
        y += passo
    if autor:
        d.rectangle((margem, y + int(28 * escala), margem + int(70 * escala), y + int(36 * escala)), fill=COR_AMARELO)
        for tam in (36, 32, 28):  # até 2 linhas; diminui a letra se precisar, sem cortar
            fa, la = quebrar(d, autor, "media", int(tam * escala), largura - 2 * margem)
            if len(la) <= 2:
                break
        ya = y + int(52 * escala)
        for linha in la[:2]:
            d.text((margem, ya), linha, font=fa, fill=COR_CINZA)
            ya += fa.size * 1.3
    colar_logo(img, (largura - int(260 * escala)) / 2, altura - int(118 * escala), int(260 * escala))
    return seta_mais(img, ("esquerda", "direita"))


def colar_logo(img, x, y, largura_logo):
    try:
        logo = Image.open(ARQ_LOGO).convert("RGBA")
    except Exception:
        d = ImageDraw.Draw(img)
        d.text((x, y), "ÁFRICAS PLAY", font=fonte("extra", int(largura_logo / 7)), fill=COR_AMARELO)
        return
    altura = int(logo.height * largura_logo / logo.width)
    logo = logo.resize((largura_logo, altura), Image.LANCZOS)
    img.paste(logo, (int(x), int(y)), logo)


def botao_loja(d, x, y, linha1, linha2, escala):
    """Botão de loja desenhado (troca pelos selos oficiais quando os arquivos chegarem)."""
    f1, f2 = fonte("media", int(24 * escala)), fonte("extra", int(40 * escala))
    w = max(d.textlength(linha1, font=f1), d.textlength(linha2, font=f2)) + int(60 * escala)
    h = int(104 * escala)
    d.rounded_rectangle((x, y, x + w, y + h), radius=int(18 * escala), fill=(0, 0, 0), outline=COR_CINZA,
                        width=max(2, int(3 * escala)))
    d.text((x + int(30 * escala), y + int(12 * escala)), linha1, font=f1, fill=COR_CINZA)
    d.text((x + int(30 * escala), y + int(40 * escala)), linha2, font=f2, fill=COR_TEXTO)
    return w


# Chamadas da tela "Comente APP" do carrossel: trocam a cada post, para não ficar com cara de robô.
CHAMADAS_APP = [
    ("Quer ler a matéria", "completa?", "Receba o link no direct."),
    ("Quer saber mais?", "", "O link chega no seu direct."),
    ("Ficou curioso?", "", "A gente manda no seu direct."),
    ("Quer ler tudo?", "", "Receba o link no direct."),
]


def tela_app(tamanho, variante=None):
    """Tela 3: comente APP e receba o link da matéria no direct (deep link: app ou loja)."""
    if variante is None:
        variante = random.randrange(len(CHAMADAS_APP))
    l1, l2, rodape = CHAMADAS_APP[variante % len(CHAMADAS_APP)]
    largura, altura = tamanho
    escala = largura / 1080
    img = Image.new("RGB", (largura, altura), COR_FUNDO)
    d = ImageDraw.Draw(img)
    margem = int(140 * escala)  # espaço para as setas laterais
    d.rectangle((0, 0, largura, int(16 * escala)), fill=COR_AMARELO)
    colar_logo(img, margem, int(110 * escala), int(430 * escala))
    fm = fonte("forte", int(68 * escala))
    y = altura * 0.27
    for linha in (l1, l2):
        if linha:
            d.text((margem, y), linha, font=fm, fill=COR_TEXTO)
            y += fm.size * 1.2
    y += fm.size * 0.4
    fg = fonte("extra", int(140 * escala))
    d.text((margem, y), "Comente", font=fg, fill=COR_TEXTO)
    y += fg.size * 1.05
    d.text((margem, y), "APP", font=fonte("extra", int(230 * escala)), fill=COR_AMARELO)
    y += int(230 * escala) * 1.2
    d.text((margem, y), rodape, font=fonte("forte", int(52 * escala)), fill=COR_TEXTO)
    y_loja = altura - int(170 * escala)
    w1 = botao_loja(d, margem, y_loja, "DISPONÍVEL NO", "Google Play", escala)
    botao_loja(d, margem + w1 + int(30 * escala), y_loja, "BAIXAR NA", "App Store", escala)
    return seta_mais(img, ("esquerda",))


def seta_mais(img, lados=("direita",)):
    """Setas amarelas no meio das laterais: ir para a próxima tela e voltar para a anterior."""
    largura, altura = img.size
    escala = largura / 1080
    d = ImageDraw.Draw(img)
    r = int(40 * escala)
    s = int(15 * escala)
    cy = altura // 2
    for lado in lados:
        if lado == "direita":
            cx = largura - int(58 * escala)
            pontos = [(cx - s // 2, cy - s), (cx + s // 2 + 2, cy), (cx - s // 2, cy + s)]
        else:
            cx = int(58 * escala)
            pontos = [(cx + s // 2, cy - s), (cx - s // 2 - 2, cy), (cx + s // 2, cy + s)]
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=COR_AMARELO)
        d.line(pontos, fill=COR_FUNDO, width=max(4, int(9 * escala)), joint="curve")
    return img


def selo_deslize(capa):
    """Capa: arte do site com a seta amarela de 'tem mais telas' na lateral direita."""
    return seta_mais(capa.convert("RGB"))


# ---------------- RSS do site ----------------
def texto_de(no, caminho):
    el = no.find(caminho, NS)
    return (el.text or "").strip() if el is not None and el.text else ""


def limpar_html(bruto):
    sem = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", bruto or "", flags=re.S | re.I)
    sem = re.sub(r"<br\s*/?>|</p>|</h\d>", "\n", sem, flags=re.I)
    sem = re.sub(r"<[^>]+>", " ", sem)
    sem = html.unescape(sem)
    return re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n\n", sem)).strip()


ITEM_RE = re.compile(r"<item\b.*?</item>", re.S | re.I)
CABECALHO_NS = ('<rss xmlns:media="http://search.yahoo.com/mrss/" xmlns:social="urn:3wcontrol:rss:social:1" '
                'xmlns:content="http://purl.org/rss/1.0/modules/content/" '
                'xmlns:dc="http://purl.org/dc/elements/1.1/"><channel>{}</channel></rss>')


def itens_do_rss(dados):
    """Lê o RSS do site. Se o arquivo vier com defeito (às vezes vem), lê matéria por matéria
    e pula só a que estiver quebrada, em vez de parar tudo."""
    try:
        return list(ET.fromstring(dados).iter("item")), 0
    except ET.ParseError:
        pass
    texto = dados.decode("utf-8", errors="replace")
    itens, quebrados = [], 0
    for bloco in ITEM_RE.findall(texto):
        bloco = re.sub(r"&(?!(?:amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)", "&amp;", bloco)
        try:
            itens.extend(ET.fromstring(CABECALHO_NS.format(bloco)).iter("item"))
        except ET.ParseError:
            quebrados += 1
    return itens, quebrados


def ler_rss_site():
    dados = baixar(RSS_SITE)
    nos, quebrados = itens_do_rss(dados)
    if quebrados:
        log(f"Aviso: o RSS do site veio com defeito; {quebrados} matéria(s) puladas nesta rodada.")
    itens = []
    for it in nos:
        midia = it.find("media:content", NS)
        data = texto_de(it, "pubDate")
        try:
            quando = parsedate_to_datetime(data)
        except Exception:
            quando = None
        itens.append({
            "titulo": html.unescape(texto_de(it, "title")),
            "link": texto_de(it, "link"),
            "resumo": html.unescape(texto_de(it, "description")),
            "texto": limpar_html(texto_de(it, "content:encoded")),
            "foto": midia.get("url", "") if midia is not None else "",
            "credito": texto_de(midia, "media:description") if midia is not None else "",
            "arte_post": texto_de(it, "social:image"),
            "arte_story": texto_de(it, "social:storyImage"),
            "categoria": html.unescape(texto_de(it, "category")),
            "autor": texto_de(it, "dc:creator"),
            "publicou": texto_de(it, "dc:publisher"),
            "quando": quando,
        })
    return itens


def normalizar(t):
    t = unicodedata.normalize("NFD", (t or "").lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def classificar(item, registro):
    """Matéria do robô: entra com nota 8+ ou breaking. Fora do registro (coluna, assessoria): entra sempre."""
    m = registro.get(normalizar(item["titulo"]))
    if m:
        nota = m.get("nota") or 0
        breaking = m.get("prioridade") == "breaking"
        entra = breaking or nota >= NOTA_MINIMA_REDES
        return {"origem": "robô", "nota": nota, "breaking": breaking, "entra": entra,
                "nota7": (not entra) and nota >= 7,
                "palavras_chave": m.get("palavras_chave") or [], "hashtags": m.get("hashtags") or []}
    autor = (item["autor"] or "").lower()
    tipo = "assessoria" if (autor == "assessoria" or not autor) else "equipe/coluna"
    return {"origem": tipo, "nota": None, "breaking": False, "entra": True, "nota7": False,
            "palavras_chave": [], "hashtags": []}


# ---------------- Claude: legendas e frase de destaque ----------------
FERRAMENTA = {
    "name": "textos_redes",
    "description": "Registra os textos das redes sociais para uma matéria do portal Áfricas.",
    "input_schema": {
        "type": "object",
        "properties": {
            "frase_destaque": {"type": "string", "description": "Frase forte para a tela 2, até 90 caracteres."},
            "autor_frase": {"type": "string", "description": "Só o nome de quem disse, sem cargo ou função; senão vazio."},
            "frases_extras": {"type": "array", "maxItems": 3, "description": "Até 3 outras frases fortes, diferentes da frase_destaque, para as telas com fotos.",
                              "items": {"type": "object", "properties": {"frase": {"type": "string"}, "autor": {"type": "string"}},
                                        "required": ["frase", "autor"]}},
            "legenda": {"type": "string", "description": "Gancho + 1 ou 2 parágrafos curtos, de 350 a 650 caracteres, sem chamada, créditos ou hashtags."},
            "hashtags": {"type": "array", "items": {"type": "string"}, "description": "De 3 a 4 hashtags específicas da matéria."},
            "alt_capa": {"type": "string", "description": "Descrição da imagem da capa para o texto alternativo, com palavras-chave."},
            "alt_destaque": {"type": "string", "description": "Descrição da tela da frase para o texto alternativo."},
        },
        "required": ["frase_destaque", "autor_frase", "legenda", "hashtags", "alt_capa", "alt_destaque"],
    },
}

INSTRUCAO = """Você escreve os textos das redes sociais do portal Áfricas (africas.com.br), agência de notícias
contra a invisibilidade midiática e o racismo estrutural, que fala com quem está no corre, de forma direta,
popular e sem sensacionalismo. O povo negro é sempre sujeito ativo, nunca vítima passiva ou estatística.
Narrador em 3ª pessoa; proibido o "nós". Nunca invente fatos, números, falas ou nomes: use só o que está no texto.
Vocabulário: escravizado (nunca escravo); difamar (nunca denegrir); grupos minorizados (nunca minorias);
violência de Estado (nunca insegurança pública); pessoa negra / população negra (nunca "de cor" ou "moreno").

1) frase_destaque: a frase mais forte da matéria, com NO MÁXIMO 90 caracteres. Se houver uma fala marcante,
copie um trecho LITERAL da fala, com as mesmas palavras e NA MESMA ORDEM do texto. É proibido reordenar,
juntar pedaços de lugares diferentes ou reescrever a fala. Se a fala for longa, escolha um pedaço contínuo
menor que caiba nos 90 caracteres. Em autor_frase, escreva SÓ O NOME de quem falou, sem cargo, função ou
explicação (ex.: "Fátima Farkas"; "Yung Peachie").
Se não houver fala, escreva uma frase-síntese do fato e deixe autor_frase vazio. Sem aspas no texto.

1b) frases_extras: até 3 OUTRAS frases de impacto da matéria, diferentes da frase_destaque e entre si, com no
máximo 90 caracteres cada, seguindo a mesma regra: fala LITERAL (mesmas palavras, mesma ordem) com SÓ O NOME de
quem disse em "autor"; ou, se não houver outra fala, um dado ou fato forte da matéria com "autor" vazio.
Nunca invente. Se a matéria não tiver material, devolva menos frases ou a lista vazia.

2) legenda (Instagram, carrossel): siga a fórmula.
- 1ª linha (gancho): o fato mais forte, com a palavra-chave principal (nome, cidade, tema) nas primeiras palavras.
  Até 125 caracteres, porque só isso aparece antes do "mais".
- Depois, 1 ou 2 parágrafos curtos (1 a 2 frases cada): o quê e por que importa para a população negra.
- O objetivo é despertar a vontade de ler a matéria completa no app. Entregue o fato, NÃO entregue o ouro.
  É PROIBIDO colocar na legenda: endereço, horário, preço, datas de funcionamento, programação detalhada,
  falas completas, números detalhados, nomes de todos os envolvidos e o desfecho. Isso fica para a matéria.
- Escreva as palavras-chave de forma natural, como as pessoas pesquisariam.
- Sem emojis, sem hashtags, sem @, sem link, sem créditos e sem chamada final (são colocados depois).
- ENTRE 350 E 650 CARACTERES no total, contando o gancho. Separe os parágrafos com uma linha em branco.

3) hashtags: de 3 a 4, específicas da matéria (tema, nome, cidade), sem a do portal.
4) alt_capa e alt_destaque: descrições objetivas das imagens, com as palavras-chave, até 300 caracteres cada.
"""


def gerar_textos(item):
    chave = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    if not chave:
        raise RuntimeError("Chave ANTHROPIC_API_KEY não encontrada no cofre.")
    pedido = (f"Título: {item['titulo']}\nLinha fina: {item['resumo']}\nCategoria: {item['categoria']}\n"
              f"Crédito da foto: {item['credito']}\n\nTexto da matéria:\n{item['texto'][:7000]}")
    corpo = json.dumps({
        "model": MODELO,
        "max_tokens": 2000,
        "system": INSTRUCAO,
        "messages": [{"role": "user", "content": pedido}],
        "tools": [FERRAMENTA],
        "tool_choice": {"type": "tool", "name": FERRAMENTA["name"]},
    }).encode("utf-8")
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=corpo, headers={
        "x-api-key": chave, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        resposta = json.loads(r.read().decode("utf-8"))
    for bloco in resposta.get("content", []):
        if bloco.get("type") == "tool_use":
            return bloco["input"]
    raise RuntimeError("O Claude não devolveu os campos.")


def cortar_legenda(corpo):
    """Trava de segurança: se o Claude passar do tamanho, mantém só os parágrafos que cabem."""
    if len(corpo) <= LIMITE_LEGENDA:
        return corpo
    partes, total = [], 0
    for p in corpo.split("\n\n"):
        if partes and total + len(p) > LIMITE_LEGENDA:
            break
        partes.append(p)
        total += len(p) + 2
    return "\n\n".join(partes)


def credito_texto(item):
    autor = (item["autor"] or "").strip()
    if not autor or autor.lower() == "assessoria":
        autor = (item["publicou"] or "").strip()
    if not autor:
        return ""
    arroba = AUTORES_INSTAGRAM.get(autor, "")
    return f"Texto: {autor}" + (f" ({arroba})" if arroba else "") + " | Áfricas Play"


def montar_legendas(item, textos):
    tags = []
    for h in [HASHTAG_FIXA] + list(textos.get("hashtags") or []):
        h = "#" + re.sub(r"[^\wÀ-ÿ]", "", h.lstrip("#"))
        if len(h) > 1 and h.lower() not in [t.lower() for t in tags]:
            tags.append(h)
    tags = tags[:5]
    corpo = cortar_legenda(textos["legenda"].strip())
    creditos = "\n".join(c for c in [credito_texto(item), f"📸 Foto: {item['credito']}" if item["credito"] else ""] if c)
    instagram = "\n\n".join(p for p in [corpo, CHAMADA_INSTAGRAM, creditos, " ".join(tags)] if p)
    facebook = "\n\n".join(p for p in [corpo, CHAMADA_FACEBOOK.format(link=item["link"]), creditos,
                                         " ".join(tags[:3])] if p)
    return instagram, facebook


# ---------------- Ensaio ----------------
def slug(t):
    return normalizar(t).replace(" ", "-")[:60] or "materia"


def salvar_ensaio(item, info, imagens, textos, legenda_ig, legenda_fb, agora):
    dia = agora.astimezone(FUSO_SP).strftime("%Y-%m-%d")
    hora = agora.astimezone(FUSO_SP).strftime("%H%M")
    rel = f"{dia}/{hora}-{slug(item['titulo'])}"
    pasta = os.path.join(PASTA_ENSAIO, rel)
    os.makedirs(pasta, exist_ok=True)
    nomes = {}
    for nome, img in imagens.items():
        if img is not None:
            arq = f"{nome}.jpg"
            img.convert("RGB").save(os.path.join(pasta, arq), "JPEG", quality=90)
            nomes[nome] = arq
    with open(os.path.join(pasta, "legendas.txt"), "w", encoding="utf-8") as f:
        f.write("=== INSTAGRAM ===\n" + legenda_ig + "\n\n=== FACEBOOK ===\n" + legenda_fb +
                f"\n\nPrimeiro comentário no Facebook: {item['link']}\n\n=== TEXTO ALTERNATIVO ===\n"
                f"Capa: {textos.get('alt_capa', '')}\nDestaque: {textos.get('alt_destaque', '')}\n")
    origem = info["origem"] + (f", nota {info['nota']}" if info["nota"] is not None else "")
    if info["breaking"]:
        origem += ", BREAKING"
    imgs = " ".join(f'<img src="{rel}/{nomes[n]}" width="240">' for n in ["1-capa", "2-destaque", "3-app", "story"]
                    if n in nomes)
    citacao = "\n".join("> " + (l if l else "") for l in legenda_ig.split("\n"))
    bloco = (f"## {item['titulo']}\n\n*{item['categoria']} · {origem} · "
             f"{item['quando'].astimezone(FUSO_SP).strftime('%d/%m %H:%M') if item['quando'] else ''}*\n\n"
             f"{imgs}\n\n**Legenda do Instagram:**\n\n{citacao}\n\n[Ver legendas do Facebook e textos alternativos]"
             f"({rel}/legendas.txt) · [Matéria no site]({item['link']})\n\n---\n\n")
    return bloco


def atualizar_vitrine(blocos):
    arq = os.path.join(PASTA_ENSAIO, "README.md")
    antigo = ""
    if os.path.exists(arq):
        with open(arq, encoding="utf-8") as f:
            antigo = f.read().split("<!-- inicio -->", 1)[-1]
    cabecalho = ("# Modo ensaio: redes sociais do Áfricas Play\n\n"
                 "Nada aqui foi publicado. As matérias mais novas ficam em cima.\n"
                 "Ordem das imagens: capa (arte do site), destaque, app e story.\n\n<!-- inicio -->\n\n")
    with open(arq, "w", encoding="utf-8") as f:
        f.write(cabecalho + "".join(blocos) + antigo.lstrip("\n"))


# ---------------- Ensaio (principal) ----------------
def main_ensaio():
    agora = datetime.now(timezone.utc)
    estado = ler_json(ARQ_REDES, {"vistos": [], "iniciado_em": None})
    if estado.get("versao") != VERSAO_ENSAIO:  # versão nova do ensaio: refaz as últimas 24 horas
        estado = {"vistos": [], "iniciado_em": None, "versao": VERSAO_ENSAIO}
    vistos = set(estado.get("vistos", []))
    primeira_vez = not estado.get("iniciado_em")
    registro = {normalizar(m.get("titulo", "")): m for m in ler_json(ARQ_PUBLICADAS, [])}
    log(f"Modo: {MODO} | matérias no registro do robô do portal: {len(registro)}")

    itens = ler_rss_site()
    log(f"RSS do site: {len(itens)} matérias")
    novos = [i for i in itens if i["link"] and i["link"] not in vistos]
    if primeira_vez:
        limite = agora - timedelta(hours=JANELA_PRIMEIRA_VEZ_HORAS)
        novos = [i for i in novos if i["quando"] and i["quando"] >= limite]
    novos.sort(key=lambda i: i["quando"] or agora, reverse=True)

    blocos, feitos = [], 0
    for item in novos:
        if feitos >= LIMITE_POR_RODADA:
            break
        info = classificar(item, registro)
        vistos.add(item["link"])
        if not info["entra"]:
            log(f"Fora (nota {info['nota']}): {item['titulo'][:80]}")
            continue
        try:
            capa = Image.open(io.BytesIO(baixar(item["arte_post"]))) if item["arte_post"] else None
            if capa is None:
                log(f"Sem arte de post, pulando: {item['titulo'][:80]}")
                continue
            story = Image.open(io.BytesIO(baixar(item["arte_story"]))) if item["arte_story"] else None
            try:
                foto = Image.open(io.BytesIO(baixar(item["foto"]))) if item["foto"] else None
            except Exception:
                foto = None
            textos = gerar_textos(item)
            tamanho = capa.size
            imagens = {
                "1-capa": selo_deslize(capa),
                "2-destaque": tela_destaque(textos["frase_destaque"], textos.get("autor_frase", ""), foto, tamanho,
                                            breaking=info["breaking"]),
                "3-app": tela_app(tamanho),
                "story": story,
            }
            legenda_ig, legenda_fb = montar_legendas(item, textos)
            blocos.append(salvar_ensaio(item, info, imagens, textos, legenda_ig, legenda_fb, agora))
            feitos += 1
            log(f"Ensaio pronto ({info['origem']}): {item['titulo'][:80]}")
        except Exception as e:
            vistos.discard(item["link"])
            log(f"Erro em '{item['titulo'][:60]}': {e}")

    if blocos:
        atualizar_vitrine(blocos)
    estado["vistos"] = list(vistos)[-500:]
    estado["iniciado_em"] = estado.get("iniciado_em") or agora.isoformat()
    salvar_json(ARQ_REDES, estado)
    log(f"Fim: {feitos} matérias no ensaio. Nada foi publicado.")


# ---------------- Publicação: Meta (Instagram e Facebook) ----------------
class ErroMeta(Exception):
    pass


def meta(metodo, caminho, token, dados=None, arquivos=None, tentativas=2):
    """Chamada à ferramenta oficial da Meta. Nunca mostra a chave no registro."""
    url = API_META + caminho
    for tentativa in range(tentativas):
        try:
            if metodo == "GET":
                r = requests.get(url, params={**(dados or {}), "access_token": token}, timeout=60)
            else:
                r = requests.post(url, data={**(dados or {}), "access_token": token}, files=arquivos, timeout=120)
            corpo = r.json()
        except Exception as e:
            if tentativa + 1 < tentativas:
                time.sleep(5)
                continue
            raise ErroMeta(f"falha de conexão ({e.__class__.__name__})")
        if "error" in corpo:
            erro = corpo["error"]
            if erro.get("is_transient") and tentativa + 1 < tentativas:
                time.sleep(8)
                continue
            raise ErroMeta(f"{erro.get('message', 'erro')} (código {erro.get('code')})")
        return corpo
    raise ErroMeta("sem resposta")


def jpeg(img):
    b = io.BytesIO()
    img.convert("RGB").save(b, "JPEG", quality=88)
    b.seek(0)
    return b


def publicar_facebook(imagens, legenda, link, token, pagina):
    """Álbum na página: sobe as 3 telas sem publicar, junta num post e põe o link no 1º comentário.
    Devolve o id do post e os endereços das imagens (usados também pelo Instagram)."""
    ids, enderecos = [], []
    for i, img in enumerate(imagens):
        r = meta("POST", f"{pagina}/photos", token, {"published": "false"},
                 {"source": (f"tela{i + 1}.jpg", jpeg(img), "image/jpeg")})
        ids.append(r["id"])
    dados = {"message": legenda}
    for i, foto in enumerate(ids):
        dados[f"attached_media[{i}]"] = json.dumps({"media_fbid": foto})
    post = meta("POST", f"{pagina}/feed", token, dados)["id"]  # o link da matéria vai no próprio texto
    for foto in ids:
        info = meta("GET", foto, token, {"fields": "images"})
        imgs = sorted(info.get("images", []), key=lambda x: x.get("width", 0), reverse=True)
        enderecos.append(imgs[0]["source"] if imgs else "")
    return post, enderecos


def esperar_container(container, token, limite=90):
    inicio = time.time()
    while time.time() - inicio < limite:
        st = meta("GET", container, token, {"fields": "status_code"}).get("status_code")
        if st == "FINISHED":
            return
        if st in ("ERROR", "EXPIRED"):
            raise ErroMeta(f"o Instagram recusou a mídia ({st})")
        time.sleep(4)
    raise ErroMeta("o Instagram demorou demais para processar a mídia")


def publicar_carrossel(enderecos, alts, legenda, token, ig):
    filhos = []
    for url, alt in zip(enderecos, alts):
        dados = {"image_url": url, "is_carousel_item": "true"}
        if alt:
            dados["alt_text"] = alt[:1000]
        filhos.append(meta("POST", f"{ig}/media", token, dados)["id"])
    for f in filhos:
        esperar_container(f, token)
    pai = meta("POST", f"{ig}/media", token,
               {"media_type": "CAROUSEL", "children": ",".join(filhos), "caption": legenda})["id"]
    esperar_container(pai, token)
    midia = meta("POST", f"{ig}/media_publish", token, {"creation_id": pai})["id"]
    try:
        link = meta("GET", midia, token, {"fields": "permalink"}).get("permalink", "")
    except ErroMeta:
        link = ""
    return midia, link


def publicar_story(url_arte, token, ig):
    c = meta("POST", f"{ig}/media", token, {"image_url": url_arte, "media_type": "STORIES"})["id"]
    esperar_container(c, token)
    return meta("POST", f"{ig}/media_publish", token, {"creation_id": c})["id"]


# ---------------- Publicação: fila, horários e limites ----------------
def agora_sp():
    return datetime.now(FUSO_SP)


def dentro_do_horario(t):
    hm = (t.hour, t.minute)
    return hm >= HORA_INICIO or hm <= HORA_FIM


def dia_de_trabalho(t):
    """O 'dia' das redes vai das 7h às 0h30: o que sai até 0h30 conta no dia anterior."""
    if (t.hour, t.minute) <= HORA_FIM:
        t = t - timedelta(days=1)
    return t.strftime("%Y-%m-%d")


def para_fila(item, info):
    if info["breaking"]:
        prioridade = "breaking"
    elif info["origem"] == "robô" and info["entra"]:
        prioridade = "alta"
    elif info["entra"]:
        prioridade = "parceiro"
    else:
        prioridade = "nota7"
    dados = {k: v for k, v in item.items() if k != "quando"}
    dados["quando"] = item["quando"].isoformat() if item["quando"] else None
    dados.update({"prioridade": prioridade, "nota": info["nota"], "origem": info["origem"],
                  "breaking": info["breaking"], "entrou_na_fila": datetime.now(timezone.utc).isoformat()})
    return dados


def da_fila(dados):
    item = dict(dados)
    item["quando"] = datetime.fromisoformat(dados["quando"]) if dados.get("quando") else None
    return item


def publicar_materia(item, token, pagina, ig):
    """Monta as telas, escreve os textos e publica no Facebook e no Instagram."""
    capa = Image.open(io.BytesIO(baixar(item["arte_post"])))
    try:
        foto = Image.open(io.BytesIO(baixar(item["foto"]))) if item.get("foto") else None
    except Exception:
        foto = None
    textos = gerar_textos(item)
    tamanho = capa.size
    telas = [selo_deslize(capa),
             tela_destaque(textos["frase_destaque"], textos.get("autor_frase", ""), foto, tamanho,
                           breaking=item.get("breaking", False))]
    alts_extras = []
    # fotos do corpo da matéria original (guardadas pelo robô do portal), até 3 telas a mais
    registro = {normalizar(m.get("titulo", "")): m for m in ler_json(ARQ_PUBLICADAS, [])}
    frases = [x for x in (textos.get("frases_extras") or []) if x.get("frase")]
    for n, f in enumerate((registro.get(normalizar(item.get("titulo", ""))) or {}).get("fotos_extras", [])[:3]):
        fx = frases[n] if n < len(frases) else {}
        try:
            telas.append(tela_foto(Image.open(io.BytesIO(baixar(f["url"]))).convert("RGB"),
                                   fx.get("frase", ""), fx.get("autor", ""), f.get("credito", ""), tamanho))
            alts_extras.append(f.get("legenda") or fx.get("frase") or "Foto da matéria")
        except Exception as e:
            log(f"  Foto extra não entrou no carrossel: {e}")
    telas.append(tela_app(tamanho))
    legenda_ig, legenda_fb = montar_legendas(item, textos)
    fb_post, enderecos = publicar_facebook(telas, legenda_fb, item["link"], token, pagina)
    alts = [textos.get("alt_capa", ""), textos.get("alt_destaque", "")] + alts_extras + \
           ["Tela do Áfricas Play: comente APP e receba o link da matéria completa no direct."]
    midia, permalink = publicar_carrossel(enderecos, alts, legenda_ig, token, ig)
    return {"titulo": item["titulo"], "link": item["link"], "ig_media": midia, "ig_link": permalink,
            "fb_post": fb_post, "prioridade": item.get("prioridade"),
            "foto": item.get("foto", ""), "categoria": item.get("categoria", ""),
            "publicado_em": datetime.now(timezone.utc).isoformat()}


ARQ_MAPA_INSTAGRAM = os.path.join(PASTA, "feeds", "instagram.json")


def gravar_mapa_instagram(posts):
    """Lista matéria do site -> post do Instagram, lida pelo código colado no Body do site
    para mostrar o post no fim de cada matéria. Acumula (não apaga as antigas)."""
    mapa = ler_json(ARQ_MAPA_INSTAGRAM, {})
    for p in posts:
        if p.get("tipo") == "reels" or not p.get("ig_link"):
            continue
        caminho = urlparse(p.get("link", "")).path
        caminho = "/" + caminho.strip("/")
        if caminho.startswith("/noticia/"):
            mapa[caminho] = p["ig_link"]
    salvar_json(ARQ_MAPA_INSTAGRAM, mapa)


def main_publicar():
    if requests is None:
        raise SystemExit("Falta instalar o requests.")
    token = (os.environ.get("META_PAGE_TOKEN") or "").strip()
    pagina = (os.environ.get("FB_PAGE_ID") or "").strip()
    ig = (os.environ.get("IG_USER_ID") or "").strip()
    if not (token and pagina and ig):
        raise SystemExit("Faltam META_PAGE_TOKEN, FB_PAGE_ID ou IG_USER_ID no cofre.")

    t = agora_sp()
    agora = datetime.now(timezone.utc)
    hoje = dia_de_trabalho(t)
    estado = ler_json(ARQ_REDES, {})
    if estado.get("modo") != "publicar":  # primeira rodada publicando: começa do zero, sem repetir o ensaio
        estado = {"modo": "publicar", "vistos": [], "fila": [], "fila_stories": [],
                  "inicio": agora.isoformat()}
    if estado.get("dia") != hoje:
        estado.update({"dia": hoje, "feed_hoje": 0, "stories_hoje": 0})
    vistos = set(estado.get("vistos", []))
    fila = estado.get("fila", [])
    fila_stories = estado.get("fila_stories", [])
    posts = ler_json(ARQ_POSTS, [])
    registro = {normalizar(m.get("titulo", "")): m for m in ler_json(ARQ_PUBLICADAS, [])}

    # 1) Novidades do site entram na fila (na primeira rodada, só as das últimas 3 horas)
    itens = ler_rss_site()
    limite_inicio = datetime.fromisoformat(estado["inicio"]) - timedelta(hours=3)
    novas = 0
    for item in sorted(itens, key=lambda i: i["quando"] or agora):
        if not item["link"] or item["link"] in vistos:
            continue
        vistos.add(item["link"])
        if not item["quando"] or item["quando"] < limite_inicio:
            continue
        info = classificar(item, registro)
        if not info["entra"] and not info["nota7"]:
            log(f"Fora (nota {info['nota']}): {item['titulo'][:70]}")
            continue
        if not item.get("arte_post"):
            log(f"Sem arte de post, fora: {item['titulo'][:70]}")
            continue
        dados = para_fila(item, info)
        fila.append(dados)
        if item.get("arte_story"):
            fila_stories.append({"titulo": item["titulo"], "url": item["arte_story"],
                                 "breaking": info["breaking"]})
        novas += 1
    log(f"Novas na fila: {novas} | fila do feed: {len(fila)} | fila de stories: {len(fila_stories)}")

    # 2) Tira da fila o que ficou velho
    validade = agora - timedelta(hours=VALIDADE_FILA_HORAS)
    fila = [f for f in fila if datetime.fromisoformat(f["entrou_na_fila"]) >= validade or f["prioridade"] == "breaking"]

    horario = dentro_do_horario(t)
    ultimo = datetime.fromisoformat(estado["ultimo_feed"]) if estado.get("ultimo_feed") else None
    # tolerância de 3 minutos: o post sai 1 ou 2 minutos depois de o robô acordar, e sem ela
    # os 45 minutos viravam 60 na prática (o robô acorda de 15 em 15)
    pode_feed = ultimo is None or (agora - ultimo) >= timedelta(minutes=INTERVALO_FEED_MIN - 3)
    janela = next((j for j in JANELAS_FEED if j[0] <= (t.hour, t.minute) < j[1]), None)
    if janela is None:
        pode_feed = False  # fora das janelas de carrossel (só breaking)
    else:
        inicio_j = t.replace(hour=janela[0][0], minute=janela[0][1], second=0, microsecond=0)
        na_janela = sum(1 for p in posts if p.get("tipo") != "reels" and p.get("publicado_em")
                        and datetime.fromisoformat(p["publicado_em"]) >= inicio_j.astimezone(timezone.utc))
        if na_janela >= janela[2]:
            pode_feed = False  # janela já completa
    log(f"Hora: {t.strftime('%H:%M')} | {'horário de publicação' if horario else 'madrugada: só breaking'} | "
        f"feed hoje: {estado['feed_hoje']}/{FEED_MAXIMO_DIA} | stories hoje: {estado['stories_hoje']}/{STORIES_MAXIMO_DIA}")

    # 3) Feed: breaking sempre na hora; o resto respeita horário, intervalo e limite do dia
    fila.sort(key=lambda f: (PRIORIDADE.get(f["prioridade"], 9), f.get("quando") or ""))
    a_publicar = [f for f in fila if f["prioridade"] == "breaking"]
    if not a_publicar and horario and pode_feed and estado["feed_hoje"] < FEED_MAXIMO_DIA:
        for f in fila:
            if f["prioridade"] == "nota7" and estado["feed_hoje"] >= FEED_MINIMO_DIA:
                continue
            a_publicar = [f]
            break
    for f in a_publicar:
        try:
            post = publicar_materia(da_fila(f), token, pagina, ig)
            posts.append(post)
            estado["feed_hoje"] += 1
            estado["ultimo_feed"] = datetime.now(timezone.utc).isoformat()
            log(f"PUBLICADO ({f['prioridade']}): {f['titulo'][:70]} {post['ig_link']}")
        except Exception as e:
            log(f"Erro ao publicar '{f['titulo'][:60]}': {e}")
            f["falhas"] = f.get("falhas", 0) + 1
            if f["falhas"] < 3:
                continue  # tenta de novo na próxima rodada
        fila = [x for x in fila if x["link"] != f["link"]]

    # 4) Stories: breaking na hora; o resto no horário, até o limite do dia
    feitos = 0
    restantes = []
    # cota até agora: proporcional ao tempo passado entre 7h e 23h (ex.: às 15h, no máximo metade dos 30)
    frac = min(1.0, max(0.0, ((t.hour + t.minute / 60) - STORIES_INICIO) / (STORIES_FIM - STORIES_INICIO)))
    cota_agora = max(1, round(STORIES_MAXIMO_DIA * frac))
    # mais novos primeiro: matéria fresca vale mais que fila acumulada
    fila_stories = sorted(fila_stories, key=lambda x: 0 if x.get("breaking") else 1)
    fila_stories = [x for x in fila_stories if x.get("breaking")] + list(reversed([x for x in fila_stories if not x.get("breaking")]))
    for s_ in fila_stories:
        liberado = s_.get("breaking") or (horario and feitos < STORIES_POR_RODADA and estado["stories_hoje"] < cota_agora)
        if liberado and estado["stories_hoje"] < STORIES_MAXIMO_DIA:
            try:
                publicar_story(s_["url"], token, ig)
                estado["stories_hoje"] += 1
                feitos += 1
                log(f"STORY: {s_['titulo'][:70]}")
                continue
            except Exception as e:
                log(f"Erro no story '{s_['titulo'][:60]}': {e}")
        restantes.append(s_)
    fila_stories = list(reversed(restantes))[-60:]  # volta à ordem de chegada para guardar

    # 5) Reels: Radar do meio-dia (a partir das 12h30) e Resumo do dia (a partir das 19h; domingo, a semana).
    #    O da noite não repete as matérias do meio-dia.
    minutos = t.hour * 60 + t.minute
    turnos = [("meio", REELS_MEIO_DIA, HORA_REELS * 60, "reels_meio_dia", "reels_meio_tentativas"),
              ("noite", HORA_REELS * 60, 24 * 60, "reels_dia", "reels_tentativas")]
    for turno, comeco, fim, chave, chave_tent in turnos:
        if not (REELS_LIGADO and horario):
            break
        if estado.get(chave) != hoje and minutos < comeco:
            estado[chave_tent] = 0
        if not (comeco <= minutos < fim) or estado.get(chave) == hoje or estado.get(chave_tent, 0) >= 3:
            continue
        semana = turno == "noite" and t.weekday() == 6
        excluir = estado.get("reels_meio_links", []) if (turno == "noite" and estado.get("reels_meio_dia") == hoje) else []
        try:
            import video
            post = video.fazer_e_publicar(posts, semana, token, pagina, ig, estado, hoje, turno, set(excluir))
            if post:
                posts.append(post)
                if turno == "meio":
                    estado["reels_meio_links"] = [m["link"] for m in post["links"]]
            estado[chave] = hoje
            estado[chave_tent] = 0
        except Exception as e:
            estado[chave_tent] = estado.get(chave_tent, 0) + 1
            log(f"Erro no Reels do turno {turno} (tentativa {estado[chave_tent]} de 3): {e}")
        break  # um Reels por rodada

    estado.update({"vistos": list(vistos)[-500:], "fila": fila, "fila_stories": fila_stories})
    salvar_json(ARQ_REDES, estado)
    salvar_json(ARQ_POSTS, posts[-300:])
    gravar_mapa_instagram(posts)
    log("Fim da rodada.")


if __name__ == "__main__":
    if MODO == "publicar":
        main_publicar()
    else:
        main_ensaio()
