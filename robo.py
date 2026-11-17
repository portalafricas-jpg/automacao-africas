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
JANELA_HORAS = 2                # só entra notícia publicada nas últimas 2 horas
NOTA_MINIMA = 7                 # nota do editor-chefe para ir para a fila
LIMITE_DIA = 20                 # matérias publicadas por dia (breaking não conta e sai sempre)
HORA_INICIO = 8                 # das 8h à meia-noite publica normal; de madrugada, só breaking
MAX_TRIAGEM_POR_RODADA = 40     # quantos títulos o editor-chefe avalia por rodada
TEXTO_MINIMO = 600              # menos que isso de texto original = descarta (evita inventar)
SEMELHANCA_MESMO_FATO = 0.62    # títulos parecidos acima disso = mesmo fato
FUSO_SP = timezone(timedelta(hours=-3))
NAVEGADOR = "Mozilla/5.0 (compatible; RoboAfricas/1.0; +https://www.africas.com.br)"

PASTA = os.path.dirname(os.path.abspath(__file__))
ARQ_FONTES = os.path.join(PASTA, "fontes.json")
ARQ_LINHA = os.path.join(PASTA, "linha-editorial.md")
PASTA_ESTADO = os.path.join(PASTA, "estado")
ARQ_FILA = os.path.join(PASTA_ESTADO, "fila.json")
ARQ_VISTOS = os.path.join(PASTA_ESTADO, "vistos-processados.json")
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
class ErroAPI(Exception):
    """Problema para falar com o Claude (chave, internet, crédito). Nada é descartado."""


def enviar_claude(sistema, pedido, ferramenta, max_tokens=8000):
    """Manda o pedido ao Claude e recebe a resposta já organizada em campos (sem risco de JSON quebrado)."""
    chave = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    if not chave:
        raise ErroAPI("Chave ANTHROPIC_API_KEY não encontrada no cofre.")
    corpo = json.dumps({
        "model": MODELO,
        "max_tokens": max_tokens,
        "system": sistema,
        "messages": [{"role": "user", "content": pedido}],
        "tools": [ferramenta],
        "tool_choice": {"type": "tool", "name": ferramenta["name"]},
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=corpo,
        headers={"x-api-key": chave, "anthropic-version": "2023-06-01", "content-type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            resposta = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detalhe = e.read().decode("utf-8", errors="replace")[:300]
        raise ErroAPI(f"HTTP {e.code}: {detalhe}")
    except Exception as e:
        raise ErroAPI(str(e))
    for bloco in resposta.get("content", []):
        if bloco.get("type") == "tool_use" and isinstance(bloco.get("input"), dict):
            return bloco["input"]
    texto = "".join(b.get("text", "") for b in resposta.get("content", []))
    raise ValueError(f"resposta sem os campos (motivo de parada: {resposta.get('stop_reason')}; início: {texto[:150]!r})")


FERRAMENTA_EDITOR = {
    "name": "avaliar_noticias",
    "description": "Registra a avaliação do editor-chefe para cada notícia nova.",
    "input_schema": {
        "type": "object",
        "properties": {
            "avaliacoes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "nota": {"type": "integer", "minimum": 0, "maximum": 10},
                        "categoria": {"type": "string", "enum": CATEGORIAS},
                        "prioridade": {"type": "string", "enum": PRIORIDADES},
                        "repetida": {"type": "boolean"},
                        "motivo": {"type": "string"},
                    },
                    "required": ["id", "nota", "categoria", "prioridade", "repetida", "motivo"],
                },
            }
        },
        "required": ["avaliacoes"],
    },
}

FERRAMENTA_REDATOR = {
    "name": "entregar_materia",
    "description": "Entrega a matéria reescrita (ou a recusa) seguindo a linha editorial.",
    "input_schema": {
        "type": "object",
        "properties": {
            "aprovada": {"type": "boolean"},
            "motivo": {"type": "string"},
            "titulo": {"type": "string", "description": "até 60 caracteres"},
            "linha_fina": {"type": "string", "description": "até 350 caracteres"},
            "corpo_html": {"type": "string", "description": "HTML só com h2, h3, p, strong e, se houver, a href dos links úteis; sem o parágrafo de crédito"},
            "palavras_chave": {"type": "array", "items": {"type": "string"}, "description": "3 a 5, escritas exatamente como aparecem no corpo"},
            "hashtags": {"type": "array", "items": {"type": "string"}, "description": "3 a 6, sem espaços, começando com #"},
        },
        "required": ["aprovada", "motivo"],
    },
}


