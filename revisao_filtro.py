"""Revisão quinzenal do filtro e das fontes pausadas (pedido de Washington em 26/11/2026).

Duas categorias:
- ETERNO: spam (cassino etc.) e fontes com "pausada": "eterna" (ex.: Black Money). Nunca voltam, nem são revistas.
- REVISÁVEL: o resto do filtro (comércio, franquias, buscas amplas) e as fontes com "pausada": "revisar"
  (ex.: O País, Angola). O robô continua lendo os títulos delas (de graça, sem o Claude) e, a cada 15 dias,
  olha os últimos 7 dias numa consulta só ao Claude para ver se algo valeria a pena.

O resultado vai para estado/relatorios/revisao-filtro-AAAA-MM-DD.md. Nada muda sozinho:
voltar uma fonte ou mexer no filtro só com o "sim" de Washington.
"""
import json
import os
from collections import defaultdict
from datetime import datetime, timedelta

PASTA = os.path.dirname(os.path.abspath(__file__))
PASTA_ESTADO = os.path.join(PASTA, "estado")
PASTA_RELATORIOS = os.path.join(PASTA_ESTADO, "relatorios")
ARQ_OBSERVACAO = os.path.join(PASTA_ESTADO, "observacao-pausadas.json")
ARQ_CONTROLE = os.path.join(PASTA_ESTADO, "revisao-filtro.json")
DIAS_ENTRE_REVISOES = 15
DIAS_OLHADOS = 7
MAX_TITULOS = 150
NOTA_VALE = 7


def _ler(caminho, padrao):
    try:
        with open(caminho, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return padrao


def _salvar(caminho, dados):
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)


def observar(fonte, itens, agora):
    """Guarda os títulos de uma fonte pausada para revisar (sem gastar nada) e mantém só 7 dias."""
    obs = _ler(ARQ_OBSERVACAO, {})
    for i in itens:
        if i.get("link") and i["link"] not in obs:
            obs[i["link"]] = {"fonte": fonte.get("nome", ""), "titulo": i.get("titulo", ""), "visto": agora.isoformat()}
    corte = (agora - timedelta(days=DIAS_OLHADOS)).isoformat()
    obs = {l: d for l, d in obs.items() if d["visto"] >= corte}
    _salvar(ARQ_OBSERVACAO, obs)


def esta_na_hora(agora):
    ultima = _ler(ARQ_CONTROLE, {}).get("ultima")
    if not ultima:
        return False  # a primeira revisão é marcada quando o filtro entra no ar (ver marcar_inicio)
    return agora - datetime.fromisoformat(ultima) >= timedelta(days=DIAS_ENTRE_REVISOES)


def marcar_inicio(agora):
    if not _ler(ARQ_CONTROLE, {}).get("ultima"):
        _salvar(ARQ_CONTROLE, {"ultima": agora.isoformat(), "obs": "início do filtro; 1ª revisão 15 dias depois"})


def _descartadas_revisaveis(agora):
    """Notícias que o filtro tirou nos últimos 7 dias, menos o spam (que é eterno)."""
    saida = []
    for d in range(DIAS_OLHADOS):
        dia = (agora - timedelta(days=d)).date().isoformat()
        for e in _ler(os.path.join(PASTA_RELATORIOS, f"{dia}.json"), []):
            det = str(e.get("detalhe", ""))
            if e.get("destino") == "descartada pelo filtro" and "spam" not in det and "alfabeto" not in det:
                saida.append({"fonte": e.get("fonte", ""), "titulo": e.get("titulo", ""), "motivo": det})
    return saida


FERRAMENTA = {
    "name": "notas_revisao",
    "description": "Dá uma nota de 0 a 10 para cada título, pela linha editorial do Áfricas.",
    "input_schema": {
        "type": "object",
        "properties": {"notas": {"type": "array", "items": {"type": "object", "properties": {
            "id": {"type": "integer"}, "nota": {"type": "integer"}, "motivo": {"type": "string"}},
            "required": ["id", "nota", "motivo"]}}},
        "required": ["notas"],
    },
}


