# Vigia de gastos do Áfricas Play (aprovado por Washington em 28/11/2026).
# Todo dia útil às 9h confere 3 coisas: espaço do repositório, gasto estimado do Claude (API)
# e saúde dos robôs (minutos e falhas). Abre um aviso (issue), que chega por e-mail:
#   - toda segunda-feira: relatório semanal com o semáforo;
#   - qualquer dia útil: aviso VERMELHO na hora, se algo passar do limite.
# Não usa o Claude (custo zero): só lê dados do próprio GitHub.
import io
import json
import os
import re
import zipfile
from datetime import datetime, timedelta, timezone

import requests

REPO = os.environ.get("GITHUB_REPOSITORY", "portalafricas-jpg/automacao-africas")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
FORCAR = os.environ.get("FORCAR_RELATORIO") == "1"
ARQ = "estado/gastos.json"
FUSO = timezone(timedelta(hours=-3))
API = f"https://api.github.com/repos/{REPO}"
H = {"Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json"}

# Preço do Claude Haiku 5.5 (US$ por milhão de tokens, pedidos de até 100 mil tokens)
PRECO = {"novos": 0.10, "cache": 0.01, "guardados": 0.125, "escritos": 0.50}
TETO_DIA = 10.0  # teto de gasto configurado na Anthropic

# Limites do semáforo
REPO_AMARELO, REPO_VERMELHO = 500, 900        # MB (o GitHub recomenda ficar abaixo de 1 GB)
DIAS_AMARELO, DIAS_VERMELHO = 60, 21          # dias até chegar a 1 GB no ritmo atual
API_AMARELO, API_VERMELHO = 2.0, 5.0          # US$ por dia
FALHA_AMARELO, FALHA_VERMELHO = 0.10, 0.25    # fração de rodadas com erro

ROBOS_COM_CLAUDE = ["robo.yml"]  # robôs que escrevem o uso do Claude no registro


def gh(caminho, **kw):
    r = requests.get(f"{API}{caminho}", headers=H, timeout=60, **kw)
    r.raise_for_status()
    return r


def cor(valor, amarelo, vermelho, maior_e_pior=True):
    if maior_e_pior:
        return "🔴" if valor >= vermelho else "🟡" if valor >= amarelo else "🟢"
    return "🔴" if valor <= vermelho else "🟡" if valor <= amarelo else "🟢"


def rodadas_24h(arquivo):
    desde = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
    r = gh(f"/actions/workflows/{arquivo}/runs", params={"per_page": 1, "created": f">={desde}"})
    return r.json().get("total_count", 0)


def uso_claude(arquivo, amostra=12):
    """Média de custo por rodada, lida do registro das últimas rodadas."""
    runs = gh(f"/actions/workflows/{arquivo}/runs",
              params={"per_page": amostra, "status": "success"}).json().get("workflow_runs", [])
    custos = []
    padrao = re.compile(r"Uso do Claude nesta rodada: (\d+) tokens novos, (\d+) lidos do cache, "
                        r"(\d+) guardados no cache, (\d+) escritos")
    for run in runs:
        try:
            z = zipfile.ZipFile(io.BytesIO(gh(f"/actions/runs/{run['id']}/logs").content))
            texto = "\n".join(z.read(n).decode("utf-8", "ignore") for n in z.namelist())
        except Exception:
            continue
        m = padrao.search(texto)
        if not m:
            continue
        novos, cache, guard, escr = map(int, m.groups())
        custos.append((novos * PRECO["novos"] + cache * PRECO["cache"]
                       + guard * PRECO["guardados"] + escr * PRECO["escritos"]) / 1_000_000)
    return sum(custos) / len(custos) if custos else None


def saude_robos():
    """Por robô: rodadas e erros em 7 dias, e quantas das 12 últimas rodadas falharam."""
    desde = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
    contagem = {}
    for wf in gh("/actions/workflows", params={"per_page": 100}).json().get("workflows", []):
        if wf.get("state") != "active":
            continue
        base = f"/actions/workflows/{wf['id']}/runs"
        total = gh(base, params={"per_page": 1, "created": f">={desde}"}).json().get("total_count", 0)
        if not total:
            continue
        erros = gh(base, params={"per_page": 1, "created": f">={desde}", "status": "failure"}).json().get("total_count", 0)
        ultimas = gh(base, params={"per_page": 12, "status": "completed"}).json().get("workflow_runs", [])
        recentes = sum(r.get("conclusion") == "failure" for r in ultimas)
        contagem[wf["name"]] = {"total": total, "erro": erros, "ultimas": len(ultimas), "recentes": recentes}
    return contagem


