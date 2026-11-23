import os, json, requests
from datetime import datetime, timezone, timedelta
tok=os.environ["META_PAGE_TOKEN"]; ig=os.environ["IG_USER_ID"]
API="https://graph.facebook.com/v26.0/"
posts=json.load(open("estado/posts-redes.json"))
corte=datetime.now(timezone.utc)-timedelta(hours=40)
for p in posts:
    if not p.get("ig_media") or datetime.fromisoformat(p["publicado_em"])<corte: continue
    met="reach,views,likes,comments,shares,saved"
    r=requests.get(API+p["ig_media"]+"/insights",params={"metric":met,"access_token":tok},timeout=30).json()
    v={m["name"]:m["values"][0]["value"] if m.get("values") else m.get("total_value",{}).get("value") for m in r.get("data",[])}
    print("POST",p["publicado_em"][5:16],p.get("tipo","carrossel"),"|",p["titulo"][:45],"|",v or r.get("error",{}).get("message"))
r=requests.get(API+ig,params={"fields":"followers_count,media_count","access_token":tok},timeout=30).json()
print("CONTA",r)
