import os, requests
tok=os.environ["META_PAGE_TOKEN"]; ig=os.environ["IG_USER_ID"]
r=requests.get(f"https://graph.facebook.com/v26.0/{ig}/insights",params={"metric":"online_followers","period":"lifetime","access_token":tok},timeout=30).json()
if "error" in r: print("ONLINE erro", r["error"].get("message")); raise SystemExit
vals=r["data"][0]["values"]
soma=[0]*24; n=0
for v in vals:
    d=v.get("value") or {}
    if not d: continue
    n+=1
    for h,c in d.items(): soma[(int(h)-3)%24]+=c   # horário do Pacífico? converte abaixo
print("ONLINE dias", n)
print("ONLINE bruto", {k:v for k,v in (vals[-1].get("value") or {}).items()})
