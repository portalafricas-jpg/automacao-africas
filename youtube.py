"""Envio de vídeos ao canal AfricasPlay no YouTube (API oficial, upload resumível).

Atenção: enquanto o Google não aprovar a auditoria do projeto "Robô Áfricas", todo vídeo
enviado pela API fica PRIVADO automaticamente, mesmo pedindo "public". Depois da aprovação,
o mesmo código passa a publicar aberto, sem mudar nada aqui.
"""
import os, json, time, requests

PRIVACIDADE = "public"   # o Google força "private" até a auditoria ser aprovada
CATEGORIA = "25"          # Notícias e política
UPLOAD = "https://www.googleapis.com/upload/youtube/v3/videos"


def configurado():
    return all(os.environ.get(k) for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"))


def token():
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": os.environ["YT_CLIENT_ID"], "client_secret": os.environ["YT_CLIENT_SECRET"],
        "refresh_token": os.environ["YT_REFRESH_TOKEN"], "grant_type": "refresh_token"}, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"YouTube: não consegui renovar o acesso ({r.status_code}: {r.text[:200]})")
    return r.json()["access_token"]


def enviar_video(caminho, titulo, descricao, tags=(), privacidade=PRIVACIDADE):
    """Envia o arquivo e devolve (id do vídeo, privacidade final)."""
    acesso = token()
    meta = {"snippet": {"title": titulo[:100], "description": descricao[:4900], "tags": list(tags)[:15],
                        "categoryId": CATEGORIA, "defaultLanguage": "pt-BR", "defaultAudioLanguage": "pt-BR"},
            "status": {"privacyStatus": privacidade, "selfDeclaredMadeForKids": False, "embeddable": True}}
    tamanho = os.path.getsize(caminho)
    ini = requests.post(UPLOAD, params={"uploadType": "resumable", "part": "snippet,status"},
                        headers={"Authorization": f"Bearer {acesso}", "Content-Type": "application/json; charset=UTF-8",
                                 "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(tamanho)},
                        data=json.dumps(meta), timeout=60)
    if ini.status_code != 200 or "Location" not in ini.headers:
        raise RuntimeError(f"YouTube: o início do envio falhou ({ini.status_code}: {ini.text[:300]})")
    destino = ini.headers["Location"]
    for tentativa in range(3):
        with open(caminho, "rb") as f:
            r = requests.put(destino, data=f, headers={"Authorization": f"Bearer {acesso}", "Content-Type": "video/mp4",
                                                         "Content-Length": str(tamanho)}, timeout=600)
        if r.status_code in (200, 201):
            v = r.json()
            return v["id"], v.get("status", {}).get("privacyStatus", "")
        if r.status_code < 500:
            break
        time.sleep(10 * (tentativa + 1))
    raise RuntimeError(f"YouTube: o envio do arquivo falhou ({r.status_code}: {r.text[:300]})")


def id_playlist(nome):
    """Procura no canal a playlist cujo título contém o nome (ex.: "Radar" acha "📡 Radar")."""
    acesso = token()
    tok = None
    while True:
        p = {"part": "snippet", "mine": "true", "maxResults": 50}
        if tok:
            p["pageToken"] = tok
        r = requests.get("https://www.googleapis.com/youtube/v3/playlists", headers={"Authorization": f"Bearer {acesso}"},
                         params=p, timeout=30)
        if r.status_code != 200:
            raise RuntimeError(f"YouTube: não consegui listar as playlists ({r.status_code}: {r.text[:200]})")
        d = r.json()
        for pl in d.get("items", []):
            if nome.lower() in pl["snippet"]["title"].lower():
                return pl["id"]
        tok = d.get("nextPageToken")
        if not tok:
            return None


def adicionar_na_playlist(video_id, nome="Radar"):
    """Coloca o vídeo na playlist indicada (a ordem segue a configuração da playlist). Devolve True se deu certo."""
    pl = id_playlist(nome)
    if not pl:
        raise RuntimeError(f"YouTube: playlist com '{nome}' no título não encontrada")
    corpo = {"snippet": {"playlistId": pl, "resourceId": {"kind": "youtube#video", "videoId": video_id}}}
    r = requests.post("https://www.googleapis.com/youtube/v3/playlistItems", params={"part": "snippet"},
                      headers={"Authorization": f"Bearer {token()}", "Content-Type": "application/json"},
                      data=json.dumps(corpo), timeout=30)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"YouTube: não consegui pôr na playlist ({r.status_code}: {r.text[:200]})")
    return True
