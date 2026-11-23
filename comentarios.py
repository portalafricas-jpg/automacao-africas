# Robô dos comentários do Instagram do Áfricas Play (roda a cada 2 minutos).
# Regras aprovadas pelo Washington em 23/11/2026:
#   APP              -> link da matéria no direct + resposta no comentário
#   elogio           -> agradecimento curto, variado
#   pergunta         -> resposta curta com base no texto da matéria (sem inventar)
#   crítica          -> não responde; avisa o Washington por e-mail (aviso do GitHub)
#   ofensa ou spam   -> esconde o comentário e avisa por e-mail
#   resto (emoji, marcação de amigos etc.) -> não faz nada
# A classificação é feita pelo Claude. Os comentários já vistos ficam guardados no cache do GitHub
# (arquivo cache/comentarios-vistos.json), para não classificar duas vezes.

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

MODELO = "claude-haiku-5-5"
LIMITE_CLAUDE = 25          # comentários classificados por rodada (trava de custo)
ARQ_VISTOS = os.path.join(PASTA, "cache", "comentarios-vistos.json")
DIAS_GUARDANDO = 7
REPO = os.environ.get("GITHUB_REPOSITORY", "portalafricas-jpg/automacao-africas")
GH_TOKEN = (os.environ.get("GITHUB_TOKEN") or "").strip()
CLAUDE_CHAVE = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()

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


# ---------------- Outros comentários (elogio, pergunta, crítica, ofensa) ----------------

INSTRUCAO = (
    "Você cuida dos comentários do Instagram do Áfricas Play, portal de jornalismo negro. Classifique o comentário "
    "e, quando for elogio ou pergunta, escreva a resposta pública.\n"
    "Tipos: elogio (parabéns, gostei, orgulho, apoio, emoji de aplauso/coração com palavra positiva); pergunta "
    "(dúvida sobre o fato da matéria); critica (discorda, reclama do conteúdo ou do portal, aponta erro, sem "
    "xingamento); ofensa (xingamento, racismo, ódio, ataque pessoal, ameaça); spam (propaganda, golpe, link, "
    "'me segue', venda); outro (só emoji, marcação de amigo, comentário neutro, conversa entre seguidores).\n"
    "Resposta: português do Brasil, tom acolhedor e direto, no máximo 160 caracteres, no máximo 1 emoji, sem "
    "hashtag, sem link. Elogio: agradeça de forma variada e natural (nunca a mesma frase pronta). Pergunta: "
    "responda SÓ com o que está no texto da matéria; se a resposta não estiver lá, diga que a matéria completa "
    "traz os detalhes e convide a comentar APP para receber o link no direct. Nunca invente fatos. Para os "
    "outros tipos, deixe a resposta vazia.")

FERRAMENTA = {
    "name": "classificar",
    "description": "Classifica o comentário e escreve a resposta pública quando couber.",
    "input_schema": {"type": "object", "properties": {
        "tipo": {"type": "string", "enum": ["elogio", "pergunta", "critica", "ofensa", "spam", "outro"]},
        "resposta": {"type": "string"}}, "required": ["tipo", "resposta"]},
}


def texto_da_materia(link, cache={}):
    if link in cache:
        return cache[link]
    texto = ""
    try:
        h = requests.get(link, timeout=30, headers={"User-Agent": "Mozilla/5.0 (robo-africas)"}).text
        i = h.find('id="content"')
        if i >= 0:
            trecho = h[i:i + 40000]
            trecho = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", trecho, flags=re.S)
            texto = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", trecho)).strip()[:6000]
    except Exception:
        pass
    cache[link] = texto
    return texto


def classificar(comentario, post):
    materia = "\n".join(f"- {m['titulo']}" for m in post["links"]) if post.get("links") else \
        texto_da_materia(post["link"])
    pedido = (f"Post: {post['titulo']}\n\nTexto da matéria:\n{materia or '(indisponível)'}\n\n"
              f"Comentário de @{comentario.get('username', '')}: {comentario.get('text', '')}")
    corpo = {"model": MODELO, "max_tokens": 400, "system": INSTRUCAO,
             "messages": [{"role": "user", "content": pedido}],
             "tools": [FERRAMENTA], "tool_choice": {"type": "tool", "name": "classificar"}}
    r = requests.post("https://api.anthropic.com/v1/messages", json=corpo, timeout=60, headers={
        "x-api-key": CLAUDE_CHAVE, "anthropic-version": "2023-06-01"}).json()
    for bloco in r.get("content", []):
        if bloco.get("type") == "tool_use":
            return bloco["input"].get("tipo", "outro"), (bloco["input"].get("resposta") or "").strip()[:220]
    raise RuntimeError(f"Claude não classificou: {str(r)[:200]}")


