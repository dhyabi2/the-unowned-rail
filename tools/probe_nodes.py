#!/usr/bin/env python3
"""Probe public Nano RPC endpoints: reachability, latency, agreement on one confirmed block. stdlib only."""
import json,time,sys,socket,urllib.request,urllib.parse,statistics
NODES=["https://rpc.nano.to","https://rainstorm.city/api","https://node.somenano.com/proxy","https://nanoslo.0x.no/proxy","https://app.natrium.io/api","https://rpc.nano-gpt.com"]
ACC="nano_3m8cz87zwxb1y16ob4bzp1eyek78qaig8ktohk7d45b18sh6u9exbowbnekr"
def rpc(u,body,t=25):
    r=urllib.request.Request(u,json.dumps(body).encode(),{"Content-Type":"application/json","User-Agent":"nano-node-probe/1.0"})
    t0=time.time()
    with urllib.request.urlopen(r,timeout=t) as f: d=json.load(f)
    return d,time.time()-t0
def sample(n,gap):
    res={u:{"ok":0,"fail":0,"lat":[],"errs":[]} for u in NODES}
    for i in range(n):
        for u in NODES:
            try:
                d,dt=rpc(u,{"action":"account_info","account":ACC,"representative":"true"})
                if d.get("frontier") and d.get("balance"): res[u]["ok"]+=1;res[u]["lat"].append(dt)
                else: res[u]["fail"]+=1;res[u]["errs"].append(str(d)[:60])
            except Exception as e: res[u]["fail"]+=1;res[u]["errs"].append(type(e).__name__+str(e)[:40])
        if i<n-1: time.sleep(gap)
    return res
def detail():
    out={}
    for u in NODES:
        o={}
        try:
            d,_=rpc(u,{"action":"version"});o["version"]=d.get("node_vendor"),d.get("network")
        except Exception as e:o["version"]=None
        try:
            d,_=rpc(u,{"action":"account_info","account":ACC,"representative":"true"});o["frontier"]=d.get("frontier");o["balance"]=d.get("balance");o["conf_height"]=d.get("confirmation_height")
        except Exception as e:o["frontier"]=None
        try:
            d,_=rpc(u,{"action":"block_count"});o["block_count"]=d.get("count");o["cemented"]=d.get("cemented")
        except Exception:pass
        h=urllib.parse.urlparse(u).hostname
        try:o["ips"]=sorted({a[4][0] for a in socket.getaddrinfo(h,443,socket.AF_INET)})
        except Exception:o["ips"]=[]
        out[u]=o
    return out
if __name__=="__main__":
    n=int(sys.argv[1]) if len(sys.argv)>1 else 20;gap=float(sys.argv[2]) if len(sys.argv)>2 else 15
    t0=time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime())
    det=detail();res=sample(n,gap)
    for u in NODES:
        l=sorted(res[u]["lat"]);det[u]["samples"]=n;det[u]["ok"]=res[u]["ok"];det[u]["fail"]=res[u]["fail"]
        det[u]["median_s"]=round(statistics.median(l),3) if l else None
        det[u]["p95_s"]=round(l[min(len(l)-1,int(len(l)*.95))],3) if l else None
        det[u]["errs"]=res[u]["errs"][:3]
    json.dump({"started":t0,"ended":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),"interval_s":gap,"nodes":det},open(sys.argv[3] if len(sys.argv)>3 else "nodes.json","w"),indent=1)
    print(json.dumps(det,indent=1))
