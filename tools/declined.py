import json,glob,re,collections
R=[
('test_or_blank_record', r"^(NOTE:)?(test|ownership probe|test claim check)?\s*$"),
('explicit_no_by_agent_or_maintainer', r"not planned|out of scope|polite pass|no interest|we won'?t accept|staying (on|with|lightning)|will stay with|do not support a nano|nano \(xno\) isn't on the list|no support for cryptocurrency|accept usdc on base only|not adding|i don'?t take part|answer, plainly: no|lane is closed|i am not adding"),
('operator_or_human_decides', r"my operator|human gates|human-in-the-loop|needs? (yabibal|operator)|operator('s)? (call|decision)|money is his decision|awaiting_human|human authorization|requires? operator|human-run|operator contact|my human"),
('no_demand_or_no_spenders', r"demand, not rail|rail with no spenders|nobody home|zero repeat organic|0 real adopting|no job|not worthwhile|without realized revenue|counterparties worth|no human buyer"),
('no_wallet_or_cannot_spend', r"do not possess a crypto wallet|not an autonomous agent that can decide to hold|cannot receive any payments|no wallet|no wallet and no payment|not a payments processor|no rail, no wallet|holds? no xno|i hold no xno|read-only observer|no settlement"),
('no_conversational_channel_or_template', r"template|same (static|canned|guide|result)|fixed (jsonrpc|loop|catalog|guide)|no (free-form|conversational|chat) (channel|surface)|not (a )?conversable|not an agent|service card|service-card|catalog echo|routes? by keyword|404|405|no a2a endpoint|moltbook login required|not messageable|human-facing web app|dead|not autonomous|directory card|not a conversion target|no live surface|ephemeral|returns? (a )?(fixed|static)|accepts one data part|read-only routing|requires agent registration|only surface|never written|not contacted before|fresh find|hunting ground|new hunting|front door|empty body"),
('usdc_or_other_rail_declared_no_nano', r"usdc|x402|stripe|card|lightning|credit|ccd|xrp|escrow|\bFJ\b|solana|base\b|no nano|outside nano|jey|platform"),
]
c=collections.Counter();lst=[]
for f in sorted(glob.glob('conversations/*.json')):
    try:d=json.load(open(f))
    except: continue
    if d.get('status')!='declined':continue
    a=' '.join(x['text'] for x in d['discussions'].get('agent_answered',[]))
    t=(a+' || '+d.get('note','')).strip()
    cls='other_unclassified'
    for k,r in R:
        if re.search(r,t,re.I) or (k=='test_or_blank_record' and len(d.get('note',''))<8 and not a): cls=k;break
    c[cls]+=1;lst.append((f.split('/')[-1][:-5],cls))
print(sum(c.values()));
for k,v in c.most_common():print(k,v)
OV={}
for n in ['fairline','Lukas-Blomqvist','spawn3']:OV[n]='no_demand_or_no_spenders'
for n in ['AgentBroker','BotHub','DecisionAnchor','GF-Agent-Toll','Perkoon','PoolParty','GanjaMon','Hive','UCP-Playground']:OV[n]='no_conversational_channel_or_template'
for n in ['HERE','BABYDOV-Agent-Microstore','Onyx-0n1x--trust-layer','AlgoVoi']:OV[n]='usdc_or_other_rail_declared_no_nano'
for n in ['Cape-Partners-Exchange','pipnyc']:OV[n]='no_wallet_or_cannot_spend'
rows=[(n,OV.get(n,k)) for n,k in lst]
json.dump({'rows':rows,'counts':collections.Counter(k for _,k in rows),'overrides':OV},open('declined_final.json','w'),indent=0)
print('after manual overrides:',dict(collections.Counter(k for _,k in rows)))
