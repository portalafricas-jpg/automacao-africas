"""Publica o formulário das assessorias no Cloudflare Workers (grátis) e conversa com o KV.

O token fica só no cofre do GitHub (CLOUDFLARE_API_TOKEN). Uso:
  python cloudflare_publicar.py publicar   -> cria o KV (se faltar), publica o formulário e grava o endereço
Funções usadas pelo robô de envio: gravar_pagina(), ler_respostas(), apagar_resposta().
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid

API = "https://api.cloudflare.com/client/v4"
NOME_WORKER = "formulario-africas"
NOME_KV = "assessorias"
SUBDOMINIO_PREFERIDO = "africasplay"
PASTA = os.path.dirname(os.path.abspath(__file__))
ARQ_FORMULARIO = os.path.join(PASTA, "assessorias", "formulario.json")
ARQ_CODIGO = os.path.join(PASTA, "cloudflare", "formulario.js")


def _token():
    t = (os.environ.get("CLOUDFLARE_API_TOKEN") or "").strip()
    if not t:
        raise SystemExit("Falta CLOUDFLARE_API_TOKEN no cofre.")
    return t


def api(metodo, caminho, dados=None, cabecalhos=None, cru=False):
    h = {"Authorization": f"Bearer {_token()}"}
    corpo = None
    if dados is not None and not isinstance(dados, (bytes, bytearray)):
        corpo = json.dumps(dados).encode()
        h["Content-Type"] = "application/json"
    elif dados is not None:
        corpo = dados
    h.update(cabecalhos or {})
    req = urllib.request.Request(API + caminho, data=corpo, method=metodo, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            bruto = r.read()
    except urllib.error.HTTPError as e:
        bruto = e.read()
        if cru:
            raise
        raise SystemExit(f"Cloudflare recusou {metodo} {caminho}: {e.code} {bruto[:500]!r}")
    if cru:
        return bruto
    return json.loads(bruto or b"{}")


def conta():
    contas = api("GET", "/accounts")["result"]
    if not contas:
        raise SystemExit("O token não enxerga nenhuma conta do Cloudflare.")
    return contas[0]["id"]


def namespace(cid):
    for ns in api("GET", f"/accounts/{cid}/storage/kv/namespaces?per_page=100")["result"]:
        if ns["title"] == NOME_KV:
            return ns["id"]
    return api("POST", f"/accounts/{cid}/storage/kv/namespaces", {"title": NOME_KV})["result"]["id"]


def subdominio(cid):
    try:
        r = api("GET", f"/accounts/{cid}/workers/subdomain")
        sub = (r.get("result") or {}).get("subdomain")
        if sub:
            return sub
    except SystemExit:
        pass
    r = api("PUT", f"/accounts/{cid}/workers/subdomain", {"subdomain": SUBDOMINIO_PREFERIDO})
    return r["result"]["subdomain"]


def publicar():
    cid = conta()
    ns = namespace(cid)
    codigo = open(ARQ_CODIGO, "rb").read()
    meta = {"main_module": "formulario.js", "compatibility_date": "2024-11-01",
            "bindings": [{"type": "kv_namespace", "name": "KV", "namespace_id": ns}]}
    fronteira = "----africas" + uuid.uuid4().hex
    partes = [
        f"--{fronteira}\r\nContent-Disposition: form-data; name=\"metadata\"\r\nContent-Type: application/json\r\n\r\n".encode()
        + json.dumps(meta).encode() + b"\r\n",
        f"--{fronteira}\r\nContent-Disposition: form-data; name=\"formulario.js\"; filename=\"formulario.js\"\r\n"
        f"Content-Type: application/javascript+module\r\n\r\n".encode() + codigo + b"\r\n",
        f"--{fronteira}--\r\n".encode(),
    ]
    api("PUT", f"/accounts/{cid}/workers/scripts/{NOME_WORKER}", b"".join(partes),
        {"Content-Type": f"multipart/form-data; boundary={fronteira}"})
    sub = subdominio(cid)
    api("POST", f"/accounts/{cid}/workers/scripts/{NOME_WORKER}/subdomain", {"enabled": True})
    endereco = f"https://{NOME_WORKER}.{sub}.workers.dev"
    with open(ARQ_FORMULARIO, "w", encoding="utf-8") as f:
        json.dump({"endereco": endereco, "conta": cid, "kv": ns}, f, ensure_ascii=False, indent=1)
    print(f"Formulário publicado: {endereco}")
    return endereco


def _dados():
    with open(ARQ_FORMULARIO, encoding="utf-8") as f:
        return json.load(f)


def gravar_pagina(token, dados):
    """Dados da página pessoal: nome, assessoria, e-mail, sugestões de @ e título da matéria."""
    d = _dados()
    chave = urllib.parse.quote(f"p:{token}", safe="")
    api("PUT", f"/accounts/{d['conta']}/storage/kv/namespaces/{d['kv']}/values/{chave}",
        json.dumps(dados, ensure_ascii=False).encode(), {"Content-Type": "text/plain; charset=utf-8"})


def ler_respostas():
    d = _dados()
    base = f"/accounts/{d['conta']}/storage/kv/namespaces/{d['kv']}"
    chaves = api("GET", f"{base}/keys?prefix=r:&limit=1000")["result"]
    respostas = []
    for k in chaves:
        bruto = api("GET", f"{base}/values/{urllib.parse.quote(k['name'], safe='')}", cru=True)
        r = json.loads(bruto)
        r["_chave"] = k["name"]
        respostas.append(r)
    return respostas


def apagar_resposta(chave):
    d = _dados()
    api("DELETE", f"/accounts/{d['conta']}/storage/kv/namespaces/{d['kv']}/values/{urllib.parse.quote(chave, safe='')}")


if __name__ == "__main__":
    if (sys.argv[1] if len(sys.argv) > 1 else "") == "publicar":
        publicar()
