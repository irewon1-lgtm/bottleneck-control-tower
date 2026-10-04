"""Bounded one-document-per-origin trial using the unchanged BCT collector."""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urljoin,urlsplit
from collections import Counter
import importlib.util,json,hashlib,os
from bct import future_body
from bct.objective_lock import objective_binding
spec=importlib.util.spec_from_file_location('official',Path('.github/scripts/future_official_precursors.py'));collector=importlib.util.module_from_spec(spec);spec.loader.exec_module(collector)
origins=[
 ('us-coal-stocks-aggregate','미국 석탄 재고','AEP','https://www.aep.com/investors/',['annual','report','2025','2026']),
 ('us-coal-stocks-aggregate','미국 석탄 재고','Peabody Energy','https://www.peabodyenergy.com/',['annual','2025','2026','report']),
 ('us-coal-stocks-aggregate','미국 석탄 재고','Core Natural Resources','https://investors.corenaturalresources.com/',['annual','2025','2026','report']),
 ('us-lng-liquefaction','미국 LNG','JERA','https://www.jera.co.jp/en/news/information',['lng','purchase','agreement','u.s.','united states','american']),
 ('us-lng-liquefaction','미국 LNG','Bechtel','https://www.bechtel.com/projects/',['golden','lng','project']),
 ('us-lng-liquefaction','미국 LNG','Venture Global','https://venturegloballng.com/',['lng','plaque','cp2','press','news']),
 ('iceye-military-sar-satellites','ICEYE 군사용 SAR','Polish Ministry of National Defence','https://www.gov.pl/web/obrona-narodowa/szukaj?query=ICEYE',['iceye','mikrosar','satelit','radar']),
 ('iceye-military-sar-satellites','ICEYE 군사용 SAR','Finnish Ministry of Defence','https://www.defmin.fi/en',['iceye','sar','satelli']),
 ('iceye-military-sar-satellites','ICEYE 군사용 SAR','German Bundeswehr','https://www.bundeswehr.de/de/organisation/ausruestung-baainbw',['iceye','sar-satell','spock'])]
allowed={urlsplit(x[3]).hostname for x in origins}|{'www.gov.fi','valtioneuvosto.fi','www.venturegloballng.com','aep.com','bechtel.com','www.bechtel.com','www.peabodyenergy.com','peabodyenergy.com','peabodyenergy.investorroom.com'}
class Links(HTMLParser):
 def __init__(self):super().__init__();self.links=[];self.current=None
 def handle_starttag(self,t,a):
  if t=='a':self.current=[dict(a).get('href',''),'']
 def handle_data(self,s):
  if self.current:self.current[1]+=s
 def handle_endtag(self,t):
  if t=='a' and self.current:self.links.append(tuple(self.current));self.current=None
sources=[];trials=[];responses={}
for tid,target,org,seed,keys in origins:
 try:
  response=collector.fetch(seed,allowed);parser=Links();parser.feed(response.get('html',''));choices=[]
  for href,title in parser.links:
   u=urljoin(response.get('final_url') or seed,href)
   if u==seed or urlsplit(u).hostname not in allowed or '#' in u or not u.startswith('https://'):continue
   # Follow only links within this organization's explicitly frozen hosts.
   hosts={urlsplit(seed).hostname}
   if org=='Venture Global':hosts.add('www.venturegloballng.com')
   if org=='Peabody Energy':hosts|={'peabodyenergy.com','peabodyenergy.investorroom.com'}
   if org=='Finnish Ministry of Defence':hosts|={'www.gov.fi','valtioneuvosto.fi'}
   if urlsplit(u).hostname not in hosts:continue
   score=sum(k.casefold() in (title+' '+u).casefold() for k in keys)
   if score>=2 or (org.startswith(('Polish','Finnish','German')) and score>=1):choices.append((score,u,title))
  choices.sort(key=lambda x:(-x[0],x[1]));chosen=choices[0][1] if choices else seed
  trials.append({'target_id':tid,'organization':org,'locator_url':seed,'locator_http_status':response.get('status'),'final_url':response.get('final_url'),'candidate_document_url':chosen,'candidate_title':choices[0][2] if choices else None,'matched_links':choices[:12],'links_followed':1 if chosen!=seed else 0})
  if chosen==seed:responses[seed]=response
 except Exception as exc:
  trials.append({'target_id':tid,'organization':org,'locator_url':seed,'error':type(exc).__name__,'http_status':getattr(exc,'code',None)});chosen=seed
 sources.append({'target_id':tid,'target':target,'organization':org,'url':chosen,'host':urlsplit(chosen).hostname,'official_document':True,'required_roles':['future_demand','independent_capacity','ramp_delivery'],'locator_only':chosen==seed})
manifest={**objective_binding(),'allowed_domains':sorted(allowed),'documents':sources,'extractor_sha256':hashlib.sha256(Path(future_body.__file__).read_bytes()).hexdigest()}
def fetch(u,domains):return responses[u] if u in responses else collector.fetch(u,domains)
snapshot=collector.collect(manifest,'/tmp/three-target-snapshot.json','/tmp/three-target-body-cache',fetcher=fetch,run_id=os.environ.get('GITHUB_RUN_ID','LOCAL'))
snapshot['bounded_origin_trials']=trials;snapshot['origin_limit_per_target']=3;snapshot['no_detection_or_operational_writes']=True
Path('three-target-snapshot.json').write_text(json.dumps(snapshot,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'documents':len(snapshot['documents']),'statuses':dict(Counter(d['body_status'] for d in snapshot['documents']))}))
