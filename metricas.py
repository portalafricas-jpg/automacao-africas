# Relatório de resultados das redes (só leitura: não publica nem apaga nada).
# Busca no Instagram e no Facebook os números de cada post recente e o perfil do público
# do Instagram (idade, gênero, cidades) e grava em estado/relatorios/metricas-redes.json.
import json
import os
import re
from datetime import datetime, timezone

import requests

API = "https://graph.facebook.com/v26.0/"
TOKEN = os.environ.get("META_PAGE_TOKEN", "")
IG = os.environ.get("IG_USER_ID", "")
PAGINA = os.environ.get("FB_PAGE_ID", "")
PASTA = os.path.dirname(os.path.abspath(__file__))
SAIDA = os.path.join(PASTA, "estado", "relatorios", "metricas-redes.json")
ARQ_POSTS = os.path.join(PASTA, "estado", "posts-redes.json")


def get(caminho, **params):
    params["access_token"] = TOKEN
    r = requests.get(API + caminho, params=params, timeout=40)
    try:
        d = r.json()
    except Exception:
        d = {"error": {"message": "resposta inválida"}}
    d.pop("paging", None)  # os links de paginação trazem a chave: nunca gravar
    return d


def sem_chave(texto):
    # apaga qualquer chave que apareça numa mensagem antes de gravar no arquivo
    return re.sub(r"access_token=[^&\s'\"]+", "access_token=OCULTO", str(texto))


def insights_ig(media_id, tipo):
    metricas = ["reach", "saved", "shares", "total_interactions", "views"]
    if tipo == "VIDEO":
        metricas.append("ig_reels_avg_watch_time")
    else:
        metricas += ["follows", "profile_visits"]  # quantos seguiram e visitaram o perfil por causa do post
    saida = {}
    for m in metricas:  # uma por vez: se uma não existir para o formato, as outras continuam
        d = get(f"{media_id}/insights", metric=m)
        for item in d.get("data", []):
            v = item.get("values", [{}])
            saida[m] = item.get("total_value", {}).get("value", v[0].get("value") if v else None)
        if "error" in d:
            saida[m] = None
    # alcance dividido entre quem já segue e quem ainda não segue (gente nova)
    d = get(f"{media_id}/insights", metric="reach", breakdown="follow_type", metric_type="total_value")
    try:
        res = d["data"][0]["total_value"]["breakdowns"][0]["results"]
        saida["alcance_por_tipo"] = {"/".join(r["dimension_values"]): r["value"] for r in res}
    except Exception:
        saida["alcance_por_tipo"] = None
    return saida


ARQ_HIST = os.path.join(PASTA, "estado", "relatorios", "seguidores-historico.json")


def novos_seguidores_30_dias():
    # quantos seguidores entraram por dia nos últimos 30 dias (dado que a própria Meta guarda)
    import time
    ate = int(time.time())
    desde = ate - 29 * 86400
    saida = {}
    d = get(f"{IG}/insights", metric="follower_count", period="day", since=desde, until=ate)
    try:
        saida["instagram"] = {v["end_time"][:10]: v["value"] for v in d["data"][0]["values"]}
    except Exception:
        saida["instagram"] = {"erro": sem_chave(d.get("error", d))[:200]}
    for m in ("page_daily_follows_unique", "page_follows"):
        d = get(f"{PAGINA}/insights", metric=m, period="day", since=desde, until=ate)
        try:
            saida["facebook"] = {v["end_time"][:10]: v["value"] for v in d["data"][0]["values"]}
            saida["facebook_metrica"] = m
            break
        except Exception:
            saida["facebook"] = {"erro": sem_chave(d.get("error", d))[:200]}
    return saida


def registrar_seguidores(conta, pagina):
    # guarda 1 linha por dia com o total de seguidores do Instagram e do Facebook
    try:
        with open(ARQ_HIST, encoding="utf-8") as f:
            hist = json.load(f)
    except Exception:
        hist = []
    hoje = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    hist = [h for h in hist if h.get("dia") != hoje]
    hist.append({"dia": hoje, "instagram": conta.get("followers_count"),
                 "facebook": pagina.get("followers_count")})
    with open(ARQ_HIST, "w", encoding="utf-8") as f:
        json.dump(hist, f, ensure_ascii=False, indent=1)


def comentarios_app(media_id):
    d = get(f"{media_id}/comments", fields="text,timestamp", limit=100)
    textos = [c.get("text", "") for c in d.get("data", [])]
    return sum(1 for t in textos if "app" in t.lower()), textos[:20]


def publico_ig():
    saida = {}
    for quebra in ("age", "gender", "city"):
        d = get(f"{IG}/insights", metric="follower_demographics", period="lifetime",
                metric_type="total_value", breakdown=quebra, timeframe="this_month")
        try:
            res = d["data"][0]["total_value"]["breakdowns"][0]["results"]
            saida[quebra] = {"/".join(r["dimension_values"]): r["value"] for r in res}
        except Exception:
            saida[quebra] = {"erro": sem_chave(d.get("error", d))[:200]}
    return saida


def main():
    try:
        with open(ARQ_POSTS, encoding="utf-8") as f:
            nossos = {p.get("ig_media"): p for p in json.load(f) if p.get("ig_media")}
    except Exception:
        nossos = {}

    conta = get(IG, fields="username,followers_count,media_count")
    lista = get(f"{IG}/media", limit=100,
                fields="id,caption,media_type,media_product_type,timestamp,permalink,like_count,comments_count")
    posts = []
    for m in lista.get("data", []):
        n_app, textos = comentarios_app(m["id"]) if m.get("comments_count") else (0, [])
        p = nossos.get(m["id"], {})
        posts.append({
            "id": m["id"], "data": m.get("timestamp"), "formato": m.get("media_product_type") or m.get("media_type"),
            "tipo": m.get("media_type"), "link": m.get("permalink"),
            "legenda": (m.get("caption") or "")[:160],
            "curtidas": m.get("like_count"), "comentarios": m.get("comments_count"),
            "comentaram_app": n_app, "textos_comentarios": textos,
            "robo": bool(p), "categoria": p.get("categoria"), "prioridade": p.get("prioridade"),
            "titulo": p.get("titulo"), "fb_post": p.get("fb_post"),
            **insights_ig(m["id"], m.get("media_type")),
        })

    for p in posts:
        if p.get("fb_post"):
            d = get(p["fb_post"], fields="shares,reactions.summary(true).limit(0),comments.summary(true).limit(0)")
            p["fb_reacoes"] = d.get("reactions", {}).get("summary", {}).get("total_count")
            p["fb_comentarios"] = d.get("comments", {}).get("summary", {}).get("total_count")
            p["fb_compartilhamentos"] = d.get("shares", {}).get("count", 0) if "error" not in d else None

    pagina = get(PAGINA, fields="name,followers_count,fan_count")
    relatorio = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "conta": conta, "publico_instagram": publico_ig(),
        "pagina_facebook": pagina,
        "seguidores_30_dias": novos_seguidores_30_dias(),
        "posts": posts,
    }
    os.makedirs(os.path.dirname(SAIDA), exist_ok=True)
    with open(SAIDA, "w", encoding="utf-8") as f:
        json.dump(relatorio, f, ensure_ascii=False, indent=1)
    registrar_seguidores(conta, pagina)
    print(f"Conta: {conta}")
    print(f"Posts lidos: {len(posts)} (do robô: {sum(1 for p in posts if p['robo'])})")
    print(f"Comentários com APP: {sum(p['comentaram_app'] for p in posts)}")


if __name__ == "__main__":
    main()
