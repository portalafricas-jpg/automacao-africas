# Teste curto da voz padrão: 3 trechos do roteiro na mesma voz, copiada do arquivo modelo (vozes-padrao/).
# Se o motor não tiver como copiar a voz, o robô PARA com erro, em vez de gerar vozes aleatórias.
# Uso: python calendario_voz_teste.py masculina calendario/2026-12/06-joao-candido saida

import inspect
import json
import os
import sys

import soundfile as sf
from voxcpm import VoxCPM

voz, pasta, saida = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(saida, exist_ok=True)
TEXTO_MODELO = ("As escolas de samba do Grupo Especial do Rio de Janeiro apresentam minidesfiles na Cidade do Samba, "
                "na Zona Portuária. A entrada é solidária: basta levar um quilo de alimento não perecível. "
                "É a festa do samba, patrimônio da cultura negra brasileira, aberta para todo mundo.")

modelo_wav = os.path.abspath(f"vozes-padrao/{voz}.wav")

modelo = VoxCPM.from_pretrained("openbmb/VoxCPM2", load_denoiser=False)
taxa = getattr(getattr(modelo, "tts_model", None), "sample_rate", 48000)

# Descobre no código do próprio motor como ele recebe a voz de referência
codigo = ""
for alvo in (modelo.generate, getattr(modelo, "_generate", None), getattr(getattr(modelo, "tts_model", None), "generate", None)):
    if alvo:
        try:
            codigo += inspect.getsource(alvo)
        except Exception:
            pass
achados = [p for p in ("prompt_wav_path", "prompt_text", "reference_wav_path") if p in codigo]
print("o motor aceita:", achados)
for linha in codigo.splitlines():
    if "def " in linha and "generate" in linha:
        print("assinatura:", linha.strip())

if "prompt_wav_path" in achados and "prompt_text" in achados:
    referencia = {"prompt_wav_path": modelo_wav, "prompt_text": TEXTO_MODELO}
elif "reference_wav_path" in achados:
    referencia = {"reference_wav_path": modelo_wav}
else:
    sys.exit("PARADO: o motor não tem como copiar a voz do modelo. Nada foi gerado.")
if "reference_wav_path" in achados:
    referencia["reference_wav_path"] = modelo_wav
print("usando:", list(referencia))

roteiro = json.load(open(os.path.join(pasta, "roteiro.json"), encoding="utf-8"))
blocos = {b["id"]: " ".join(fr["fala"] for fr in b["frases"]) for b in roteiro["blocos"]}
for bid in ("b1", "b4", "b6"):
    wav = modelo.generate(text=blocos[bid], cfg_value=2.0, inference_timesteps=10, **referencia)
    sf.write(os.path.join(saida, f"{voz}_{bid}.wav"), wav, taxa)
    print("gerado:", voz, bid)
