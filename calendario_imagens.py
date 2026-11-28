# Calendário Afro: pesquisa de imagens no Wikimedia Commons (gratuito, sem chave).
# Lê o arquivo busca.json da pasta do episódio, procura as imagens, lê a licença de cada uma
# e baixa SÓ as de domínio público. As demais ficam listadas no relatório, sem baixar.
# Nada é publicado: o relatório serve para a conferência foto × nome.
# Uso: python calendario_imagens.py calendario/2026-12/06-joao-candido

import html
import json
import os
import re
import sys
import time

import requests

API = "https://commons.wikimedia.org/w/api.php"
CABECALHO = {"User-Agent": "AfricasPlay-CalendarioAfro/1.0 (https://www.africas.com.br)"}
LIVRES = ("public domain", "pd-", "pd ", "cc0", "domínio público")
MAX_BAIXAR = 25
LARGURA = 2000


def api(params):
    params.update({"format": "json", "formatversion": "2"})
    for tentativa in range(3):
        try:
            r = requests.get(API, params=params, headers=CABECALHO, timeout=40)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print("  erro na consulta:", e)
            time.sleep(3)
    return {}


def limpar(texto):
    texto = re.sub(r"<[^>]+>", " ", texto or "")
    return re.sub(r"\s+", " ", html.unescape(texto)).strip()


def arquivos_da_categoria(categoria):
    dados = api({"action": "query", "list": "categorymembers", "cmtitle": categoria,
                 "cmtype": "file", "cmlimit": "100"})
    return [m["title"] for m in dados.get("query", {}).get("categorymembers", [])]


def arquivos_da_busca(termo):
    dados = api({"action": "query", "list": "search", "srsearch": termo,
                 "srnamespace": "6", "srlimit": "30"})
    return [m["title"] for m in dados.get("query", {}).get("search", [])]


def informacoes(titulos):
    saida = {}
    for i in range(0, len(titulos), 40):
        lote = titulos[i:i + 40]
        dados = api({"action": "query", "titles": "|".join(lote), "prop": "imageinfo",
                     "iiprop": "url|size|mime|extmetadata", "iiurlwidth": str(LARGURA)})
        for p in dados.get("query", {}).get("pages", []):
            info = (p.get("imageinfo") or [{}])[0]
            meta = info.get("extmetadata", {})

            def pega(k):
                return limpar(meta.get(k, {}).get("value", ""))

            saida[p["title"]] = {
                "titulo": p["title"],
                "descricao": pega("ImageDescription")[:300],
                "data": pega("DateTimeOriginal")[:60],
                "autor": pega("Artist")[:120],
                "licenca": pega("LicenseShortName"),
                "pagina": info.get("descriptionurl", ""),
                "url": info.get("thumburl") or info.get("url", ""),
                "mime": info.get("mime", ""),
            }
    return saida


def livre(item):
    lic = item["licenca"].lower()
    return any(p in lic for p in LIVRES)


def nome_arquivo(n, titulo, mime):
    base = re.sub(r"[^A-Za-z0-9_-]+", "_", titulo.replace("File:", "").rsplit(".", 1)[0])[:60]
    ext = ".png" if "png" in mime else ".jpg"
    return f"{n:02d}_{base}{ext}"


def celula(s):
    return (s or "—").replace("|", "/")


def main(pasta):
    with open(os.path.join(pasta, "busca.json"), encoding="utf-8") as f:
        busca = json.load(f)

    titulos = []
    for t in busca.get("arquivos", []):
        titulos.append(t if t.startswith("File:") else "File:" + t)
    for c in busca.get("categorias", []):
        titulos += arquivos_da_categoria(c)
    for termo in busca.get("buscas", []):
        titulos += arquivos_da_busca(termo)
    titulos = list(dict.fromkeys(titulos))
    print(f"{len(titulos)} imagens encontradas")

    itens = informacoes(titulos)
    pasta_img = os.path.join(pasta, "imagens")
    os.makedirs(pasta_img, exist_ok=True)

    linhas, baixadas = [], 0
    for item in itens.values():
        if not item["mime"].startswith("image/") or "svg" in item["mime"]:
            continue
        status = "não baixada (licença não é domínio público)"
        arquivo = ""
        if livre(item) and baixadas < MAX_BAIXAR and item["url"]:
            arquivo = nome_arquivo(baixadas + 1, item["titulo"], item["mime"])
            try:
                r = requests.get(item["url"], headers=CABECALHO, timeout=60)
                r.raise_for_status()
                with open(os.path.join(pasta_img, arquivo), "wb") as f:
                    f.write(r.content)
                baixadas += 1
                status = "BAIXADA"
            except Exception as e:
                status = f"erro ao baixar: {e}"
                arquivo = ""
            time.sleep(1)
        linhas.append((status, arquivo, item))

    linhas.sort(key=lambda x: (x[0] != "BAIXADA", x[1]))
    with open(os.path.join(pasta, "relatorio-imagens.md"), "w", encoding="utf-8") as f:
        f.write(f"# Relatório de imagens — {busca.get('episodio', pasta)}\n\n")
        f.write(f"{baixadas} baixadas (domínio público) de {len(linhas)} encontradas no Wikimedia Commons.\n")
        f.write("Conferência foto × nome: PENDENTE (feita pelo Claude antes de qualquer montagem).\n\n")
        f.write("| Status | Arquivo | Descrição | Data | Autor | Licença | Página |\n|---|---|---|---|---|---|---|\n")
        for status, arquivo, it in linhas:
            f.write(f"| {status} | {celula(arquivo)} | {celula(it['descricao'])} | {celula(it['data'])} | "
                    f"{celula(it['autor'])} | {celula(it['licenca'])} | {it['pagina']} |\n")
    print(f"{baixadas} imagens baixadas; relatório gravado")


if __name__ == "__main__":
    main(sys.argv[1])
