import urllib.request,urllib.parse,xml.etree.ElementTree as ET,json,pathlib,concurrent.futures,hashlib,datetime
root=pathlib.Path(__file__).resolve().parent;root.joinpath('sources').mkdir(exist_ok=True)
def get(item):
 key,url=item;t=datetime.datetime.now(datetime.timezone.utc).isoformat();r={'key':key,'url':url,'acquired_at':t}
 try:
  with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'BCT-stage2-research/1.0'}),timeout=20) as f:b=f.read(4000000);r.update(http_status=f.status,final_url=f.url,content_type=f.headers.get('Content-Type'),sha256=hashlib.sha256(b).hexdigest());root.joinpath('sources',key+'.raw').write_bytes(b)
  if key.startswith('search'):
   r['leads']=[{'title':x.findtext('title'),'url':x.findtext('link'),'description':x.findtext('description')} for x in ET.fromstring(b).findall('.//item')]
 except Exception as e:r.update(error=str(e),classification='CONNECT_BLOCKED' if 'Tunnel connection failed: 403' in str(e) else 'SITE_HTTP_BLOCKED' if 'HTTP Error 403' in str(e) else 'NETWORK_FAILED')
 root.joinpath('sources',key+'.json').write_text(json.dumps(r,ensure_ascii=False,indent=2));return r
if __name__=='__main__':
 import sys
 items=json.loads(pathlib.Path(sys.argv[1]).read_text())
 with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
  for r in pool.map(get,items):print(json.dumps(r,ensure_ascii=False))
