# Testador de fontes do robô Áfricas - versão 2
# Para cada fonte, confere se o RSS funciona e se dá para ler o texto completo de uma matéria.
# Buscas: testa o Google Notícias (com uma segunda forma de atravessar o desvio) e o Bing Notícias.
# Sites sem RSS: procura o RSS e, se não achar, lê a página de notícias e pega os links das matérias.

import base64
import html
import json
import re
import time
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

NAVEGADORES = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
]
FUSO_SP = timezone(timedelta(hours=-3))
AGORA = datetime.now(timezone.utc)


def baixar(url, tempo=25, dados=None, extra=None):
    erro = None
    for nav in NAVEGADORES:
        cab = {
            "User-Agent": nav,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.5",
        }
        if extra:
            cab.update(extra)
        req = urllib.request.Request(url, data=dados, headers=cab)
        try:
            with urllib.request.urlopen(req, timeout=tempo) as r:
                return r.read().decode("utf-8", errors="replace"), r.geturl()
        except urllib.error.HTTPError as e:
            erro = e
            if e.code not in (403, 406):
                raise
        time.sleep(1)
    raise erro


def ler_rss(texto):
    raiz = ET.fromstring(texto.encode("utf-8"))
    itens = []
    for item in raiz.iter("item"):
        titulo = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        data = None
        try:
            data = parsedate_to_datetime(item.findtext("pubDate") or "")
        except Exception:
            pass
        if titulo and link:
            itens.append({"titulo": html.unescape(titulo), "link": link, "data": data})
    if not itens:
        ns = "{http://www.w3.org/2005/Atom}"
        for e in raiz.iter(ns + "entry"):
            titulo = (e.findtext(ns + "title") or "").strip()
            l = e.find(ns + "link")
            link = l.get("href") if l is not None else ""
            if titulo and link:
                itens.append({"titulo": html.unescape(titulo), "link": link, "data": None})
    return itens


def achar_rss_do_site(url):
    candidatos = []
    pagina, final = "", url
    try:
        pagina, final = baixar(url)
        for tag in re.findall(r"<link[^>]+>", pagina, flags=re.I):
            if re.search(r"application/(rss|atom)\+xml", tag, re.I):
                m = re.search(r'href=["\']([^"\']+)["\']', tag)
                if m:
                    candidatos.append(urljoin(final, html.unescape(m.group(1))))
    except Exception:
        pass
    base = url if url.endswith("/") else url + "/"
    dominio = "{0.scheme}://{0.netloc}/".format(urlparse(url))
    candidatos += [base + "feed/", base + "rss", base + "RSS", dominio + "feed/", dominio + "rss.xml", dominio + "feed.xml"]
    vistos = []
    for c in candidatos:
        if c in vistos or "comments" in c:
            continue
        vistos.append(c)
        try:
            texto, _ = baixar(c)
            itens = ler_rss(texto)
            if itens:
                return c, itens, pagina
        except Exception:
            continue
    return None, [], pagina


def links_da_pagina(url, pagina):
    """Sem RSS: pega da página de notícias os links que parecem matérias do mesmo site."""
    if not pagina:
        try:
            pagina, _ = baixar(url)
        except Exception:
            return []
    dom = urlparse(url).netloc
    itens, vistos = [], set()
    for href, texto in re.findall(r'<a[^>]+href=["\']([^"\'#]+)["\'][^>]*>(.*?)</a>', pagina, flags=re.S | re.I):
        link = urljoin(url, html.unescape(href))
        p = urlparse(link)
        titulo = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", texto))).strip()
        if p.netloc != dom or link in vistos or len(titulo) < 35:
            continue
        caminho = p.path.strip("/")
        if caminho.count("/") < 2 and not re.search(r"\d{4}", caminho):
            continue
        vistos.add(link)
        itens.append({"titulo": titulo, "link": link, "data": None})
    return itens[:20]


