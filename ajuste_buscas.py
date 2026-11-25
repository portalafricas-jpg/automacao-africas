# Ajuste semanal das buscas (aprovado em 25/11/2026), roda toda segunda às 9h.
# Olha os relatórios do robô e decide a frequência de cada busca:
#   4 ou mais matérias publicadas em 14 dias -> busca todo dia
#   1 a 3 em 14 dias (ou alguma em 30 dias)  -> busca uma vez por semana
#   nenhuma em 30 dias                        -> lista de espera (sai das buscas)
# O resultado fica em estado/buscas-ajuste.json (o robô lê sozinho) e um resumo vai por e-mail (aviso do GitHub).
import glob
import json
import os
from collections import Counter
from datetime import datetime, timedelta, timezone

import requests

import robo as R

PROTEGIDAS = ("expo",)  # buscas de campanha não entram no ajuste


def main():
    hoje = datetime.now(R.FUSO_SP).date()
    arquivos = sorted(glob.glob(os.path.join(R.PASTA_RELATORIOS, "20*.json")))
    dias = {os.path.basename(a)[:10]: a for a in arquivos}
    primeiro_dia = min(dias) if dias else hoje.isoformat()
    tem_30_dias = primeiro_dia <= (hoje - timedelta(days=30)).isoformat()
    if primeiro_dia > (hoje - timedelta(days=14)).isoformat():
        print(f"Só há relatórios desde {primeiro_dia}: o ajuste começa quando houver 14 dias de histórico.")
        return
    pub14, pub30, anal14 = Counter(), Counter(), Counter()
    for dia, arq in dias.items():
        idade = (hoje - datetime.fromisoformat(dia).date()).days
        if idade > 30:
            continue
        for e in R.ler_json(arq, []):
            fonte = e.get("fonte", "")
            if not fonte.startswith("Busca"):
                continue
            if e.get("destino") == "publicada":
                pub30[fonte] += 1
                if idade <= 14:
                    pub14[fonte] += 1
            if idade <= 14:
                anal14[fonte] += 1
    fontes = R.juntar_buscas(R.ler_json(R.ARQ_FONTES, []))
    ajuste_antigo = R.ler_json(R.ARQ_AJUSTE_BUSCAS, {})
    ajuste, mudancas = {}, []
    for f in R.ler_json(R.ARQ_FONTES, []) + R.ler_json(R.ARQ_BUSCAS_AUTO, []):
        if f.get("tipo") != "busca" or any(p in f["nome"].lower() for p in PROTEGIDAS):
            continue
        nome = f["nome"]
        criada = f.get("auto") or f.get("criada") or ""
        nova_demais = criada and criada > (hoje - timedelta(days=14)).isoformat()
        if nova_demais:
            continue  # busca criada há menos de 14 dias: espera juntar dados
        if pub14[nome] >= 4:
            regra = "diaria"
        elif pub14[nome] >= 1 or pub30[nome] >= 1:
            regra = sum(map(ord, nome)) % 7
        elif tem_30_dias:
            regra = "espera"
        else:
            regra = sum(map(ord, nome)) % 7  # ainda sem 30 dias de histórico: no máximo vira semanal
        ajuste[nome] = regra
        if ajuste_antigo.get(nome, "diaria" if "dia_semana" not in f else f["dia_semana"]) != regra:
            mudancas.append((nome, regra, pub14[nome], anal14[nome]))
    R.salvar_json(R.ARQ_AJUSTE_BUSCAS, ajuste)
    nomes_dia = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
    txt = lambda r: "todo dia" if r == "diaria" else ("lista de espera" if r == "espera" else f"semanal ({nomes_dia[r]})")
    linhas = [f"- {n}: **{txt(r)}** ({p} publicadas e {a} analisadas em 14 dias)" for n, r, p, a in mudancas]
    auto = R.ler_json(R.ARQ_BUSCAS_AUTO, [])
    novos = [b["nome"] for b in auto if b.get("auto", "") >= (hoje - timedelta(days=7)).isoformat()]
    corpo = (f"Ajuste semanal das buscas ({hoje.strftime('%d/%m/%Y')}).\n\n"
             f"**Mudanças de frequência ({len(mudancas)}):**\n" + ("\n".join(linhas) or "- nenhuma") +
             f"\n\n**Nomes novos que entraram sozinhos na semana ({len(novos)}):**\n" +
             ("\n".join(f"- {n}" for n in novos) or "- nenhum") +
             f"\n\nTotal de buscas: {sum(1 for f in fontes if f.get('tipo') == 'busca')}.")
    print(corpo)
    token = os.environ.get("GITHUB_TOKEN", "")
    if token:
        repo = os.environ.get("GITHUB_REPOSITORY", "portalafricas-jpg/automacao-africas")
        requests.post(f"https://api.github.com/repos/{repo}/issues", timeout=30,
                      headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
                      json={"title": f"Ajuste semanal das buscas — {hoje.strftime('%d/%m')}", "body": corpo,
                            "labels": ["ajuste-buscas"]})


if __name__ == "__main__":
    main()
