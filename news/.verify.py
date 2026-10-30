import json,os,sys,urllib.request,time
sys.path.insert(0,os.path.join(os.getcwd(),'scripts'))
import push_github as pg
BS=chr(92)
TOKEN=None
for n in ('load_token','read_token','get_token'):
    if hasattr(pg,n): TOKEN=getattr(pg,n)(); break
if TOKEN is None:
    TOKEN=open(os.path.join('..','.workbuddy','github_token.txt')).read().strip()
REPO='guijiequan-spec/guijiequan-spec.github.io'
H={'Authorization':'Bearer '+TOKEN,'Accept':'application/vnd.github+json','User-Agent':'wb'}
def get(u,tries=3):
    for i in range(tries):
        try:
            r=urllib.request.Request(u,headers=H)
            with urllib.request.urlopen(r,timeout=40) as f:
                return json.loads(f.read().decode())
        except Exception:
            if i==tries-1: raise
            time.sleep(3)
br=get('https://api.github.com/repos/%s/branches/main'%REPO)
head=br['commit']['sha']
tree=get('https://api.github.com/repos/%s/git/trees/%s?recursive=1'%(REPO,head))
remote={t['path']:t['sha'] for t in tree['tree'] if t['type']=='blob' and t['path'].startswith('news/')}
print('HEAD',head[:10])
loc={}
for root,d,fs in os.walk('.'):
    for f in fs:
        p=os.path.join(root,f).replace('.','',1).replace(BS,'/')
        p=p[1:] if p.startswith('/') else p
        loc[p]=pg.blob_sha(open(os.path.join(root,f),'rb').read())
ln={k:v for k,v in loc.items() if k.startswith('news/')}
print('local news',len(ln),'remote news',len(remote))
print('only_local',[k for k in ln if k not in remote])
print('only_remote',[k for k in remote if k not in ln])
print('diff',[k for k in ln if k in remote and remote[k]!=ln[k]])
c=get('https://api.github.com/repos/%s/commits/%s'%(REPO,head))
print('commit',c['sha'][:10],'|',c['commit']['message'].splitlines()[0])
print('files',len(c['files']))
for f in c['files']: print('  ',f['status'],f['filename'])
