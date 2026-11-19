# Testador de fontes do robô Áfricas
# Abre cada fonte da lista, confere se funciona e se dá para ler o texto completo
# de uma matéria. Escreve o resultado em relatorio-fontes.md.

import html
import json
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlparse

try:
    import trafilatura
except ImportError:
    trafilatura = None
try:
    from googlenewsdecoder import gnewsdecoder
except ImportError:
    gnewsdecoder = None

NAVEGADOR = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
FUSO_SP = timezone(timedelta(hours=-3))


def baixar(url, tempo=25):
    req = urllib.request.Request(url, headers={"User-Agent": NAVEGADOR, "Accept-Language": "pt-BR,pt;q=0.9"})
    with urllib.request.urlopen(req, timeout=tempo) as r:
        return r.read().decode("utf-8", errors="replace"), r.geturl()


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
    # Atom (alguns sites usam esse formato)
    if not itens:
        ns = "{http://www.w3.org/2005/Atom}"
        for e in raiz.iter(ns + "entry"):
            titulo = (e.findtext(ns + "title") or "").strip()
            l = e.find(ns + "link")
            link = l.get("href") if l is not None else ""
            data = None
            try:
                data = datetime.fromisoformat((e.findtext(ns + "updated") or "").replace("Z", "+00:00"))
            except Exception:
                pass
            if titulo and link:
                itens.append({"titulo": html.unescape(titulo), "link": link, "data": data})
    return itens


def achar_rss_do_site(url):
    """Procura o endereço de RSS de um site que não informou."""
    candidatos = []
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
    candidatos += [base + "feed/", base + "rss", base + "RSS", url.rstrip("/") + "/rss.xml"]
    vistos = []
    for c in candidatos:
        if c in vistos or "comments" in c:
            continue
        vistos.append(c)
        try:
            texto, _ = baixar(c)
            itens = ler_rss(texto)
            if itens:
                return c, itens
        except Exception:
            continue
    return None, []


def resolver_link(link):
    """Atravessa o desvio do Google Notícias até o site do jornal."""
    if "news.google.com" not in link:
        return link, ""
    if not gnewsdecoder:
        return None, "decodificador não instalado"
    try:
        r = gnewsdecoder(link, interval=1)
        if r.get("status"):
            return r["decoded_url"], ""
        return None, str(r.get("message", "falhou"))[:80]
    except Exception as e:
        return None, str(e)[:80]


def ler_texto(link):
    try:
        pagina, _ = baixar(link)
    except Exception as e:
        return 0, f"não abriu ({str(e)[:50]})"
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


def main():
    fontes = json.load(open("fontes-lista.json", encoding="utf-8"))
    agora = datetime.now(timezone.utc)
    linhas = []
    resumo = {"ok": 0, "sem_texto": 0, "erro": 0}
    for n, f in enumerate(fontes, start=1):
        print(f"[{n}/{len(fontes)}] {f['nome']}", flush=True)
        url_rss, itens, obs = f["url"], [], ""
        try:
            if f["tipo"] == "site":
                url_rss, itens = achar_rss_do_site(f["url"])
                if not url_rss:
                    obs = "não achou RSS no site"
            else:
                texto, _ = baixar(f["url"])
                itens = ler_rss(texto)
                if not itens:
                    obs = "RSS sem notícias"
        except Exception as e:
            obs = f"erro ao abrir ({str(e)[:60]})"
        if not itens:
            resumo["erro"] += 1
            linhas.append(f"| {n} | {f['nome']} | {f['categoria']} | ERRO | 0 | - | - | {obs} |")
            continue
        recentes = sum(1 for i in itens if i["data"] and agora - i["data"] < timedelta(hours=48))
        datas = [i["data"] for i in itens if i["data"]]
        ultima = max(datas).astimezone(FUSO_SP).strftime("%d/%m %H:%M") if datas else "sem data"
        link_final, erro_link = resolver_link(itens[0]["link"])
        if not link_final:
            leitura = f"não atravessou o Google ({erro_link})"
            resumo["sem_texto"] += 1
            status = "SEM TEXTO"
        else:
            tamanho, erro = ler_texto(link_final)
            dominio = urlparse(link_final).netloc.replace("www.", "")
            if tamanho >= 600:
                leitura = f"leu {tamanho} caracteres ({dominio})"
                resumo["ok"] += 1
                status = "OK"
            else:
                leitura = f"texto curto ou bloqueado ({dominio}) {erro}"
                resumo["sem_texto"] += 1
                status = "SEM TEXTO"
        if f["tipo"] == "site":
            obs = f"RSS encontrado: {url_rss}"
        linhas.append(f"| {n} | {f['nome']} | {f['categoria']} | {status} | {len(itens)} ({recentes} em 48h) | {ultima} | {leitura} | {obs} |")
        time.sleep(1)

    relatorio = [
        "# Relatório do teste de fontes",
        "",
        f"Teste feito em {datetime.now(FUSO_SP).strftime('%d/%m/%Y %H:%M')}.",
        "",
        f"Resultado: {resumo['ok']} OK | {resumo['sem_texto']} sem texto completo | {resumo['erro']} com erro, de {len(fontes)} fontes.",
        "",
        "| # | Fonte | Categoria | Status | Notícias | Mais recente | Leitura do texto | Observação |",
        "|---|---|---|---|---|---|---|---|",
    ] + linhas
    with open("relatorio-fontes.md", "w", encoding="utf-8") as arq:
        arq.write("\n".join(relatorio) + "\n")
    print("\n".join(relatorio))


if __name__ == "__main__":
    main()
