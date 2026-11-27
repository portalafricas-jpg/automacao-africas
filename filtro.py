"""Filtro grátis antes do Claude (aprovado por Washington em 26/11/2026).

Descarta o lixo óbvio sem gastar crédito da API:
1. spam (cassino): sempre fora; comércio (Black Friday, cupom...): fora se não tiver sinal;
2. títulos em alfabeto cirílico (spam de cassino que invadiu a Lista Preta): fora;
3. franquias (Marvel, DC, games...): só passam com personagem negro, artista da lista ou termo de sinal;
4. buscas amplas (samba, Carnaval 2027, Cultura negra...): só passam com artista da lista, escola/bloco ou termo de sinal.
Tudo o que sai aparece no relatório como "descartada pelo filtro", para conferir se nada bom se perdeu.
"""
import json
import os
import re
import unicodedata

PASTA = os.path.dirname(os.path.abspath(__file__))
ARQ_FILTRO = os.path.join(PASTA, "filtro.json")
ARQ_ARTISTAS = os.path.join(PASTA, "estado", "artistas-vistos.json")
ARQ_BUSCAS_AUTO = os.path.join(PASTA, "estado", "buscas-auto.json")
ARQ_FONTES = os.path.join(PASTA, "fontes.json")

CIRILICO = re.compile(r"[Ѐ-ӿ]")


def _sem_acento(texto):
    texto = unicodedata.normalize("NFD", (texto or "").lower())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def _ler(caminho, padrao):
    try:
        with open(caminho, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return padrao


def _regex(lista):
    termos = sorted({_sem_acento(t) for t in lista if t and len(t) >= 3}, key=len, reverse=True)
    if not termos:
        return None
    return re.compile(r"(?<![\w])(" + "|".join(re.escape(t) for t in termos) + r")(?![\w])")


def _nomes_de_artistas():
    """Nomes que o robô já conhece: artistas de Gente e Música e buscas de pessoas (vale na hora para nomes novos)."""
    nomes = set(_ler(ARQ_ARTISTAS, {}).keys())
    for b in _ler(ARQ_BUSCAS_AUTO, []) + [f for f in _ler(ARQ_FONTES, []) if f.get("tipo") == "busca"]:
        busca = (b.get("busca") or "")
        if busca.startswith('"') and busca.endswith('"'):
            nomes.add(busca.strip('"'))
    return nomes


class Filtro:
    def __init__(self):
        cfg = _ler(ARQ_FILTRO, {})
        self.spam = _regex(cfg.get("spam", []))
        self.lixo = _regex(cfg.get("lixo", []))
        self.franquias = _regex(cfg.get("franquias", []))
        self.buscas_amplas = {_sem_acento(n) for n in cfg.get("buscas_amplas", [])}
        self.sinal = _regex(cfg.get("termos_sinal", []) + cfg.get("nomes_sinal", []) + list(_nomes_de_artistas()))
        self.personagens = _regex(cfg.get("personagens", []))

    def _tem(self, regex, texto):
        return bool(regex and regex.search(texto))

    def motivo_descarte(self, item, nome_fonte):
        """Devolve o motivo do descarte, ou None se a notícia deve ir para o editor-chefe."""
        titulo = item.get("titulo") or ""
        texto = _sem_acento(titulo + " " + (item.get("descricao") or ""))
        if CIRILICO.search(titulo):
            return "filtro: título em outro alfabeto (spam)"
        achou = self.spam.search(texto) if self.spam else None
        if achou:
            return f"filtro: spam ({achou.group(1)})"
        tem_sinal = self._tem(self.sinal, texto)
        achou = self.lixo.search(texto) if self.lixo else None
        if achou and not tem_sinal:
            return f"filtro: comércio ({achou.group(1)})"
        franquia = self.franquias.search(texto) if self.franquias else None
        if franquia and not tem_sinal and not self._tem(self.personagens, texto):
            return f"filtro: {franquia.group(1)} sem personagem ou artista negro"
        if _sem_acento(nome_fonte) in self.buscas_amplas and not tem_sinal:
            return "filtro: busca ampla sem sinal (artista, escola/bloco ou termo)"
        return None
