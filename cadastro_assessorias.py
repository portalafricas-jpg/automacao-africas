"""Cadastro das assessorias (aprovado por Washington em 27/11/2026).

A cada rodada do robô das redes, lê as matérias do RSS do site e:
1. anota quem publicou cada matéria e passa a pessoa para "ativo";
2. tira os @ e os e-mails do texto das matérias e guarda na tabela;
3. separa os autores desconhecidos para o aviso (modelo 13) a portalafricas@gmail.com.

Só lê e anota. Não manda nada para as assessorias.
Regras completas: assessorias/PROTOCOLO.md e emails/modelos.md.
"""
import json
import os
import re
import unicodedata
from datetime import datetime, timezone

PASTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assessorias")
ARQ_CADASTRO = os.path.join(PASTA, "cadastro.json")
ARQ_ARROBAS = os.path.join(PASTA, "arrobas.json")
ARQ_HISTORICO = os.path.join(PASTA, "historico.json")
ARQ_AVISOS = os.path.join(PASTA, "avisos-pendentes.json")

ARROBA_RE = re.compile(r"(?<![\w.@])@([A-Za-z0-9_](?:[A-Za-z0-9_.]{0,28}[A-Za-z0-9_])?)")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
ARROBAS_DA_CASA = {"africasplay", "africas.play", "araraquaranews"}
DOMINIOS_DA_CASA = ("africas.com.br", "africasplay.com.br")
EMAILS_DA_CASA = {"portalafricas@gmail.com", "redacao@africas.com.br"}
NOMES_GENERICOS = {"", "assessoria", "redacao", "redação", "admin", "africas", "áfricas", "africas play"}


def _ler(caminho, padrao):
    try:
        with open(caminho, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return padrao


def _salvar(caminho, dados):
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=1)