def avisar(titulo, texto):
    """Abre um aviso (issue) no GitHub; o GitHub manda por e-mail para o dono do repositório."""
    if not GH_TOKEN:
        log(f"  (sem GITHUB_TOKEN para avisar) {titulo}")
        return
    try:
        r = requests.post(f"https://api.github.com/repos/{REPO}/issues", timeout=30,
                          headers={"Authorization": f"Bearer {GH_TOKEN}", "Accept": "application/vnd.github+json"},
                          json={"title": titulo, "body": texto, "labels": ["comentario"]})
        if r.status_code >= 300:
            log(f"  aviso não foi aberto: {r.status_code} {r.text[:150]}")
    except Exception as e:
        log(f"  aviso não foi aberto: {e}")


def ler_vistos():
    try:
        with open(ARQ_VISTOS, encoding="utf-8") as f:
            vistos = json.load(f)
    except Exception:
        vistos = {}
    corte = (datetime.now(timezone.utc) - timedelta(days=DIAS_GUARDANDO)).isoformat()
    return {k: v for k, v in vistos.items() if v.get("em", "") >= corte}


def salvar_vistos(vistos):
    os.makedirs(os.path.dirname(ARQ_VISTOS), exist_ok=True)
    with open(ARQ_VISTOS, "w", encoding="utf-8") as f:
        json.dump(vistos, f, ensure_ascii=False)


def tratar_outro(c, post, vistos):
    """Elogio, pergunta, crítica, ofensa ou spam. Devolve True se chamou o Claude."""
    autor = c.get("username", "")
    tipo, resposta = classificar(c, post)
    vistos[c["id"]] = {"tipo": tipo, "em": datetime.now(timezone.utc).isoformat()}
    link_post = post.get("ig_link") or ""
    if tipo in ("elogio", "pergunta") and resposta:
        try:
            meta("POST", f"{c['id']}/replies", {"message": resposta})
            log(f"{tipo.capitalize()}: @{autor} -> respondido: {resposta}")
        except RuntimeError as e:
            log(f"  resposta falhou ({e})")
    elif tipo == "critica":
        avisar(f"Crítica no Instagram: @{autor}",
               f"**Comentário:** {c.get('text', '')}\n\n**Post:** {post['titulo']}\n{link_post}\n\n"
               f"O robô não respondeu. Responda você mesmo, se achar necessário.")
        log(f"Crítica: @{autor} -> aviso enviado")
    elif tipo in ("ofensa", "spam"):
        escondido = True
        try:
            meta("POST", c["id"], {"hide": "true"})
        except RuntimeError as e:
            escondido = False
            log(f"  não conseguiu esconder ({e})")
        avisar(f"Comentário {'escondido' if escondido else 'NÃO escondido'} ({tipo}): @{autor}",
               f"**Comentário:** {c.get('text', '')}\n\n**Post:** {post['titulo']}\n{link_post}\n\n"
               f"{'O robô escondeu o comentário. Se foi engano, mostre de novo pelo Instagram (comentário > Mostrar).' if escondido else 'O robô não conseguiu esconder; veja no Instagram.'}")
        log(f"{tipo.capitalize()}: @{autor} -> {'escondido' if escondido else 'falhou ao esconder'}")
    else:
        log(f"Outro: @{autor} -> sem ação")


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
    vistos = ler_vistos()
    chamadas_claude = 0
    for post in recentes:
        try:
            dados = meta("GET", f"{post['ig_media']}/comments",
                         {"fields": "id,text,username,timestamp,hidden,replies{username}", "limit": "50"})
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
            if autor == nosso or c.get("hidden"):
                continue
            ja_respondido = any((r.get("username") or "").lower() == nosso
                                for r in (c.get("replies") or {}).get("data", []))
            if not pediu_app(c.get("text")):
                if ja_respondido or c["id"] in vistos or not CLAUDE_CHAVE or chamadas_claude >= LIMITE_CLAUDE:
                    continue
                chamadas_claude += 1
                try:
                    tratar_outro(c, post, vistos)
                except Exception as e:
                    log(f"  comentário de @{autor} fica para a próxima rodada ({e})")
                time.sleep(1)
                continue
            if autor in atendidos:
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
    salvar_vistos(vistos)
    log(f"Fim: {respondidos} pedidos de APP atendidos, {chamadas_claude} outros comentários avaliados, "
        f"{len(recentes)} posts olhados.")


if __name__ == "__main__":
    main()