INSTRUCAO_EDITOR = """

## Sua função agora: EDITOR-CHEFE (decide, não escreve)
Você recebe uma lista de notícias novas (só título e resumo), a data de hoje e uma lista de matérias recentes do portal.
Para cada notícia nova, dê:
- nota de 0 a 10, seguindo exatamente a "Régua de notas do editor-chefe" e as "Datas da memória negra" da linha editorial acima. Ser local não diminui a nota.
- categoria: mundo, cotidiano, protagonista, cultura, politica ou ancestralidade.
- prioridade: breaking, alta ou media, conforme a seção "Prioridade" da linha editorial.
- repetida: true se for o mesmo fato de outra notícia da lista nova (fique só com a primeira) ou de uma matéria recente do portal.
- motivo: frase curta explicando a nota com base na régua.
Registre a avaliação de todas as notícias usando a ferramenta avaliar_noticias.
"""


INSTRUCAO_REDATOR = """

## Sua função agora: REDATOR (escreve)
Você recebe uma notícia original já aprovada pelo editor-chefe. Reescreva seguindo a linha editorial acima à risca.
Se, lendo o texto completo, perceber que não há informação suficiente para uma matéria honesta, recuse.
Entregue o resultado usando a ferramenta entregar_materia. O corpo_html não leva o parágrafo de crédito, que é colocado automaticamente.
Se "aprovada" for false, os demais campos podem ficar vazios.
"""


def editor_chefe(linha_editorial, noticias, recentes):
    """Avalia vários títulos numa única consulta. Devolve {id: avaliação}."""
    lista = "\n".join(
        f"{n['id']}. {n['titulo']} | {n.get('descricao', '')[:300]}" for n in noticias
    )
    portal = "\n".join(f"- {r.get('titulo_original') or r.get('titulo')}" for r in recentes[-80:]) or "nenhuma"
    hoje = datetime.now(FUSO_SP).strftime("%d/%m/%Y")
    pedido = (f"DATA DE HOJE: {hoje}\n\nNOTÍCIAS NOVAS:\n{lista}\n\n"
              f"MATÉRIAS RECENTES DO PORTAL (para achar repetidas):\n{portal}")
    resultado = enviar_claude(linha_editorial + INSTRUCAO_EDITOR, pedido, FERRAMENTA_EDITOR)
    return {a.get("id"): a for a in resultado.get("avaliacoes", []) if isinstance(a, dict)}


def redator(linha_editorial, noticia):
    pedido = (
        f"Veículo de origem: {noticia['veiculo']}\n"
        f"Link: {noticia['link']}\n"
        f"Data: {noticia['data_texto']}\n"
        f"Título original: {noticia['titulo']}\n"
        f"Links úteis do original (ingressos, inscrições, informações): "
        f"{json.dumps(noticia.get('links_uteis', []), ensure_ascii=False)}\n\n"
        f"Texto original:\n{noticia['texto'][:12000]}"
    )
    return enviar_claude(linha_editorial + INSTRUCAO_REDATOR, pedido, FERRAMENTA_REDATOR)


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


def fim_do_dia_seguinte(momento):
    sp = momento.astimezone(FUSO_SP)
    amanha = (sp + timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=0)
    return amanha.astimezone(timezone.utc).isoformat()


