"""Envio dos e-mails das assessorias (aprovado por Washington em 27/11/2026).

Sai pela conta portalafricas@gmail.com, com o remetente redacao@africas.com.br ("Enviar como").
A senha de app fica só no cofre do GitHub (GMAIL_SENHA_APP).

Por enquanto só envia o aviso interno de autor desconhecido (modelo 13) para portalafricas@gmail.com.
Os modelos para as assessorias entram depois do teste aprovado.
"""
import email
import imaplib
import json
import os
import re
import smtplib
import ssl
import sys
from email.message import EmailMessage
from email.header import decode_header, make_header
from email.utils import make_msgid, formatdate, parseaddr
from datetime import timedelta
from datetime import datetime, timezone

CONTA = "portalafricas@gmail.com"
REMETENTE = "Áfricas Play <redacao@africas.com.br>"
AVISOS_PARA = "portalafricas@gmail.com"
PASTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assessorias")
ARQ_AVISOS = os.path.join(PASTA, "avisos-pendentes.json")
ARQ_ENVIADOS = os.path.join(PASTA, "enviados.json")
ARQ_CADASTRO = os.path.join(PASTA, "cadastro.json")
ARQ_ARROBAS = os.path.join(PASTA, "arrobas.json")
ARQ_CAIXA = os.path.join(PASTA, "caixa.json")
NOSSOS = {"portalafricas@gmail.com", "redacao@africas.com.br"}
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
IG_RE = re.compile(r"instagram\.com/([A-Za-z0-9_.]{2,30})|(?<![\w.@])@([A-Za-z0-9_](?:[A-Za-z0-9_.]{0,28}[A-Za-z0-9_])?)")
SEM_INTERESSE = ("não temos interesse", "nao temos interesse", "sem interesse")
DESCADASTRAR = ("não quero mais receber", "nao quero mais receber", "não quero receber", "nao quero receber",
                "remover meu e-mail", "remover meu email", "descadastr", "parar de receber", "não enviar mais",
                "nao enviar mais", "unsubscribe")


def _ler(caminho, padrao):
    try:
        with open(caminho, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return padrao


def _salvar(caminho, dados):
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=1)


def conectar():
    senha = (os.environ.get("GMAIL_SENHA_APP") or "").replace(" ", "").strip()
    if not senha:
        raise SystemExit("Falta GMAIL_SENHA_APP no cofre.")
    smtp = smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context(), timeout=60)
    smtp.login(CONTA, senha)
    return smtp


def enviar(smtp, para, assunto, texto, responder_a=None):
    msg = EmailMessage()
    msg["From"] = REMETENTE
    msg["To"] = para
    msg["Subject"] = assunto
    msg["Date"] = formatdate(localtime=False)
    msg["Message-ID"] = make_msgid(domain="africas.com.br")
    if responder_a:  # lembretes saem na mesma conversa do e-mail original
        msg["In-Reply-To"] = responder_a
        msg["References"] = responder_a
    msg.set_content(texto)
    smtp.send_message(msg)
    return msg["Message-ID"]


def texto_aviso(d):
    return (f"Washington, apareceu no site uma matéria de alguém que não está na lista de assessores, "
            f"colunistas e colaboradores:\n\n"
            f"- Nome no site: {d['nome']}\n"
            f"- Matéria: {d['materia']} — {d['link']}\n\n"
            f"Responda este e-mail só com o e-mail da pessoa. Se forem vários, uma linha por pessoa: "
            f"\"Nome: e-mail\". Se o e-mail já existir no cadastro, o robô entende que é a mesma pessoa "
            f"e atualiza o nome.\n")


