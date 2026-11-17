# Robô de conteúdo do portal Áfricas
# Busca notícias nas fontes, filtra, manda o Claude reescrever na linha editorial
# e atualiza um RSS por categoria, no mesmo formato do RSS que o site já lê.

import difflib
import html
import json
import os
import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

try:
    import trafilatura
except ImportError:
    trafilatura = None

# ---------------- Configurações ----------------
CATEGORIAS = ["mundo", "cotidiano", "protagonista", "cultura", "politica", "ancestralidade"]
PRIORIDADES = ["breaking", "alta", "media"]
MODELO = "claude-haiku-5-5"
MAX_NOVAS_POR_RODADA = 6        # quantas notícias novas, no máximo, vão para o Claude por rodada
IDADE_MAXIMA_HORAS = 48         # notícia mais antiga que isso não entra
TEXTO_MINIMO = 600              # menos que isso de texto original = descarta (evita inventar)
SEMELHANCA_MESMO_FATO = 0.62    # títulos parecidos acima disso = mesmo fato
FUSO_SP = timezone(timedelta(hours=-3))
NAVEGADOR = "Mozilla/5.0 (compatible; RoboAfricas/1.0; +https://www.africas.com.br)"

PASTA = os.path.dirname(os.path.abspath(__file__))
ARQ_FONTES = os.path.join(PASTA, "fontes.json")
ARQ_LINHA = os.path.join(PASTA, "linha-editorial.md")
PASTA_ESTADO = os.path.join(PASTA, "estado")
ARQ_FILA = os.path.join(PASTA_ESTADO, "fila.json")
ARQ_VISTOS = os.path.join(PASTA_ESTADO, "vistos.json")
ARQ_PUBLICADAS = os.path.join(PASTA_ESTADO, "publicadas.json")
PASTA_FEEDS = os.path.join(PASTA, "feeds")


def log(msg):
    print(datetime.now(FUSO_SP).strftime("%H:%M:%S"), msg, flush=True)


def ler_json(caminho, padrao):
    try:
        with open(caminho, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return padrao


def salvar_json(caminho, dados):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=1)


def baixar(url, tempo=30):
    req = urllib.request.Request(url, headers={"User-Agent": NAVEGADOR})
    with urllib.request.urlopen(req, timeout=tempo) as r:
        return r.read().decode("utf-8", errors="replace")


