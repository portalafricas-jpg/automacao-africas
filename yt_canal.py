"""Atualiza a descrição e as palavras-chave do canal AfricasPlay (aprovadas em 24/11/2026)."""
import json, requests, youtube

DESCRICAO = """Notícias pretas, cultura negra e protagonismo negro no Brasil e no mundo. O AfricasPlay é o canal do portal Áfricas (africas.com.br), jornalismo negro desde 2008.

Aqui você encontra:
📡 Radar: as principais notícias da população negra em vídeos curtos
🎬 Lançamentos de filmes, séries e músicas com protagonistas negros
🥁 Carnaval, ancestralidade e cultura afro-brasileira
🎙️ Entrevistas, colunas e eventos como a Expo África Brasil e A Grande Travessia

🌐 Portal: https://www.africas.com.br
📲 App Áfricas Play: notícias, vídeos, podcasts e alertas em um só lugar: https://app.africas.com.br

🔔 Inscreva-se e ative o sininho para acompanhar.
Áfricas Play — Conecta. Informa. Fortalece."""

PALAVRAS = ["notícias pretas", "notícia preta", "Áfricas Play", "africas", "cultura negra", "população negra",
            "consciência negra", "movimento negro", "antirracismo", "racismo", "quilombo", "quilombolas",
            "religiões de matriz africana", "mulher negra", "protagonismo negro", "carnaval",
            "filmes com protagonistas negros", "música negra", "diáspora africana", "igualdade racial"]

H = {"Authorization": "Bearer " + youtube.token()}
API = "https://www.googleapis.com/youtube/v3/channels"
c = requests.get(API, headers=H, params={"part": "brandingSettings", "mine": "true"}, timeout=30).json()["items"][0]
b = c["brandingSettings"]
b.setdefault("channel", {})
b["channel"]["description"] = DESCRICAO
b["channel"]["keywords"] = " ".join(f'"{p}"' if " " in p else p for p in PALAVRAS)
r = requests.put(API, headers={**H, "Content-Type": "application/json"}, params={"part": "brandingSettings"},
                 data=json.dumps({"id": c["id"], "brandingSettings": b}), timeout=30)
print("status:", r.status_code)
if r.status_code != 200:
    print(r.text[:500]); raise SystemExit(1)
novo = r.json()["brandingSettings"]["channel"]
print("descrição ok:", novo.get("description", "").startswith("Notícias pretas"), "| palavras:", novo.get("keywords", "")[:80])
