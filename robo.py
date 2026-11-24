# Robô de conteúdo do portal Áfricas
# Busca notícias nas fontes, filtra, manda o Claude reescrever na linha editorial
# e atualiza um RSS por categoria, no mesmo formato do RSS que o site já lê.

import difflib
import html
import json
from collections import Counter
import os
import re
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlparse

try:
    import trafilatura
except ImportError:
    trafilatura = None

# ---------------- Configurações ----------------
CATEGORIAS = ["mundo", "cotidiano", "protagonista", "cultura", "politica", "ancestralidade"]
PRIORIDADES = ["breaking", "alta", "media"]
MODELO = "claude-haiku-5-5"
JANELA_HORAS = 1                # só entra notícia publicada na última hora (sites com RSS)
JANELA_HORAS_BUSCA = 3          # buscas no Google Notícias: notícias das últimas 3 horas
VALIDADE_HORAS = 4              # notícia com mais de 4 horas não é publicada, nem saindo da fila
NOTA_MINIMA = 8                 # nota do editor-chefe para ir para a fila (era 7; mudou em 23/11)
NOTA_EXCECAO = 7                # carnaval/escolas de samba e lançamentos de artistas negros continuam com 7
TETO_DIA = 25                   # no máximo 25 matérias por dia no site (breaking e ministérios fora do teto)
def teto_por_hora(hora):
    """Picos de leitura no celular (aprovado em 24/11): manhã no trajeto, expediente calmo, noite."""
    if 6 <= hora < 9:
        return 4
    if hora >= 18:
        return 2
    return 1
TETO_EDITORIA = {"politica": 3, "cultura": 6, "cotidiano": 5, "ancestralidade": 4, "protagonista": 4, "mundo": 3}  # política 3 (23/11)
LIMITE_AFRICA_DIA = 5           # no máximo 5 matérias por dia de fontes África (breaking não conta)
INTERVALO_AFRICA_HORAS = 2      # e no mínimo 2 horas entre uma e outra
MINUTO_PARTIDA = 2              # o cron-job.org dá a partida em :02, :17, :32 e :47 (o site lê em :00, :15, :30, :45)
MINUTOS_PARA_PUBLICAR = 7       # só publica até 7 minutos depois da partida, para o site ver a matéria com certeza
HORA_INICIO = 6                 # das 6h à meia-noite publica normal; de madrugada, só breaking (6h desde 24/11)
MAX_TRIAGEM_POR_RODADA = 40     # quantos títulos o editor-chefe avalia por rodada
TEXTO_MINIMO = 600              # menos que isso de texto original = descarta (evita inventar)
SEMELHANCA_MESMO_FATO = 0.62    # títulos parecidos acima disso = mesmo fato (entre fontes da mesma rodada)
SEMELHANCA_JA_PUBLICADA = 0.85  # quase idêntico a matéria do portal = repetida sem precisar do editor-chefe
DIAS_REPETIDAS = 5              # o editor-chefe compara com as matérias dos últimos 5 dias
GRUPOS_BUSCA = 4                # as buscas são divididas em 4 grupos: cada termo é buscado uma vez por hora
INSTAGRAM = "https://www.instagram.com/africasplay"
ROBO_WIKI = "RoboAfricas/1.0 (https://www.africas.com.br; robo do portal)"
FUSO_SP = timezone(timedelta(hours=-3))
NAVEGADORES = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
]

PASTA = os.path.dirname(os.path.abspath(__file__))
ARQ_FONTES = os.path.join(PASTA, "fontes.json")
ARQ_LINHA = os.path.join(PASTA, "linha-editorial.md")
PASTA_ESTADO = os.path.join(PASTA, "estado")
ARQ_FILA = os.path.join(PASTA_ESTADO, "fila.json")
ARQ_VISTOS = os.path.join(PASTA_ESTADO, "vistos-processados.json")
ARQ_PUBLICADAS = os.path.join(PASTA_ESTADO, "publicadas.json")
ARQ_PRIMEIRA_VEZ = os.path.join(PASTA_ESTADO, "primeira-vez.json")
PASTA_FEEDS = os.path.join(PASTA, "feeds")
PASTA_RELATORIOS = os.path.join(PASTA_ESTADO, "relatorios")
LIMITE_TITULO = 60
LIMITE_CORPO = 3500


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
    """Abre a página como um navegador comum; se o site recusar, tenta com outro navegador."""
    erro = None
    for nav in NAVEGADORES:
        req = urllib.request.Request(url, headers={
            "User-Agent": nav,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.5",
        })
        try:
            with urllib.request.urlopen(req, timeout=tempo) as r:
                return r.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            erro = e
            if e.code not in (403, 406):
                raise
    raise erro


