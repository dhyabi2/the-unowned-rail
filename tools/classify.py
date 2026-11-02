import json,glob,collections,re,sys
CL=[
('operator_call',r"(my|our) (human|operator|owner|principal)|operator('s)? (call|decision|approval)|human('s)? (call|decision)|owner approval|needs? (my )?(human|operator|owner)|(human|operator|owner) (decides|approves|must|would need)|not mine to|above my"),
('own_rail_or_escrow_design',r"(only|exclusively) (settle|accept|take|pay)s?|settles? (in|jobs) |(in|via) (usdc|usdt|usd)\b.{0,40}\b(only|escrow)|escrow|no second rail|not on (the |our |my )?roadmap|not planned|our own (token|credit|rail|ledger)|platform credit|\bFJ\b|rail is (usdc|lightning|fj)|no (lightning|usdc|stables)"),
('no_payer_no_demand',r"no (one|body) (has )?(ever )?(paid|bought|buys|orders)|nobody (has )?(paid|bought|home)|0 jobs|no job|never (been )?settled|no (buyers|demand|counterpart|customers)|counterparties worth|no payer|traffic"),
('price_or_cost_too_small',r"too small|dust|gas|fee[s]? (eat|exceed)|not worth(while)?|microp|sub-?cent|minimum|\bspread\b|slippage"),
('no_wallet_or_cannot_hold',r"(no|not|cannot|can't|don't|do not|never) (have |hold |hold a |control |custody |possess )?(a )?(crypto )?wallet|can't hold|cannot hold|no (private )?key|no funds|do not hold"),
]
CPAY=re.compile(r"\b(xno|nano|usdc|usdt|wallet|settle|settlement|payment|pay|paid|rail|escrow|x402|invoice|checkout|stripe|lightning|bitcoin|crypto|ethereum|base)\b",re.I)
def load():
    out=[]
    for f in sorted(glob.glob('conversations/*.json')):
        try:d=json.load(open(f))
        except: continue
        if 'status' not in d: continue
        a=d['discussions'].get('agent_answered') or []
        if a: out.append((f.split('/')[-1][:-5],d['status'],' '.join(x['text'] for x in a),d))
    return out
if __name__=='__main__':
    A=load();c=collections.Counter();ex=collections.defaultdict(list);rail=0;multi=0
    for name,st,t,d in A:
        if not CPAY.search(t): c['not_about_payment']+=1;continue
        rail+=1
        hits=[k for k,r in CL if re.search(r,t,re.I)]
        if not hits: c['payment_mentioned_no_objection_class']+=1;continue
        for k in hits:
            c[k]+=1
            if len(ex[k])<4:
                m=re.search(CL[[x for x,_ in CL].index(k)][1],t,re.I)
                s=max(0,m.start()-110);ex[k].append((name,t[s:m.end()+110].replace('\n',' ')))
        if len(hits)>1:multi+=1
    print(len(A),rail,multi);
    for k,v in c.most_common():print(k,v)
    json.dump({'n_with_reply':len(A),'payment_related':rail,'counts':c,'examples':ex},open('cls.json','w'),indent=1)
    for k,v in ex.items():
        print('##',k)
        for n,s in v:print(' ',n,'|',s)
