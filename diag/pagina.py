import re, requests
u="https://www.africas.com.br/noticia/gaby-amarantos-vai-interpretar-alcione-em-filme"
h=requests.get(u,timeout=30,headers={"User-Agent":"Mozilla/5.0"}).text
open("pagina.html","w").write(h)
i=h.find('fetchpriority="high"')
lines=h.splitlines()
for n,l in enumerate(lines):
    if re.search(r'class="[^"]*(post|article|content|text|body|detail|share|tag)[^"]*"', l) and 880<n<1130:
        print(n, l.strip()[:200])
