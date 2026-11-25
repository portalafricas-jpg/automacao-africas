# Teste (25/11/2026): o Instagram aceita BOTÕES já no primeiro direct (resposta a um comentário)?
# Procura nos posts recentes um comentário com a palavra TESTEBOTAO e responde no direct com uma
# mensagem de botões clicáveis: Ler a matéria / Baixar o app / Seguir o Áfricas.
import json
import unicodedata
from datetime import datetime, timedelta, timezone

import comentarios as C

PERFIL = "https://www.instagram.com/africasplay/"
LOJA = "https://play.google.com/store/apps/details?id=br.com.app.gpu2633271.gpuc8cfd42c63ec76c640904e227254c57c"


def normal(t):
    t = unicodedata.normalize("NFD", (t or "").upper())
    return "".join(c for c in t if unicodedata.category(c) != "Mn").replace(" ", "")


def mensagem(post):
    texto = f"Oi! Aqui está a matéria completa:\n{post['titulo']}\n\nToque nos botões abaixo 👇"
    return {"attachment": {"type": "template", "payload": {
        "template_type": "button", "text": texto[:640],
        "buttons": [
            {"type": "web_url", "url": post["link"], "title": "Ler a matéria"},
            {"type": "web_url", "url": LOJA, "title": "Baixar o app"},
            {"type": "web_url", "url": PERFIL, "title": "Seguir o Áfricas"},
        ]}}}


def main():
    posts = json.load(open(C.ARQ_POSTS, encoding="utf-8"))
    limite = datetime.now(timezone.utc) - timedelta(hours=72)
    for post in [p for p in posts if p.get("ig_media") and datetime.fromisoformat(p["publicado_em"]) >= limite]:
        try:
            dados = C.meta("GET", f"{post['ig_media']}/comments", {"fields": "id,text,username", "limit": "50"})
        except RuntimeError:
            continue
        for c in dados.get("data", []):
            if "TESTEBOTAO" not in normal(c.get("text")):
                continue
            print(f"Achei o comentário de @{c.get('username')} em '{post['titulo']}'")
            mensagem, _ = C.mensagem_direct(post)
            ok = C.mandar_direct(c["id"], mensagem)  # sem texto reserva: queremos ver se os botões passam
            print(f"RESULTADO: {'botões ENVIADOS' if ok else 'botões RECUSADOS'}")
            return
    print("RESULTADO: nenhum comentário TESTEBOTAO encontrado nos posts dos últimos 3 dias")


if __name__ == "__main__":
    main()
