import json, re, unicodedata, requests
from datetime import datetime, timezone, timedelta
sp=timezone(timedelta(hours=-3))
def slug(t):
    t=unicodedata.normalize("NFKD",t).encode("ascii","ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+","-",t).strip("-")
p=json.load(open("estado/publicadas.json"))
hoje=[x for x in p if x.get("publicado_em") and datetime.fromisoformat(x["publicado_em"].replace("Z","+00:00")).astimezone(sp).date().isoformat()=="2026-11-23"]
ok=0; falta=[]
for x in hoje:
    r=requests.get("https://www.africas.com.br/noticia/"+slug(x["titulo"]),timeout=30,headers={"User-Agent":"Mozilla/5.0"},allow_redirects=True)
    if r.status_code==200 and x["titulo"][:20].lower() in r.text.lower(): ok+=1
    else: falta.append(x["titulo"][:60])
print("SITE robo hoje", len(hoje), "| no site:", ok, "| nao achadas:", len(falta))
for t in falta[:8]: print("SITE falta:", t)
