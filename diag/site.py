import re, requests, collections
xml=requests.get("https://www.africas.com.br/sitemap.xml",timeout=60,headers={"User-Agent":"Mozilla/5.0"}).text
locs=re.findall(r"<url>\s*<loc>([^<]+)</loc>\s*<lastmod>([^<]+)</lastmod>",xml)
c=collections.Counter(l[:10] for u,l in locs if "/noticia/" in u)
print("SITEMAP", sorted(c.items())[-6:], "total", len(locs))
for cat in ["politica","cultura","mundo","esporte","racismo","cotidiano","brasil"]:
    pass
