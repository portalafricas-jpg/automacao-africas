"""Atualiza sozinho a parte automática do CONEXOES.md: lista de robôs (workflows), horários e chaves que cada um usa.
Roda pelo workflow conexoes.yml sempre que um robô muda no repositório. A parte escrita à mão (o que falta, conectores) fica intacta."""
import os, re, glob

PASTA = os.path.dirname(os.path.abspath(__file__))
ARQ = os.path.join(PASTA, "CONEXOES.md")
INI, FIM = "<!-- AUTOMATICO:INICIO -->", "<!-- AUTOMATICO:FIM -->"

linhas, chaves = [], {}
for f in sorted(glob.glob(os.path.join(PASTA, ".github", "workflows", "*.yml"))):
    txt = open(f, encoding="utf-8").read()
    nome = (re.search(r"^name:\s*(.+)$", txt, re.M) or [None, "?"])[1].strip()
    crons = re.findall(r'cron:\s*"([^"]+)"', txt)
    usa = sorted(set(re.findall(r"secrets\.([A-Z_]+)", txt)))
    for c in usa:
        chaves.setdefault(c, []).append(os.path.basename(f))
    quando = ("agendado (UTC): " + ", ".join(crons)) if crons else "acionado sob demanda ou pelo cron-job.org"
    linhas.append(f"- {os.path.basename(f)}: {nome} ({quando})" + (f". Chaves: {', '.join(usa)}" if usa else ""))

bloco = [INI, "", "### Robôs (gerado automaticamente a partir de .github/workflows)", *linhas, "",
         "### Chaves guardadas nos Secrets do GitHub (só os nomes) e quem usa", *[f"- {c}: {', '.join(v)}" for c, v in sorted(chaves.items())],
         "", FIM]
atual = open(ARQ, encoding="utf-8").read()
novo = re.sub(re.escape(INI) + r".*?" + re.escape(FIM), "\n".join(bloco), atual, flags=re.S)
if novo != atual:
    open(ARQ, "w", encoding="utf-8").write(novo)
    print("CONEXOES.md atualizado")
else:
    print("Sem mudanças")
