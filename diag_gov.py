# Diagnóstico (26/11/2026): como o gov.br e a Agência Gov mostram as matérias e as fotos do MIR e da Palmares.
import re, urllib.request
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
def get(u):
    try:
        return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30).read().decode("utf-8", "ignore")
    except Exception as e:
        print("ERRO", u, e); return ""
for u in ["https://www.gov.br/igualdaderacial/pt-br/assuntos/noticias",
          "https://agenciagov.ebc.com.br/noticias/igualdade-racial",
          "https://www.gov.br/igualdaderacial/pt-br/assuntos/noticias/seminario-internacional-reune-pesquisadores-antirracistas-na-universidade-de-brasilia",
          "https://www.gov.br/palmares/pt-br/assuntos/noticias/fundacao-cultural-palmares-lanca-sistema-nacional-de-informacoes-quilombolas-na-serra-da-barriga"]:
    h = get(u); print("\n=====", u, len(h))
    if not h: continue
    print("article:", len(re.findall(r"<article\b", h, re.I)), "figure:", len(re.findall(r"<figure\b", h, re.I)), "img:", len(re.findall(r"<img\b", h, re.I)))
    for m in re.findall(r"<img[^>]+>", h, re.I)[:25]:
        print("IMG", m[:220])
    for m in re.findall(r'href="([^"]*(?:flickr|album|galeria|@@images|\.jpe?g)[^"]*)"', h, re.I)[:15]:
        print("LINK-FOTO", m[:200])
    links = re.findall(r'<a[^>]+href="([^"#]+)"[^>]*>(.*?)</a>', h, re.S | re.I)
    n = 0
    for href, t in links:
        t = re.sub(r"<[^>]+>|\s+", " ", t).strip()
        if len(t) >= 35 and ("noticias" in href):
            print("NOTICIA", href[:160], "|", t[:90]); n += 1
            if n >= 12: break
    for m in re.findall(r"(?:rss|feed|@@search|json)[^\"' ]{0,120}", h, re.I)[:10]:
        print("PISTA", m)
