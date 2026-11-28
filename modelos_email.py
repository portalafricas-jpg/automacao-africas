"""Monta os e-mails das assessorias a partir de emails/modelos.md (textos aprovados pelo Washington).

- Lê os modelos 1 a 13 direto do arquivo: mudou o texto lá, mudou o e-mail.
- Troca os campos entre colchetes ([nome], [link] etc.) pelos dados de cada envio.
- Versão evento ou versão pauta (modelo 7) e blocos "Só quando houver vídeo" entram só quando se aplicam.
- Assinatura em rodízio entre a equipe (27/11/2026): a mesma pessoa assina toda a conversa de uma assessoria.
- Textos variados: quando existirem versões aprovadas (emails/variacoes/), o robô sorteia uma.
"""
import hashlib
import os
import re

PASTA = os.path.dirname(os.path.abspath(__file__))
ARQ_MODELOS = os.path.join(PASTA, "emails", "modelos.md")
EQUIPE = ["Thays Andrade", "Maria Andrade", "Washington Andrade", "Larissa Mariano", "Ricardo Martins", "Vitor Lúcio Andrade"]


def ler_modelos():
    texto = open(ARQ_MODELOS, encoding="utf-8").read()
    modelos = {}
    for bloco in re.split(r"\n(?=## \d+\. )", texto):
        m = re.match(r"## (\d+)\. (.+)\n", bloco)
        if not m:
            continue
        n = int(m.group(1))
        corpo = bloco[m.end():].strip()
        corpo = corpo.split("\n---")[0].strip()
        assunto = ""
        ma = re.search(r"^\*\*Assunto:\*\*\s*(.+)$", corpo, re.M)
        if ma:
            assunto = ma.group(1).strip()
            corpo = (corpo[:ma.start()] + corpo[ma.end():]).strip()
        modelos[n] = {"titulo": m.group(2).strip(), "assunto": assunto, "corpo": corpo}
    return modelos


def assinante(email):
    """Sempre o mesmo nome para a mesma assessoria (rodízio entre assessorias)."""
    h = int(hashlib.sha1((email or "").lower().encode()).hexdigest(), 16)
    return EQUIPE[h % len(EQUIPE)]


def _blocos_opcionais(corpo, ctx):
    # Modelo 7: fica só a versão que se aplica
    versao = ctx.get("versao")  # "evento" ou "pauta"
    partes = re.split(r"^\*\*\[Versão (evento|pauta)\]\*\*\s*$", corpo, flags=re.M)
    if len(partes) > 1:
        saida = partes[0]
        resto = partes[1:]
        for i in range(0, len(resto), 2):
            nome, txt = resto[i], resto[i + 1]
            # o texto da última versão segue até o próximo bloco comum (linha que começa com "[Só quando" ou "Pode mandar")
            corte = re.search(r"^\[Só quando|^Pode mandar sem editar", txt, flags=re.M)
            proprio, comum = (txt[:corte.start()], txt[corte.start():]) if corte else (txt, "")
            if nome == versao:
                saida += proprio
            saida += comum
        corpo = saida
    # Blocos "[Só quando houver vídeo ...:]": entram só se houver vídeo
    corpo = re.sub(r"^\[Só quando[^\]]*\]\s*\n((.+\n?)+?)(?=\n|\Z)", lambda m: m.group(1) if ctx.get("tem_video") else "", corpo, flags=re.M)
    return corpo


def montar(n, ctx):
    """ctx: nome, assessoria, link, link_formulario, link_video, link_recusa, artista, evento, data, local,
    perguntas (lista), assunto_original, versao, tem_video, email (para o rodízio)."""
    md = ler_modelos()[n]
    corpo = _blocos_opcionais(md["corpo"], ctx)
    assunto = md["assunto"]

    perguntas = ctx.get("perguntas") or []
    def pergunta(i):
        return perguntas[i] if i < len(perguntas) else ""
    # perguntas numeradas: troca na ordem em que aparecem
    cont = {"i": 0}
    def troca_pergunta(m):
        p = pergunta(cont["i"])
        cont["i"] += 1
        return p
    corpo = re.sub(r"\[pergunta(?: criada a partir da matéria)?\]", troca_pergunta, corpo)

    campos = {
        "nome": ctx.get("nome", ""), "Nome": ctx.get("nome", ""),
        "assessoria": ctx.get("assessoria") or "sua assessoria",
        "artista": ctx.get("artista", ""), "Artista": ctx.get("artista", ""),
        "artista/tema": ctx.get("artista", ""),
        "evento": ctx.get("evento", ""), "Evento": ctx.get("evento", ""),
        "data": ctx.get("data", ""), "local": ctx.get("local", ""),
        "link da matéria": ctx.get("link", ""),
        "link do formulário": ctx.get("link_formulario", ""),
        "assunto do convite": ctx.get("assunto_original", ""),
        "assunto do pedido": ctx.get("assunto_original", ""),
    }
    def troca(m):
        chave = m.group(1)
        if chave in campos:
            return campos[chave]
        return m.group(0)
    corpo = re.sub(r"\[([^\]\n]{1,40})\]", troca, corpo)
    assunto = re.sub(r"\[([^\]\n]{1,40})\]", troca, assunto)

    # [link]: depende da linha (formulário, vídeo, recusa ou matéria)
    linhas = []
    for l in corpo.split("\n"):
        if "[link]" in l:
            baixo = l.lower()
            if "não temos interesse" in baixo:
                l = l.replace("[link]", ctx.get("link_recusa", ""))
            elif "enviar" in baixo:
                l = l.replace("[link]", ctx.get("link_video", ""))
            elif "instagram" in baixo or "👉" in l:
                l = l.replace("[link]", ctx.get("link_formulario", ""))
            else:
                l = l.replace("[link]", ctx.get("link", ""))
        linhas.append(l)
    corpo = "\n".join(linhas)

    # e-mail em texto simples: tira o negrito do markdown e linhas vazias repetidas
    corpo = corpo.replace("**", "")
    corpo = re.sub(r"\n{3,}", "\n\n", corpo).strip()

    # assinatura em rodízio
    quem = ctx.get("assinante") or assinante(ctx.get("email"))
    corpo = re.sub(r"Equipe Áfricas\s*$", f"{quem} | Equipe Áfricas Play", corpo)
    return {"assunto": assunto, "corpo": corpo, "assinante": quem}


def campos_faltando(texto):
    """Colchetes que sobraram (dado que o robô não tinha): o e-mail não sai assim."""
    return re.findall(r"\[[^\]\n]{1,60}\]", texto)
