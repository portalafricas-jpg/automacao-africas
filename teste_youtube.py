"""Teste: monta um Radar com as matérias do dia e envia SÓ ao YouTube (privado) + playlist Radar.
Não publica no Instagram nem no Facebook e não mexe no estado do robô."""
import os, tempfile
import redes as R
import video

posts = R.ler_json(R.ARQ_POSTS, [])
saida = os.path.join(tempfile.mkdtemp(), "teste.mp4")
escolhidas, dur = video.fazer_video(posts, False, R.agora_sp(), saida, turno="meio")
if not escolhidas:
    raise SystemExit("Sem matérias suficientes para o teste.")
titulo, descricao, tags = video.texto_youtube(escolhidas, False, R.agora_sp(), "meio")
print("TÍTULO:", titulo, f"({len(titulo)} caracteres)")
vid = video.publicar_no_youtube(saida, escolhidas, False, R.agora_sp(), "teste", {}, "teste")
print("RESULTADO:", f"https://youtu.be/{vid}" if vid else "falhou (ver linhas acima)")
