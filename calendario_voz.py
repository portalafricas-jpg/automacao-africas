# Calendário Afro: grava a narração do roteiro aprovado com a voz gratuita VoxCPM2 (Apache-2.0).
# Uma faixa por frase (para a legenda e os cortes caírem nas pausas).
# Para a voz não mudar de uma frase para outra, a primeira frase é gerada pela descrição
# e serve de referência para todas as outras. Só gera áudio; não publica nada.
# Uso: python calendario_voz.py calendario/2026-12/06-joao-candido saida_voz

import inspect
import json
import os
import sys
import traceback

import soundfile as sf
from voxcpm import VoxCPM

pasta, saida = sys.argv[1], sys.argv[2]
os.makedirs(saida, exist_ok=True)
with open(os.path.join(pasta, "roteiro.json"), encoding="utf-8") as f:
    roteiro = json.load(f)

modelo = VoxCPM.from_pretrained("openbmb/VoxCPM2", load_denoiser=False)
taxa = getattr(getattr(modelo, "tts_model", None), "sample_rate", 48000)
params = inspect.signature(modelo.generate).parameters
print("parâmetros do motor:", list(params))

frases = [(b["id"], i, fr["fala"]) for b in roteiro["blocos"] for i, fr in enumerate(b["frases"])]

# 1) frase-âncora: define a voz pela descrição aprovada
ancora_txt = frases[0][2]
wav = modelo.generate(text=f"({roteiro['voz']}){ancora_txt}", cfg_value=2.0, inference_timesteps=10)
ancora = os.path.join(saida, f"{frases[0][0]}_{frases[0][1]}.wav")
sf.write(ancora, wav, taxa)
print("âncora gerada")

# 2) nome do parâmetro de referência, conforme a versão do motor
ref_wav = next((p for p in ("prompt_wav_path", "reference_wav_path", "prompt_wav", "ref_wav_path") if p in params), None)
ref_txt = next((p for p in ("prompt_text", "reference_text", "ref_text") if p in params), None)
print("referência de voz:", ref_wav, ref_txt)

falhas = 0
for bid, i, texto in frases[1:]:
    nome = os.path.join(saida, f"{bid}_{i}.wav")
    try:
        if ref_wav and ref_txt:
            wav = modelo.generate(text=texto, **{ref_wav: ancora, ref_txt: ancora_txt},
                                  cfg_value=2.0, inference_timesteps=10)
        else:
            wav = modelo.generate(text=f"({roteiro['voz']}){texto}", cfg_value=2.0, inference_timesteps=10)
        sf.write(nome, wav, taxa)
        print("gerado:", nome)
    except Exception:
        traceback.print_exc()
        falhas += 1
sys.exit(1 if falhas else 0)
