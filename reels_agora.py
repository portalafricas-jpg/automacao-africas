# Publica um Reels na hora (teste pedido pelo Washington). Instagram sempre; Facebook só se ainda não saiu hoje.
# Não repete as matérias do último Reels publicado.
import os
import redes as R
import video

token = os.environ["META_PAGE_TOKEN"].strip()
pagina = os.environ["FB_PAGE_ID"].strip()
ig = os.environ["IG_USER_ID"].strip()
posts = R.ler_json(R.ARQ_POSTS, [])
estado = R.ler_json(R.ARQ_REDES, {})
hoje = R.dia_de_trabalho(R.agora_sp())
ultimos = [p for p in posts if p.get("tipo") == "reels"]
excluir = {m["link"] for m in (ultimos[-1].get("links", []) if ultimos else [])}
post = video.fazer_e_publicar(posts, False, token, pagina, ig, estado, hoje, "noite", excluir)
if post:
    posts.append(post)
    R.salvar_json(R.ARQ_POSTS, posts[-300:])
    R.salvar_json(R.ARQ_REDES, estado)
    R.gravar_mapa_instagram(posts)
