# Robô das redes sociais do Áfricas Play
# Lê o RSS geral do site, escolhe o que vai para as redes, monta o carrossel
# (capa do site + frase de destaque + chamada para o app) e escreve as legendas.
#
# MODO "ensaio": não publica nada. Salva tudo na pasta "ensaio" para aprovação.
# (O modo de publicação de verdade entra no próximo passo, depois do ensaio aprovado.)

import html
import io
import json
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
CHAMADA_FACEBOOK = "👉🏿 Leia a matéria completa no link do primeiro comentário ou no app Áfricas Play."
LIMITE_LEGENDA = 700           # trava de segurança: o corpo da legenda nunca passa disso
VERSAO_ENSAIO = 3              # mudou a versão: o ensaio refaz as matérias das últimas 24 horas

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


def tela_app(tamanho):
    """Tela 3: comente APP e receba o link da matéria no direct (deep link: app ou loja)."""
    largura, altura = tamanho
    escala = largura / 1080
    img = Image.new("RGB", (largura, altura), COR_FUNDO)
    d = ImageDraw.Draw(img)
    margem = int(140 * escala)  # espaço para as setas laterais
    d.rectangle((0, 0, largura, int(16 * escala)), fill=COR_AMARELO)
    colar_logo(img, margem, int(110 * escala), int(430 * escala))
    fm = fonte("forte", int(62 * escala))
    y = altura * 0.27
    d.text((margem, y), "Quer ler a matéria", font=fm, fill=COR_TEXTO)
    y += fm.size * 1.2
    d.text((margem, y), "completa?", font=fm, fill=COR_TEXTO)
    y += fm.size * 1.6
    fg = fonte("extra", int(140 * escala))
    d.text((margem, y), "Comente", font=fg, fill=COR_TEXTO)
    y += fg.size * 1.05
    d.text((margem, y), "APP", font=fonte("extra", int(230 * escala)), fill=COR_AMARELO)
    y += int(230 * escala) * 1.15
    fp = fonte("media", int(42 * escala))
    for linha in ["e receba o link no seu direct.", "Quem tem o app abre na matéria;", "quem não tem baixa grátis."]:
        d.text((margem, y), linha, font=fp, fill=COR_CINZA)
        y += fp.size * 1.35
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


def ler_rss_site():
    dados = baixar(RSS_SITE)
    raiz = ET.fromstring(dados)
    itens = []
    for it in raiz.iter("item"):
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
                "palavras_chave": m.get("palavras_chave") or [], "hashtags": m.get("hashtags") or []}
    autor = (item["autor"] or "").lower()
    tipo = "assessoria" if (autor == "assessoria" or not autor) else "equipe/coluna"
    return {"origem": tipo, "nota": None, "breaking": False, "entra": True, "palavras_chave": [], "hashtags": []}


# ---------------- Claude: legendas e frase de destaque ----------------
FERRAMENTA = {
    "name": "textos_redes",
    "description": "Registra os textos das redes sociais para uma matéria do portal Áfricas.",
    "input_schema": {
        "type": "object",
        "properties": {
            "frase_destaque": {"type": "string", "description": "Frase forte para a tela 2, até 90 caracteres."},
            "autor_frase": {"type": "string", "description": "Só o nome de quem disse, sem cargo ou função; senão vazio."},
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
use um trecho fiel da fala (pode encurtar, sem mudar o sentido) e escreva em autor_frase SÓ O NOME de quem
falou, sem cargo, função ou explicação (ex.: "Fátima Farkas"; "Yung Peachie").
Se não houver fala, escreva uma frase-síntese do fato e deixe autor_frase vazio. Sem aspas no texto.

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
    facebook = "\n\n".join(p for p in [corpo, CHAMADA_FACEBOOK, creditos, " ".join(tags[:3])] if p)
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


# ---------------- Principal ----------------
def main():
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


if __name__ == "__main__":
    main()
