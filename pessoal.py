"""Cópia dos posts do @africasplay no Instagram pessoal do Washington (@washington_andrade1).

Combinado com o Washington em 28/11/2026:
- cópia automática (não é collab): o mesmo carrossel e o mesmo story saem também no Instagram pessoal;
- legenda em primeira pessoa, escrita pelo Claude a partir da legenda do Áfricas;
- só funciona com a chave ligada em pessoal-config.json ("ligado": true), que fica desligada até ele aprovar a prévia;
- se algo der errado aqui, o @africasplay segue normal (os erros só vão para o registro).

A chave da página do Washington não fica no cofre: é tirada na hora da META_USER_TOKEN
(chave de usuário, que não vence), pela lista de páginas que essa chave alcança.
"""
import json
import os
import re
import urllib.request

import requests

PASTA = os.path.dirname(os.path.abspath(__file__))
ARQ_CONFIG = os.path.join(PASTA, "pessoal-config.json")
API_META = "https://graph.facebook.com/v26.0/"
MODELO = "claude-haiku-5-5"
INSTAGRAM = "washington_andrade1"  # Instagram ligado à página "Washington Lúcio Andrade"
LIMITE = 700

CHAMADA_PESSOAL = "👉🏿 A matéria completa está no @africasplay e no app Áfricas Play."

INSTRUCAO = """Você reescreve legendas do Instagram do Áfricas Play para o Instagram pessoal de
Washington Lúcio Andrade, jornalista, CEO e editor-chefe do Áfricas Play.

Regras:
- OBRIGATÓRIO: a primeira frase já é em primeira pessoa, com a voz do Washington apresentando a notícia
  que o Áfricas publicou (ex.: "Publicamos no Áfricas Play...", "Contamos no Áfricas...",
  "Uma história que fiz questão de trazer para o Áfricas Play:"). Use "eu" ou "nós" (a equipe do Áfricas)
  também em pelo menos mais um trecho. Não copie a legenda original: reescreva com as suas palavras.
- NUNCA diga que ele esteve num lugar, conversou com alguém, viu algo ou participou de algo,
  a não ser que isso esteja escrito na legenda original. Não invente fato, nome, número nem opinião forte.
- Mantenha os fatos, os nomes e o sentido da legenda original. Português do Brasil.
- Nada de referência de tempo relativa ("hoje", "ontem", "nesta manhã") e nada de datas.
- Sem emojis, sem hashtags, sem @, sem link, sem créditos e sem chamada final (são colocados depois).
- Entre 300 e 600 caracteres. Separe os parágrafos com uma linha em branco.
Responda só com o texto da legenda."""


def log(t):
    print(t, flush=True)


def ligado():
    try:
        with open(ARQ_CONFIG, encoding="utf-8") as f:
            return bool(json.load(f).get("ligado"))
    except Exception:
        return False


def contexto():
    """Devolve (chave_da_pagina, id_do_instagram) da conta pessoal, ou None. Nunca mostra a chave."""
    usuario = (os.environ.get("META_USER_TOKEN") or "").strip()
    if not usuario:
        log("Instagram pessoal: falta META_USER_TOKEN no ambiente do robô.")
        return None
    try:
        r = requests.get(API_META + "me/accounts", timeout=60, params={
            "access_token": usuario, "limit": 100,
            "fields": "id,name,access_token,instagram_business_account{id,username}"}).json()
    except Exception as e:
        log(f"Instagram pessoal: falha ao ler as páginas ({e.__class__.__name__}).")
        return None
    if "error" in r:
        log(f"Instagram pessoal: a Meta recusou a leitura das páginas ({r['error'].get('message')}).")
        return None
    for p in r.get("data", []):
        conta = p.get("instagram_business_account") or {}
        if (conta.get("username") or "").lower() == INSTAGRAM and p.get("access_token") and conta.get("id"):
            return p["access_token"], conta["id"]
    log("Instagram pessoal: a página Washington Lúcio Andrade ou o Instagram dela não apareceu para a chave.")
    return None


def corpo_da_legenda(legenda_ig):
    """Separa da legenda do Áfricas só o corpo (sem a chamada do Comente APP, créditos, @ e hashtags)."""
    partes = [p for p in legenda_ig.split("\n\n") if p.strip()]
    corpo = []
    for p in partes:
        s = p.strip()
        if s.startswith("👉") or s.startswith("Texto:") or s.startswith("📸") or s.startswith("#") or s.startswith("@"):
            break
        corpo.append(s)
    resto = partes[len(corpo):]
    return "\n\n".join(corpo), resto


MARCAS = ("publicamos", "contamos", "trouxemos", "trago", "fiz questão", "nós", "nosso", "nossa",
          "eu ", "meu ", "minha ", "acompanhei", "acompanhamos", "destaco", "convido", "recomendo")


