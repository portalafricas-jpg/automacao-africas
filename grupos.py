# Links para os grupos do Facebook (aprovado por Washington em 26/11/2026).
# Todo dia útil escolhe as 2 melhores matérias de política do site e abre um aviso (issue)
# no GitHub, que chega por e-mail. Washington toca no link, o Facebook abre a janela de
# compartilhar e ele escolhe "Compartilhar em um grupo". O robô não posta em grupo nenhum.
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import requests

from redes import ARQ_PUBLICADAS, FUSO_SP, ler_rss_site, normalizar

REPO = os.environ.get("GITHUB_REPOSITORY", "portalafricas-jpg/automacao-africas")
GH_TOKEN = os.environ.get("GITHUB_TOKEN", "")
DONO = "portalafricas-jpg"
CATEGORIAS = {"radar", "politica", "política"}
QUANTAS = 2
TESTE = os.environ.get("TESTE_GRUPOS") == "1"


def registro_do_robo():
    try:
        with open(ARQ_PUBLICADAS, encoding="utf-8") as f:
            return {normalizar(m.get("titulo")): m for m in json.load(f) if m.get("titulo")}
    except Exception:
        return {}


def escolher():
    agora = datetime.now(timezone.utc)
    reg = registro_do_robo()
    candidatas = []
    for it in ler_rss_site():
        if normalizar(it["categoria"]) not in {normalizar(c) for c in CATEGORIAS}:
            continue
        if it["quando"] and agora - it["quando"] > timedelta(hours=30):
            continue
        m = reg.get(normalizar(it["titulo"]), {})
        nota = m.get("nota") or 7
        bonus = (1 if m.get("gente") else 0) + (2 if m.get("prioridade") == "breaking" else 0)
        candidatas.append((nota + bonus, it))
    candidatas.sort(key=lambda x: -x[0])
    return [it for _, it in candidatas[:QUANTAS]]


def pergunta_para_grupo(item):
    """Uma pergunta curta para puxar debate no grupo. Se a IA falhar, usa uma frase padrão."""
    chave = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    padrao = "O que vocês acham disso?"
    if not chave:
        return padrao
    for tentativa in range(2):  # tenta 2 vezes antes de usar a frase padrão
        texto = _perguntar(chave, item)
        if texto and len(texto.split()) <= 22:
            return texto
    return padrao


def _perguntar(chave, item):
    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": chave, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": "claude-haiku-5-5", "max_tokens": 120, "messages": [{"role": "user", "content":
                  "Escreva UMA pergunta curta e direta (no máximo 15 palavras), em português do Brasil, para eu postar num "
                  "grupo do movimento negro no Facebook junto com esta matéria, puxando debate respeitoso. "
                  "Não invente fatos além do texto. Responda só a pergunta.\n\n"
                  f"Título: {item['titulo']}\nResumo: {item['resumo'][:600]}"}]},
            timeout=40)
        return r.json()["content"][0]["text"].strip().strip('"')
    except Exception:
        return ""


def montar(itens):
    hoje = datetime.now(FUSO_SP).strftime("%d/%m")
    titulo = f"{'[TESTE] ' if TESTE else ''}Grupos do Facebook — {hoje}: {len(itens)} matérias para compartilhar"
    linhas = [f"@{DONO}", "", "Toque no link, escolha **Compartilhar em um grupo**, escolha o grupo e confirme.", ""]
    for n, it in enumerate(itens, 1):
        link = "https://www.facebook.com/sharer/sharer.php?u=" + quote(it["link"], safe="")
        linhas += [f"### {n}. {it['titulo']}",
                   f"Frase sugerida para o grupo: _{pergunta_para_grupo(it)}_",
                   "", f"👉 [Compartilhar no Facebook]({link})", ""]
    return titulo, "\n".join(linhas)


def gh(metodo, caminho, **kw):
    return requests.request(metodo, f"https://api.github.com/repos/{REPO}/{caminho}",
                            headers={"Authorization": f"Bearer {GH_TOKEN}",
                                     "Accept": "application/vnd.github+json"}, timeout=30, **kw)


def main():
    itens = escolher()
    if not itens:
        print("Nenhuma matéria de política nas últimas 30 horas. Nada enviado.")
        return
    titulo, corpo = montar(itens)
    print(titulo)
    print(corpo)
    if not GH_TOKEN:
        print("(sem GITHUB_TOKEN: só mostrei a prévia)")
        return
    # fecha os avisos antigos para não acumular
    antigos = gh("GET", "issues", params={"state": "open", "labels": "grupos-facebook", "per_page": 50})
    for i in antigos.json() if antigos.ok else []:
        gh("PATCH", f"issues/{i['number']}", json={"state": "closed"})
    r = gh("POST", "issues", json={"title": titulo, "body": corpo, "labels": ["grupos-facebook"]})
    print("Aviso criado:", r.status_code, r.json().get("html_url") if r.ok else r.text[:200])
    if not r.ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
