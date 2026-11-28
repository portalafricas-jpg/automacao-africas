"""Trava da campanha da Expo África Brasil (28/11/2026).

Roda em toda rodada do robô das redes, mas confere só uma vez por dia, a partir das 9h.
Até 2/12, confere se o dia tem: matéria da Expo agendada (materias/AAAA-MM-DD-*.json),
pasta da campanha (campanhas/expo/AAAA-MM-DD/plano.json) com stories, carrossel, Reels e Short,
e vídeo com áudio. Se faltar algo, manda e-mail para portalafricas@gmail.com na hora.
"""
import glob, json, os, subprocess
from datetime import datetime, timezone, timedelta

PASTA = os.path.dirname(os.path.abspath(__file__))
SP = timezone(timedelta(hours=-3))
ARQ = os.path.join(PASTA, "estado", "trava-expo.json")
ULTIMO_DIA = "2026-12-02"
PARA = "portalafricas@gmail.com"


def tem_audio(video):
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries",
                              "stream=codec_type", "-of", "csv=p=0", video], capture_output=True, text=True).stdout
        return "audio" in out
    except Exception:
        return False  # sem ffprobe não dá para garantir o áudio: avisa


def faltas(hoje):
    f = []
    if not glob.glob(os.path.join(PASTA, "materias", f"{hoje}-*.json")):
        f.append("Matéria da Expo do dia (pasta materias/)")
    dia = os.path.join(PASTA, "campanhas", "expo", hoje)
    try:
        plano = json.load(open(os.path.join(dia, "plano.json"), encoding="utf-8"))
    except Exception:
        return f + ["Pasta da campanha do dia (campanhas/expo/%s/plano.json)" % hoje]
    if len(plano.get("stories", [])) < 5:
        f.append("Stories do dia (precisa de 5)")
    for k, nome in (("carrossel", "Carrossel das 20h"), ("reels", "Reels das 21h"), ("youtube", "Short do YouTube")):
        if not plano.get(k):
            f.append(nome)
    r = plano.get("reels")
    if r:
        # O vídeo fica no galho "midia" (o .gitignore barra .mp4 no main): buscar por lá
        rel = f"campanhas/expo/{hoje}/{r.get('arquivo', 'reels.mp4')}"
        try:
            import midia
            video = midia.arquivo(rel)
        except Exception:
            video = None
        if not video or not os.path.exists(video) or os.path.getsize(video) == 0:
            f.append(f"O vídeo do Reels não está no depósito de mídia ({rel})")
        elif not tem_audio(video):
            f.append("O vídeo do Reels está sem áudio")
    return f


def main():
    agora = datetime.now(SP)
    hoje = agora.strftime("%Y-%m-%d")
    if hoje > ULTIMO_DIA or agora.hour < 9:
        return
    try:
        estado = json.load(open(ARQ, encoding="utf-8"))
    except Exception:
        estado = {}
    if estado.get("conferido") == hoje:
        return
    f = faltas(hoje)
    estado["conferido"] = hoje
    estado["faltas"] = f
    if f:
        import envio_assessorias as E
        texto = ("Alerta da campanha da Expo África Brasil de %s.\n\nFalta:\n- %s\n\n"
                 "Abra a conversa da Expo com o Claude e peça para repor agora." % (hoje, "\n- ".join(f)))
        smtp = E.conectar()
        E.enviar(smtp, PARA, f"⚠️ Expo: falta conteúdo hoje ({hoje})", texto)
        smtp.quit()
        estado["email"] = agora.isoformat()
    json.dump(estado, open(ARQ, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("Trava da Expo:", f or "tudo programado")


if __name__ == "__main__":
    main()