def revisar(agora, enviar_claude, linha_editorial, log=print):
    """Faz a revisão quinzenal: uma consulta só ao Claude, com até 150 títulos."""
    obs = list(_ler(ARQ_OBSERVACAO, {}).values())
    desc = _descartadas_revisaveis(agora)
    vistos, itens = set(), []
    for origem, lista in (("fonte pausada", obs), ("filtro", desc)):
        for x in lista:
            chave = x["titulo"].strip().lower()
            if chave and chave not in vistos:
                vistos.add(chave)
                itens.append(dict(x, origem=origem))
    itens = itens[:MAX_TITULOS]
    notas = {}
    if itens:
        pedido = "Dê nota a cada título como o editor-chefe do Áfricas daria (0 a 10). Só o título, sem abrir a matéria.\n\n"
        pedido += "\n".join(f"{n}. {i['titulo']}" for n, i in enumerate(itens, start=1))
        resposta = enviar_claude("Você revisa o filtro do robô do portal Áfricas.", pedido, FERRAMENTA,
                                 max_tokens=6000, fixo=linha_editorial)
        notas = {a["id"]: a for a in resposta.get("notas", [])}
    dia = agora.date().isoformat()
    por_fonte = defaultdict(lambda: [0, []])
    filtro_bons = []
    for n, i in enumerate(itens, start=1):
        a = notas.get(n, {})
        nota = a.get("nota", 0)
        if i["origem"] == "fonte pausada":
            por_fonte[i["fonte"]][0] += 1
            if nota >= NOTA_VALE:
                por_fonte[i["fonte"]][1].append((nota, i["titulo"], a.get("motivo", "")))
        elif nota >= NOTA_VALE:
            filtro_bons.append((nota, i["titulo"], i["fonte"], i["motivo"], a.get("motivo", "")))
    linhas = [f"# Revisão quinzenal do filtro — {dia}", "",
              f"Últimos {DIAS_OLHADOS} dias. Nada foi alterado: as sugestões dependem do \"sim\" do Washington.", "",
              "## Fontes pausadas (revisáveis)", ""]
    if not por_fonte:
        linhas.append("- Nenhum título guardado das fontes pausadas.")
    for fonte, (total, bons) in sorted(por_fonte.items()):
        sugestao = "VALE CONVERSAR SOBRE VOLTAR" if bons else "continua pausada"
        linhas.append(f"- **{fonte}**: {total} títulos, {len(bons)} com nota {NOTA_VALE}+ → {sugestao}")
        for nota, titulo, motivo in bons[:10]:
            linhas.append(f"  - ({nota}) {titulo} — {motivo}")
    linhas += ["", "## Notícias boas que o filtro tirou (revisáveis)", ""]
    if not filtro_bons:
        linhas.append("- Nenhuma: o filtro não tirou nada com nota 7+.")
    for nota, titulo, fonte, motivo_filtro, motivo in filtro_bons[:40]:
        linhas.append(f"- ({nota}) {titulo} [{fonte}] — {motivo_filtro}; Claude: {motivo}")
    linhas += ["", f"Títulos revistos: {len(itens)} (fontes pausadas: {sum(v[0] for v in por_fonte.values())}, "
               f"filtro: {len(itens) - sum(v[0] for v in por_fonte.values())})."]
    with open(os.path.join(PASTA_RELATORIOS, f"revisao-filtro-{dia}.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(linhas) + "\n")
    _salvar(ARQ_CONTROLE, {"ultima": agora.isoformat(), "relatorio": f"estado/relatorios/revisao-filtro-{dia}.md"})
    log(f"Revisão quinzenal do filtro feita: {len(itens)} títulos, {len(filtro_bons)} bons tirados pelo filtro.")
