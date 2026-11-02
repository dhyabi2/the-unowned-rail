#!/usr/bin/env python3
"""Read blocks from public nodes (quorum of 2). stdlib. usage: blocks.py HASH... -> JSON"""
import json,sys,time,urllib.request
NODES=["https://rainstorm.city/api","https://rpc.nano.to","https://node.somenano.com/proxy","https://app.natrium.io/api"]
def rpc(u,b,t=25):
    r=urllib.request.Request(u,json.dumps(b).encode(),{"Content-Type":"application/json","User-Agent":"xno-evidence/1.0"})
    return json.load(urllib.request.urlopen(r,timeout=t))
def read(h):
    out=[]
    for u in NODES:
        try:
            d=rpc(u,{"action":"blocks_info","hashes":[h],"json_block":"true"})
            b=d.get("blocks",{}).get(h)
            if b: out.append((u,b))
            else: out.append((u,{"error":str(d)[:80]}))
        except Exception as e: out.append((u,{"error":type(e).__name__}))
        if sum(1 for _,x in out if 'error' not in x)>=2:break
    return out
if __name__=="__main__":
    res={}
    for h in sys.argv[1:]:
        r=read(h);good=[x for _,x in r if 'error' not in x]
        if not good: res[h]={"found":False,"tries":[(u,x) for u,x in r]};continue
        g=good[0]
        res[h]={"found":True,"nodes_agreeing":len(good),"confirmed":g.get("confirmed"),"subtype":g.get("subtype"),"account":g["block_account"],"amount_raw":g["amount"],"amount_xno":str(int(g["amount"])/10**30),"time_utc":time.strftime("%Y-%m-%d %H:%M:%SZ",time.gmtime(int(g["local_timestamp"]))) if g.get("local_timestamp") not in (None,"0") else None,"link_as_account":g["contents"].get("link_as_account"),"height":g.get("height"),"source_account":g.get("source_account")}
    print(json.dumps(res,indent=1))
