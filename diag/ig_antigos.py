import os, requests
tok=os.environ["META_PAGE_TOKEN"]; ig=os.environ["IG_USER_ID"]
r=requests.get(f"https://graph.facebook.com/v26.0/{ig}/media",params={"fields":"caption,permalink,timestamp,media_type","limit":40,"access_token":tok},timeout=40).json()
for m in r.get("data",[]):
    print("POST", m["timestamp"][:16], m.get("media_type"), m["permalink"], "|", (m.get("caption") or "").replace("\n"," / ")[:260])
print("PROXIMA", bool(r.get("paging",{}).get("next")), r.get("error"))
for u in ["https://www.africas.com.br/sitemap.xml","https://www.africas.com.br/rss","https://www.africas.com.br/feed"]:
    try:
        x=requests.get(u,timeout=30,headers={"User-Agent":"Mozilla/5.0"}); print("SITE",u,x.status_code,x.headers.get("content-type"),x.text[:300].replace("\n"," "))
    except Exception as e: print("SITE",u,e)
