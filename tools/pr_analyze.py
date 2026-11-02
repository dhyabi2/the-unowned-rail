import json, re, statistics, datetime, collections
P = json.load(open('prs.json')); M = json.load(open('repos.json'))
LIST_RX = re.compile(r'awesome|\blist\b|-list|directory|catalog|registry|landscape|curated|collection|resources|marketplace|index|toolkit-list|handbook', re.I)
def klass(i):
    m = M.get(i['repo'], {})
    blob = i['repo'] + ' ' + m.get('desc', '') + ' ' + ' '.join(m.get('topics', []))
    return 'list_or_directory' if LIST_RX.search(blob) else 'code_or_docs_repo'
def stars(i):
    s = M.get(i['repo'], {}).get('stars')
    return None if s is None else ('<3k' if s < 3000 else '>=3k')
now = datetime.datetime(2026, 11, 2, tzinfo=datetime.timezone.utc)
def active(i):
    p = M.get(i['repo'], {}).get('pushed')
    if not p: return None
    return (now - datetime.datetime.fromisoformat(p.replace('Z', '+00:00'))).days <= 7
rows = []
for st, items in P.items():
    for i in items: rows.append(dict(i, state=st, klass=klass(i), stars=stars(i), active7=active(i)))
res = {'since': '2026-09-15', 'author': 'dhyabi2', 'total': len(rows), 'by_state': dict(collections.Counter(r['state'] for r in rows))}
def tab(keyf):
    t = collections.defaultdict(lambda: collections.Counter())
    for r in rows: t[keyf(r)][r['state']] += 1
    out = {}
    for k, c in t.items():
        dec = c['merged'] + c['closed_unmerged']
        out[str(k)] = {'merged': c['merged'], 'open': c['open'], 'closed_unmerged': c['closed_unmerged'], 'total': sum(c.values()), 'merge_share_of_decided': round(c['merged'] / dec, 3) if dec else None, 'merge_share_of_all': round(c['merged'] / sum(c.values()), 3)}
    return out
res['by_class'] = tab(lambda r: r['klass'])
res['by_class_stars'] = tab(lambda r: (r['klass'], r['stars']))
res['by_class_stars_active'] = tab(lambda r: (r['klass'], r['stars'], r['active7']))
days = [ (datetime.datetime.fromisoformat(r['closed'].replace('Z','+00:00')) - datetime.datetime.fromisoformat(r['created'].replace('Z','+00:00'))).days for r in rows if r['state']=='merged' and r['closed']]
res['merge_days'] = {'n': len(days), 'median': statistics.median(days), 'min': min(days), 'max': max(days)}
res['merged_with_zero_comments'] = sum(1 for r in rows if r['state']=='merged' and r['comments']==0)
res['open_with_zero_comments'] = sum(1 for r in rows if r['state']=='open' and r['comments']==0)
res['open_older_than_10d'] = sum(1 for r in rows if r['state']=='open' and (now - datetime.datetime.fromisoformat(r['created'].replace('Z','+00:00'))).days > 10)
res['merged_list'] = sorted([(r['repo'], r['n'], r['klass'], r['stars'], r['comments']) for r in rows if r['state']=='merged'])
json.dump(res, open('prs_analysis.json', 'w'), indent=1)
for k in ('total','by_state','by_class','by_class_stars','merge_days','merged_with_zero_comments','open_with_zero_comments','open_older_than_10d'): print(k, json.dumps(res[k]))
print(json.dumps(res['by_class_stars_active']))
for m in res['merged_list']: print(m)
