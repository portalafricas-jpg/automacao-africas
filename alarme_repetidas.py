# Alarme diário do protocolo anti-repetição (27/11/2026).
# Confere as matérias das últimas 24 horas contra as dos 3 dias anteriores.
# Se alguma repetida escapou, abre um aviso no GitHub (chega por e-mail). Se não, não manda nada.
import json
import os
from datetime import datetime, timedelta, timezone

import requests

import mesmo_fato

PASTA = os.path.dirname(os.path.abspath(__file__))
REPO = os.environ.get("GITHUB_REPOSITORY", "portalafricas-jpg/automacao-africas")
GH_TOKEN = os.environ.get("GITHUB_TOKEN", "")


def main():
    with open(os.path.join(PASTA, "estado", "publicadas.json"), encoding="utf-8") as f:
        publicadas = json.load(f)
    agora = datetime.now(timezone.utc)
    ontem, tres_dias = (agora - timedelta(hours=24)).isoformat(), (agora - timedelta(days=4)).isoformat()
    achados = []
    for i, nova in enumerate(publicadas):
        if nova.get("criado_em", "") < ontem:
            continue
        anteriores = [m for m in publicadas[:i] if m.get("criado_em", "") >= tres_dias]
        rep, antiga = mesmo_fato.repetida(nova, anteriores)
        if rep:
            achados.append((antiga, nova))
    if not achados:
        print("Nenhuma repetida nas últimas 24 horas.")
        return
    linhas = [f"@portalafricas-jpg", "", f"O alarme achou {len(achados)} repetida(s) que escaparam:", ""]
    for antiga, nova in achados:
        linhas += [f"- **{antiga.get('titulo')}** ({antiga.get('veiculo', '')})",
                   f"  repetida por **{nova.get('titulo')}** ({nova.get('veiculo', '')})", ""]
    linhas.append("Abra uma conversa com o Claude para ele propor a correção.")
    corpo = "\n".join(linhas)
    print(corpo)
    if GH_TOKEN:
        r = requests.post(f"https://api.github.com/repos/{REPO}/issues",
                          headers={"Authorization": f"Bearer {GH_TOKEN}", "Accept": "application/vnd.github+json"},
                          json={"title": f"Alarme: {len(achados)} matéria(s) repetida(s) no site",
                                "body": corpo, "labels": ["alarme-repetidas"]}, timeout=30)
        print("Aviso:", r.status_code)


if __name__ == "__main__":
    main()
