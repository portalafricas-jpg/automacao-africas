# Diagnóstico (26/11/2026): RSS e fotos da Agência Gov (republica MIR e Palmares).
import re, urllib.request
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
def get(u):
    try:
        r = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30)
        return r.read().decode("utf-8", "ignore")
    except Exception as e:
        print("ERRO", u, e); return ""
h = get("https://agenciagov.ebc.com.br/noticias/igualdade-racial")
for m in re.findall(r'<link[^>]+(?:rss|atom)[^>]*>', h, re.I): print("LINKTAG", m)
for m in re.findall(r'href="([^"]*(?:RSS|rss)[^"]*)"', h): print("HREF-RSS", m)
for u in ["https://agenciagov.ebc.com.br/noticias/igualdade-racial/RSS", "https://agenciagov.ebc.com.br/noticias/igualdade-racial/rss.xml",
          "https://agenciagov.ebc.com.br/RSS", "https://agenciagov.ebc.com.br/rss.xml"]:
    x = get(u); print("\n==", u, len(x), x[:300].replace("\n", " "))
    for t in re.findall(r"<item>.*?<title>(.*?)</title>.*?<link>(.*?)</link>", x, re.S)[:5]: print("  ITEM", t)
a = get("https://agenciagov.ebc.com.br/noticias/202611/a-igualdade-racial-pelo-olhar-de-quem-faz-o-servico-publico")
print("\n== ARTIGO", len(a), "article:", len(re.findall(r"<article\b", a, re.I)), "figure:", len(re.findall(r"<figure\b", a, re.I)))
m = re.search(r"<article\b.*?</article>", a, re.S | re.I)
miolo = m.group(0) if m else a
for i in re.findall(r"<img[^>]+>", miolo, re.I)[:20]: print("IMG", i[:250])
for f in re.findall(r"<figure\b.*?</figure>", miolo, re.S | re.I)[:5]: print("FIG", re.sub(r"\s+", " ", f)[:400])
for l in re.findall(r'href="([^"]*(?:flickr|galeria|album)[^"]*)"', a, re.I)[:10]: print("ALBUM", l)
for c in re.findall(r"(?:Foto|Crédito)[^<]{0,80}", miolo)[:8]: print("CRED", c)
