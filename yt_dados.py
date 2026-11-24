"""Baixa dados (título, descrição, tags) e quadros dos vídeos para preparar ajustes. Uso: python yt_dados.py pasta ID1 ID2..."""
import sys, os, json, requests, youtube
pasta = sys.argv[1]; ids = sys.argv[2:]
os.makedirs(pasta, exist_ok=True)
H = {"Authorization": "Bearer " + youtube.token()}
r = requests.get("https://www.googleapis.com/youtube/v3/videos", headers=H,
                 params={"part": "snippet,contentDetails,statistics", "id": ",".join(ids)}, timeout=30).json()
saida = []
for v in r.get("items", []):
    vid = v["id"]
    s = requests.head(f"https://www.youtube.com/shorts/{vid}", allow_redirects=False, timeout=20)
    saida.append({"id": vid, "titulo": v["snippet"]["title"], "descricao": v["snippet"]["description"],
                  "tags": v["snippet"].get("tags", []), "categoria": v["snippet"]["categoryId"],
                  "duracao": v["contentDetails"]["duration"], "views": v["statistics"].get("viewCount"),
                  "short": s.status_code == 200})
    for n in ("maxresdefault", "maxres1", "maxres2", "maxres3"):
        q = requests.get(f"https://i.ytimg.com/vi/{vid}/{n}.jpg", timeout=20)
        if q.status_code == 200:
            open(os.path.join(pasta, f"{vid}_{n}.jpg"), "wb").write(q.content)
json.dump(saida, open(os.path.join(pasta, "dados.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(saida), "vídeos")
