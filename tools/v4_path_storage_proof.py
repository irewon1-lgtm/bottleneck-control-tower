import sqlite3,json,pathlib,hashlib,shutil,subprocess
from bct.v4.store import Ledger,now
r=pathlib.Path('var/v4/path-comparison');out={}
def digest(db):
 c=sqlite3.connect(db.as_uri()+'?mode=ro',uri=True);stats={}
 for table in ['metadata','blobs','documents','captures','readings','runs','firsts','events']:
  h=hashlib.sha256();rows=c.execute('SELECT * FROM '+table+' ORDER BY rowid').fetchall()
  for row in rows:
   for v in row:
    b=v if isinstance(v,bytes) else json.dumps(v,ensure_ascii=False).encode();h.update(len(b).to_bytes(8,'big'));h.update(b)
  stats[table]={'rows':len(rows),'sha256':h.hexdigest()}
 assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok';c.close();return stats
for name in ['oracle-ledger','model-r2-ledger','structured-ledger','final-events']:
 root=r/name
 if not (root/'v4.sqlite3').exists():continue
 backup=r/'final-storage-backups-v2'/name/'v4.sqlite3';restored=r/'final-storage-restored-v2'/name/'v4.sqlite3'
 l=Ledger(root);l.backup(backup);l.close();restored.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(backup,restored)
 a=digest((root/'v4.sqlite3').resolve());b=digest(backup.resolve());c=digest(restored.resolve());assert a==b==c
 l=Ledger(restored.parent);l.close();assert digest(restored.resolve())==a
 out[name]={'status':'PASS','tables':a,'backup_restore_restart_exact':True}
a=sqlite3.connect('var/v4/quality/backup/v4.sqlite3');b=sqlite3.connect('var/v4/sequential/api-ledger/v4.sqlite3')
old=a.execute('SELECT * FROM events ORDER BY seq').fetchall();current=b.execute('SELECT * FROM events WHERE seq<=? ORDER BY seq',(old[-1][0],)).fetchall();assert old==current
out['historical_API_prefix']={'rows':len(old),'unchanged':True}
old_paths=subprocess.check_output(['git','ls-tree','-r','--name-only','1827b590ec3eda9dc9125a5890d8eff1734dffe3','docs/v4'],text=True).splitlines();count=0
for p in old_paths:
 if p in ['docs/v4/PROGRESS.json','docs/v4/EXECUTION_PLAN.md']:continue
 oldcontent=subprocess.check_output(['git','show','1827b590ec3eda9dc9125a5890d8eff1734dffe3:'+p]);assert pathlib.Path(p).read_bytes()==oldcontent,p;count+=1
out['historical_tracked_evidence']={'files_unchanged':count};out['at']=now()
pathlib.Path('docs/v4/path-comparison/final-storage-proof.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:{'PASS':True,'rows':v.get('rows'),'files':v.get('files_unchanged')}for k,v in out.items()if isinstance(v,dict)}))