# ---------- Google Notícias: segunda forma de atravessar o desvio ----------
def decodificar_google(link):
    m = re.search(r"/articles/([^?/]+)", link)
    if not m:
        return None, "link sem código"
    codigo = m.group(1)
    # 1) códigos antigos trazem o endereço escondido no próprio código
    try:
        bruto = base64.urlsafe_b64decode(codigo + "=" * (-len(codigo) % 4))
        achado = re.search(rb"https?://[^\x00-\x20\"<>]+", bruto)
        if achado and b"news.google" not in achado.group(0):
            return achado.group(0).decode("utf-8", errors="ignore"), ""
    except Exception:
        pass
    # 2) códigos novos: pede ao próprio Google a assinatura e depois o endereço
    try:
        pagina, _ = baixar(f"https://news.google.com/articles/{codigo}?hl=pt-BR&gl=BR&ceid=BR:pt-419")
        sg = re.search(r'data-n-a-sg="([^"]+)"', pagina)
        ts = re.search(r'data-n-a-ts="([^"]+)"', pagina)
        if not sg or not ts:
            return None, "Google não entregou a assinatura"
        carga = ["Fbv4je", f'["garturlreq",[["X","X",["X","X"],null,null,1,1,"BR:pt-419",null,1,null,null,null,null,null,0,1],"X","X",1,[1,1,1],1,1,null,0,0,null,0],"{codigo}",{ts.group(1)},"{sg.group(1)}"]']
        dados = ("f.req=" + urllib.parse.quote(json.dumps([[carga]]))).encode()
        resp, _ = baixar("https://news.google.com/_/DotsSplashUi/data/batchexecute", dados=dados,
                         extra={"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"})
        parte = json.loads(resp.split("\n\n")[1])[:-2]
        return json.loads(parte[0][2])[1], ""
    except urllib.error.HTTPError as e:
        return None, f"Google respondeu erro {e.code}"
    except Exception as e:
        return None, f"falhou ({str(e)[:50]})"


# ---------- Bing Notícias ----------
def bing_url(busca):
    return "https://www.bing.com/news/search?" + urllib.parse.urlencode(
        {"q": busca, "format": "rss", "mkt": "pt-BR", "setlang": "pt-BR", "cc": "BR"})


def decodificar_bing(link):
    q = urllib.parse.parse_qs(urlparse(link).query)
    if "url" in q:
        return q["url"][0], ""
    if "bing.com" not in link:
        return link, ""
    return None, "link do Bing sem endereço"


def ler_texto(link):
    try:
        pagina, _ = baixar(link)
    except Exception as e:
        return 0, f"não abriu ({str(e)[:45]})"
    texto = ""
    if trafilatura:
        try:
            texto = trafilatura.extract(pagina, url=link) or ""
        except Exception:
            texto = ""
    if not texto:
        ps = re.findall(r"<p[^>]*>(.*?)</p>", pagina, flags=re.S | re.I)
        texto = "\n".join(re.sub(r"<[^>]+>", "", p) for p in ps if len(p) > 60)
    return len(texto), ""


def resumo_itens(itens):
    recentes = sum(1 for i in itens if i["data"] and AGORA - i["data"] < timedelta(hours=48))
    datas = [i["data"] for i in itens if i["data"]]
    ultima = max(datas).astimezone(FUSO_SP).strftime("%d/%m %H:%M") if datas else "sem data"
    return f"{len(itens)} ({recentes} em 48h)", ultima


def testar_leitura(itens, decodificar):
    """Tenta ler o texto de até 3 matérias; devolve OK se conseguir em pelo menos uma."""
    ultimo = ""
    for item in itens[:3]:
        final, erro = decodificar(item["link"])
        if not final:
            ultimo = erro
            continue
        tamanho, erro = ler_texto(final)
        dom = urlparse(final).netloc.replace("www.", "")
        if tamanho >= 600:
            return True, f"leu {tamanho} caracteres ({dom})"
        ultimo = f"texto curto ou bloqueado ({dom}) {erro}"
        time.sleep(1)
    return False, ultimo