def chave(nome):
    """Compara nomes sem maiúsculas, acentos e pontuação."""
    t = unicodedata.normalize("NFD", (nome or "").lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


PARTICULAS = {"de", "da", "do", "das", "dos", "e"}


def _partes(nome):
    return [p for p in chave(nome).split() if p not in PARTICULAS]


def eh_abreviado(nome):
    return any(len(p) == 1 for p in _partes(nome)) or "." in (nome or "")


def bate(nome_rss, nome_cadastro):
    """'Luana B.' e 'luana barreto' batem com 'Luana Barreto'. Primeiro nome igual;
    cada parte seguinte do nome da matéria tem que ser o começo de uma parte do cadastro, na ordem."""
    a, b = _partes(nome_rss), _partes(nome_cadastro)
    if not a or not b or a[0] != b[0]:
        return False
    if a == b:
        return True
    if len(a) == 1:
        return False  # só o primeiro nome não basta
    j = 1
    for p in a[1:]:
        while j < len(b) and not b[j].startswith(p):
            j += 1
        if j == len(b):
            return False
        j += 1
    return True


def _um_so(achados):
    """Uma pessoa só, ou o mesmo grupo de e-mails da mesma pessoa (campo mesma_pessoa)."""
    ids = {p["email"] or p["nome"] for p in achados}
    if len(ids) == 1:
        return True
    return all(ids - {p["email"]} <= set(p.get("mesma_pessoa", [])) for p in achados)


def procurar(nome, pessoas):
    """Devolve as pessoas do cadastro (uma, ou os e-mails da mesma pessoa) só quando a correspondência é segura."""
    k = chave(nome)
    exatos = [p for p in pessoas if k in [chave(p["nome"])] + [chave(x) for x in p.get("apelidos", [])]]
    if not exatos:
        exatos = [p for p in pessoas if any(bate(nome, n) for n in [p["nome"]] + p.get("apelidos", []))]
        como = "parecido"
    else:
        como = "exato"
    if exatos and _um_so(exatos):
        unicos = {p["email"] or p["nome"]: p for p in exatos}
        ligados = [p for p in pessoas if p["email"] and any(p["email"] in q.get("mesma_pessoa", []) for q in unicos.values())]
        for p in ligados:
            unicos.setdefault(p["email"], p)
        return list(unicos.values()), como
    return [], ("ambíguo" if exatos else "desconhecido")


def _agora():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def registrar(itens, log=print):
    """Chamado pelo redes.py a cada rodada. Nunca deve derrubar o robô das redes."""
    try:
        return _registrar(itens, log)
    except Exception as erro:  # o robô das redes segue mesmo se o cadastro falhar
        log(f"Aviso: cadastro das assessorias não rodou nesta rodada ({erro}).")
        return None


def _registrar(itens, log):
    cad = _ler(ARQ_CADASTRO, None)
    if not cad:
        log("Cadastro das assessorias não encontrado; pulando.")
        return None
    pessoas = cad["pessoas"]
    arrobas = _ler(ARQ_ARROBAS, {"assessoria": [], "sistema": []})
    hist = _ler(ARQ_HISTORICO, {"vistos": [], "materias": []})
    avisos = _ler(ARQ_AVISOS, {"desconhecidos": [], "nomes_atualizados": []})
    vistos = set(hist["vistos"])
    ja_tem_arroba = {r["arroba"].lower() for r in arrobas["sistema"] + arrobas["assessoria"]}
    ja_tem_email = {p["email"] for p in pessoas if p["email"]}
    contagem = {"materias": 0, "ativados": 0, "arrobas": 0, "emails": 0, "desconhecidos": 0}

    for item in itens:
        link = item.get("link") or ""
        if not link or link in vistos:
            continue
        vistos.add(link)
        contagem["materias"] += 1
        titulo = item.get("titulo", "")
        quando = item["quando"].isoformat() if item.get("quando") else ""
        publicou = (item.get("publicou") or "").strip()
        autor = (item.get("autor") or "").strip()

        # 1) Quem publicou / assinou a matéria
        nomes = []
        for n in (publicou, autor):
            if n and not n.startswith("@") and chave(n) not in NOMES_GENERICOS and chave(n) not in [chave(x) for x in nomes]:
                nomes.append(n)
        registro = {"link": link, "titulo": titulo, "categoria": item.get("categoria", ""),
                    "quando": quando, "publicou": publicou, "autor": autor, "pessoas": []}
        for n in nomes:
            grupo, como = procurar(n, pessoas)
            for p in grupo:
                registro["pessoas"].append(p["email"] or p["nome"])
                if p["tipo"] == "equipe":
                    continue
                p.setdefault("materias", []).append({"link": link, "titulo": titulo, "quando": quando})
                p["materias"] = p["materias"][-20:]
                p["ultima_materia"] = quando or _agora()
                if p["situacao"] in ("parado", "novo"):
                    p["situacao"] = "ativo"
                    p["ativo_desde"] = _agora()
                    contagem["ativados"] += 1
                # Nome diferente na matéria: atualiza, guarda o antigo como apelido (só se não for abreviado)
                if como == "parecido" and not eh_abreviado(n) and chave(n) != chave(p["nome"]):
                    if p["nome"] not in p["apelidos"]:
                        p["apelidos"].append(p["nome"])
                    avisos["nomes_atualizados"].append({"email": p["email"], "de": p["nome"], "para": n, "quando": _agora()})
                    p["nome"] = n
                elif chave(n) != chave(p["nome"]) and n not in p["apelidos"]:
                    p["apelidos"].append(n)
            if grupo:
                continue
            if not any(chave(d["nome"]) == chave(n) for d in avisos["desconhecidos"]):
                avisos["desconhecidos"].append({"nome": n, "motivo": como, "materia": titulo, "link": link,
                                                "quando": _agora(), "aviso_enviado": False})
                contagem["desconhecidos"] += 1
            else:
                for d in avisos["desconhecidos"]:
                    if chave(d["nome"]) == chave(n):
                        d.setdefault("outras_materias", []).append(link)
        hist["materias"].append(registro)

        # 2) Os @ e os e-mails do texto
        texto = " ".join([autor, item.get("resumo", ""), item.get("texto", "")])
        for a in ARROBA_RE.findall(texto):
            a = a.lower()
            if a in ARROBAS_DA_CASA or ("@" + a) in ja_tem_arroba:
                continue
            ja_tem_arroba.add("@" + a)
            arrobas["sistema"].append({"arroba": "@" + a, "nome": "(a confirmar)", "tipo": "",
                                       "materia": titulo, "link": link, "visto_em": _agora()[:10]})
            contagem["arrobas"] += 1
        for e in EMAIL_RE.findall(texto):
            e = e.lower().rstrip(".")
            if e in ja_tem_email or e in EMAILS_DA_CASA or e.endswith(DOMINIOS_DA_CASA):
                continue
            ja_tem_email.add(e)
            pessoas.append({"email": e, "nome": "(a confirmar)", "apelidos": [], "tipo": "novo", "instagram": "",
                            "empresa": e.split("@")[1], "situacao": "novo", "convite": "pendente",
                            "origem": f"achado na matéria: {titulo}", "obs": link})
            contagem["emails"] += 1

    hist["vistos"] = list(vistos)[-2000:]
    hist["materias"] = hist["materias"][-2000:]
    _salvar(ARQ_CADASTRO, cad)
    _salvar(ARQ_ARROBAS, arrobas)
    _salvar(ARQ_HISTORICO, hist)
    _salvar(ARQ_AVISOS, avisos)
    log(f"Assessorias ({len(itens)} no RSS do site): " + ", ".join(f"{k} {v}" for k, v in contagem.items()))
    return contagem
