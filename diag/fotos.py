import re, requests, io
from PIL import Image
for u in ["https://www.africas.com.br/noticia/com-sangue-de-samba-carioca-neto-do-sindico-da-sapucai-e-eleito-novo-rei-momo-de-porto-alegre",
          "https://www.africas.com.br/noticia/gaby-amarantos-vai-interpretar-alcione-em-filme"]:
    h = requests.get(u, timeout=30, headers={"User-Agent": "Mozilla/5.0"}).text
    print("=====", u[-50:])
    for m in re.finditer(r'<meta[^>]+(og:image|twitter:image)[^>]*>', h): print("META", m.group(0)[:250])
    for m in re.finditer(r'<img[^>]+>', h):
        t = m.group(0)
        if "uploads" in t: print("IMG", h[:m.start()].count("\n"), t[:260])
    for m in re.finditer(r'https?://[^"\' ]+uploads/images/[^"\' ]+', h):
        try:
            img = Image.open(io.BytesIO(requests.get(m.group(0), timeout=20).content)).convert("L")
            print("BRILHO", round(sum(img.resize((64,64)).getdata())/4096), img.size, m.group(0)[-70:])
        except Exception as e: print("ERRO", m.group(0)[-70:])
