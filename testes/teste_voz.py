# Teste de vozes gratuitas (27/11/2026): mesmo texto em vozes diferentes, para Washington escolher.
# Motor: VoxCPM2 (licença Apache-2.0, um dos motores do VoiceStudio). Só gera áudio; não publica nada.
import sys, traceback
import soundfile as sf

TEXTO = ("As escolas de samba do Grupo Especial do Rio de Janeiro apresentam minidesfiles na Cidade do Samba, "
         "na Zona Portuária. A entrada é solidária: basta levar um quilo de alimento não perecível. "
         "É a festa do samba, patrimônio da cultura negra brasileira, aberta para todo mundo.")
VOZES = {
    "voz1_masculina_locutor": "Homem brasileiro adulto, voz grave e calorosa de locutor de rádio, sotaque do Brasil, ritmo firme",
    "voz2_feminina_jornalista": "Mulher brasileira adulta, voz clara e confiante de apresentadora de telejornal, sotaque do Brasil",
}

from voxcpm import VoxCPM
modelo = VoxCPM.from_pretrained("openbmb/VoxCPM2", load_denoiser=False)
taxa = getattr(getattr(modelo, "tts_model", None), "sample_rate", 48000)
ok = 0
for nome, descricao in VOZES.items():
    try:
        wav = modelo.generate(text=f"({descricao}){TEXTO}", cfg_value=2.0, inference_timesteps=10)
        sf.write(f"saida/{nome}.wav", wav, taxa)
        print("gerado:", nome); ok += 1
    except Exception:
        traceback.print_exc()
sys.exit(0 if ok else 1)
