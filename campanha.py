"""Campanhas programadas (ex.: Expo África Brasil 2026).

Cada dia da campanha é uma pasta em campanhas/<nome>/<AAAA-MM-DD>/ com as artes e um plano.json:
  {"carrossel": {"hora": "20:00", "imagens": ["c1.jpg", ...], "legenda": "...", "link": "https://..."},
   "reels":     {"hora": "21:00", "arquivo": "reels.mp4", "legenda": "..."},   (vídeos ficam no galho "midia": ver midia.py)
   "youtube":   {"hora": "21:00", "arquivo": "short.mp4", "titulo": "...", "descricao": "...", "tags": [...],
                 "playlist": "Expo"},
   "stories":   [{"hora": "10:00", "arquivo": "story1.jpg"}, ...],
   "colaboradores": ["expoafricabrasil", "joaocandaoficial"]}
O robô das redes chama rodar() a cada rodada; cada peça sai uma vez só, na hora marcada ou logo depois.
"""
import os, json
from PIL import Image
import redes as R
import midia as deposito

PASTA = os.path.join(R.PASTA, "campanhas")
RAW = "https://raw.githubusercontent.com/portalafricas-jpg/automacao-africas/main/campanhas"


def _hora(h):
    hh, mm = h.split(":")
    return int(hh), int(mm)


def _ig_com_colab(fazer, colab):
    """Tenta com colaboradores; se o Instagram recusar só por isso, publica sem e avisa."""
    try:
        return fazer(colab)
    except Exception as e:
        if colab and "collab" in str(e).lower():
            R.log(f"  Instagram recusou os colaboradores ({e}); publicando sem collab.")
            return fazer(())
        raise


def rodar(token, pagina, ig, estado):
    agora = R.agora_sp()
    hoje = agora.strftime("%Y-%m-%d")
    feitos = set(estado.get("campanha_feitos", []))
    if not os.path.isdir(PASTA):
        return
    for nome in sorted(os.listdir(PASTA)):
        dia = os.path.join(PASTA, nome, hoje)
        plano_arq = os.path.join(dia, "plano.json")
        if not os.path.exists(plano_arq):
            continue
        plano = json.load(open(plano_arq, encoding="utf-8"))
        colab = plano.get("colaboradores", [])
        url_base = f"{RAW}/{nome}/{hoje}"

        def na_hora(h):
            return (agora.hour, agora.minute) >= _hora(h)

        # stories
        for i, s in enumerate(plano.get("stories", [])):
            chave = f"{nome}/{hoje}/story{i}"
            if chave in feitos or not na_hora(s["hora"]):
                continue
            try:
                R.publicar_story(f"{url_base}/{s['arquivo']}", token, ig)
                feitos.add(chave)
                R.log(f"CAMPANHA {nome}: story {s['arquivo']} publicado")
            except Exception as e:
                R.log(f"CAMPANHA {nome}: erro no story {s['arquivo']}: {e}")
            break  # um story de campanha por rodada

        # carrossel (Facebook + Instagram com collab)
        c = plano.get("carrossel")
        chave = f"{nome}/{hoje}/carrossel"
        if c and chave not in feitos and na_hora(c["hora"]):
            try:
                imgs = [Image.open(os.path.join(dia, a)).convert("RGB") for a in c["imagens"]]
                fb, enderecos = R.publicar_facebook(imgs, c["legenda"], c.get("link", ""), token, pagina)

                def fazer(cb):
                    filhos = [R.meta("POST", f"{ig}/media", token, {"image_url": u, "is_carousel_item": "true"})["id"]
                              for u in enderecos]
                    for f in filhos:
                        R.esperar_container(f, token)
                    dados = {"media_type": "CAROUSEL", "children": ",".join(filhos), "caption": c["legenda"]}
                    if cb:
                        dados["collaborators"] = json.dumps(list(cb))
                    pai = R.meta("POST", f"{ig}/media", token, dados)["id"]
                    R.esperar_container(pai, token)
                    return R.meta("POST", f"{ig}/media_publish", token, {"creation_id": pai})["id"]

                midia = _ig_com_colab(fazer, colab)
                feitos.add(chave)
                R.log(f"CAMPANHA {nome}: carrossel publicado (IG {midia}, FB {fb})")
            except Exception as e:
                R.log(f"CAMPANHA {nome}: erro no carrossel: {e}")

        # Reels (Instagram com collab + Facebook)
        r = plano.get("reels")
        chave = f"{nome}/{hoje}/reels"
        if r and chave not in feitos and na_hora(r["hora"]):
            try:
                import video
                arq = deposito.arquivo(f"campanhas/{nome}/{hoje}/{r['arquivo']}")
                midia, link = _ig_com_colab(lambda cb: video.publicar_instagram(arq, r["legenda"], token, ig, cb), colab)
                try:
                    video.publicar_facebook(arq, r["legenda"], token, pagina)
                except Exception as e:
                    R.log(f"CAMPANHA {nome}: Reels no Facebook falhou: {e}")
                feitos.add(chave)
                R.log(f"CAMPANHA {nome}: Reels publicado {link}")
            except Exception as e:
                R.log(f"CAMPANHA {nome}: erro no Reels: {e}")

        # YouTube (Short)
        y = plano.get("youtube")
        chave = f"{nome}/{hoje}/youtube"
        if y and chave not in feitos and na_hora(y["hora"]):
            try:
                import youtube
                if youtube.configurado():
                    vid, priv = youtube.enviar_video(deposito.arquivo(f"campanhas/{nome}/{hoje}/{y['arquivo']}"), y["titulo"],
                                                     y["descricao"] + "\n\n" + youtube.bloco_links(), y.get("tags", []))
                    if y.get("playlist"):
                        try:
                            youtube.adicionar_na_playlist(vid, y["playlist"])
                        except Exception as e:
                            R.log(f"CAMPANHA {nome}: playlist {y['playlist']}: {e}")
                    feitos.add(chave)
                    R.log(f"CAMPANHA {nome}: Short no YouTube https://youtu.be/{vid} ({priv})")
            except Exception as e:
                R.log(f"CAMPANHA {nome}: erro no YouTube: {e}")
    estado["campanha_feitos"] = sorted(feitos)[-300:]