def publicar(materia_fila, linha_editorial, agora):
    """Extrai o texto original, manda o redator escrever e devolve a matéria pronta (ou None)."""
    original = extrair_materia(materia_fila["link"], materia_fila["titulo_original"], materia_fila.get("descricao", ""))
    if len(original["texto"]) < TEXTO_MINIMO:
        log("  Descartada: não deu para ler o texto completo no site original.")
        return None
    data = datetime.fromisoformat(materia_fila["data_original"])
    noticia = {
        "titulo": materia_fila["titulo_original"], "link": materia_fila["link"], "veiculo": original["veiculo"],
        "texto": original["texto"], "links_uteis": original["links_uteis"],
        "data_texto": data.astimezone(FUSO_SP).strftime("%d/%m/%Y %H:%M"),
    }
    try:
        resultado = redator(linha_editorial, noticia)
    except ErroAPI:
        raise
    except Exception as e:
        log(f"  Resposta inválida do redator: {e}")
        return "tentar_de_novo"
    if not resultado.get("aprovada"):
        log(f"  Recusada pelo redator: {resultado.get('motivo', '')}")
        return None
    corpo = montar_corpo(resultado, original)
    titulo = decodificar(resultado.get("titulo"))
    if not titulo or not corpo:
        log("  Descartada: o redator não devolveu título ou texto.")
        return None
    return dict(materia_fila, **{
        "titulo": titulo,
        "linha_fina": decodificar(resultado.get("linha_fina")),
        "corpo_html": corpo,
        "imagem": original["imagem"] or materia_fila.get("imagem_rss", ""),
        "credito_imagem": original["credito_foto"] or "Divulgação",
        "veiculo": original["veiculo"],
        "autor": original["autor"],
        "palavras_chave": resultado.get("palavras_chave") or [],
        "hashtags": [h if h.startswith("#") else "#" + h for h in (resultado.get("hashtags") or [])],
        "publicado_em": agora.isoformat(),
    })


