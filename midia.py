"""Depósito de mídia do Áfricas Play (aprovado por Washington em 28/11/2026).

Vídeos (.mp4) NÃO vão para o galho principal (main), porque o GitHub guarda o histórico de tudo
e o repositório engorda para sempre. Eles ficam no galho separado "midia", que o robô
limpa-midia.yml esvazia: o que tem mais de 7 dias é apagado de verdade.

- Guardar (numa conversa ou num robô):  bash guardar_midia.sh "mensagem" campanhas/expo/2026-12-03/reels.mp4
- Ler (nos robôs):  midia.arquivo("campanhas/expo/2026-12-03/reels.mp4") devolve o caminho local,
  baixando do galho "midia" se o arquivo não estiver na pasta.
"""
import os
import subprocess
import urllib.request

PASTA = os.path.dirname(os.path.abspath(__file__))
RAW_MIDIA = "https://raw.githubusercontent.com/portalafricas-jpg/automacao-africas/midia"
CACHE = os.path.join(PASTA, "cache", "midia")


def arquivo(rel):
    rel = rel.replace(os.sep, "/").lstrip("/")
    local = os.path.join(PASTA, rel)
    if os.path.exists(local):
        return local
    destino = os.path.join(CACHE, rel)
    if not os.path.exists(destino):
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        tmp = destino + ".baixando"
        try:
            with urllib.request.urlopen(f"{RAW_MIDIA}/{urllib.request.quote(rel)}", timeout=300) as r, open(tmp, "wb") as f:
                while True:
                    bloco = r.read(1 << 20)
                    if not bloco:
                        break
                    f.write(bloco)
        except Exception:
            # Reserva: buscar pelo próprio git (funciona onde o endereço direto estiver bloqueado)
            subprocess.run(["git", "-C", PASTA, "fetch", "-q", "--depth", "1", "origin", "midia"], check=True)
            with open(tmp, "wb") as f:
                subprocess.run(["git", "-C", PASTA, "show", f"FETCH_HEAD:{rel}"], stdout=f, check=True)
        os.replace(tmp, destino)
    return destino
