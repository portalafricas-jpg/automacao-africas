"""Envio dos e-mails das assessorias (aprovado por Washington em 27/11/2026).

Sai pela conta portalafricas@gmail.com, com o remetente redacao@africas.com.br ("Enviar como").
A senha de app fica só no cofre do GitHub (GMAIL_SENHA_APP).

Por enquanto só envia o aviso interno de autor desconhecido (modelo 13) para portalafricas@gmail.com.
Os modelos para as assessorias entram depois do teste aprovado.
"""
import json
import os
import smtplib
import ssl
import sys
from email.message import EmailMessage
from email.utils import make_msgid, formatdate
from datetime import datetime, timezone

CONTA = "portalafricas@gmail.com"
REMETENTE = "Áfricas Play <redacao@africas.com.br>"
AVISOS_PARA = "portalafricas@gmail.com"
PASTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assessorias")
ARQ_AVISOS = os.path.join(PASTA, "avisos-pendentes.json")
ARQ_ENVIADOS = os.path.join(PASTA, "enviados.json")


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


if __name__ == "__main__":
    modo = sys.argv[1] if len(sys.argv) > 1 else "avisos"
    if modo == "avisos":
        enviar_avisos()
