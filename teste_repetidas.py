# Teste só de leitura do protocolo anti-repetição: roda a conferência nas matérias já publicadas
# e mostra o que o robô teria feito. Não publica nem altera nada.
import json
from datetime import datetime, timedelta
import mesmo_fato

pub = json.load(open("estado/publicadas.json", encoding="utf-8"))
for i, nova in enumerate(pub):
    t = datetime.fromisoformat(nova["criado_em"])
    anteriores = [m for m in pub[:i] if t - datetime.fromisoformat(m["criado_em"]) <= timedelta(days=3)]
    for antiga in mesmo_fato.suspeitas(nova, anteriores):
        v = mesmo_fato.conferir(nova, antiga)
        acao = {"MESMO": "BLOQUEADA", "DESDOBRAMENTO": "publica (fato novo)", "DIFERENTE": "publica"}.get(v, "SEGURADA (sem resposta)")
        print(f"{acao:24} | {antiga['titulo'][:55]}  x  {nova['titulo'][:55]}")