def normalizar(texto):
    texto = html.unescape(texto or "").lower()
    texto = re.sub(r"[^\w\s]", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


# ---------------- Relatório diário ----------------
RELATORIO = []


def registrar(materia, destino, detalhe="", **extra):
    """Anota no relatório do dia o que aconteceu com cada notícia."""
    RELATORIO.append(dict({
        "hora": datetime.now(FUSO_SP).strftime("%H:%M"),
        "fonte": materia.get("fonte_nome") or materia.get("veiculo") or "",
        "titulo": materia.get("titulo_original") or materia.get("titulo") or "",
        "link": materia.get("link", ""),
        "categoria": materia.get("categoria", ""),
        "prioridade": materia.get("prioridade", ""),
        "nota": materia.get("nota", ""),
        "destino": destino,
        "detalhe": detalhe,
    }, **extra))


def salvar_relatorio(agora):
    """Junta o que aconteceu nesta rodada ao relatório do dia e reescreve o resumo."""
    dia = agora.astimezone(FUSO_SP).date().isoformat()
    arq_json = os.path.join(PASTA_RELATORIOS, f"{dia}.json")
    eventos = ler_json(arq_json, []) + RELATORIO
    salvar_json(arq_json, eventos)
    from collections import Counter
    por_destino = Counter(e["destino"] for e in eventos)
    publicadas = [e for e in eventos if e["destino"] == "publicada"]
    por_categoria = Counter(e["categoria"] for e in publicadas)
    analisadas_fonte = Counter(e["fonte"] for e in eventos if e["destino"] in ("na fila", "nota baixa", "repetida"))
    publicadas_fonte = Counter(e["fonte"] for e in publicadas)
    linhas = [f"# Relatório do robô Áfricas — {dia}", "",
              f"Atualizado em {agora.astimezone(FUSO_SP).strftime('%d/%m/%Y %H:%M')}.", "",
              "## Resumo por destino", ""]
    linhas += [f"- {d}: {n}" for d, n in por_destino.most_common()]
    linhas += ["", "## Publicadas por categoria", ""]
    linhas += [f"- {c}: {por_categoria.get(c, 0)}" for c in CATEGORIAS]
    linhas += ["", "## Fontes (notícias analisadas / publicadas)", ""]
    for f, n in analisadas_fonte.most_common():
        linhas.append(f"- {f}: {n} / {publicadas_fonte.get(f, 0)}")
    linhas += ["", "## Todas as notícias do dia", "",
               "| Hora | Destino | Nota | Categoria | Prioridade | Fonte | Título | Detalhe |",
               "|---|---|---|---|---|---|---|---|"]
    for e in eventos:
        titulo = e["titulo"].replace("|", "/")[:90]
        detalhe = str(e.get("detalhe", "")).replace("|", "/").replace("\n", " ")[:160]
        linhas.append(f"| {e['hora']} | {e['destino']} | {e['nota']} | {e['categoria']} | {e['prioridade']} | "
                      f"{e['fonte'][:30]} | [{titulo}]({e['link']}) | {detalhe} |")
    with open(os.path.join(PASTA_RELATORIOS, f"{dia}.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(linhas) + "\n")


# ---------------- 1. Ler as fontes (RSS) ----------------
def consertar_xml(texto):
    """Conserta caracteres que às vezes vêm quebrados no RSS (principalmente do Bing)."""
    texto = (texto or "").lstrip("\ufeff \r\n\t")
    if "<" in texto and not texto.startswith("<"):
        texto = texto[texto.index("<"):]
    texto = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", texto)
    texto = re.sub(r"&(?!(?:[a-zA-Z][a-zA-Z0-9]*|#\d+|#x[0-9a-fA-F]+);)", "&amp;", texto)
    return texto


def ler_rss(url):
    itens = []
    try:
        raiz = ET.fromstring(consertar_xml(baixar(url)).encode("utf-8"))
    except Exception as e:
        log(f"  Erro ao ler fonte {url[:90]}: {e}")
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
    if not itens:  # alguns sites usam o formato Atom em vez de RSS
        ns = "{http://www.w3.org/2005/Atom}"
        for e in raiz.iter(ns + "entry"):
            titulo = (e.findtext(ns + "title") or "").strip()
            link = ""
            for l in e.findall(ns + "link"):
                if l.get("rel", "alternate") == "alternate":
                    link = l.get("href", "")
            data = None
            try:
                data = datetime.fromisoformat((e.findtext(ns + "published") or e.findtext(ns + "updated") or "").replace("Z", "+00:00"))
            except Exception:
                pass
            resumo = e.findtext(ns + "summary") or ""
            if titulo and link:
                itens.append({"titulo": decodificar(titulo), "link": link, "data": data, "imagem": "",
                              "descricao": decodificar(re.sub(r"<[^>]+>", " ", resumo))})
    return itens


def bing_url(busca):
    # qft=sortbydate="1": pede ao Bing as notícias mais novas primeiro (sem isso ele ordena por relevância)
    return "https://www.bing.com/news/search?" + urllib.parse.urlencode(
        {"q": busca, "format": "rss", "mkt": "pt-BR", "setlang": "pt-BR", "cc": "BR", "qft": 'sortbydate="1"'})


def google_url(busca):
    # Google Notícias (troca do Bing em 23/11/2026: o Bing mostrava as notícias com 10 a 24 horas de atraso)
    return "https://news.google.com/rss/search?" + urllib.parse.urlencode(
        {"q": f"{busca} when:1d", "hl": "pt-BR", "gl": "BR", "ceid": "BR:pt-419"})


def link_real_google(link):
    """O Google Notícias entrega o link 'embrulhado'; aqui ele é desembrulhado para o endereço real da matéria."""
    if "news.google.com" not in link:
        return link
    try:
        from googlenewsdecoder import gnewsdecoder
        r = gnewsdecoder(link, interval=1)
        if (r.get("success") or r.get("status")) and r.get("decoded_url"):
            return r["decoded_url"]
        log(f"  Não desembrulhou o link do Google Notícias: {r.get('message', '')}")
    except Exception as e:
        log(f"  Não desembrulhou o link do Google Notícias: {e}")
    return ""


_EM_ALTA = None


def assuntos_em_alta():
    """Assuntos em alta no Google no Brasil (lista pública e gratuita do Google Trends).
    Serve só de BÔNUS: matéria que já passou na linha editorial (nota 7+) e bate com um assunto em alta
    ganha +1. Matéria fora da linha editorial nunca entra por estar em alta. (Aprovado em 23/11/2026.)"""
    global _EM_ALTA
    if _EM_ALTA is not None:
        return _EM_ALTA
    _EM_ALTA = []
    try:
        raiz = ET.fromstring(baixar("https://trends.google.com/trending/rss?geo=BR"))
        for item in raiz.iter("item"):
            termo = normalizar(sem_acento(item.findtext("title") or ""))
            if len(termo) >= 4:
                _EM_ALTA.append(termo)
        log(f"Google Trends: {len(_EM_ALTA)} assuntos em alta no Brasil agora.")
    except Exception as e:
        log(f"Google Trends indisponível nesta rodada ({e}); segue sem o bônus.")
    return _EM_ALTA


def em_alta(texto):
    t = " " + normalizar(sem_acento(texto or "")) + " "
    for termo in assuntos_em_alta():
        if f" {termo} " in t:
            return termo
    return ""


def link_real_bing(link):
    """O Bing esconde o endereço da matéria no pedaço url= do link."""
    q = urllib.parse.parse_qs(urlparse(link).query)
    if "url" in q:
        return q["url"][0]
    return link if "bing.com" not in link else ""


def ler_pagina_de_noticias(url):
    """Site sem RSS: pega da página de notícias os links que parecem matérias do mesmo site."""
    try:
        pagina = baixar(url)
    except Exception as e:
        log(f"  Erro ao ler a página {url}: {e}")
        return []
    dominio = urlparse(url).netloc
    itens, vistos = [], set()
    for href, texto in re.findall(r'<a[^>]+href=["\']([^"\'#]+)["\'][^>]*>(.*?)</a>', pagina, flags=re.S | re.I):
        link = urljoin(url, html.unescape(href))
        p = urlparse(link)
        titulo = decodificar(re.sub(r"<[^>]+>", " ", texto))
        if p.netloc != dominio or link in vistos or len(titulo) < 35:
            continue
        caminho = p.path.strip("/")
        if caminho.count("/") < 2 and not re.search(r"\d{4}", caminho):
            continue
        vistos.add(link)
        itens.append({"titulo": titulo, "link": link, "data": None, "imagem": "", "descricao": ""})
    return itens[:20]


def ler_fonte(fonte, rodada):
    """Lê uma fonte da lista conforme o tipo: rss, pagina (site sem RSS) ou busca (Google Notícias)."""
    tipo = fonte.get("tipo")
    if tipo == "rss":
        return ler_rss(fonte["url"])
    if tipo == "pagina":
        return ler_pagina_de_noticias(fonte["url"])
    if tipo == "busca":
        if "dia_semana" in fonte and datetime.now(FUSO_SP).weekday() != fonte["dia_semana"]:
            return []  # busca semanal: só roda no dia dela (0 = segunda ... 6 = domingo)
        if fonte.get("grupo", 0) % GRUPOS_BUSCA != rodada % GRUPOS_BUSCA:
            return []
        itens = []
        for item in ler_rss(google_url(fonte["busca"])):
            # o Google põe " - Nome do veículo" no fim do título
            partes = item["titulo"].rsplit(" - ", 1)
            if len(partes) == 2 and len(partes[1]) <= 40:
                item["titulo"] = partes[0].strip()
            if item["link"]:
                itens.append(item)  # o link real é desembrulhado só quando a matéria vai ser escrita
        return itens
    log(f"  Tipo de fonte desconhecido: {fonte.get('nome')}")
    return []


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

    # crédito da foto: campo de crédito do site, legenda da imagem ou "Foto: ..." no texto
    candidatos = []
    for trecho in re.findall(r"<[^>]+class=[\"'][^\"']*(?:credit|credito|creditos|photo-credit|foto-credito)[^\"']*[\"'][^>]*>(.*?)</[a-z]+>", pagina, flags=re.S | re.I):
        candidatos.append(decodificar(re.sub(r"<[^>]+>", " ", trecho)))
    for legenda in re.findall(r"<figcaption[^>]*>(.*?)</figcaption>", pagina, flags=re.S | re.I):
        candidatos.append(decodificar(re.sub(r"<[^>]+>", " ", legenda)))
    candidatos.append(resultado["texto"])
    for c in candidatos:
        c = re.sub(r"(?i)cr[ée]ditos?\s+da\s+(?:imagem|foto)\s*:", "Foto:", c or "")
        m = PADRAO_CREDITO.search(c + "\n")
        if m:
            resultado["credito_foto"] = limpar_credito(m.group(1))
            if resultado["credito_foto"]:
                break

    resultado["fotos_corpo"] = achar_fotos_corpo(pagina, resultado["imagem"])
    resultado["embeds"] = achar_embeds(pagina)
    resultado["links_uteis"] = achar_links_uteis(pagina)
    resultado["texto"] = limpeza_mecanica(resultado["texto"], titulo, descricao)
    resultado["veiculo"] = decodificar(resultado["veiculo"])
    resultado["autor"] = decodificar(resultado["autor"])
    return resultado



def limpar_credito(texto):
    """Tira parênteses, colchetes e sinais soltos do crédito da foto."""
    c = decodificar(texto)
    c = re.sub(r"\(\s*\)|\[\s*\]", "", c)
    if c.count("(") != c.count(")"):
        c = c.replace("(", "").replace(")", "")
    if c.count("[") != c.count("]"):
        c = c.replace("[", "").replace("]", "")
    c = re.sub(r"\s+", " ", c)
    return c.strip(" .,;:-–—/|")


def trecho_da_materia(pagina):
    """Pega só o miolo da matéria (tag <article>), para não pegar menus e rodapé."""
    m = re.search(r"<article\b.*?</article>", pagina, flags=re.S | re.I)
    return m.group(0) if m else ""


def achar_fotos_corpo(pagina, principal=""):
    """Fotos dentro do texto da matéria original (com legenda e crédito), além da foto principal."""
    miolo = trecho_da_materia(pagina) or pagina
    base_principal = re.sub(r"[-_]\d+x\d+|[-_](?:c|k|b|o)(?=\.)", "", os.path.basename(urlparse(principal).path))
    fotos, vistas = [], set()
    for fig in re.findall(r"<figure\b.*?</figure>", miolo, flags=re.S | re.I):
        m = re.search(r"<img[^>]+(?:data-src|data-lazy-src|src)=[\"']([^\"']+)[\"']", fig, re.I)
        if not m:
            continue
        src = html.unescape(m.group(1))
        if src.startswith("//"):
            src = "https:" + src
        if not src.startswith("http") or re.search(r"logo|icon|avatar|banner|publicidade|\.svg|\.gif", src, re.I):
            continue
        base = re.sub(r"[-_]\d+x\d+|[-_](?:c|k|b|o)(?=\.)", "", os.path.basename(urlparse(src).path))
        if base in vistas or (base_principal and base == base_principal):
            continue
        vistas.add(base)
        cap = decodificar(re.sub(r"<[^>]+>", " ", " ".join(re.findall(r"<figcaption[^>]*>(.*?)</figcaption>", fig, flags=re.S | re.I))))
        cap = re.sub(r"\s+", " ", cap).strip()
        credito, legenda = "", cap
        c = re.search(r"(?i)\b(?:foto|fotos|imagem|crédito|credito)\s*:?\s*([^|]{3,80})$", cap)
        if c:
            credito = limpar_credito(c.group(1))
            legenda = cap[:c.start()].strip(" –—-|,.")
        fotos.append({"url": src, "legenda": legenda[:200], "credito": credito})
        if len(fotos) >= 6:
            break
    return fotos


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


USO = {"input_tokens": 0, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0, "output_tokens": 0}
CACHE = {"ligado": True}


def enviar_claude(sistema, pedido, ferramenta, max_tokens=8000, fixo=None):
    """Manda o pedido ao Claude e recebe a resposta já organizada em campos (sem risco de JSON quebrado).
    O texto 'fixo' (a linha editorial) vai com cache de prompt: o Claude guarda por 1 hora e cobra bem menos."""
    chave = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    if not chave:
        raise ErroAPI("Chave ANTHROPIC_API_KEY não encontrada no cofre.")
    for tentativa in (1, 2):
        if fixo:
            bloco_fixo = {"type": "text", "text": fixo}
            if CACHE["ligado"]:
                bloco_fixo["cache_control"] = {"type": "ephemeral", "ttl": "1h"}
            system = [bloco_fixo, {"type": "text", "text": sistema}]
        else:
            system = sistema
        corpo = json.dumps({
            "model": MODELO,
            "max_tokens": max_tokens,
            "system": system,
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
            break
        except urllib.error.HTTPError as e:
            detalhe = e.read().decode("utf-8", errors="replace")[:300]
            if e.code == 400 and fixo and CACHE["ligado"] and re.search(r"cache|ttl", detalhe, re.I):
                log("  O cache de prompt não foi aceito; seguindo sem cache.")
                CACHE["ligado"] = False
                continue
            raise ErroAPI(f"HTTP {e.code}: {detalhe}")
        except Exception as e:
            raise ErroAPI(str(e))
    uso = resposta.get("usage", {}) or {}
    for k in USO:
        USO[k] += int(uso.get(k) or 0)
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
                        "excecao_nota7": {"type": "boolean", "description": "true se for carnaval/escola de samba ou lançamento de artista negro (disco, livro, filme, série, espetáculo)"},
                        "evento_local_pequeno": {"type": "boolean", "description": "true se for evento local pequeno (oficina, palestra, celebração municipal, ação de biblioteca ou escola) fora de capital ou grande cidade e sem personagem ou fato relevante"},
                        "ministerio": {"type": "boolean", "description": "true se for ação, anúncio ou decisão do Ministério da Igualdade Racial ou de outro ministério do governo federal que atinja a população negra"},
                        "motivo": {"type": "string"},
                    },
                    "required": ["id", "nota", "categoria", "prioridade", "repetida", "excecao_nota7", "evento_local_pequeno", "ministerio", "motivo"],
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
            "titulo": {"type": "string", "description": "até 60 caracteres, contando espaços"},
            "linha_fina": {"type": "string", "description": "até 350 caracteres"},
            "corpo_html": {"type": "string", "description": "HTML só com h2, p, strong e, se houver, a href dos links úteis; formato de matéria jornalística, sem perguntas e respostas e sem intertítulo em forma de pergunta; sem parágrafo de crédito ao site de origem"},
            "palavras_chave": {"type": "array", "items": {"type": "string"}, "description": "3 a 5 assuntos curtos (1 a 3 palavras, até 4 se for nome próprio), do tipo que vira tag, tirados do próprio corpo e escritos exatamente como aparecem nele"},
            "hashtags": {"type": "array", "items": {"type": "string"}, "description": "3 a 6, sem espaços, começando com #"},
            "pessoa_principal": {"type": "string", "description": "nome completo da pessoa de quem a matéria trata, se for sobre uma pessoa específica; senão, vazio"},
            "busca_foto": {"type": "string", "description": "2 a 4 palavras em inglês que descrevem a cena do tema, para buscar foto ilustrativa (ex.: black woman entrepreneur)"},
            "busca_foto_sem_rosto": {"type": "string", "description": "2 a 4 palavras em inglês com objetos ou lugar do tema, sem pessoas (ex.: african drums, books library, stage microphone)"},
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
- repetida: true se for o mesmo fato de outra notícia da lista nova (fique só com a primeira) ou de uma matéria do portal dos últimos 5 dias. Um mesmo lançamento, evento ou anúncio já publicado é repetida, mesmo com entrevista, falas novas ou outro ângulo. Só marque false se trouxer fato novo de verdade (desdobramento, decisão, resultado, número novo).
- excecao_nota7: true só para carnaval/escolas de samba e lançamentos de artistas negros (disco, livro, filme, série, espetáculo).
- evento_local_pequeno: true para oficina, palestra, celebração municipal, ação de biblioteca, escola ou prefeitura do interior, fora de capital ou grande cidade, sem personagem conhecido ou fato relevante.
- ministerio: true para ação, anúncio ou decisão do Ministério da Igualdade Racial ou de qualquer ministério do governo federal que atinja a população negra.
- motivo: frase curta explicando a nota com base na régua.
Release de órgão público (prefeitura, governo estadual, secretaria, assembleia) só merece nota 8 ou mais se trouxer fato relevante de verdade para a população negra.
Notícia sobre o próprio veículo de imprensa (parceria comercial ou de conteúdo entre veículos, prêmio do veículo, aniversário, nova edição, nova equipe, evento ou campanha do veículo, como "RAÇA Brasil e UOL anunciam parceria") não interessa ao público do Áfricas: nota 0.
Notícias marcadas com [FONTE ÁFRICA] vêm de veículos africanos ou de buscas sobre o continente: avalie pela seção "Notícias da África e do mundo" da linha editorial, e não pela pergunta sobre a questão racial.
Registre a avaliação de todas as notícias usando a ferramenta avaliar_noticias.
"""


INSTRUCAO_REDATOR = """

## Sua função agora: REDATOR (escreve)
Você recebe uma notícia original já aprovada pelo editor-chefe. Reescreva seguindo a linha editorial acima à risca.
A decisão sobre relevância, nota e categoria já foi tomada pelo editor-chefe: não julgue de novo se o assunto interessa ou tem recorte racial suficiente.
Recuse somente nestes casos: (1) o texto original não traz informação suficiente para uma matéria honesta (o quê, quem, onde, quando); (2) é conteúdo exclusivo de outro veículo; (3) é publicidade ou conteúdo patrocinado; (4) é artigo de opinião.
Recuse também se o texto original for conteúdo exclusivo do veículo de origem (entrevista exclusiva concedida ao veículo, reportagem investigativa ou levantamento próprio, furo) ou artigo de opinião: o Áfricas não se apropria do trabalho de outros veículos. Não cite o veículo de origem no texto.
Atenção: citar outro veículo como fonte de uma informação (por exemplo, "segundo o The New York Times",
"de acordo com a Folha") NÃO torna o conteúdo exclusivo e NÃO é motivo de recusa: é apuração comum da imprensa.
Fato noticiado por vários veículos, com reações públicas de pessoas conhecidas, também não é exclusivo.
Só recuse por exclusividade quando o próprio veículo de origem fez a entrevista, a investigação, o levantamento ou deu o furo.
Antes de entregar, confira os limites: título até 60 caracteres, linha fina até 350 e corpo até 3.500 caracteres. Se passar, encurte.
Formato de jornal: pirâmide invertida, sem bloco de perguntas e respostas e sem intertítulo em forma de pergunta; intertítulos curtos e afirmativos só em matérias longas.
Se o pedido vier marcado com [FONTE ÁFRICA], siga a seção "Notícias da África e do mundo" da linha editorial: não recuse por falta de recorte racial.
As palavras-chave precisam estar escritas no corpo exatamente como na lista.
Entregue o resultado usando a ferramenta entregar_materia. O corpo_html não leva parágrafo de crédito ao site de origem.
Se "aprovada" for false, os demais campos podem ficar vazios.
"""


def editor_chefe(linha_editorial, noticias, recentes):
    """Avalia vários títulos numa única consulta. Devolve {id: avaliação}."""
    lista = "\n".join(
        f"{n['id']}. {'[FONTE ÁFRICA] ' if n.get('fonte_africa') else ''}{n['titulo']} | {n.get('descricao', '')[:300]}" for n in noticias
    )
    portal = "\n".join(f"- {r.get('titulo_original') or r.get('titulo')}" for r in recentes[-150:]) or "nenhuma"
    hoje = datetime.now(FUSO_SP).strftime("%d/%m/%Y")
    pedido = (f"DATA DE HOJE: {hoje}\n\nNOTÍCIAS NOVAS:\n{lista}\n\n"
              f"MATÉRIAS DO PORTAL NOS ÚLTIMOS {DIAS_REPETIDAS} DIAS (para achar repetidas):\n{portal}")
    resultado = enviar_claude(INSTRUCAO_EDITOR, pedido, FERRAMENTA_EDITOR, fixo=linha_editorial)
    return {a.get("id"): a for a in resultado.get("avaliacoes", []) if isinstance(a, dict)}


def redator(linha_editorial, noticia):
    pedido = (
        f"{'[FONTE ÁFRICA] ' if noticia.get('fonte_africa') else ''}"
        f"Veículo de origem: {noticia['veiculo']}\n"
        f"Link: {noticia['link']}\n"
        f"Data: {noticia['data_texto']}\n"
        f"Título original: {noticia['titulo']}\n"
        f"Links úteis do original (ingressos, inscrições, informações): "
        f"{json.dumps(noticia.get('links_uteis', []), ensure_ascii=False)}\n\n"
        f"Texto original:\n{noticia['texto'][:12000]}"
    )
    return enviar_claude(INSTRUCAO_REDATOR, pedido, FERRAMENTA_REDATOR, fixo=linha_editorial)


FERRAMENTA_REVISOR = {
    "name": "entregar_revisao",
    "description": "Entrega a matéria revisada.",
    "input_schema": {
        "type": "object",
        "properties": {
            "titulo": {"type": "string"},
            "linha_fina": {"type": "string"},
            "corpo_html": {"type": "string"},
        },
        "required": ["titulo", "linha_fina", "corpo_html"],
    },
}

INSTRUCAO_REVISOR = """Você é o revisor do portal Áfricas. Revise a matéria recebida:
- corrija erros de digitação, ortografia, concordância e acentuação;
- título com no máximo 60 caracteres contando espaços (encurte sem perder a informação principal);
- linha fina com no máximo 350 caracteres;
- texto com no máximo 3.500 caracteres: se passar, encurte tirando repetições e detalhes menos importantes;
- formato de jornal: se houver bloco de perguntas e respostas, transforme as informações em texto corrido ou retire o que já foi dito; se houver intertítulo em forma de pergunta, troque por intertítulo curto (2 a 4 palavras), afirmativo e concreto; matéria curta fica sem intertítulo;
- não acrescente fatos, nomes, números ou aspas; não mude o sentido; mantenha o HTML (h2, p, strong, a) e os links;
- mantenha escritas exatamente iguais estas palavras-chave, que viram links: {palavras}.
Se nada precisar mudar, devolva o texto igual. Entregue usando a ferramenta entregar_revisao."""


def texto_principal(corpo):
    return re.sub(r"<[^>]+>", "", corpo or "")


def revisor(resultado):
    """Revisão final: ortografia e limites de tamanho. Se der problema, fica a versão do redator."""
    palavras = ", ".join(resultado.get("palavras_chave") or []) or "nenhuma"
    pedido = (f"TÍTULO: {resultado.get('titulo', '')}\n\nLINHA FINA: {resultado.get('linha_fina', '')}\n\n"
              f"CORPO:\n{resultado.get('corpo_html', '')}")
    try:
        revisado = enviar_claude(INSTRUCAO_REVISOR.replace("{palavras}", palavras), pedido, FERRAMENTA_REVISOR)
    except ErroAPI:
        raise
    except Exception as e:
        log(f"  Revisor não respondeu direito ({e}); fica a versão do redator.")
        return resultado
    novo = dict(resultado)
    for campo in ("titulo", "linha_fina", "corpo_html"):
        valor = (revisado.get(campo) or "").strip()
        if valor and (campo != "corpo_html" or len(valor) > len(resultado.get("corpo_html", "")) * 0.4):
            novo[campo] = valor
    mudou = [c for c in ("titulo", "linha_fina", "corpo_html") if novo[c] != resultado.get(c)]
    if mudou:
        log(f"  Revisor ajustou: {', '.join(mudou)}.")
    return novo


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
    # segurança: tira bloco de perguntas e respostas, se ainda vier
    corpo = re.split(r"<h[23]>\s*(?:Perguntas(?: e respostas| frequentes)?|FAQ)\b", corpo, maxsplit=1, flags=re.I)[0]
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


def inserir_fotos(corpo, fotos):
    """Coloca as fotos do corpo entre os parágrafos (depois do 2º, do 4º e do 6º), com legenda e crédito."""
    fins = [m.end() for m in re.finditer(r"</p>", corpo)]
    posicoes = [fins[i] for i in (1, 3, 5) if i < len(fins) - 1][:len(fotos)]
    for pos, f in sorted(zip(posicoes, fotos), key=lambda x: -x[0]):
        texto = (f["legenda"] + ". " if f["legenda"] else "") + "Foto: " + f["credito"]
        bloco = (f'<figure><img src="{html.escape(f["url"], quote=True)}" alt="{html.escape(f["legenda"] or "Foto da matéria", quote=True)}" '
                 f'style="max-width:100%;height:auto;" /><figcaption>{html.escape(texto, quote=False)}</figcaption></figure>')
        corpo = corpo[:pos] + bloco + corpo[pos:]
    return corpo


URL_BUSCA = "https://www.africas.com.br/noticias/buscar/"
COR_LINK = "#FF0000"
MAX_LINKS = 5


def slug(texto):
    t = unicodedata.normalize("NFD", texto or "")
    t = "".join(c for c in t if unicodedata.category(c) != "Mn").lower()
    t = re.sub(r"[^a-z0-9\s-]", "", t).strip()
    return re.sub(r"-+", "-", re.sub(r"\s+", "-", t))


def sem_acento(texto):
    """Mesmo tamanho do texto original, só que sem acentos e em minúsculas (para comparar)."""
    return "".join(unicodedata.normalize("NFD", c)[0].lower() if c else c for c in texto)


def links_internos(corpo, palavras):
    """Liga de 3 a 5 assuntos à busca do site: cada assunto uma vez e no máximo um link por parágrafo.
    Acha a palavra no texto mesmo com diferença de acento ou de maiúscula."""
    palavras = [decodificar(p) for p in palavras if p and p.strip() and len(p.split()) <= 4]
    palavras = sorted(dict.fromkeys(palavras), key=len, reverse=True)
    paragrafos = re.findall(r"<p>.*?</p>", corpo, flags=re.S)
    usados = set()
    total = 0
    for palavra in palavras:
        if total >= MAX_LINKS:
            break
        padrao = re.compile(r"(?<![\w])" + re.escape(sem_acento(palavra)) + r"(?![\w])")
        for i, par in enumerate(paragrafos):
            if i in usados or "<a " in par:
                continue
            partes = re.split(r"(<[^>]+>)", par)
            feito = False
            for k, parte in enumerate(partes):
                if parte.startswith("<"):
                    continue
                m = padrao.search(sem_acento(parte))
                if m:
                    achado = parte[m.start():m.end()]
                    partes[k] = (parte[:m.start()]
                                 + f'<a href="{URL_BUSCA}{slug(palavra)}/p/1" style="color:{COR_LINK};text-decoration:none;">{achado}</a>'
                                 + parte[m.end():])
                    feito = True
                    break
            if feito:
                novo = "".join(partes)
                corpo = corpo.replace(par, novo, 1)
                paragrafos[i] = novo
                usados.add(i)
                total += 1
                break
    return corpo


# ---------------- Foto substituta (quando a foto original não pode ser usada: foto livre da pessoa ou foto do Unsplash) ----------------
def baixar_json(url, cabecalho):
    req = urllib.request.Request(url, headers=cabecalho)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def foto_da_pessoa(nome):
    """Foto livre da própria pessoa: a foto principal dela na Wikipédia, se a licença for livre."""
    try:
        q = urllib.parse.urlencode({"action": "query", "titles": nome, "prop": "pageimages",
                                    "piprop": "name", "redirects": 1, "format": "json"})
        dados = baixar_json("https://pt.wikipedia.org/w/api.php?" + q, {"User-Agent": ROBO_WIKI})
        arquivo = ""
        for pagina in dados.get("query", {}).get("pages", {}).values():
            arquivo = pagina.get("pageimage", "")
        if not arquivo:
            return None
        q = urllib.parse.urlencode({"action": "query", "titles": "File:" + arquivo, "prop": "imageinfo",
                                    "iiprop": "url|extmetadata", "iiurlwidth": 1200, "format": "json"})
        dados = baixar_json("https://commons.wikimedia.org/w/api.php?" + q, {"User-Agent": ROBO_WIKI})
        for pagina in dados.get("query", {}).get("pages", {}).values():
            info = (pagina.get("imageinfo") or [{}])[0]
            meta = info.get("extmetadata", {})
            licenca = (meta.get("LicenseShortName", {}).get("value") or "")
            if not re.search(r"CC|domínio público|public domain|PD", licenca, re.I):
                return None
            autor = decodificar(re.sub(r"<[^>]+>", "", meta.get("Artist", {}).get("value") or "")) or "Autor desconhecido"
            url = info.get("thumburl") or info.get("url")
            if url:
                return url, limpar_credito(f"{autor}/Wikimedia Commons ({licenca})")
    except Exception as e:
        log(f"  Wikimedia sem foto: {e}")
    return None


def foto_banco(busca, usadas):
    """Foto ilustrativa gratuita do Unsplash, evitando repetir foto já usada."""
    chave = (os.environ.get("UNSPLASH_ACCESS_KEY") or "").strip()
    if not chave or not busca:
        return None
    cabecalho = {"Authorization": f"Client-ID {chave}", "Accept-Version": "v1", "User-Agent": ROBO_WIKI}
    try:
        q = urllib.parse.urlencode({"query": busca, "per_page": 15, "orientation": "landscape"})
        dados = baixar_json("https://api.unsplash.com/search/photos?" + q, cabecalho)
        for foto in dados.get("results", []):
            url = foto.get("urls", {}).get("regular")
            if url and url not in usadas:
                # regra do Unsplash: avisar quando uma foto é usada
                aviso = foto.get("links", {}).get("download_location")
                if aviso:
                    try:
                        baixar_json(aviso, cabecalho)
                    except Exception:
                        pass
                nome = foto.get("user", {}).get("name") or "Unsplash"
                return url, f"Foto ilustrativa: {nome}/Unsplash"
    except Exception as e:
        log(f"  Unsplash sem foto: {e}")
    return None


COMUNS_DOMINIO = {"www", "com", "br", "org", "net", "gov", "ao", "inf", "pt", "fr", "uol", "abril", "blog", "news", "noticias"}
PALAVRAS_IA = re.compile(r"gerad[ao] (?:por|com) (?:ia|intelig[eê]ncia artificial)|intelig[eê]ncia artificial|\bia\b|midjourney|dall-?e|ai generated|\bai\b", re.I)


# Grandes veículos: foto com direito autoral. Citar a fonte não autoriza o uso.
# Regra (23/11/2026): procurar foto livre parecida; se não achar, foto genérica de tema.
# Foto com crédito "Divulgação" ou "Reprodução" pode ser usada, venha de onde vier.
GRANDES_VEICULOS = ("globo.com", "estadao.com.br", "folha.uol.com.br", "uol.com.br", "cnnbrasil.com.br",
                    "r7.com", "terra.com.br", "metropoles.com", "bbc.com", "abril.com.br", "exame.com",
                    "correiobraziliense.com.br", "band.uol.com.br", "sbt.com.br", "cartacapital.com.br",
                    "istoe.com.br", "poder360.com.br", "gazetadopovo.com.br", "jovempan.com.br",
                    "em.com.br", "otempo.com.br", "opovo.com.br", "jc.com.br", "zh.clicrbs.com.br")
CREDITO_LIVRE = re.compile(r"divulga|reprodu", re.I)
# Agências pagas: foto só com licença (regra de 24/11/2026)
AGENCIAS_PAGAS = re.compile(r"reuters|\bap\b|associated press|\bafp\b|getty|folhapress|estad[aã]o conte[uú]do|"
                            r"ag[eê]ncia o globo|shutterstock|istock|alamy|\bepa\b|efe\b|bloomberg|sipa|abaca|"
                            r"agif|futura press|photopress|brazil photo press|ag[eê]ncia estado", re.I)


def foto_nao_pode(credito, veiculo, link, exigir_credito, imagem):
    """Diz se a foto original não pode ser usada (e por quê). Vazio = pode usar."""
    if not imagem:
        return "a matéria original não tem foto"
    dominio = urlparse(link).netloc.lower()
    if dominio.endswith("gov.br") or dominio.endswith("ebc.com.br"):
        return ""  # fotos de governo e da Agência Brasil são de uso livre com crédito
    c = credito or ""
    if any(dominio == g or dominio.endswith("." + g) for g in GRANDES_VEICULOS) and not CREDITO_LIVRE.search(c):
        return "foto de grande veículo (direito autoral)"
    if not c.strip():
        return "foto sem crédito"  # regra de 24/11: sem crédito não usa, em qualquer fonte
    if AGENCIAS_PAGAS.search(c):
        return f"agência paga ({credito})"
    if PALAVRAS_IA.search(c):
        return "imagem gerada por IA"
    c_norm = normalizar(sem_acento(c))
    c_junto = c_norm.replace(" ", "")
    nomes = [normalizar(sem_acento(veiculo or ""))]
    nomes += [p for p in dominio.split(".") if p not in COMUNS_DOMINIO]
    for nome in nomes:
        junto = nome.replace(" ", "")
        if not junto:
            continue
        if len(junto) >= 5 and junto in c_junto:
            return f"crédito do próprio site ({credito})"
        if len(junto) < 5 and re.search(r"(?<!\w)" + re.escape(nome) + r"(?!\w)", c_norm):
            return f"crédito do próprio site ({credito})"
    return ""


FOTOS_USADAS = set()


def foto_substituta(resultado, generica=True):
    """Pessoa específica: foto livre dela; senão, foto do tema sem rosto. Tema geral: foto ilustrativa.
    Com generica=False, não usa a foto genérica de reserva: devolve None se não achar nada parecido."""
    pessoa = (resultado.get("pessoa_principal") or "").strip()
    achou = None
    if pessoa:
        achou = foto_da_pessoa(pessoa) or foto_banco(resultado.get("busca_foto_sem_rosto"), FOTOS_USADAS)
    else:
        achou = foto_banco(resultado.get("busca_foto"), FOTOS_USADAS) or \
            foto_banco(resultado.get("busca_foto_sem_rosto"), FOTOS_USADAS)
    if not achou and not generica:
        return None
    achou = achou or foto_banco("african art pattern", FOTOS_USADAS)
    if not achou:
        log("  Aviso: não achou foto substituta; a matéria sai sem imagem.")
        return "", "Divulgação"
    FOTOS_USADAS.add(achou[0])
    return achou


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
    corpo += f'<p><strong>Siga o Áfricas no Instagram: <a href="{INSTAGRAM}" target="_blank" rel="noopener">@africasplay</a></strong></p>'
    return corpo


# ---------------- Rodada principal ----------------
def mesmo_fato(titulo, lista, limite):
    x = normalizar(titulo)
    if not x:
        return False
    for r in lista:
        for y in (normalizar(r.get("titulo_original")), normalizar(r.get("titulo"))):
            if y and difflib.SequenceMatcher(None, x, y).ratio() >= limite:
                return True
    return False


def cortar_linha_fina(texto, limite=350):
    """Se a linha fina passar de 350 caracteres, corta na última frase completa."""
    if len(texto) <= limite:
        return texto
    corte = texto[:limite]
    fim = max(corte.rfind(". "), corte.rfind("! "), corte.rfind("? "))
    if fim > 100:
        return corte[:fim + 1]
    return corte[:corte.rfind(" ")].rstrip(",;:") + "."


def publicar(materia_fila, linha_editorial, agora):
    """Extrai o texto original, manda o redator escrever e devolve a matéria pronta (ou None)."""
    if "news.google.com" in materia_fila["link"]:
        real = link_real_google(materia_fila["link"])
        if not real:
            registrar(materia_fila, "não abriu o texto", "link do Google Notícias não desembrulhou")
            return None
        materia_fila["link"] = real
    original = extrair_materia(materia_fila["link"], materia_fila["titulo_original"], materia_fila.get("descricao", ""))
    if len(original["texto"]) < TEXTO_MINIMO:
        log("  Descartada: não deu para ler o texto completo no site original.")
        registrar(materia_fila, "não abriu o texto", "texto original curto ou bloqueado")
        return None
    data = datetime.fromisoformat(materia_fila["data_original"])
    noticia = {
        "titulo": materia_fila["titulo_original"], "link": materia_fila["link"], "veiculo": original["veiculo"],
        "texto": original["texto"], "links_uteis": original["links_uteis"],
        "fonte_africa": materia_fila.get("fonte_africa", False),
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
        registrar(materia_fila, "recusada pelo redator", resultado.get("motivo", ""))
        return None
    resultado = revisor(resultado)
    corpo = montar_corpo(resultado, original)
    imagem = original["imagem"] or materia_fila.get("imagem_rss", "")
    credito = original["credito_foto"]
    # Regra única de fotos (24/11/2026), para todas as fontes, imprensa negra incluída:
    # crédito do próprio veículo, agência paga ou sem crédito = não usa; qualquer outro crédito = usa.
    if True:
        motivo_troca = foto_nao_pode(credito, original["veiculo"], materia_fila["link"],
                                     materia_fila.get("imagem_banco", False), imagem)
        if motivo_troca:
            log(f"  Foto trocada: {motivo_troca}.")
            imagem, credito = foto_substituta(resultado)
    credito = credito or "Divulgação"
    fotos_extras = []
    for f in original.get("fotos_corpo", []):
        motivo = foto_nao_pode(f["credito"], original["veiculo"], materia_fila["link"], True, f["url"])
        if motivo:
            log(f"  Foto do corpo não usada: {motivo}.")
            continue
        fotos_extras.append(f)
        if len(fotos_extras) >= 3:
            break
    if fotos_extras:
        corpo = inserir_fotos(corpo, fotos_extras)
        # crédito geral da matéria com todos os fotógrafos (24/11)
        nomes = [credito] + [f["credito"] for f in fotos_extras]
        unicos = [n for i, n in enumerate(nomes) if n and n.lower() not in [x.lower() for x in nomes[:i]]]
        credito = unicos[0] if len(unicos) == 1 else ", ".join(unicos[:-1]) + " e " + unicos[-1]
        log(f"  {len(fotos_extras)} foto(s) do corpo da matéria original incluída(s).")
    titulo = decodificar(resultado.get("titulo"))
    if not titulo or not corpo:
        log("  Descartada: o redator não devolveu título ou texto.")
        registrar(materia_fila, "recusada pelo redator", "sem título ou texto")
        return None
    if len(titulo) > LIMITE_TITULO:
        log(f"  Aviso: título com {len(titulo)} caracteres (limite {LIMITE_TITULO}).")
    if len(texto_principal(resultado.get("corpo_html"))) > LIMITE_CORPO + 300:
        log("  Aviso: texto principal acima do limite mesmo depois da revisão.")
    return dict(materia_fila, **{
        "titulo": titulo,
        "linha_fina": cortar_linha_fina(decodificar(resultado.get("linha_fina"))),
        "corpo_html": corpo,
        "imagem": imagem,
        "credito_imagem": credito,
        "fotos_extras": fotos_extras,
        "veiculo": original["veiculo"],
        "autor": original["autor"],
        "palavras_chave": resultado.get("palavras_chave") or [],
        "hashtags": [h if h.startswith("#") else "#" + h for h in (resultado.get("hashtags") or [])],
        "publicado_em": agora.isoformat(),
    })


def main():
    agora = datetime.now(timezone.utc)
    agora_sp = agora.astimezone(FUSO_SP)
    fontes = ler_json(ARQ_FONTES, [])
    primeira_vez = ler_json(ARQ_PRIMEIRA_VEZ, {"fontes_iniciadas": [], "links": {}})
    rodada = int(agora.timestamp() // 900)  # número da rodada de 15 minutos (define o grupo de buscas)
    with open(ARQ_LINHA, encoding="utf-8") as f:
        linha_editorial = f.read()
    fila = ler_json(ARQ_FILA, [])
    vistos = ler_json(ARQ_VISTOS, [])
    publicadas = ler_json(ARQ_PUBLICADAS, [])
    FOTOS_USADAS.update(m.get("imagem", "") for m in publicadas[-200:])
    vistos_set = set(vistos)

    def marcar_visto(link):
        if link not in vistos_set:
            vistos_set.add(link)
            vistos.append(link)

    # Limpa da fila o que passou da validade de 4 horas
    antes = len(fila)
    limite_validade = (agora - timedelta(hours=VALIDADE_HORAS)).isoformat()
    def vencida(m):
        if m.get("valido_ate") and m["valido_ate"] >= agora.isoformat():
            return False  # notícia da África encontrada de madrugada: vale até as 12h
        return m.get("data_original", "") < limite_validade
    for m in fila:
        if vencida(m):
            registrar(m, "venceu na fila", f"passou de {VALIDADE_HORAS} horas sem ser publicada")
    fila = [m for m in fila if not vencida(m)]
    if antes != len(fila):
        log(f"Saíram da fila por passar de {VALIDADE_HORAS} horas: {antes - len(fila)}")

    recentes = [m for m in fila + publicadas
                if m.get("data_original", m.get("criado_em", "")) >= (agora - timedelta(days=DIAS_REPETIDAS)).isoformat()]

    # Etapa A: buscar notícias novas (janela de 2 horas)
    candidatas = []
    bing = {"buscas": 0, "recebidas": 0, "na_janela": 0}
    for fonte in fontes:
        itens = ler_fonte(fonte, rodada)
        if fonte.get("tipo") == "busca" and itens:
            bing["buscas"] += 1
            bing["recebidas"] += len(itens)
            bing["na_janela"] += sum(1 for i in itens if i["data"] and agora - i["data"] <= timedelta(hours=JANELA_HORAS_BUSCA))
        nome = fonte.get("nome", "")
        sem_data = [i for i in itens if not i["data"]]
        if sem_data and nome not in primeira_vez["fontes_iniciadas"]:
            # primeira vez que o robô lê esta fonte sem data: só anota o que já existe, não publica
            for i in sem_data:
                marcar_visto(i["link"])
            primeira_vez["fontes_iniciadas"].append(nome)
            log(f"Fonte nova sem data ({nome}): {len(sem_data)} matérias antigas anotadas, nada publicado.")
            itens = [i for i in itens if i["data"]]
        for item in itens:
            if item["link"] in vistos_set or item["link"] in [c["link"] for c in candidatas]:
                continue
            if not item["data"]:
                # sem data: vale o momento em que o robô viu a matéria pela primeira vez
                visto_em = primeira_vez["links"].setdefault(item["link"], agora.isoformat())
                item["data"] = datetime.fromisoformat(visto_em)
            janela = JANELA_HORAS_BUSCA if fonte.get("tipo") == "busca" else JANELA_HORAS
            if agora - item["data"] > timedelta(hours=janela):
                marcar_visto(item["link"])
                continue
            if mesmo_fato(item["titulo"], recentes, SEMELHANCA_JA_PUBLICADA) or \
                    mesmo_fato(item["titulo"], candidatas, SEMELHANCA_MESMO_FATO):
                log(f"Repetida (mesmo fato): {item['titulo'][:80]}")
                registrar(dict(item, fonte_nome=nome), "repetida", "título quase igual a outra notícia")
                marcar_visto(item["link"])
                continue
            item["categoria_fonte"] = fonte.get("categoria", "")
            item["imagem_banco"] = fonte.get("imagem") in ("exigir_credito", "substituir_sempre")
            item["imagem_trocar"] = fonte.get("imagem") == "substituir_sempre"
            item["fonte_africa"] = bool(fonte.get("africa"))
            item["fonte_nome"] = nome
            candidatas.append(dict(item, titulo_original=item["titulo"]))
    candidatas.sort(key=lambda i: i["data"] or agora)
    candidatas = candidatas[:MAX_TRIAGEM_POR_RODADA]
    log(f"Google Notícias nesta rodada: {bing['buscas']} buscas com resultado, {bing['recebidas']} notícias recebidas, "
        f"{bing['na_janela']} das últimas {JANELA_HORAS_BUSCA} horas")
    log(f"Notícias novas para avaliar: {len(candidatas)}")

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
                    registrar(dict(c, nota=nota, categoria=a.get("categoria", "")), "repetida", a.get("motivo", ""))
                    continue
                ministerio = bool(a.get("ministerio"))
                minima = NOTA_EXCECAO if a.get("excecao_nota7") else NOTA_MINIMA
                if a.get("evento_local_pequeno") and not ministerio:
                    log(f"Evento local pequeno, fora: {c['titulo'][:70]}")
                    registrar(dict(c, nota=nota, categoria=a.get("categoria", "")), "nota baixa", "evento local pequeno: " + a.get("motivo", ""))
                    continue
                if nota < minima and not ministerio:
                    log(f"Nota {nota}, fora: {c['titulo'][:70]} ({a.get('motivo', '')})")
                    registrar(dict(c, nota=nota, categoria=a.get("categoria", "")), "nota baixa", a.get("motivo", ""))
                    continue
                assunto = em_alta(c["titulo"] + " " + c.get("descricao", ""))
                if assunto and nota < 10:
                    nota += 1
                    log(f"Em alta no Google ({assunto}): nota sobe para {nota} — {c['titulo'][:60]}")
                categoria = a.get("categoria") if a.get("categoria") in CATEGORIAS else c["categoria_fonte"]
                if categoria not in CATEGORIAS:
                    continue
                prioridade = a.get("prioridade") if a.get("prioridade") in PRIORIDADES else "media"
                fila.append({
                    "link": c["link"], "titulo_original": c["titulo"], "descricao": c.get("descricao", ""),
                    "imagem_rss": c.get("imagem", ""), "imagem_banco": c.get("imagem_banco", False),
                    "imagem_trocar": c.get("imagem_trocar", False),
                    "fonte_nome": c.get("fonte_nome", ""), "fonte_africa": c.get("fonte_africa", False),
                    "categoria": categoria, "prioridade": prioridade,
                    "nota": nota, "motivo_nota": a.get("motivo", ""), "ministerio": ministerio, "excecao_nota7": bool(a.get("excecao_nota7")),
                    "data_original": (c["data"] or agora).astimezone(timezone.utc).isoformat(),
                    "criado_em": agora.isoformat(),
                    "valido_ate": (agora_sp.replace(hour=12, minute=0, second=0, microsecond=0).astimezone(timezone.utc).isoformat()
                                   if c.get("fonte_africa") and agora_sp.hour < HORA_INICIO else ""),
                })
                log(f"Nota {nota}, na fila: [{categoria} / {prioridade}] {c['titulo'][:70]}")
                registrar(fila[-1], "na fila", a.get("motivo", ""))

    # Etapa C: publicar (uma por categoria por rodada)
    hoje = agora_sp.date().isoformat()
    def conta_no_teto(m):
        return m.get("prioridade") != "breaking" and not m.get("ministerio")
    do_dia = [m for m in publicadas
              if datetime.fromisoformat(m["publicado_em"]).astimezone(FUSO_SP).date().isoformat() == hoje]
    publicadas_hoje = sum(1 for m in do_dia if conta_no_teto(m))
    por_editoria = Counter(m.get("categoria") for m in do_dia if conta_no_teto(m))
    ultima_hora = sum(1 for m in do_dia if conta_no_teto(m)
                      and agora - datetime.fromisoformat(m["publicado_em"]) < timedelta(hours=1))
    africa_hoje = [m for m in publicadas
                   if m.get("fonte_africa") and m.get("prioridade") != "breaking"
                   and datetime.fromisoformat(m["publicado_em"]).astimezone(FUSO_SP).date().isoformat() == hoje]
    ultima_africa = max((datetime.fromisoformat(m["publicado_em"]) for m in africa_hoje), default=None)
    horario_normal = agora_sp.hour >= HORA_INICIO
    minuto_no_ciclo = (agora_sp.minute - MINUTO_PARTIDA) % 15
    pode_publicar = minuto_no_ciclo <= MINUTOS_PARA_PUBLICAR
    log(f"Publicadas hoje no teto: {publicadas_hoje} de {TETO_DIA} | na última hora: {ultima_hora} | "
        f"{'horário normal' if horario_normal else 'madrugada: só breaking'}")
    if not pode_publicar:
        log("Fora da janela de publicação (o site poderia não ver a matéria): publica na próxima rodada.")

    def ordem(m):
        # fontes África: dentro da mesma prioridade, a de nota mais alta sai primeiro
        # com teto diário, dentro da mesma prioridade sai primeiro a de nota mais alta
        return (PRIORIDADES.index(m["prioridade"]), -(m.get("nota") or 0), m["data_original"])

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
        if parar or not pode_publicar:
            break
        for materia_fila in da_categoria[:3]:  # tenta até 3 da mesma categoria se alguma for recusada
            e_breaking = materia_fila["prioridade"] == "breaking"
            if not e_breaking and not horario_normal:
                break  # madrugada: só breaking
            if (materia_fila.get("nota") or 0) < NOTA_MINIMA and not (
                    e_breaking or materia_fila.get("ministerio") or materia_fila.get("excecao_nota7")):
                fila.remove(materia_fila)  # entrou na fila pela regra antiga (nota 7)
                registrar(materia_fila, "nota baixa", "nota 7 deixou de entrar (regra de 23/11)")
                continue
            fora_do_teto = e_breaking or materia_fila.get("ministerio")
            if not fora_do_teto:
                if publicadas_hoje >= TETO_DIA:
                    break  # teto diário atingido
                if ultima_hora >= teto_por_hora(agora.astimezone(FUSO_SP).hour):
                    break  # espera a próxima hora para espalhar ao longo do dia
                if por_editoria[materia_fila["categoria"]] >= TETO_EDITORIA.get(materia_fila["categoria"], 3):
                    break  # teto da editoria atingido hoje
            if materia_fila.get("fonte_africa") and not e_breaking:
                if len(africa_hoje) >= LIMITE_AFRICA_DIA:
                    continue  # limite diário de matérias da África atingido
                if ultima_africa and agora - ultima_africa < timedelta(hours=INTERVALO_AFRICA_HORAS):
                    continue  # espera o intervalo entre matérias da África
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
                    registrar(materia_fila, "recusada pelo redator", "duas respostas inválidas seguidas")
                    fila.remove(materia_fila)
                continue
            fila.remove(materia_fila)
            if not pronta:
                continue
            with open(os.path.join(PASTA_FEEDS, f"{pronta['categoria']}.xml"), "w", encoding="utf-8") as f:
                f.write(montar_rss(pronta, pronta["categoria"]))
            publicadas.append(pronta)
            if pronta.get("fonte_africa") and not e_breaking:
                africa_hoje.append(pronta)
                ultima_africa = agora
            registrar(pronta, "publicada", pronta["titulo"], foto=pronta["credito_imagem"])
            if not (e_breaking or pronta.get("ministerio")):
                publicadas_hoje += 1
                ultima_hora += 1
                por_editoria[pronta["categoria"]] += 1
            log(f"  RSS {pronta['categoria']} atualizado: {pronta['titulo']}")
            break  # uma por categoria por rodada

    salvar_json(ARQ_FILA, fila)
    salvar_json(ARQ_VISTOS, vistos[-5000:])
    salvar_json(ARQ_PUBLICADAS, publicadas[-500:])
    limite_links = (agora - timedelta(days=3)).isoformat()
    primeira_vez["links"] = {l: d for l, d in primeira_vez["links"].items() if d >= limite_links}
    salvar_json(ARQ_PRIMEIRA_VEZ, primeira_vez)
    try:
        salvar_relatorio(agora)
    except Exception as e:
        log(f"Não conseguiu salvar o relatório do dia: {e}")
    log(f"Fim. Na fila de espera: {len(fila)} | Publicadas hoje: {publicadas_hoje}")
    if any(USO.values()):
        log(f"Uso do Claude nesta rodada: {USO['input_tokens']} tokens novos, "
            f"{USO['cache_read_input_tokens']} lidos do cache, {USO['cache_creation_input_tokens']} guardados no cache, "
            f"{USO['output_tokens']} escritos.")


if __name__ == "__main__":
    main()
