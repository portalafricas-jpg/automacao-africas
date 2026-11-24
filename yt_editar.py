"""Troca descrição e tags de vídeos do canal, mantendo título e categoria. Uso: python yt_editar.py arquivo.json"""
import sys, json, requests, youtube
H = {"Authorization": "Bearer " + youtube.token()}
API = "https://www.googleapis.com/youtube/v3/videos"
for item in json.load(open(sys.argv[1], encoding="utf-8")):
    v = requests.get(API, headers=H, params={"part": "snippet", "id": item["id"]}, timeout=30).json()["items"][0]
    sn = v["snippet"]
    novo = {"title": item["titulo_novo"] if item.get("aplicar_titulo") else sn["title"], "categoryId": sn["categoryId"], "description": item["descricao"], "tags": item["tags"]}
    for k in ("defaultLanguage", "defaultAudioLanguage"):
        if sn.get(k): novo[k] = sn[k]
    r = requests.put(API, headers={**H, "Content-Type": "application/json"}, params={"part": "snippet"},
                     data=json.dumps({"id": item["id"], "snippet": novo}), timeout=30)
    print(item["id"], "OK" if r.status_code == 200 else f"ERRO {r.status_code} {r.text[:200]}", "|", sn["title"][:50])
