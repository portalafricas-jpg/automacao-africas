"""Matérias da redação (escritas pelo Claude com aprovação do Washington).

Cada arquivo materias/*.json traz uma matéria pronta. Na hora marcada (publicar_em),
este script grava a matéria no RSS da categoria (feeds/<categoria>.xml) e o site publica.
A capa vem do banco de fotos (Unsplash) pela busca indicada; as fotos das pessoas já vão no corpo.
Roda depois do robo.py, no mesmo workflow; se o robô acabou de gravar o mesmo RSS, espera a próxima rodada.
"""
import glob, json, os, subprocess
from datetime import datetime
import robo as R

ARQ_ESTADO = os.path.join(R.PASTA_ESTADO, "materias-manuais.json")


def mexido_nesta_rodada(arquivo):
    try:
        antes = subprocess.run(["git", "show", f"HEAD:feeds/{os.path.basename(arquivo)}"],
                               capture_output=True, text=True, cwd=R.PASTA).stdout
        return antes != open(arquivo, encoding="utf-8").read()
    except Exception:
        return False


def main():
    feitas = R.ler_json(ARQ_ESTADO, [])
    agora = datetime.now(R.FUSO_SP)
    for arq in sorted(glob.glob(os.path.join(R.PASTA, "materias", "*.json"))):
        nome = os.path.basename(arq)
        if nome in feitas:
            continue
        m = json.load(open(arq, encoding="utf-8"))
        if datetime.fromisoformat(m["publicar_em"]) > agora:
            continue
        feed = os.path.join(R.PASTA_FEEDS, f"{m['categoria']}.xml")
        if os.path.exists(feed) and mexido_nesta_rodada(feed):
            R.log(f"MATÉRIA MANUAL {nome}: o robô acabou de gravar {m['categoria']}; fica para a próxima rodada")
            return
        usadas = {p.get("imagem") for p in R.ler_json(R.ARQ_PUBLICADAS, [])} if hasattr(R, "ARQ_PUBLICADAS") else set()
        foto = R.foto_banco(m.get("busca_foto", ""), usadas)
        if foto:
            m["imagem"], m["credito_imagem"] = foto
        with open(feed, "w", encoding="utf-8") as f:
            f.write(R.montar_rss(m, m["categoria"]))
        feitas.append(nome)
        R.salvar_json(ARQ_ESTADO, feitas)
        R.log(f"MATÉRIA MANUAL {nome}: publicada em {m['categoria']} ({m['titulo']}) | capa: {m.get('credito_imagem')}")
        return  # uma por rodada (cada RSS leva uma matéria)


if __name__ == "__main__":
    main()