def normalizar(texto):
    texto = html.unescape(texto or "").lower()
    texto = re.sub(r"[^\w\s]", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


# ---------------- 1. Ler as fontes (RSS) ----------------
def ler_rss(url):
    itens = []
    try:
        raiz = ET.fromstring(baixar(url).encode("utf-8"))
    except Exception as e:
        log(f"  Erro ao ler fonte {url}: {e}")
        return itens
    for item in raiz.iter("item"):
        titulo = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        descricao = item.findtext("description") or ""
        data = None
        try:
            data = parsedate_to_datetime(item.findtext("pubDate") or "")
        except Exception:
            pass
        imagem = ""
        achou = re.search(r'<img[^>]+src="([^"]+)"', descricao)
        if achou:
            imagem = achou.group(1)
        for m in item:
            if m.tag.endswith("content") and m.get("url"):
                imagem = m.get("url")
            if m.tag == "enclosure" and m.get("url") and "image" in (m.get("type") or ""):
                imagem = m.get("url")
        if titulo and link:
            itens.append({"titulo": decodificar(titulo), "link": link, "data": data, "imagem": imagem,
                          "descricao": decodificar(re.sub(r"<[^>]+>", " ", descricao))})
    return itens


# ---------------- 2. Pegar o texto completo no site original ----------------
def decodificar(texto):
    """Conserta caracteres como &amp;, &quot;, &#8220; e espaços sobrando."""
    texto = html.unescape(str(texto or ""))
    texto = texto.replace("\r", "")
    texto = re.sub(r"[ \t]+", " ", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto.strip()


PADRAO_CREDITO = re.compile(r"(?i:Foto|Fotos|Imagem|Crédito|Credito)\s*:\s*([^\n|]{3,90}?)(?=\s*(?:\n|\||$|\.\s))")


def limpeza_mecanica(texto, titulo="", descricao=""):
    """Tira do texto original o 'lixo' dos sites (vindo do fluxo antigo do n8n)."""
    t = texto or ""
    if titulo:
        t = t.replace(titulo, "", 1)
    if descricao and len(descricao) > 30:
        t = t.replace(descricao, "", 1)
    t = re.sub(r"^Notícias\s*", "", t, flags=re.I)
    t = re.sub(r"Compartilhe(?: por (?:Facebook|Twitter|LinkedIn|WhatsApp))?:?", "", t, flags=re.I)
    t = re.sub(r"link para Copiar para área de transferência", "", t, flags=re.I)
    t = re.sub(r"(?:Publicado|Atualizado) em\s+\d{2}/\d{2}/\d{4}\s+\d{2}h\d{2}", "", t, flags=re.I)
    t = PADRAO_CREDITO.sub("", t)
    t = re.sub(r"\.\s*\.(?=\s)", ".", t)
    t = re.sub(r"\n\s*Tags:\s.*$", "", t, flags=re.I | re.S)
    t = re.sub(r"\n\s*Categoria\s.*$", "", t, flags=re.I | re.S)
    return decodificar(t)


def extrair_materia(link, titulo="", descricao=""):
    """Abre a matéria original e devolve texto, imagem, crédito da foto, autor e veículo."""
    resultado = {"texto": "", "imagem": "", "veiculo": "", "autor": "", "credito_foto": "",
                 "embeds": [], "links_uteis": []}
    try:
        pagina = baixar(link)
    except Exception as e:
        log(f"  Não abriu a matéria: {e}")
        return resultado

    if trafilatura:
        try:
            dados = trafilatura.bare_extraction(pagina, url=link, include_comments=False)
            if dados:
                if not isinstance(dados, dict):
                    dados = dados.as_dict()
                resultado["texto"] = (dados.get("text") or "").strip()
                resultado["imagem"] = dados.get("image") or ""
                resultado["veiculo"] = dados.get("sitename") or ""
                resultado["autor"] = dados.get("author") or ""
        except Exception as e:
            log(f"  Falha na extração: {e}")

    if not resultado["texto"]:
        paragrafos = re.findall(r"<p[^>]*>(.*?)</p>", pagina, flags=re.S | re.I)
        limpos = [html.unescape(re.sub(r"<[^>]+>", "", p)).strip() for p in paragrafos]
        resultado["texto"] = "\n\n".join(p for p in limpos if len(p) > 60)

    def meta(propriedade):
        m = re.search(r'<meta[^>]+(?:property|name)="' + propriedade + r'"[^>]+content="([^"]+)"', pagina, re.I)
        if not m:
            m = re.search(r'<meta[^>]+content="([^"]+)"[^>]+(?:property|name)="' + propriedade + r'"', pagina, re.I)
        return decodificar(m.group(1)) if m else ""

    resultado["imagem"] = resultado["imagem"] or meta("og:image")
    resultado["veiculo"] = resultado["veiculo"] or meta("og:site_name") or urlparse(link).netloc.replace("www.", "")
    resultado["autor"] = resultado["autor"] or meta("author") or meta("article:author")
    if resultado["autor"].startswith("http"):
        resultado["autor"] = ""

    # crédito da foto: legenda da imagem ou "Foto: ..." no texto
    legenda = re.search(r"<figcaption[^>]*>(.*?)</figcaption>", pagina, flags=re.S | re.I)
    candidatos = [resultado["texto"]]
    if legenda:
        candidatos.insert(0, decodificar(re.sub(r"<[^>]+>", " ", legenda.group(1))))
    for c in candidatos:
        m = PADRAO_CREDITO.search(c or "")
        if m:
            resultado["credito_foto"] = decodificar(m.group(1)).strip(" .-–")
            break

    resultado["embeds"] = achar_embeds(pagina)
    resultado["links_uteis"] = achar_links_uteis(pagina)
    resultado["texto"] = limpeza_mecanica(resultado["texto"], titulo, descricao)
    resultado["veiculo"] = decodificar(resultado["veiculo"])
    resultado["autor"] = decodificar(resultado["autor"])
    return resultado



def trecho_da_materia(pagina):
    """Pega só o miolo da matéria (tag <article>), para não pegar menus e rodapé."""
    m = re.search(r"<article\b.*?</article>", pagina, flags=re.S | re.I)
    return m.group(0) if m else ""


def achar_embeds(pagina):
    """Acha vídeos do YouTube, áudios do Spotify e posts do Instagram dentro da matéria."""
    miolo = trecho_da_materia(pagina)
    iframes = " ".join(re.findall(r"<iframe[^>]+src=\"([^\"]+)\"", pagina, flags=re.I))
    onde = miolo + " " + iframes
    embeds = []
    for vid in re.findall(r"(?:youtube\.com/embed/|youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([A-Za-z0-9_-]{11})", onde):
        embeds.append(f'<iframe width="560" height="315" src="https://www.youtube.com/embed/{vid}" title="Vídeo do YouTube" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>')
    for tipo, cod in re.findall(r"open\.spotify\.com/(?:embed/)?(track|episode|show|album|playlist)/([A-Za-z0-9]+)", onde):
        embeds.append(f'<iframe src="https://open.spotify.com/embed/{tipo}/{cod}" width="100%" height="152" frameborder="0" allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture" loading="lazy"></iframe>')
    for tipo, cod in re.findall(r"instagram\.com/(p|reel)/([A-Za-z0-9_-]+)", onde):
        embeds.append(f'<iframe src="https://www.instagram.com/{tipo}/{cod}/embed" width="400" height="480" frameborder="0" scrolling="no" allowtransparency="true"></iframe>')
    unicos = []
    for e in embeds:
        if e not in unicos:
            unicos.append(e)
    return unicos[:2]


PALAVRAS_LINK_UTIL = re.compile(r"ingresso|inscri|inscreva|compr|sympla|eventim|ticket|bilheteria|programa[çc][ãa]o|edital|site oficial|saiba mais|cadastr|formul[áa]rio", re.I)


def achar_links_uteis(pagina):
    """Links do texto original sobre ingressos, inscrições e informações."""
    miolo = trecho_da_materia(pagina) or pagina
    links = []
    for href, texto in re.findall(r"<a[^>]+href=\"(https?://[^\"]+)\"[^>]*>(.*?)</a>", miolo, flags=re.S | re.I):
        texto = decodificar(re.sub(r"<[^>]+>", "", texto))
        if not texto or len(texto) > 120:
            continue
        if PALAVRAS_LINK_UTIL.search(texto) or PALAVRAS_LINK_UTIL.search(href):
            href = html.unescape(href)
            if href not in [l["url"] for l in links]:
                links.append({"texto": texto, "url": href})
    return links[:5]


# ---------------- 3. Mandar para o Claude ----------------
INSTRUCAO_SAIDA = """

## Como responder
Você recebe uma notícia original. Siga a linha editorial acima à risca.
Responda SOMENTE com um objeto JSON válido, sem nenhum texto antes ou depois, com estes campos:
{
 "aprovada": true ou false (false se a notícia não passar no filtro ou não tiver informação suficiente),
 "motivo": "frase curta explicando a decisão",
 "categoria": uma destas: mundo, cotidiano, protagonista, cultura, politica, ancestralidade,
 "prioridade": uma destas: breaking, alta, media,
 "fato": "o fato principal em até 12 palavras, para comparar com outras notícias",
 "titulo": "título com até 60 caracteres",
 "linha_fina": "linha fina com até 350 caracteres",
 "corpo_html": "corpo em HTML só com <h2>, <h3>, <p>, <strong> e, se houver, <a href> dos links úteis informados; sem o parágrafo de crédito, que é colocado automaticamente",
 "palavras_chave": ["de 3 a 5 palavras-chave que aparecem escritas exatamente assim no corpo_html"],
 "hashtags": ["de 3 a 6 hashtags para redes sociais, sem espaços, começando com #"]
}
Se "aprovada" for false, os demais campos podem ficar vazios.
"""


def chamar_claude(linha_editorial, noticia):
    chave = os.environ.get("ANTHROPIC_API_KEY")
    if not chave:
        raise RuntimeError("Chave ANTHROPIC_API_KEY não encontrada no cofre.")
    pedido = (
        f"Veículo de origem: {noticia['veiculo']}\n"
        f"Link: {noticia['link']}\n"
        f"Data: {noticia['data_texto']}\n"
        f"Título original: {noticia['titulo']}\n"
        f"Links úteis do original (ingressos, inscrições, informações): "
        f"{json.dumps(noticia.get('links_uteis', []), ensure_ascii=False) or 'nenhum'}\n\n"
        f"Texto original:\n{noticia['texto'][:12000]}"
    )
    corpo = json.dumps({
        "model": MODELO,
        "max_tokens": 4000,
        "system": linha_editorial + INSTRUCAO_SAIDA,
        "messages": [{"role": "user", "content": pedido}],
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=corpo,
        headers={
            "x-api-key": chave,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        resposta = json.loads(r.read().decode("utf-8"))
    texto = "".join(b.get("text", "") for b in resposta.get("content", []))
    texto = re.sub(r"^```(?:json)?\s*", "", texto.strip(), flags=re.I)
    texto = re.sub(r"\s*```$", "", texto)
    inicio, fim = texto.find("{"), texto.rfind("}")
    if inicio < 0 or fim < 0:
        raise ValueError("O Claude não devolveu JSON.")
    texto = re.sub(r",\s*([}\]])", r"\1", texto[inicio:fim + 1])
    return json.loads(texto)


def limpar_html(corpo, links_permitidos=()):
    """Deixa só as tags permitidas: h2, h3, p, strong e <a> dos links úteis do original."""
    permitidos = set(links_permitidos)

    def tratar_link(m):
        href = html.unescape(m.group(1) or "")
        if href in permitidos:
            return f'<a href="{html.escape(href, quote=True)}" target="_blank" rel="noopener">{m.group(2)}</a>'
        return m.group(2)

    corpo = re.sub(r"<a\b[^>]*?href=\"([^\"]*)\"[^>]*>(.*?)</a>", tratar_link, corpo or "", flags=re.S | re.I)
    corpo = re.sub(r"</?(?!(?:h2|h3|p|strong|a)\b)[a-zA-Z0-9]+[^>]*>", "", corpo)
    corpo = re.sub(r"<(h2|h3|p|strong)\s[^>]*>", r"<\1>", corpo)
    return corpo.replace("*", "").strip()


def inserir_embeds(corpo, embeds):
    """Coloca os vídeos e áudios logo depois do primeiro parágrafo (o lead)."""
    if not embeds:
        return corpo
    blocos = "".join(f"<p>{e}</p>" for e in embeds)
    pos = corpo.find("</p>")
    if pos < 0:
        return blocos + corpo
    pos += len("</p>")
    return corpo[:pos] + blocos + corpo[pos:]


URL_BUSCA = "https://www.africas.com.br/noticias/buscar/"
COR_LINK = "#FF0000"
MAX_LINKS = 5


def slug(texto):
    import unicodedata
    t = unicodedata.normalize("NFD", texto or "")
    t = "".join(c for c in t if unicodedata.category(c) != "Mn").lower()
    t = re.sub(r"[^a-z0-9\s-]", "", t).strip()
    return re.sub(r"-+", "-", re.sub(r"\s+", "-", t))


def links_internos(corpo, palavras):
    """Liga até 5 palavras-chave à busca do site (igual ao Finalizador HTML do n8n)."""
    palavras = sorted({p.strip() for p in palavras if p and p.strip()}, key=len, reverse=True)
    total = 0
    for palavra in palavras:
        if total >= MAX_LINKS:
            break
        padrao = re.compile(re.escape(palavra), re.I)

        def trocar_paragrafo(m):
            nonlocal total, feito
            if feito:
                return m.group(0)
            partes = re.split(r"(<a\b.*?</a>|<[^>]+>)", m.group(0), flags=re.S)
            for i, parte in enumerate(partes):
                if parte.startswith("<") or feito:
                    continue
                nova, n = padrao.subn(lambda x: f'<a href="{URL_BUSCA}{slug(palavra)}/p/1" style="color:{COR_LINK};text-decoration:none;">{x.group(0)}</a>', parte, count=1)
                if n:
                    partes[i] = nova
                    feito = True
                    total += 1
            return "".join(partes)

        feito = False
        corpo = re.sub(r"<p>.*?</p>", trocar_paragrafo, corpo, flags=re.S)
    return corpo


# ---------------- 4. Montar o RSS no formato do site ----------------
DIAS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MESES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def data_rss(momento):
    m = momento.astimezone(FUSO_SP)
    return f"{DIAS[m.weekday()]}, {m.day:02d} {MESES[m.month - 1]} {m.year} {m:%H:%M:%S} -0300"


def cdata(texto):
    return (texto or "").replace("]]>", "]]&gt;")


def montar_rss(materia, categoria):
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:media="http://search.yahoo.com/mrss/">
<channel>
<title>Portal Áfricas</title>
<link>https://www.africas.com.br</link>
<description>Portal Áfricas</description>
<language>pt-br</language>
<item>
<title><![CDATA[{cdata(materia['titulo'])}]]></title>
<link>{html.escape(materia['link'], quote=False)}</link>
<guid isPermaLink="true">{html.escape(materia['link'], quote=False)}</guid>
<description><![CDATA[{cdata(materia['linha_fina'])}]]></description>
<content:encoded><![CDATA[{cdata(materia['corpo_html'])}]]></content:encoded>
<category>{categoria}</category>
<media:content url="{html.escape(materia['imagem'] or '', quote=True)}" medium="image" />

<media:description type="plain">
{html.escape(materia['credito_imagem'] or 'Divulgação', quote=False)}
</media:description>

<pubDate>{data_rss(datetime.now(timezone.utc))}</pubDate>
</item>
</channel>
</rss>"""


RSS_VAZIO = """<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>Portal Áfricas</title>
<link>https://www.africas.com.br</link><description>Sem postagens no momento</description><language>pt-br</language></channel></rss>"""


def montar_corpo(resultado, original):
    corpo = limpar_html(resultado.get("corpo_html"), [l["url"] for l in original["links_uteis"]])
    if not corpo:
        return ""
    corpo = links_internos(corpo, resultado.get("palavras_chave") or [])
    corpo = inserir_embeds(corpo, original["embeds"])
    corpo += f"<p>Com colaboração de {html.escape(original['veiculo'], quote=False)}.</p>"
    return corpo


# ---------------- Rodada principal ----------------
def mesmo_fato(titulo, fato, recentes):
    a, b = normalizar(titulo), normalizar(fato)
    for r in recentes:
        for x in (a, b):
            if not x:
                continue
            for y in (normalizar(r.get("titulo_original")), normalizar(r.get("fato"))):
                if y and difflib.SequenceMatcher(None, x, y).ratio() >= SEMELHANCA_MESMO_FATO:
                    return True
    return False


def main():
    agora = datetime.now(timezone.utc)
    fontes = ler_json(ARQ_FONTES, {})
    with open(ARQ_LINHA, encoding="utf-8") as f:
        linha_editorial = f.read()
    fila = ler_json(ARQ_FILA, [])
    vistos = ler_json(ARQ_VISTOS, [])
    publicadas = ler_json(ARQ_PUBLICADAS, [])
    vistos_set = set(vistos)
    limite_recentes = (agora - timedelta(days=3)).isoformat()
    recentes = [m for m in fila + publicadas if m.get("criado_em", "") >= limite_recentes]

    # Etapa A: buscar notícias novas nas fontes
    candidatas = []
    for categoria, urls in fontes.items():
        for url in urls:
            for item in ler_rss(url):
                if item["link"] in vistos_set:
                    continue
                if item["data"] and agora - item["data"] > timedelta(hours=IDADE_MAXIMA_HORAS):
                    vistos_set.add(item["link"])
                    vistos.append(item["link"])
                    continue
                item["categoria_fonte"] = categoria
                candidatas.append(item)
    candidatas.sort(key=lambda i: i["data"] or agora, reverse=True)
    log(f"Notícias novas encontradas: {len(candidatas)}")

    # Etapa B: processar no máximo MAX_NOVAS_POR_RODADA
    processadas = 0
    for item in candidatas:
        if processadas >= MAX_NOVAS_POR_RODADA:
            break
        link = item["link"]
        if link in vistos_set:
            continue
        log(f"> {item['titulo'][:80]}")
        if mesmo_fato(item["titulo"], "", recentes):
            log("  Descartada: mesmo fato de outra notícia já na fila ou publicada.")
            vistos_set.add(link); vistos.append(link)
            continue
        original = extrair_materia(link, item["titulo"], item.get("descricao", ""))
        if len(original["texto"]) < TEXTO_MINIMO:
            log("  Descartada: não deu para ler o texto completo no site original.")
            vistos_set.add(link); vistos.append(link)
            continue
        noticia = {
            "titulo": item["titulo"], "link": link, "veiculo": original["veiculo"],
            "texto": original["texto"], "links_uteis": original["links_uteis"],
            "data_texto": item["data"].astimezone(FUSO_SP).strftime("%d/%m/%Y %H:%M") if item["data"] else "",
        }
        try:
            resultado = chamar_claude(linha_editorial, noticia)
        except urllib.error.HTTPError as e:
            log(f"  Erro na API do Claude ({e.code}). Tenta de novo na próxima rodada.")
            if e.code in (400, 401, 403):
                break
            continue
        except Exception as e:
            log(f"  Resposta inválida do Claude: {e}")
            vistos_set.add(link); vistos.append(link)
            continue
        processadas += 1
        vistos_set.add(link); vistos.append(link)

        if not resultado.get("aprovada"):
            log(f"  Fora da linha: {resultado.get('motivo', '')}")
            continue
        categoria = resultado.get("categoria")
        if categoria not in CATEGORIAS:
            categoria = item["categoria_fonte"] if item["categoria_fonte"] in CATEGORIAS else None
        if not categoria:
            log("  Descartada: categoria inválida.")
            continue
        if mesmo_fato(item["titulo"], resultado.get("fato", ""), recentes):
            log("  Descartada: mesmo fato de outra notícia já na fila ou publicada.")
            continue
        materia = {
            "link": link,
            "titulo_original": item["titulo"],
            "fato": resultado.get("fato", ""),
            "titulo": decodificar(resultado.get("titulo")),
            "linha_fina": decodificar(resultado.get("linha_fina")),
            "corpo_html": montar_corpo(resultado, original),
            "categoria": categoria,
            "prioridade": resultado.get("prioridade") if resultado.get("prioridade") in PRIORIDADES else "media",
            "imagem": original["imagem"] or item["imagem"],
            "credito_imagem": original["credito_foto"] or "Divulgação",
            "veiculo": original["veiculo"],
            "autor": original["autor"],
            "palavras_chave": resultado.get("palavras_chave") or [],
            "hashtags": [h if h.startswith("#") else "#" + h for h in (resultado.get("hashtags") or [])],
            "criado_em": agora.isoformat(),
        }
        if not materia["titulo"] or not materia["corpo_html"]:
            log("  Descartada: o Claude não devolveu título ou texto.")
            continue
        fila.append(materia)
        recentes.append(materia)
        log(f"  Na fila: [{categoria} / {materia['prioridade']}] {materia['titulo']}")

    # Etapa C: soltar a próxima matéria de cada categoria
    os.makedirs(PASTA_FEEDS, exist_ok=True)
    for categoria in CATEGORIAS:
        arquivo = os.path.join(PASTA_FEEDS, f"{categoria}.xml")
        da_categoria = [m for m in fila if m["categoria"] == categoria]
        if not da_categoria:
            if not os.path.exists(arquivo):
                with open(arquivo, "w", encoding="utf-8") as f:
                    f.write(RSS_VAZIO)
            continue  # mantém o RSS como está
        da_categoria.sort(key=lambda m: (PRIORIDADES.index(m["prioridade"]), m["criado_em"]))
        escolhida = da_categoria[0]
        with open(arquivo, "w", encoding="utf-8") as f:
            f.write(montar_rss(escolhida, categoria))
        fila.remove(escolhida)
        escolhida["publicado_em"] = agora.isoformat()
        publicadas.append(escolhida)
        log(f"RSS {categoria} atualizado: {escolhida['titulo']}")

    salvar_json(ARQ_FILA, fila)
    salvar_json(ARQ_VISTOS, vistos[-5000:])
    salvar_json(ARQ_PUBLICADAS, publicadas[-300:])
    log(f"Fim. Na fila: {len(fila)} | Processadas nesta rodada: {processadas}")


if __name__ == "__main__":
    main()