def main():
    agora = datetime.now(timezone.utc)
    agora_sp = agora.astimezone(FUSO_SP)
    fontes = ler_json(ARQ_FONTES, {})
    with open(ARQ_LINHA, encoding="utf-8") as f:
        linha_editorial = f.read()
    fila = ler_json(ARQ_FILA, [])
    vistos = ler_json(ARQ_VISTOS, [])
    publicadas = ler_json(ARQ_PUBLICADAS, [])
    vistos_set = set(vistos)

    def marcar_visto(link):
        if link not in vistos_set:
            vistos_set.add(link)
            vistos.append(link)

    # Limpa da fila o que passou do fim do dia seguinte
    antes = len(fila)
    fila = [m for m in fila if m.get("expira_em", "9") >= agora.isoformat()]
    if antes != len(fila):
        log(f"Saíram da fila por tempo: {antes - len(fila)}")

    recentes = [m for m in fila + publicadas
                if m.get("data_original", m.get("criado_em", "")) >= (agora - timedelta(days=2)).isoformat()]

    # Etapa A: buscar notícias novas (janela de 2 horas)
    candidatas = []
    for categoria, urls in fontes.items():
        for url in urls:
            for item in ler_rss(url):
                if item["link"] in vistos_set or item["link"] in [c["link"] for c in candidatas]:
                    continue
                if item["data"] and agora - item["data"] > timedelta(hours=JANELA_HORAS):
                    marcar_visto(item["link"])
                    continue
                if mesmo_fato(item["titulo"], "", recentes + candidatas):
                    log(f"Repetida (mesmo fato): {item['titulo'][:80]}")
                    marcar_visto(item["link"])
                    continue
                item["categoria_fonte"] = categoria
                candidatas.append(dict(item, titulo_original=item["titulo"]))
    candidatas.sort(key=lambda i: i["data"] or agora)
    candidatas = candidatas[:MAX_TRIAGEM_POR_RODADA]
    log(f"Notícias novas na janela de {JANELA_HORAS}h: {len(candidatas)}")

    # Etapa B: editor-chefe dá nota (uma consulta só para todas)
    if candidatas:
        for n, c in enumerate(candidatas, start=1):
            c["id"] = n
        try:
            avaliacoes = editor_chefe(linha_editorial, candidatas, recentes)
        except ErroAPI as e:
            log(f"Não conseguiu falar com o Claude: {e}")
            log("Nada foi descartado. Tenta de novo na próxima rodada.")
            avaliacoes = None
        except Exception as e:
            log(f"Resposta inválida do editor-chefe: {e}. Tenta de novo na próxima rodada.")
            avaliacoes = None
        if avaliacoes is not None:
            for c in candidatas:
                a = avaliacoes.get(c["id"])
                if not a:
                    continue  # sem avaliação: tenta na próxima rodada
                marcar_visto(c["link"])
                nota = a.get("nota") or 0
                if a.get("repetida"):
                    log(f"Repetida: {c['titulo'][:70]}")
                    continue
                if nota < NOTA_MINIMA:
                    log(f"Nota {nota}, fora: {c['titulo'][:70]} ({a.get('motivo', '')})")
                    continue
                categoria = a.get("categoria") if a.get("categoria") in CATEGORIAS else c["categoria_fonte"]
                if categoria not in CATEGORIAS:
                    continue
                prioridade = a.get("prioridade") if a.get("prioridade") in PRIORIDADES else "media"
                fila.append({
                    "link": c["link"], "titulo_original": c["titulo"], "descricao": c.get("descricao", ""),
                    "imagem_rss": c.get("imagem", ""), "categoria": categoria, "prioridade": prioridade,
                    "nota": nota, "motivo_nota": a.get("motivo", ""),
                    "data_original": (c["data"] or agora).astimezone(timezone.utc).isoformat(),
                    "criado_em": agora.isoformat(), "expira_em": fim_do_dia_seguinte(agora),
                })
                log(f"Nota {nota}, na fila: [{categoria} / {prioridade}] {c['titulo'][:70]}")

    # Etapa C: publicar (uma por categoria por rodada)
    hoje = agora_sp.date().isoformat()
    publicadas_hoje = sum(
        1 for m in publicadas
        if m.get("prioridade") != "breaking"
        and datetime.fromisoformat(m["publicado_em"]).astimezone(FUSO_SP).date().isoformat() == hoje
    )
    horario_normal = agora_sp.hour >= HORA_INICIO
    log(f"Publicadas hoje (sem contar breaking): {publicadas_hoje} de {LIMITE_DIA} | "
        f"{'horário normal' if horario_normal else 'madrugada: só breaking'}")

    def ordem(m):
        return (PRIORIDADES.index(m["prioridade"]), m["data_original"])

    os.makedirs(PASTA_FEEDS, exist_ok=True)
    for categoria in CATEGORIAS:
        arquivo = os.path.join(PASTA_FEEDS, f"{categoria}.xml")
        if not os.path.exists(arquivo):
            with open(arquivo, "w", encoding="utf-8") as f:
                f.write(RSS_VAZIO)

    parar = False
    tops = []
    for categoria in CATEGORIAS:
        da_categoria = sorted([m for m in fila if m["categoria"] == categoria], key=ordem)
        if da_categoria:
            tops.append(da_categoria)
    tops.sort(key=lambda lista: ordem(lista[0]))  # quem tem a mais urgente/antiga vai primeiro

    for da_categoria in tops:
        if parar:
            break
        for materia_fila in da_categoria[:3]:  # tenta até 3 da mesma categoria se alguma for recusada
            e_breaking = materia_fila["prioridade"] == "breaking"
            if not e_breaking and (not horario_normal or publicadas_hoje >= LIMITE_DIA):
                break  # espera: fora do horário ou limite do dia atingido
            log(f"> Publicando [{materia_fila['categoria']} / {materia_fila['prioridade']}] {materia_fila['titulo_original'][:70]}")
            try:
                pronta = publicar(materia_fila, linha_editorial, agora)
            except ErroAPI as e:
                log(f"  Não conseguiu falar com o Claude: {e}. A matéria continua na fila.")
                parar = True
                break
            if pronta == "tentar_de_novo":
                materia_fila["tentativas"] = materia_fila.get("tentativas", 0) + 1
                if materia_fila["tentativas"] >= 2:
                    log("  Duas falhas seguidas: matéria retirada da fila.")
                    fila.remove(materia_fila)
                continue
            fila.remove(materia_fila)
            if not pronta:
                continue
            with open(os.path.join(PASTA_FEEDS, f"{pronta['categoria']}.xml"), "w", encoding="utf-8") as f:
                f.write(montar_rss(pronta, pronta["categoria"]))
            publicadas.append(pronta)
            if not e_breaking:
                publicadas_hoje += 1
            log(f"  RSS {pronta['categoria']} atualizado: {pronta['titulo']}")
            break  # uma por categoria por rodada

    salvar_json(ARQ_FILA, fila)
    salvar_json(ARQ_VISTOS, vistos[-5000:])
    salvar_json(ARQ_PUBLICADAS, publicadas[-500:])
    log(f"Fim. Na fila de espera: {len(fila)} | Publicadas hoje: {publicadas_hoje}")


if __name__ == "__main__":
    main()