def main():
    hoje = datetime.now(FUSO)
    info = gh("").json()
    tamanho = round(info["size"] / 1024, 1)  # MB
    publico = not info.get("private")

    # Histórico do tamanho, para calcular o ritmo de crescimento
    try:
        hist = json.load(open(ARQ, encoding="utf-8"))
    except Exception:
        hist = []
    hist = [h for h in hist if h["data"] != hoje.strftime("%Y-%m-%d")]
    hist.append({"data": hoje.strftime("%Y-%m-%d"), "repo_mb": tamanho})
    hist = hist[-90:]
    base = next((h for h in hist if (hoje.date() - datetime.strptime(h["data"], "%Y-%m-%d").date()).days <= 7), hist[0])
    dias_base = (hoje.date() - datetime.strptime(base["data"], "%Y-%m-%d").date()).days
    if dias_base >= 1:
        ritmo = (tamanho - base["repo_mb"]) / dias_base
    else:
        criado = datetime.strptime(info["created_at"][:10], "%Y-%m-%d").date()
        ritmo = tamanho / max(1, (hoje.date() - criado).days)
    dias_1gb = (1024 - tamanho) / ritmo if ritmo > 0 else 9999

    # Claude (API)
    linhas_api, gasto_dia = [], 0.0
    for arq in ROBOS_COM_CLAUDE:
        media = uso_claude(arq)
        n = rodadas_24h(arq)
        if media is None:
            linhas_api.append(f"- {arq}: {n} rodadas em 24h, uso não encontrado no registro")
            continue
        gasto_dia += media * n
        linhas_api.append(f"- {arq}: {n} rodadas em 24h × US$ {media:.4f} = US$ {media * n:.2f}/dia")
    for arq in ["redes.yml", "comentarios.yml"]:
        linhas_api.append(f"- {arq}: {rodadas_24h(arq)} rodadas em 24h (ainda não registra o uso do Claude; gasto pequeno)")

    # Robôs
    saude = saude_robos()
    total_runs = sum(c["total"] for c in saude.values())
    # O semáforo olha as 12 últimas rodadas dos robôs automáticos (20+ rodadas na semana);
    # testes rodados à mão não contam, e problema já resolvido não fica vermelho.
    pior, pior_nome = 0, "-"
    for nome, c in saude.items():
        if c["total"] >= 20 and c["ultimas"] >= 4 and c["recentes"] / c["ultimas"] > pior:
            pior, pior_nome = c["recentes"] / c["ultimas"], nome

    c_repo = max(cor(tamanho, REPO_AMARELO, REPO_VERMELHO), cor(dias_1gb, DIAS_AMARELO, DIAS_VERMELHO, False),
                 key="🟢🟡🔴".index)
    c_api = cor(gasto_dia, API_AMARELO, API_VERMELHO)
    c_robos = cor(pior, FALHA_AMARELO, FALHA_VERMELHO)
    c_min = "🟢" if publico else "🟡"
    vermelho = "🔴" in (c_repo, c_api, c_robos)

    hist[-1].update({"api_dia_usd": round(gasto_dia, 2), "rodadas_7d": total_runs})
    os.makedirs("estado", exist_ok=True)
    json.dump(hist, open(ARQ, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    segunda = hoje.weekday() == 0
    if not (segunda or vermelho or FORCAR):
        print("Tudo dentro do limite; hoje não é dia de relatório.")
        return

    tabela_robos = "\n".join(
        f"| {nome} | {c['total']} | {c['erro']} | {c['recentes']} |"
        for nome, c in sorted(saude.items(), key=lambda x: -x[1]["total"]))
    corpo = f"""## Semáforo de gastos — {hoje.strftime('%d/%m/%Y')}

{c_repo} **Espaço do repositório:** {tamanho:.0f} MB (crescendo {ritmo:.1f} MB/dia). \
No ritmo atual, chega a 1 GB em {dias_1gb:.0f} dias.

{c_api} **Claude (API) dos robôs:** cerca de US$ {gasto_dia:.2f} por dia \
(≈ US$ {gasto_dia * 30:.0f} por mês). Teto configurado: US$ {TETO_DIA:.0f} por dia.
{chr(10).join(linhas_api)}

{c_min} **Minutos do GitHub:** repositório {'público, minutos grátis' if publico else 'PRIVADO, minutos contam no limite'}. \
{total_runs} rodadas nos últimos 7 dias.

{c_robos} **Saúde dos robôs:** pior taxa de erro dos robôs automáticos nas 12 últimas rodadas: {pior * 100:.0f}% ({pior_nome}).

| Robô | Rodadas (7 dias) | Com erro (7 dias) | Erro nas 12 últimas |
|---|---|---|---|
{tabela_robos}

Limites: espaço amarelo a partir de {REPO_AMARELO} MB e vermelho a partir de {REPO_VERMELHO} MB \
(ou menos de {DIAS_VERMELHO} dias até 1 GB); Claude amarelo a partir de US$ {API_AMARELO:.0f}/dia \
e vermelho a partir de US$ {API_VERMELHO:.0f}/dia; robôs vermelhos com mais de {FALHA_VERMELHO * 100:.0f}% de erro.
O gasto do Claude é estimativa pelo registro dos robôs; o valor exato fica no painel da Anthropic.
"""
    titulo = ("🔴 ALERTA de gastos" if vermelho else "Relatório semanal de gastos") + f" — {hoje.strftime('%d/%m')}"
    if not TOKEN:
        print(titulo, corpo, sep="\n")
        return
    post = {"Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json"}
    for i in gh("/issues", params={"state": "open", "labels": "gastos", "per_page": 50}).json():
        requests.patch(f"{API}/issues/{i['number']}", headers=post, json={"state": "closed"}, timeout=30)
    r = requests.post(f"{API}/issues", headers=post, timeout=30,
                      json={"title": titulo, "body": corpo, "labels": ["gastos"], "assignees": ["portalafricas-jpg"]})
    r.raise_for_status()
    print("Aviso aberto:", r.json().get("html_url"))


if __name__ == "__main__":
    main()
