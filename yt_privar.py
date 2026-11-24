"""Deixa vídeos do canal como PRIVADOS (reversível). Uso: python yt_privar.py ID1 ID2 ..."""
import sys, json, requests, youtube
H = {"Authorization": "Bearer " + youtube.token()}
API = "https://www.googleapis.com/youtube/v3/videos"
for vid in sys.argv[1:]:
    v = requests.get(API, headers=H, params={"part": "status,snippet", "id": vid}, timeout=30).json().get("items", [])
    if not v:
        print(vid, "não encontrado"); continue
    st = v[0]["status"]; titulo = v[0]["snippet"]["title"][:60]
    if st.get("privacyStatus") == "private":
        print(vid, "já estava privado |", titulo); continue
    st["privacyStatus"] = "private"
    for k in ("uploadStatus", "failureReason", "rejectionReason", "publishAt"):
        st.pop(k, None)
    r = requests.put(API, headers={**H, "Content-Type": "application/json"}, params={"part": "status"},
                     data=json.dumps({"id": vid, "status": st}), timeout=30)
    print(vid, "OK privado" if r.status_code == 200 else f"ERRO {r.status_code} {r.text[:150]}", "|", titulo)
