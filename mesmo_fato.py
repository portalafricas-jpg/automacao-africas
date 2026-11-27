# Protocolo anti-repetição (aprovado por Washington em 27/11/2026).
# Duas notícias com 2 ou mais nomes próprios em comum nos últimos 3 dias são "suspeitas".
# O Claude confere cada par suspeito e responde: MESMO (não publica), DESDOBRAMENTO (fato novo,
# publica) ou DIFERENTE (publica). Usado pelo robô do portal, pelo robô das redes e pelo alarme diário.
import json
import os
import re
import time
import unicodedata
import urllib.error
import urllib.request

ULTIMO_ERRO = [""]

MODELO = "claude-haiku-5-5"
LIGACOES = {"de", "da", "do", "das", "dos", "e"}
# nomes comuns demais para indicar o mesmo fato sozinhos
GENERICOS = {
    "rio", "brasil", "sao paulo", "rio de janeiro", "salvador", "bahia", "recife", "belo horizonte", "bh",
    "brasilia", "pt", "stf", "governo", "governo federal", "senado", "camara", "a camara", "a camara dos deputados",
    "camara dos deputados", "sus", "negro", "negra", "mulheres", "sexta", "sabado", "domingo", "segunda", "terca",
    "quarta", "quinta", "novembro negro", "consciencia negra", "dia da consciencia negra", "igualdade racial",
    "semana da consciencia negra", "o", "a", "os", "as", "em", "no", "na", "para", "com", "o iphan", "levantamento",
}


def normalizar(t):
    t = unicodedata.normalize("NFD", (t or "").lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9 ]+", " ", t).strip()


def entidades(texto):
    """Nomes próprios do texto (sequências de palavras com maiúscula, sem contar a 1ª palavra)."""
    palavras = re.findall(r"[\wÀ-ÿ]+", texto or "")
    grupos, atual = [], []
    for i, p in enumerate(palavras):
        if i > 0 and p[0].isupper():
            atual.append(p)
        elif atual and p.lower() in LIGACOES:
            atual.append(p)
        else:
            if atual:
                grupos.append(atual)
            atual = []
    if atual:
        grupos.append(atual)
    saida = set()
    for g in grupos:
        while g and g[-1].lower() in LIGACOES:
            g = g[:-1]
        n = re.sub(r"\s+", " ", normalizar(" ".join(g)))
        if n and n not in GENERICOS and len(n) > 2:
            saida.add(n)
    return saida


def texto_de(m):
    return ". ".join(x for x in (m.get("titulo"), m.get("linha_fina") or m.get("resumo") or m.get("descricao"),
                                 m.get("titulo_original")) if x)


def suspeitas(nova, lista):
    """Devolve as matérias da lista com 2 ou mais nomes próprios em comum com a nova."""
    e_nova = entidades(texto_de(nova))
    if len(e_nova) < 2:
        return []
    return [m for m in lista if len(e_nova & entidades(texto_de(m))) >= 2]


def conferir(nova, antiga):
    """Pergunta ao Claude. Devolve 'MESMO', 'DESDOBRAMENTO', 'DIFERENTE' ou None (se falhar)."""
    chave = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    if not chave:
        return None
    pedido = (
        "Você é editor de um portal de notícias. Compare as duas notícias e responda com UMA palavra:\n"
        "MESMO = contam o mesmo fato (mesmo evento, mesma morte, mesmo lançamento, mesma decisão), mesmo com "
        "palavras, fontes ou detalhes diferentes;\n"
        "DESDOBRAMENTO = a nova traz um fato novo sobre o mesmo assunto (ex.: antes 'vai a júri', agora 'foi condenado');\n"
        "DIFERENTE = são fatos diferentes (ex.: o mesmo tipo de evento em cidades diferentes).\n\n"
        f"JÁ PUBLICADA: {texto_de(antiga)[:700]}\n\nNOVA: {texto_de(nova)[:700]}"
    )
    corpo = json.dumps({"model": MODELO, "max_tokens": 1000,
                        "messages": [{"role": "user", "content": pedido}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=corpo, headers={
        "x-api-key": chave, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    resposta = None
    for tentativa in range(4):  # a API às vezes pede para esperar (muitas consultas seguidas)
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                dados = json.loads(r.read())
            resposta = " ".join(b.get("text", "") for b in dados.get("content", []) if b.get("type") == "text").upper()
            if not resposta:
                ULTIMO_ERRO[0] = f"sem texto ({dados.get('stop_reason')})"
                resposta = None
                continue
            break
        except urllib.error.HTTPError as e:
            ULTIMO_ERRO[0] = f"HTTP {e.code}"
            if e.code in (429, 500, 502, 503, 529):
                time.sleep(5 * (tentativa + 1))
                continue
            return None
        except Exception as e:
            ULTIMO_ERRO[0] = str(e)[:100]
            time.sleep(3)
    if resposta is None:
        return None
    for palavra in ("DESDOBRAMENTO", "DIFERENTE", "MESMO"):
        if palavra in resposta:
            return palavra
    return None


def repetida(nova, lista):
    """True = mesmo fato já publicado; None = não deu para conferir (segurar); False = pode publicar.
    Devolve (resultado, matéria antiga ou None)."""
    for antiga in suspeitas(nova, lista):
        veredito = conferir(nova, antiga)
        if veredito is None:
            return None, antiga
        if veredito == "MESMO":
            return True, antiga
    return False, None
