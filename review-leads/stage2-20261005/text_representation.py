from html.parser import HTMLParser
from pathlib import Path
import json
class P(HTMLParser):
 def __init__(self):super().__init__();self.skip=0;self.text=[];self.links=[];self.metas=[]
 def handle_starttag(self,t,a):
  d=dict(a)
  if t in ['script','style']:self.skip+=1
  if t=='a' and d.get('href'):self.links.append(d['href'])
  if t=='meta':self.metas.append(d)
 def handle_endtag(self,t):
  if t in ['script','style'] and self.skip:self.skip-=1
 def handle_data(self,d):
  if not self.skip and d.strip():self.text.append(d.strip())
for p in (Path(__file__).resolve().parent/'sources').glob('*.raw'):
 if p.stem.startswith('search'):continue
 s=P();s.feed(p.read_text(errors='replace'));p.with_suffix('.txt').write_text('\n'.join(s.text));p.with_suffix('.page.json').write_text(json.dumps({'links':s.links,'meta':s.metas},indent=2));print(p.stem,'\n'.join(s.text)[:17000]);print('LINKS',s.links)
