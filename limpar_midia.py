"""Apaga do galho "midia" os vídeos com mais de 7 dias e refaz o galho do zero,
para que o que foi apagado deixe de ocupar espaço no GitHub.
Idade: pela data AAAA-MM-DD no caminho (ex.: dia da campanha); se não houver, pela data em que entrou."""
import os, re, subprocess, sys
from datetime import date, datetime, timedelta

DIAS = 7
hoje = date.today()
limite = hoje - timedelta(days=DIAS)


def git(*a):
    return subprocess.run(["git", *a], check=True, capture_output=True, text=True).stdout


arquivos = [f for f in git("ls-files").splitlines() if f]
apagar = []
for f in arquivos:
    datas = re.findall(r"(20\d\d-\d\d-\d\d)", f)
    if datas:
        dia = max(datetime.strptime(d, "%Y-%m-%d").date() for d in datas)
    else:
        ts = git("log", "-1", "--format=%ct", "--", f).strip()
        dia = datetime.fromtimestamp(int(ts)).date() if ts else hoje
    if dia < limite:
        apagar.append(f)

print(f"{len(arquivos)} arquivos no galho midia; {len(apagar)} com mais de {DIAS} dias.")
for f in apagar:
    print("  apagar:", f)
    os.remove(f)
if not apagar:
    sys.exit(0)
# Refaz o galho com um único registro (sem histórico): o que saiu deixa de ocupar espaço.
git("checkout", "-q", "--orphan", "midia-nova")
git("add", "-A")
git("commit", "-qm", f"Depósito de mídia: só os últimos {DIAS} dias ({hoje.isoformat()})", "--allow-empty")
open(os.environ.get("GITHUB_OUTPUT", os.devnull), "a").write("refazer=1\n")
