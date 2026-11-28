# Opções de voz para o Calendário Afro: cada opção gera UMA amostra pela descrição.
# A amostra escolhida por Washington vira o arquivo-modelo fixo (vozes-padrao/), e a partir daí a voz é copiada.
# Uso: python calendario_voz_opcoes.py ID saida

import os
import sys

import soundfile as sf
from voxcpm import VoxCPM

OPCOES = {
    "1_grave_fm": "Homem brasileiro adulto, voz muito grave e aveludada de locutor de rádio FM, sotaque do Brasil, fala pausada e envolvente",
    "2_historiador": "Homem brasileiro maduro, cerca de sessenta anos, voz grave e serena de historiador narrando um documentário, sotaque do Brasil, ritmo calmo",
    "3_feminina_documentario": "Mulher brasileira adulta, voz grave e calorosa de narradora de documentário, sotaque do Brasil, ritmo pausado e firme",
    "4_feminina_contadora": "Mulher brasileira madura, voz profunda e acolhedora de contadora de histórias, sotaque do Brasil, ritmo calmo",
}
TEXTO = ("Duzentas e cinquenta chibatadas. Esse foi o castigo que acendeu uma das maiores revoltas da história do Brasil. "
         "À frente dela estava um marinheiro negro: João Cândido. "
         "Fora da Marinha, sobreviveu vendendo peixe no Rio de Janeiro, sem o reconhecimento que merecia.")

op, saida = sys.argv[1], sys.argv[2]
os.makedirs(saida, exist_ok=True)
modelo = VoxCPM.from_pretrained("openbmb/VoxCPM2", load_denoiser=False)
taxa = getattr(getattr(modelo, "tts_model", None), "sample_rate", 48000)
wav = modelo.generate(text=f"({OPCOES[op]}){TEXTO}", cfg_value=2.0, inference_timesteps=10)
sf.write(os.path.join(saida, f"{op}.wav"), wav, taxa)
print("gerado:", op)
