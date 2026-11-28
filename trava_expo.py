"""Trava da campanha da Expo África Brasil (28/11/2026).

Roda em toda rodada do robô das redes. Confere o dia uma vez, a partir das 9h, e a véspera
(o dia seguinte) uma vez, a partir das 18h.
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


def avisar(dia, f, quando):
    import envio_assessorias as E
    texto = ("Alerta da campanha da Expo África Brasil de %s (%s).\n\nFalta:\n- %s\n\n"
             "Abra a conversa da Expo com o Claude e peça para repor agora." % (dia, quando, "\n- ".join(f)))
    smtp = E.conectar()
    E.enviar(smtp, PARA, f"⚠️ Expo: falta conteúdo {quando} ({dia})", texto)
    smtp.quit()


def main():
    agora = datetime.now(SP)
    hoje = agora.strftime("%Y-%m-%d")
    amanha = (agora + timedelta(days=1)).strftime("%Y-%m-%d")
    try:
        estado = json.load(open(ARQ, encoding="utf-8"))
    except Exception:
        estado = {}
    mudou = False
    # 1) O próprio dia, a partir das 9h
    if hoje <= ULTIMO_DIA and agora.hour >= 9 and estado.get("conferido") != hoje:
        f = faltas(hoje)
        estado.update(conferido=hoje, faltas=f)
        if f:
            avisar(hoje, f, "hoje")
            estado["email"] = agora.isoformat()
        print("Trava da Expo (hoje):", f or "tudo programado")
        mudou = True
    # 2) Véspera: a partir das 18h, confere o dia seguinte (aprovado por Washington em 28/11/2026)
    if amanha <= ULTIMO_DIA and agora.hour >= 18 and estado.get("vespera_conferida") != amanha:
        f = faltas(amanha)
        estado.update(vespera_conferida=amanha, vespera_faltas=f)
        if f:
            avisar(amanha, f, "amanhã")
            estado["vespera_email"] = agora.isoformat()
        print("Trava da Expo (amanhã):", f or "tudo programado")
        mudou = True
    if mudou:
        json.dump(estado, open(ARQ, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