def em_primeira_pessoa(texto, original):
    t = (texto or "").lower()
    if not t or t.strip() == (original or "").lower().strip():
        return False
    return any(m in t for m in MARCAS)


def primeira_pessoa(corpo, tentativas=2):
    for _ in range(tentativas):
        texto = _primeira_pessoa(corpo)
        if texto:
            return texto
    log("  Instagram pessoal: o Claude não entregou legenda em primeira pessoa; post pessoal fica de fora.")
    return ""


def _primeira_pessoa(corpo):
    chave = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    if not chave or not corpo:
        return ""
    dados = json.dumps({"model": MODELO, "max_tokens": 700, "system": INSTRUCAO,
                        "messages": [{"role": "user", "content": "Legenda do Áfricas Play:\n\n" + corpo}]}).encode("utf-8")
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=dados, headers={
        "x-api-key": chave, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as r:
        resp = json.loads(r.read().decode("utf-8"))
    texto = "".join(b.get("text", "") for b in resp.get("content", []) if b.get("type") == "text").strip()
    if not em_primeira_pessoa(texto, corpo):
        return ""
    texto = re.sub(r"#\S+", "", texto).strip()
    if len(texto) > LIMITE:
        texto = texto[:LIMITE].rsplit("\n\n", 1)[0]
    return texto


def legenda_pessoal(legenda_ig):
    """Legenda em primeira pessoa + chamada para o Áfricas + créditos e hashtags da original."""
    corpo, resto = corpo_da_legenda(legenda_ig)
    novo = primeira_pessoa(corpo)
    if not novo:
        return ""
    creditos = [p for p in resto if p.strip().startswith(("Texto:", "📸"))]
    tags = [p for p in resto if p.strip().startswith("#")]
    return "\n\n".join(x for x in [novo, CHAMADA_PESSOAL] + creditos + tags if x)


def copiar_carrossel(enderecos, alts, legenda_ig):
    """Chamado pelo redes.py logo depois do carrossel do @africasplay. Nunca derruba o robô."""
    if not ligado():
        return None
    try:
        ctx = contexto()
        if not ctx:
            return None
        import redes
        token, ig = ctx
        legenda = legenda_pessoal(legenda_ig)
        if not legenda:
            return None
        midia, link = redes.publicar_carrossel(enderecos, alts, legenda, token, ig)
        log(f"  Instagram pessoal: carrossel copiado {link}")
        return link
    except Exception as e:
        log(f"  Instagram pessoal: erro ao copiar o carrossel ({e}). O @africasplay não foi afetado.")
        return None


def copiar_story(url_arte):
    if not ligado():
        return None
    try:
        ctx = contexto()
        if not ctx:
            return None
        import redes
        token, ig = ctx
        redes.publicar_story(url_arte, token, ig)
        log("  Instagram pessoal: story copiado.")
        return True
    except Exception as e:
        log(f"  Instagram pessoal: erro ao copiar o story ({e}). O @africasplay não foi afetado.")
        return None


def previa():
    """Só lê e escreve: monta a legenda pessoal das últimas matérias do feed do @africasplay. Não publica nada."""
    import redes
    linhas = ["# Prévia do Instagram pessoal (@washington_andrade1)", "",
              "Nada foi publicado. Abaixo, a legenda do @africasplay e como ela sairia no seu Instagram.", ""]
    ok = contexto()
    linhas.append(f"- Conexão com o seu Instagram: {'OK' if ok else 'com problema (ver registro)'}")
    linhas.append(f"- Chave de liga/desliga: {'LIGADA' if ligado() else 'desligada (nada sai no pessoal)'}")
    linhas.append("")
    itens = [i for i in redes.ler_rss_site() if i.get("arte_post")][:2]
    for item in itens:
        textos = redes.gerar_textos(item)
        leg_ig, _ = redes.montar_legendas(item, textos)
        linhas += [f"## {item['titulo']}", "", "### No @africasplay", "", leg_ig, "",
                   "### No seu Instagram (primeira pessoa)", "", legenda_pessoal(leg_ig) or "(sem legenda: não sairia no pessoal)", "", "---", ""]
    texto = "\n".join(linhas)
    os.makedirs(os.path.join(PASTA, "estado"), exist_ok=True)
    with open(os.path.join(PASTA, "estado", "previa-instagram-pessoal.md"), "w", encoding="utf-8") as f:
        f.write(texto)
    resumo = os.environ.get("GITHUB_STEP_SUMMARY")
    if resumo:
        with open(resumo, "a", encoding="utf-8") as f:
            f.write(texto + "\n")
    print(texto)


if __name__ == "__main__":
    previa()
