"""One official structured feed: EIA860M, two immutable workbook versions.

Reported status transition is distinct from effective date, qualification,
capacity correction and row disappearance. No AI or operating integration.
"""
from collections import Counter
from io import BytesIO
import re,zipfile,xml.etree.ElementTree as ET
from .store import sha

NS='{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
REL='{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'


def snapshot(raw,period,url):
    raw_hash=sha(raw);archive=zipfile.ZipFile(BytesIO(raw));strings=[]
    if 'xl/sharedStrings.xml'in archive.namelist():
        for _,node in ET.iterparse(archive.open('xl/sharedStrings.xml'),events=('end',)):
            if node.tag==NS+'si':strings.append(''.join(n.text or ''for n in node.iter(NS+'t')));node.clear()
    links={n.get('Id'):n.get('Target')for n in ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))}
    records={};duplicates=[];titles=[]
    for sheet in ET.fromstring(archive.read('xl/workbook.xml')).find(NS+'sheets'):
        if sheet.get('name')not in('Operating','Planned','Retired','Canceled or Postponed'):continue
        target=links[sheet.get(REL+'id')];path=target.lstrip('/')if target.startswith('/')else'xl/'+target
        headers={}
        for _,row in ET.iterparse(archive.open(path),events=('end',)):
            if row.tag!=NS+'row':continue
            cells={}
            for cell in row:
                val=cell.find(NS+'v');text=val.text or ''if val is not None else ''
                if cell.get('t')=='s'and text:text=strings[int(text)]
                elif cell.get('t')=='inlineStr':text=''.join(n.text or ''for n in cell.iter(NS+'t'))
                cells[re.sub(r'\d','',cell.get('r'))]=(text,cell.get('r'))
            number=int(row.get('r'))
            if number==1:titles.extend(t[0]for t in cells.values()if t[0].startswith('Inventory'))
            if number==3:headers={k:v[0].strip()for k,v in cells.items()}
            if number>3:
                fields={headers[k]:v[0]for k,v in cells.items()if k in headers and headers[k]}
                key=(fields.get('Plant ID','').strip(),fields.get('Generator ID','').strip())
                if key[0]and key[1]:
                    record={'id':key,'period':period,'url':url,'raw_sha256':raw_hash,'sheet':sheet.get('name'),'xml_path':path,'row':number,'fields':fields,
                       'cells':{headers[k]:v[1]for k,v in cells.items()if k in headers and headers[k]}}
                    if key in records:duplicates.append(key)
                    else:records[key]=record
            row.clear()
    if not any(period.split('-')[0]in t for t in titles):raise ValueError('SNAPSHOT_YEAR_MISMATCH')
    for key in duplicates:records.pop(key,None)
    return {'period':period,'url':url,'raw_sha256':raw_hash,'records':records,'duplicate_ids_quarantined':duplicates,'titles':titles}


def compare(before,after):
    events=[];unknown=[];corrections=[]
    for key in sorted(set(before['records'])|set(after['records'])):
        a,b=before['records'].get(key),after['records'].get(key)
        if not a or not b:
            unknown.append({'id':key,'type':'ROW_ADDED_OR_MISSING_NOT_STATUS_TRANSITION','before':a,'after':b});continue
        changed={k:[a['fields'].get(k),b['fields'].get(k)]for k in set(a['fields'])|set(b['fields'])if a['fields'].get(k)!=b['fields'].get(k)}
        status=a['fields'].get('Status'),b['fields'].get('Status')
        if status[0]!=status[1]or a['sheet']!=b['sheet']:
            if a['sheet']=='Planned'and b['sheet']=='Operating':kind='REPORTED_BECAME_OPERATING';role='SUPPLY_READINESS_REPORTED'
            elif a['sheet']=='Operating'and b['sheet']=='Retired':kind='REPORTED_RETIREMENT';role='SUPPLY_DECREASE_REPORTED'
            else:kind='STATUS_OR_CLASSIFICATION_CHANGE_UNVERIFIED';role='UNKNOWN'
            events.append({'id':sha([key,before['period'],after['period'],status]),'generator_id':key,'type':kind,'role':role,'before':a,'after':b,'changed_fields':changed,'unit':'MW','qualified_supply':'UNKNOWN','publication_date':'UNKNOWN','s_stage':'UNKNOWN','research_only':True})
        elif changed:corrections.append({'id':key,'type':'VALUE_CHANGE_OR_CORRECTION_NOT_PROVEN_CAPACITY_CHANGE','before':a,'after':b,'changed_fields':changed})
    return {'version':'bct-eia860m-diff-1','events':events,'row_additions_or_missing':unknown,'corrections_or_metadata':corrections,
            'counts':{'events':len(events),'by_type':dict(Counter(x['type']for x in events)),'row_additions_or_missing':len(unknown),'corrections_or_metadata':len(corrections)},'AI_calls':0,'operational_integration_enabled':False}
