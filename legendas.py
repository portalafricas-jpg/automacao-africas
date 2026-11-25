# Legenda palavra por palavra (25/11/2026)
# Transcreve a fala com o Whisper (modelo aberto, roda no servidor do GitHub, grátis)
# e devolve cada palavra com o segundo em que começa e termina.
import json
import os
import sys

NOMES_DA_CASA = {  # correções fixas de nomes que a transcrição costuma errar
    "Busa": "Buza", "Busa,": "Buza,", "Busa.": "Buza.",
}


def audio_16k(caminho):
    """Extrai o áudio com o FFmpeg (16 kHz, mono), do jeito que o Whisper espera."""
    import subprocess
    import numpy as np
    bruto = subprocess.run(["ffmpeg", "-v", "error", "-i", caminho, "-f", "s16le", "-ac", "1", "-ar", "16000", "-"],
                           capture_output=True, check=True).stdout
    return np.frombuffer(bruto, np.int16).astype(np.float32) / 32768.0


def transcrever(caminho, modelo="medium"):
    from faster_whisper import WhisperModel
    m = WhisperModel(modelo, device="cpu", compute_type="int8")
    trechos, _ = m.transcribe(audio_16k(caminho), language="pt", word_timestamps=True, vad_filter=True)
    palavras = []
    for t in trechos:
        for w in t.words:
            texto = w.word.strip()
            texto = NOMES_DA_CASA.get(texto, texto)
            if texto:
                palavras.append({"inicio": round(w.start, 2), "fim": round(w.end, 2), "palavra": texto})
    return palavras


if __name__ == "__main__":
    entrada, saida = sys.argv[1], sys.argv[2]
    p = transcrever(entrada)
    os.makedirs(os.path.dirname(saida), exist_ok=True)
    json.dump(p, open(saida, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(" ".join(x["palavra"] for x in p))