def enviar_avisos():
    avisos = _ler(ARQ_AVISOS, {"desconhecidos": []})
    pendentes = [d for d in avisos.get("desconhecidos", []) if not d.get("aviso_enviado")]
    if not pendentes:
        print("Nenhum aviso de autor desconhecido pendente.")
        return
    enviados = _ler(ARQ_ENVIADOS, [])
    smtp = conectar()
    try:
        for d in pendentes:
            assunto = f"Não localizamos o e-mail de {d['nome']}"
            mid = enviar(smtp, AVISOS_PARA, assunto, texto_aviso(d))
            d["aviso_enviado"] = True
            d["aviso_id"] = mid
            d["aviso_em"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            enviados.append({"modelo": 13, "para": AVISOS_PARA, "assunto": assunto, "id": mid, "em": d["aviso_em"]})
            print(f"Aviso enviado: {assunto}")
    finally:
        smtp.quit()
    _salvar(ARQ_AVISOS, avisos)
    _salvar(ARQ_ENVIADOS, enviados)


# ---------------- Modo teste (27-28/11/2026): tudo vai só para portalafricas@gmail.com ----------------
MODO_ENVIO = (os.environ.get("MODO_ENVIO") or "teste").strip().lower()


def enviar_assessoria(smtp, para, assunto, texto, responder_a=None):
    """Único caminho de envio para as assessorias. Enquanto o Washington não aprovar o teste,
    qualquer e-mail é desviado para portalafricas@gmail.com e marcado [TESTE]."""
    if MODO_ENVIO != "real":
        texto = f"[TESTE — iria para: {para}]\n\n" + texto
        para, assunto = AVISOS_PARA, "[TESTE] " + assunto
    return enviar(smtp, para, assunto, texto, responder_a)


def enviar_teste_completo():
    """Manda os modelos 1 a 12 para portalafricas@gmail.com, com os lembretes na mesma conversa."""
    import time
    import modelos_email as me
    form = _ler(os.path.join(PASTA, "formulario.json"), {}).get("endereco") or "(formulário ainda não publicado)"
    ctx = dict(nome="Washington", assessoria="Assessoria Teste", email="teste@exemplo.com.br",
               link="https://www.africas.com.br", link_formulario=form + "/?t=teste",
               link_video="(link de envio do vídeo: próxima etapa)", link_recusa=form + "/recusar?t=teste",
               artista="(nome do artista da matéria)", evento="(nome do evento)", data="(data do evento)",
               local="(local do evento)", perguntas=["(pergunta 1 criada a partir da matéria)",
               "(pergunta 2)", "(pergunta 3)"], versao="pauta", tem_video=True)
    enviados = _ler(ARQ_ENVIADOS, [])
    smtp = conectar()
    fio = {}
    try:
        for n, pai in [(1, None), (2, 1), (3, 1), (4, None), (5, None), (6, None), (7, None),
                       (8, None), (9, 8), (10, 8), (11, None), (12, 11)]:
            c = dict(ctx)
            if pai:
                c["assunto_original"] = fio[pai]["assunto"]
            r = me.montar(n, c)
            mid = enviar_assessoria(smtp, "teste@exemplo.com.br", f"Modelo {n} — " + r["assunto"] if not pai else r["assunto"],
                                    r["corpo"], fio[pai]["id"] if pai else None)
            fio[n] = {"id": mid, "assunto": r["assunto"]}
            enviados.append({"modelo": n, "para": AVISOS_PARA, "assunto": r["assunto"], "id": mid, "teste": True,
                             "em": datetime.now(timezone.utc).isoformat(timespec="seconds")})
            print(f"Teste enviado: modelo {n} ({r['assinante']})")
            time.sleep(3)
    finally:
        smtp.quit()
    _salvar(ARQ_ENVIADOS, enviados)


# ---------------- Leitura da caixa (só lê; não apaga, não marca como lido, não responde) ----------------
def _cab(msg, nome):
    try:
        return str(make_header(decode_header(msg.get(nome, "") or "")))
    except Exception:
        return msg.get(nome, "") or ""


def _corpo(msg):
    """Texto da resposta, sem a parte citada do e-mail original."""
    texto = ""
    for parte in (msg.walk() if msg.is_multipart() else [msg]):
        if parte.get_content_type() == "text/plain" and not parte.get_filename():
            try:
                texto = parte.get_payload(decode=True).decode(parte.get_content_charset() or "utf-8", errors="replace")
            except Exception:
                texto = ""
            break
    if not texto:
        for parte in (msg.walk() if msg.is_multipart() else [msg]):
            if parte.get_content_type() == "text/html":
                bruto = parte.get_payload(decode=True).decode(parte.get_content_charset() or "utf-8", errors="replace")
                texto = re.sub(r"<[^>]+>", " ", re.sub(r"<br\s*/?>|</p>|</div>", "\n", bruto, flags=re.I))
                break
    linhas = []
    for l in texto.splitlines():
        if l.strip().startswith(">") or re.match(r"\s*(Em .+ escreveu:|On .+ wrote:|-----Original Message|De: )", l):
            break
        linhas.append(l)
    return "\n".join(linhas).strip()


def _chave(n):
    import unicodedata
    t = unicodedata.normalize("NFD", (n or "").lower())
    return re.sub(r"[^a-z0-9]+", " ", "".join(c for c in t if unicodedata.category(c) != "Mn")).strip()


def _registrar_pessoa(cad, email_, nome, aviso):
    """Resposta a um aviso de autor desconhecido: e-mail é a chave."""
    agora = datetime.now(timezone.utc).isoformat(timespec="seconds")
    p = next((x for x in cad["pessoas"] if x["email"] == email_), None)
    materia = {"link": aviso.get("link", ""), "titulo": aviso.get("materia", ""), "quando": aviso.get("quando", "")}
    if p:  # já existe: mesma pessoa, atualiza o nome e guarda o antigo
        if nome and _chave(nome) != _chave(p["nome"]):
            if p["nome"] and p["nome"] not in p["apelidos"] and p["nome"] != "(a confirmar)":
                p["apelidos"].append(p["nome"])
            p["nome"] = nome
        acao = "nome atualizado" if nome else "já cadastrado"
    else:
        p = {"email": email_, "nome": nome or "(a confirmar)", "apelidos": [], "tipo": "assessoria",
             "instagram": "", "empresa": email_.split("@")[1], "situacao": "ativo", "convite": "pendente",
             "origem": "resposta ao aviso de autor desconhecido", "obs": ""}
        cad["pessoas"].append(p)
        acao = "cadastrado"
    if p.get("tipo") != "equipe":
        p["situacao"] = "ativo"
        p.setdefault("materias", []).append(materia)
        p["ultima_materia"] = materia["quando"] or agora
    return acao


def ler_caixa():
    senha = (os.environ.get("GMAIL_SENHA_APP") or "").replace(" ", "").strip()
    if not senha:
        raise SystemExit("Falta GMAIL_SENHA_APP no cofre.")
    caixa = _ler(ARQ_CAIXA, {"processados": [], "respostas_para_conferir": []})
    feitos = set(caixa["processados"])
    avisos = _ler(ARQ_AVISOS, {"desconhecidos": []})
    enviados = _ler(ARQ_ENVIADOS, [])
    cad = _ler(ARQ_CADASTRO, {"pessoas": []})
    arrobas = _ler(ARQ_ARROBAS, {"assessoria": [], "sistema": []})
    por_id = {e["id"]: e for e in enviados if e.get("id")}
    avisos_por_id = {d["aviso_id"]: d for d in avisos.get("desconhecidos", []) if d.get("aviso_id")}
    avisos_por_nome = {_chave(d["nome"]): d for d in avisos.get("desconhecidos", [])}
    desde = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%d-%b-%Y")
    contagem = {"lidos": 0, "avisos_respondidos": 0, "respostas": 0, "conferir": 0}

    imap = imaplib.IMAP4_SSL("imap.gmail.com", 993)
    imap.login(CONTA, senha)
    try:
        imap.select("INBOX", readonly=True)  # só leitura: nada muda na caixa
        _, dados = imap.search(None, f'(SINCE "{desde}")')
        for num in dados[0].split():
            _, partes = imap.fetch(num, "(BODY.PEEK[])")
            msg = email.message_from_bytes(partes[0][1])
            mid = (msg.get("Message-ID") or "").strip()
            if not mid or mid in feitos:
                continue
            if mid in avisos_por_id or mid in por_id:
                continue  # é o próprio e-mail que o robô mandou, não uma resposta
            refs = " ".join([msg.get("In-Reply-To") or "", msg.get("References") or ""])
            de = parseaddr(msg.get("From", ""))[1].lower()
            assunto = _cab(msg, "Subject")
            original = next((i for i in list(avisos_por_id) + list(por_id) if i in refs), None)
            m_aviso = re.search(r"N[ãa]o localizamos o e-mail de (.+)$", assunto)
            aviso = avisos_por_id.get(original) or (avisos_por_nome.get(_chave(m_aviso.group(1))) if m_aviso else None)
            eh_resposta = bool(refs.strip()) or assunto.lower().startswith(("re:", "res:", "resp:"))
            if not eh_resposta or (not original and not (aviso and de in NOSSOS)):
                continue  # não é resposta a um e-mail do robô
            feitos.add(mid)
            contagem["lidos"] += 1
            corpo = _corpo(msg)

            # a) Washington respondendo ao aviso de autor desconhecido
            if aviso and de in NOSSOS:
                achados = []
                for linha in corpo.splitlines():
                    for e_ in EMAIL_RE.findall(linha):
                        e_ = e_.lower()
                        if e_ in NOSSOS:
                            continue
                        nome = re.sub(r"[:\-–<>]+\s*$", "", linha.split(e_)[0].replace("<", "")).strip(" :-–") or None
                        achados.append((e_, nome))
                if not achados:
                    caixa["respostas_para_conferir"].append({"assunto": assunto, "de": de, "texto": corpo[:500]})
                    contagem["conferir"] += 1
                    continue
                for e_, nome in achados:
                    if len(achados) == 1 and not nome:
                        nome = aviso["nome"]
                    acao = _registrar_pessoa(cad, e_, nome, aviso)
                    print(f"Aviso respondido: {nome} <{e_}> ({acao})")
                aviso["resolvido"] = True
                aviso["resolvido_em"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
                contagem["avisos_respondidos"] += 1
                continue

            # b) Assessoria respondendo a um e-mail do robô
            env = por_id.get(original, {})
            p = next((x for x in cad["pessoas"] if x["email"] == de), None)
            baixo = corpo.lower()
            registro = {"de": de, "assunto": assunto, "modelo": env.get("modelo"),
                        "em": datetime.now(timezone.utc).isoformat(timespec="seconds")}
            if p:
                p["respondeu"] = True  # os lembretes param
                for outro in p.get("mesma_pessoa", []):
                    q = next((x for x in cad["pessoas"] if x["email"] == outro), None)
                    if q:
                        q["respondeu"] = True
            if any(t in baixo for t in DESCADASTRAR):
                registro["acao"] = "não quer mais receber"
                if p:
                    p["convite"] = "descadastrado"
            elif any(t in baixo for t in SEM_INTERESSE):
                registro["acao"] = "não temos interesse"
                if p:
                    p["convite"] = "sem_interesse"
            else:
                igs = []
                for a, b in IG_RE.findall(corpo):
                    h = "@" + (a or b).lower().rstrip(".")
                    if h not in igs and h not in ("@africasplay", "@gmail"):
                        igs.append(h)
                if igs and p:
                    p["instagram"] = p.get("instagram") or igs[0]
                    p["convite"] = "respondido"
                    for h in igs[:3]:
                        if not any(r["arroba"].lower() == h for r in arrobas["assessoria"]):
                            arrobas["assessoria"].append({"arroba": h, "nome": p["nome"] if h == igs[0] else "(a confirmar)",
                                                          "tipo": "", "email": de, "origem": "resposta por e-mail"})
                    registro["acao"] = "mandou Instagram: " + " ".join(igs[:3])
                else:
                    registro["acao"] = "resposta para conferir"
                    registro["texto"] = corpo[:500]
                    caixa["respostas_para_conferir"].append(registro)
                    contagem["conferir"] += 1
            caixa.setdefault("respostas", []).append(registro)
            contagem["respostas"] += 1
            print(f"Resposta de {de}: {registro['acao']}")
    finally:
        imap.logout()
    caixa["processados"] = list(feitos)[-3000:]
    _salvar(ARQ_CAIXA, caixa)
    _salvar(ARQ_AVISOS, avisos)
    _salvar(ARQ_CADASTRO, cad)
    _salvar(ARQ_ARROBAS, arrobas)
    print("Caixa: " + ", ".join(f"{k} {v}" for k, v in contagem.items()))


if __name__ == "__main__":
    modo = sys.argv[1] if len(sys.argv) > 1 else "avisos"
    if modo in ("caixa", "tudo"):
        ler_caixa()
    if modo in ("avisos", "tudo"):
        enviar_avisos()
    if modo == "teste":
        enviar_teste_completo()
