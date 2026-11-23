# Comente APP: responde quem comentou "APP" nos posts do Áfricas Play no Instagram.
# Para cada comentário novo com "APP":
#   1) manda no direct o link da matéria (abre no app de quem tem; no site, para quem não tem)
#      e os links das lojas;
#   2) responde no comentário: "Te mandamos o link no direct!".
# Não guarda arquivo nenhum: para saber se já respondeu, olha se o @africasplay já respondeu o comentário.

import json
import os
import re
import time
import unicodedata
from datetime import datetime, timedelta, timezone

import requests

API = "https://graph.facebook.com/v26.0/"
PASTA = os.path.dirname(os.path.abspath(__file__))
ARQ_POSTS = os.path.join(PASTA, "estado", "posts-redes.json")
HORAS_OLHANDO = 72          # olha os comentários dos posts dos últimos 3 dias
LIMITE_POR_RODADA = 40      # trava de segurança

LOJA_ANDROID = "https://play.google.com/store/apps/details?id=br.com.app.gpu2633271.gpuc8cfd42c63ec76c640904e227254c57c"
LOJA_IPHONE = "https://apps.apple.com/app/id6448585492"

RESPOSTA_OK = "Te mandamos o link no direct! 📲"
RESPOSTA_SEM_DIRECT = "Não conseguimos te mandar no direct 😕 O link do app Áfricas Play está na nossa bio."

TOKEN = (os.environ.get("META_PAGE_TOKEN") or "").strip()
PAGINA = (os.environ.get("FB_PAGE_ID") or "").strip()
IG = (os.environ.get("IG_USER_ID") or "").strip()


def log(t):
    print(t, flush=True)


def meta(metodo, caminho, dados=None, json_corpo=None):
    url = API + caminho
    if metodo == "GET":
        r = requests.get(url, params={**(dados or {}), "access_token": TOKEN}, timeout=40)
    elif json_corpo is not None:
        r = requests.post(url, params={"access_token": TOKEN}, json=json_corpo, timeout=40)
    else:
        r = requests.post(url, data={**(dados or {}), "access_token": TOKEN}, timeout=40)
    corpo = r.json()
    if "error" in corpo:
        e = corpo["error"]
        raise RuntimeError(f"{e.get('message', 'erro')} (código {e.get('code')})")
    return corpo


def pediu_app(texto):
    t = unicodedata.normalize("NFD", (texto or "").lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.search(r"\b(app|aplicativo|apps)\b", t) is not None


def mensagem_direct(post):
    if post.get("links"):  # Reels com várias matérias
        lista = "\n\n".join(f"• {m['titulo']}\n{m['link']}" for m in post["links"])
        return (f"Oi! Aqui estão as matérias completas do {post['titulo']}:\n\n{lista}\n\n"
                f"Se você tem o app Áfricas Play, elas abrem direto nele.\n"
                f"Ainda não tem? Baixe grátis:\nAndroid: {LOJA_ANDROID}\niPhone: {LOJA_IPHONE}")
    return (f"Oi! Aqui está a matéria completa: {post['titulo']}\n{post['link']}\n\n"
            f"Se você tem o app Áfricas Play, ela abre direto nele.\n"
            f"Ainda não tem? Baixe grátis:\nAndroid: {LOJA_ANDROID}\niPhone: {LOJA_IPHONE}")


def mandar_direct(comentario_id, texto):
    corpo = {"recipient": {"comment_id": comentario_id}, "message": {"text": texto}}
    try:
        meta("POST", f"{PAGINA}/messages", json_corpo=corpo)
        return True
    except RuntimeError as e:
        log(f"  direct pela página falhou ({e}); tentando pela conta do Instagram")
    try:
        meta("POST", f"{IG}/messages", json_corpo=corpo)
        return True
    except RuntimeError as e:
        log(f"  direct falhou ({e})")
        return False


def main():
    if not (TOKEN and PAGINA and IG):
        raise SystemExit("Faltam META_PAGE_TOKEN, FB_PAGE_ID ou IG_USER_ID no cofre.")
    try:
        with open(ARQ_POSTS, encoding="utf-8") as f:
            posts = json.load(f)
    except Exception:
        posts = []
    limite = datetime.now(timezone.utc) - timedelta(hours=HORAS_OLHANDO)
    recentes = [p for p in posts if p.get("ig_media") and datetime.fromisoformat(p["publicado_em"]) >= limite]
    nosso = meta("GET", IG, {"fields": "username"}).get("username", "africasplay").lower()
    respondidos = 0
    for post in recentes:
        try:
            dados = meta("GET", f"{post['ig_media']}/comments",
                         {"fields": "id,text,username,timestamp,replies{username}", "limit": "50"})
        except RuntimeError as e:
            log(f"Não leu os comentários de '{post['titulo'][:50]}': {e}")
            continue
        comentarios = dados.get("data", [])
        # quem já foi atendido neste post não recebe de novo
        atendidos = {c.get("username", "").lower() for c in comentarios
                     if any((r.get("username") or "").lower() == nosso for r in (c.get("replies") or {}).get("data", []))}
        for c in comentarios:
            if respondidos >= LIMITE_POR_RODADA:
                break
            autor = (c.get("username") or "").lower()
            if autor == nosso or autor in atendidos or not pediu_app(c.get("text")):
                continue
            ok = mandar_direct(c["id"], mensagem_direct(post))
            try:
                meta("POST", f"{c['id']}/replies", {"message": RESPOSTA_OK if ok else RESPOSTA_SEM_DIRECT})
            except RuntimeError as e:
                log(f"  resposta no comentário falhou ({e})")
            atendidos.add(autor)
            respondidos += 1
            log(f"Comente APP: @{autor} em '{post['titulo'][:50]}' -> {'direct enviado' if ok else 'sem direct'}")
            time.sleep(1)
    log(f"Fim: {respondidos} pedidos atendidos em {len(recentes)} posts olhados.")


if __name__ == "__main__":
    main()