def main():
    fontes = json.load(open("fontes-lista.json", encoding="utf-8"))
    linhas_fontes, linhas_buscas = [], []
    placar = {"fonte_ok": 0, "google_ok": 0, "bing_ok": 0}
    for n, f in enumerate(fontes, start=1):
        print(f"[{n}/{len(fontes)}] {f['nome']}", flush=True)
        if f["tipo"] == "busca":
            res = {}
            for nome, url, dec in [
                ("Google", "https://news.google.com/rss/search?q=" + urllib.parse.quote(f["busca"]) + "&hl=pt-BR&gl=BR&ceid=BR:pt-419", decodificar_google),
                ("Bing", bing_url(f["busca"]), decodificar_bing),
            ]:
                try:
                    texto, _ = baixar(url)
                    itens = ler_rss(texto)
                except Exception as e:
                    res[nome] = ("ERRO", "-", f"não abriu o RSS ({str(e)[:40]})")
                    continue
                if not itens:
                    res[nome] = ("ERRO", "0", "RSS sem notícias")
                    continue
                ok, leitura = testar_leitura(itens, dec)
                qtd, _ = resumo_itens(itens)
                res[nome] = ("OK" if ok else "SEM TEXTO", qtd, leitura)
                if ok:
                    placar["google_ok" if nome == "Google" else "bing_ok"] += 1
                time.sleep(2)
            g, b = res["Google"], res["Bing"]
            linhas_buscas.append(f"| {n} | {f['busca']} | {f['categoria']} | {g[0]} | {g[1]} | {g[2]} | {b[0]} | {b[1]} | {b[2]} |")
            continue

        url_rss, itens, obs, pagina = f.get("url"), [], "", ""
        try:
            if f["tipo"] == "site":
                url_rss, itens, pagina = achar_rss_do_site(f["url"])
                if url_rss:
                    obs = f"RSS: {url_rss}"
                else:
                    itens = links_da_pagina(f["url"], pagina)
                    obs = "sem RSS: lendo a página de notícias" if itens else "sem RSS e sem links de matérias na página"
            else:
                texto, _ = baixar(f["url"])
                itens = ler_rss(texto)
        except Exception as e:
            obs = f"erro ao abrir ({str(e)[:50]})"
        if not itens:
            linhas_fontes.append(f"| {n} | {f['nome']} | {f['categoria']} | ERRO | 0 | - | - | {obs} |")
            continue
        qtd, ultima = resumo_itens(itens)
        ok, leitura = testar_leitura(itens, lambda l: (l, ""))
        if ok:
            placar["fonte_ok"] += 1
        linhas_fontes.append(f"| {n} | {f['nome']} | {f['categoria']} | {'OK' if ok else 'SEM TEXTO'} | {qtd} | {ultima} | {leitura} | {obs} |")
        time.sleep(1)

    total_buscas = len(linhas_buscas)
    relatorio = [
        "# Relatório do teste de fontes (versão 2)",
        "",
        f"Teste feito em {datetime.now(FUSO_SP).strftime('%d/%m/%Y %H:%M')}.",
        "",
        f"Sites: {placar['fonte_ok']} OK de {len(linhas_fontes)}.",
        f"Buscas: Google Notícias {placar['google_ok']} OK e Bing Notícias {placar['bing_ok']} OK, de {total_buscas}.",
        "",
        "## Sites",
        "",
        "| # | Fonte | Categoria | Status | Notícias | Mais recente | Leitura do texto | Observação |",
        "|---|---|---|---|---|---|---|---|",
    ] + linhas_fontes + [
        "",
        "## Buscas: Google Notícias x Bing Notícias",
        "",
        "| # | Busca | Categoria | Google | Notícias | Leitura | Bing | Notícias | Leitura |",
        "|---|---|---|---|---|---|---|---|---|",
    ] + linhas_buscas
    with open("relatorio-fontes.md", "w", encoding="utf-8") as arq:
        arq.write("\n".join(relatorio) + "\n")
    print("\n".join(relatorio))


if __name__ == "__main__":
    main()
