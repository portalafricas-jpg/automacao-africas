# Liga os posts antigos do Instagram (@africasplay) às matérias do site, pelo título.
# Só leitura no Instagram: não publica nem apaga nada. Grava o resultado em feeds/instagram.json,
# a mesma lista que o código do Body do site usa para mostrar o post no fim da matéria.
import difflib
import json
import os
import re
import unicodedata
from urllib.parse import urlparse

import requests

TOKEN = os.environ["META_PAGE_TOKEN"]
IG = os.environ["IG_USER_ID"]
ARQ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "feeds", "instagram.json")
LIMITE_POSTS = 3000
UA = {"User-Agent": "Mozilla/5.0 (robo-africas)"}


def slug(t):
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def paginas_do_site():
    vistos, fila, saida = set(), ["https://www.africas.com.br/sitemap.xml"], set()
    while fila:
        u = fila.pop()
        if u in vistos:
            continue
        vistos.add(u)
        try:
            xml = requests.get(u, timeout=60, headers=UA).text
        except Exception as e:
            print("Erro no sitemap", u, e)
            continue
        for loc in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", xml):
            if loc.endswith(".xml") or "sitemap" in loc:
                fila.append(loc)
            else:
                caminho = "/" + urlparse(loc).path.strip("/")
                if caminho.startswith("/noticia/"):
                    saida.add(caminho)
    return saida


def posts_do_instagram():
    url = f"https://graph.facebook.com/v26.0/{IG}/media"
    params = {"fields": "caption,permalink,timestamp", "limit": 100, "access_token": TOKEN}
    posts = []
    while url and len(posts) < LIMITE_POSTS:
        r = requests.get(url, params=params, timeout=60).json()
        if "error" in r:
            print("Erro da Meta:", r["error"].get("message"))
            break
        posts += r.get("data", [])
        url, params = r.get("paging", {}).get("next"), None
    return posts


def main():
    site = paginas_do_site()
    print(f"Matérias no mapa do site: {len(site)}")
    por_slug = {c[len("/noticia/"):]: c for c in site}
    slugs = list(por_slug)
    posts = posts_do_instagram()
    print(f"Posts lidos no Instagram: {len(posts)}")
    try:
        mapa = json.load(open(ARQ, encoding="utf-8"))
    except Exception:
        mapa = {}
    antes = len(mapa)
    ligados, sem_par = 0, []
    for p in posts:
        titulo = (p.get("caption") or "").split("\n")[0].strip()
        if len(titulo) < 15 or not p.get("permalink"):
            continue
        s = slug(titulo)
        achou = por_slug.get(s)
        if not achou:
            # o site às vezes põe um número no fim do endereço
            parecidos = [x for x in slugs if x.startswith(s)]
            if not parecidos:
                parecidos = difflib.get_close_matches(s, slugs, n=1, cutoff=0.9)
            achou = por_slug[parecidos[0]] if parecidos else None
        if achou:
            if achou not in mapa:  # não troca o que o robô das redes já ligou
                mapa[achou] = p["permalink"]
                ligados += 1
        else:
            sem_par.append(titulo[:70])
    os.makedirs(os.path.dirname(ARQ), exist_ok=True)
    json.dump(mapa, open(ARQ, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"Ligados agora: {ligados} | lista tinha {antes} e ficou com {len(mapa)}")
    print(f"Posts sem matéria correspondente: {len(sem_par)} (ex.: vídeos, avisos ou matérias apagadas)")
    for t in sem_par[:15]:
        print("  sem par:", t)


if __name__ == "__main__":
    main()
