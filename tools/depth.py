#!/usr/bin/env python3
"""XNO order-book depth/spread from saved public snapshots (an/ob_*.json). stdlib only. Reproduce: re-fetch URLs in the report."""
import json,sys,os
D=os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','data','2026-11-02')
def load(n):
    d=json.load(open(f'{D}/ob_{n}.json'))
    if n in('binance','binanceus'): b,a=d['bids'],d['asks']
    elif n=='kraken': r=list(d['result'].values())[0]; b,a=r['bids'],r['asks']
    elif n=='kuc': b,a=d['data']['bids'],d['data']['asks']
    elif n=='gate': b,a=d['bids'],d['asks']
    elif n=='cdc': x=d['result']['data'][0]; b,a=x['bids'],x['asks']
    elif n=='htx': b,a=d['tick']['bids'],d['tick']['asks']
    f=lambda L:[(float(x[0]),float(x[1])) for x in L]
    return sorted(f(b),reverse=True),sorted(f(a))
def vwap_buy(asks,usd):
    spent=0;qty=0
    for p,q in asks:
        take=min(q,(usd-spent)/p); spent+=take*p; qty+=take
        if spent>=usd-1e-9:return spent/qty,True
    return (spent/qty if qty else None),False
def vwap_sell(bids,usd,mid):
    got=0;qty=0;need=usd/mid
    for p,q in bids:
        take=min(q,need-qty); got+=take*p; qty+=take
        if qty>=need-1e-9:return got/qty,True
    return (got/qty if qty else None),False
def row(n):
    b,a=load(n); mid=(b[0][0]+a[0][0])/2
    spread=(a[0][0]-b[0][0])/mid*1e4
    def depth(side,pct,sign):
        lim=mid*(1+sign*pct/100); return sum(p*q for p,q in side if (p>=lim if sign<0 else p<=lim))
    o={'venue':n,'best_bid':b[0][0],'best_ask':a[0][0],'spread_bps':round(spread,1),
       'bid_depth_usd_1pct':round(depth(b,1,-1)),'ask_depth_usd_1pct':round(depth(a,1,1)),
       'bid_depth_usd_2pct':round(depth(b,2,-1)),'ask_depth_usd_2pct':round(depth(a,2,1)),
       'bid_levels':len(b),'ask_levels':len(a)}
    for usd in (10,100,1000,10000):
        v,ok=vwap_buy(a,usd); s,ok2=vwap_sell(b,usd,mid)
        o[f'buy_{usd}_slip_bps']=round((v/mid-1)*1e4,1) if ok else None
        o[f'sell_{usd}_slip_bps']=round((1-s/mid)*1e4,1) if ok2 else None
    return o
if __name__=='__main__':
    out=[row(n) for n in ('binance','binanceus','kraken','kuc','gate','cdc','htx')]
    for o in out:print(o)
    json.dump(out,open(f'{D}/depth_result.json','w'),indent=1)
