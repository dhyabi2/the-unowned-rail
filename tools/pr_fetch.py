import subprocess, json, time, sys
def gh(args):
    for i in range(5):
        r = subprocess.run(['gh', 'api'] + args, capture_output=True, text=True)
        if r.returncode == 0: return json.loads(r.stdout)
        if 'rate limit' in r.stderr.lower() or '403' in r.stderr: time.sleep(30 + 30*i); continue
        print('ERR', r.stderr[:200], file=sys.stderr); return None
    return None
out = {}
for label, q in (('merged', 'is:merged'), ('open', 'is:open'), ('closed_unmerged', 'is:closed is:unmerged')):
    items = []
    for page in range(1, 6):
        d = gh(['-X', 'GET', 'search/issues', '-f', f'q=author:dhyabi2 type:pr {q} -user:dhyabi2 created:>=2026-09-15', '-f', 'per_page=100', '-f', f'page={page}'])
        if not d: break
        for it in d['items']:
            items.append({'repo': it['repository_url'].split('repos/')[1], 'n': it['number'], 'title': it['title'], 'created': it['created_at'], 'closed': it.get('closed_at'), 'comments': it['comments'], 'url': it['html_url']})
        time.sleep(6)
        if len(d['items']) < 100: break
    print(label, len(items), file=sys.stderr)
    out[label] = items
json.dump(out, open('prs.json', 'w'))
repos = sorted({i['repo'] for v in out.values() for i in v})
meta = {}
for r in repos:
    d = gh([f'repos/{r}'])
    if d: meta[r] = {'stars': d['stargazers_count'], 'pushed': d['pushed_at'], 'archived': d['archived'], 'desc': (d.get('description') or '')[:100], 'topics': d.get('topics', []), 'fork': d['fork']}
    time.sleep(0.3)
json.dump(meta, open('repos.json', 'w'))
print('repos', len(repos), len(meta), file=sys.stderr)
