import requests, re
u="https://www.africas.com.br/noticia/exposicao-no-rio-resgata-o-lado-humano-de-joao-candido"
for nome, ua in [("PC","Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/130"),("CELULAR","Mozilla/5.0 (Linux; Android 14; SM-A546B) AppleWebKit/537.36 Chrome/130 Mobile Safari/537.36"),("IPHONE","Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Version/18.0 Mobile/15E148 Safari/604.1")]:
    r=requests.get(u,timeout=30,headers={"User-Agent":ua})
    h=r.text
    print(nome, r.status_code, r.url, "| codigo instagram:", "instagram.json" in h, "| no lugar do Siga:", "Siga o Áfricas" in h and "replaceChild" in h, "| id=content:", 'id="content"' in h, "| amp:", "amphtml" in h, "| cache:", r.headers.get("cf-cache-status") or r.headers.get("x-cache") or r.headers.get("age"))
