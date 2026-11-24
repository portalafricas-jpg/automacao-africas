"""Diagnóstico do canal AfricasPlay no YouTube. Só lê, não altera nada."""
import os, json, datetime, requests

def token():
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": os.environ["YT_CLIENT_ID"], "client_secret": os.environ["YT_CLIENT_SECRET"],
        "refresh_token": os.environ["YT_REFRESH_TOKEN"], "grant_type": "refresh_token"}, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]

H = {"Authorization": "Bearer " + token()}
API = "https://www.googleapis.com/youtube/v3/"
AN = "https://youtubeanalytics.googleapis.com/v2/reports"
hoje = datetime.date.today()
saida = {"gerado_em": hoje.isoformat()}

def get(url, **p):
    r = requests.get(url, headers=H, params=p, timeout=60)
    if r.status_code != 200:
        return {"erro": r.status_code, "texto": r.text[:300]}
    return r.json()

canal = get(API + "channels", part="snippet,statistics,status,contentDetails,brandingSettings", mine="true")["items"][0]
saida["canal"] = {"id": canal["id"], "titulo": canal["snippet"]["title"], "estatisticas": canal["statistics"],
                  "status": canal["status"], "descricao": canal["snippet"].get("description", ""),
                  "palavras_chave": canal.get("brandingSettings", {}).get("channel", {}).get("keywords", "")}
uploads = canal["contentDetails"]["relatedPlaylists"]["uploads"]

ids, tok = [], None
while True:
    p = {"part": "contentDetails", "playlistId": uploads, "maxResults": 50}
    if tok: p["pageToken"] = tok
    d = get(API + "playlistItems", **p)
    ids += [i["contentDetails"]["videoId"] for i in d.get("items", [])]
    tok = d.get("nextPageToken")
    if not tok: break

videos = []
for k in range(0, len(ids), 50):
    d = get(API + "videos", part="snippet,statistics,contentDetails,status", id=",".join(ids[k:k+50]))
    for v in d.get("items", []):
        videos.append({"id": v["id"], "titulo": v["snippet"]["title"], "publicado": v["snippet"]["publishedAt"][:10],
                       "duracao": v["contentDetails"]["duration"], "privacidade": v["status"]["privacyStatus"],
                       "views": int(v["statistics"].get("viewCount", 0)), "likes": int(v["statistics"].get("likeCount", 0)),
                       "comentarios": int(v["statistics"].get("commentCount", 0)),
                       "tags": v["snippet"].get("tags", [])[:15], "descricao_tam": len(v["snippet"].get("description", "")),
                       "capa": v["snippet"]["thumbnails"].get("maxres", v["snippet"]["thumbnails"].get("high", {})).get("url", "")})

def relatorio(inicio, metricas, dimensoes=None, **extra):
    p = {"ids": "channel==MINE", "startDate": inicio, "endDate": hoje.isoformat(), "metrics": metricas}
    if dimensoes: p["dimensions"] = dimensoes
    p.update(extra)
    return get(AN, **p)

m = "views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,subscribersGained"
por_video = relatorio("2015-01-01", m, "video", sort="-views", maxResults=200)
por_video_90 = relatorio((hoje - datetime.timedelta(days=90)).isoformat(), m, "video", sort="-views", maxResults=200)
def mapa(rel):
    cab = [c["name"] for c in rel.get("columnHeaders", [])]
    return {r[0]: dict(zip(cab[1:], r[1:])) for r in rel.get("rows", [])}
total, ult90 = mapa(por_video), mapa(por_video_90)
for v in videos:
    v["analytics_total"] = total.get(v["id"], {})
    v["analytics_90d"] = ult90.get(v["id"], {})
saida["videos"] = videos

d365 = (hoje - datetime.timedelta(days=365)).isoformat()
d90 = (hoje - datetime.timedelta(days=90)).isoformat()
d28 = (hoje - datetime.timedelta(days=28)).isoformat()
saida["canal_365d"] = relatorio(d365, m)
saida["canal_28d"] = relatorio(d28, m)
saida["tipo_conteudo_90d"] = relatorio(d90, "views,estimatedMinutesWatched", "creatorContentType")
saida["tipo_conteudo_365d"] = relatorio(d365, "views,estimatedMinutesWatched", "creatorContentType")
saida["origem_trafego_90d"] = relatorio(d90, "views,estimatedMinutesWatched", "insightTrafficSourceType", sort="-views")
saida["paises_90d"] = relatorio(d90, "views", "country", sort="-views", maxResults=10)
saida["idade_genero_365d"] = relatorio(d365, "viewerPercentage", "ageGroup,gender")
saida["mensal_365d"] = relatorio(d365, "views,estimatedMinutesWatched,subscribersGained,subscribersLost", "month")
saida["dia_semana_90d"] = relatorio(d90, "views", "day")

os.makedirs("ensaio", exist_ok=True)
with open("ensaio/yt-diagnostico.json", "w", encoding="utf-8") as f:
    json.dump(saida, f, ensure_ascii=False, indent=1)
print("vídeos:", len(videos))
