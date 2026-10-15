"""Deterministic SEC inline facts and Census monthly rows; never stage decisions."""
import json,re
from decimal import Decimal
from html.parser import HTMLParser
from .quantitative import observation,number
from .store import sha


def census_safe(raw,key):
    """Remove only an explicit credential column; refuse arbitrary key echoes."""
    obj=json.loads(raw)
    if not isinstance(obj,list)or not obj or not isinstance(obj[0],list):raise ValueError('CENSUS_ARRAY_REQUIRED')
    header=obj[0]
    if any(len(row)!=len(header)for row in obj[1:]):raise ValueError('CENSUS_COLUMN_ALIGNMENT')
    remove=[i for i,k in enumerate(header)if k.lower()in {'key','api_key'}]
    safe=[[v for i,v in enumerate(row)if i not in remove]for row in obj]
    encoded=json.dumps(safe,separators=(',',':')).encode()
    if key and key.encode()in encoded:raise ValueError('CENSUS_UNREVIEWED_CREDENTIAL_ECHO')
    return encoded,{'credential_columns_removed':len(remove),'original_hash_not_raw_persisted':sha(raw)}


def parse_trade(raw,meta,direction,codebook_state):
    data=json.loads(raw);head=data[0];out=[];seen=set()
    if len(set(head))!=len(head):raise ValueError('CENSUS_DUPLICATE_COLUMNS')
    codecol='I_COMMODITY'if direction=='imports'else'E_COMMODITY'
    metrics=[('GEN_QY1_MO','PHYSICAL','UNIT_QY1'),('CON_QY1_MO','PHYSICAL','UNIT_QY1'),('GEN_VAL_MO','MONEY',None),('CON_VAL_MO','MONEY',None)]if direction=='imports'else[('QTY_1_MO','PHYSICAL','UNIT_QY1'),('QTY_2_MO','PHYSICAL','UNIT_QY2'),('ALL_VAL_MO','MONEY',None)]
    for i,cells in enumerate(data[1:],1):
        row=dict(zip(head,cells));code=row[codecol];month=row['time'];country=row.get('CTY_CODE','UNKNOWN');df=row.get('DF','NOT_APPLICABLE')
        if not re.fullmatch(r'\d{10}',code)or not re.fullmatch(r'\d{4}-\d{2}',month):raise ValueError('CENSUS_CODE_OR_MONTH_CONTRACT')
        for metric,kind,unitcol in metrics:
            if metric not in row:continue
            unit=row.get(unitcol)if unitcol else'USD'
            if not unit or str(unit).strip()in {'-','N/A'}:continue
            ident=(code,month,country,df,metric)
            if ident in seen:raise ValueError('CENSUS_DUPLICATE_OBSERVATION')
            seen.add(ident)
            r=observation(meta,code+'/'+country+'/'+df,code,metric,row[metric],unit,kind,month,
               {'format':'JSON','path':[i,head.index(metric)]},geography='US/partner-code-'+country,
               stock_or_flow='MONTHLY_TRADE_FLOW_NOT_CUSTOMER_ORDER',lineage='US_CENSUS_INTLTRADE',
               attributes={'trade_direction':direction,'commodity_code_year':month[:4],'codebook_state':codebook_state,
                           'definition':row.get(codecol+'_LDESC','UNKNOWN'),'quantity_flag_original':row.get(metric+'_FLAG','UNKNOWN'),
                           'domestic_foreign_code':df,'qualified_supply':'UNKNOWN','physical_quantity_role':'TRADE_NOT_ACTUAL_ORDER_OR_PRODUCTION'})
            r['parser_version']='bct-q1-census-trade-1'
            if codebook_state!='VERIFIED_ANNUAL_CODE_UNIT':r.update(quality_state='HELD_CODE_REVISION_UNVERIFIED',unknown_reason='Annual official code/unit unresolved; no cross-year join assumed')
            if r['value_decimal_or_null']is not None and Decimal(r['value_decimal_or_null'])==0:
                r.update(quality_state='HELD_ZERO_SEMANTICS',unknown_reason='Reported zero preserved; true-zero flag semantics not independently confirmed')
            out.append(r)
    return out


class InlineFacts(HTMLParser):
    def __init__(self,text):
        super().__init__(convert_charrefs=False);self.text=text;self.offsets=[0]
        for m in re.finditer('\n',text):self.offsets.append(m.end())
        self.contexts={};self.units={};self.current=None;self.current_unit=None;self.fact=None;self.facts=[];self.leaf=None
    def handle_starttag(self,tag,attrs):
        a=dict(attrs);local=tag.split(':')[-1]
        if local=='context':self.current={'id':a.get('id'),'start':None,'end':None};self.contexts[a.get('id')]=self.current
        if local=='unit':self.current_unit={'id':a.get('id'),'measure':None};self.units[a.get('id')]=self.current_unit
        if local=='nonfraction':self.fact={'attrs':a,'chunks':[]}
        self.leaf=local
    def handle_data(self,data):
        line,column=self.getpos();start=self.offsets[line-1]+column
        if self.fact is not None and data.strip():self.fact['chunks'].append((data,start,start+len(data)))
        if self.current is not None and self.leaf in {'startdate','enddate','instant'}:
            if self.leaf=='startdate':self.current['start']=data.strip()
            else:self.current['end']=data.strip()
        if self.current_unit is not None and self.leaf=='measure':self.current_unit['measure']=data.strip()
    def handle_endtag(self,tag):
        local=tag.split(':')[-1]
        if local=='context':self.current=None
        if local=='unit':self.current_unit=None
        if local=='nonfraction'and self.fact is not None:self.facts.append(self.fact);self.fact=None
        self.leaf=None


def parse_sec_inline(raw,meta,cik,accession):
    text=raw.decode('utf-8');parser=InlineFacts(text);parser.feed(text);out=[];held=0;seen=set()
    for fact in parser.facts:
        a=fact['attrs'];name=a.get('name','');unit=parser.units.get(a.get('unitref'),{}).get('measure')
        context=parser.contexts.get(a.get('contextref'),{});chunks=fact['chunks']
        if len(chunks)!=1 or not unit or not context.get('end'):held+=1;continue
        token,start,end=chunks[0];value,flag=number(token)
        if value is None:held+=1;continue
        leafunit=unit.split(':')[-1];money=leafunit.upper()in {'USD','EUR','JPY','GBP'}
        physical=bool(re.fullmatch(r'(?i)(megawatts?|kilowatts?|MW|MWh|kg|tonnes?|metrictons?|vehicles?|barrels?|gallons?|wafers?|units?)',leafunit))and not re.search('share|stock|award|vesting',name,re.I)
        if not physical and not(money and re.search('backlog|purchaseorder|capitalexpend|contractcommit|capex',name,re.I)):continue
        key=(a.get('contextref'),name,unit,token,a.get('scale'),a.get('sign'))
        if key in seen:continue
        seen.add(key)
        r=observation(meta,cik+'/'+str(a.get('contextref')),name,'sec_inline:'+name,token,leafunit,'MONEY'if money else'PHYSICAL',context['end'],
            {'format':'SEC_INLINE','start':start,'end':end,'fact_id':a.get('id'),'context_id':a.get('contextref'),'unit_id':a.get('unitref')},
            stock_or_flow='CONTEXT_PERIOD_NOT_DELIVERY',status='INLINE_FACT_SEMANTICS_PENDING',
            attributes={'accession':accession,'context_id':a.get('contextref'),'ix_name':name,'ix_scale':a.get('scale','0'),'ix_sign':a.get('sign','+'),'qualified_supply':'UNKNOWN','is_actual_order':False})
        scale=int(a.get('scale','0'))
        if not -12<=scale<=12:held+=1;continue
        val=Decimal(value)*(-1 if a.get('sign')=='-'else 1)
        r.update(value_decimal_or_null=format(val,'f'),value_normalized_or_null=format(val*(Decimal(10)**scale),'f'),scale=str(Decimal(10)**scale),period_start=context.get('start')or context['end'],period_end=context['end'],parser_version='bct-q1-sec-inline-1')
        out.append(r)
    return out,{'inline_tags':len(parser.facts),'selected_numeric_facts':len(out),'unresolved_inline_context_or_unit':held}


def parse_codebook_text(text,direction):
    """PDF column text: retain printed HTS parent/statistical suffix and unit lines."""
    lines=text.splitlines();entries=[];parent=None
    for i,line in enumerate(lines):
        if direction=='import':
            m=re.match(r'^\s*(\d{4}\.\d{2}\.\d{2})(?:\s+(\d{2}))?\s+(.+)',line)
            if m:
                parent=m[1].replace('.','');code=parent+m[2]if m[2]else None
            else:
                suffix=re.match(r'^\s{8,22}(\d{2})\s{2,}(.+)',line)
                if suffix and parent:code=parent+suffix[1]
                else:
                    if re.match(r'^\s*\d{4}(?:\.\d{2})?\s',line):parent=None
                    continue
            if code is None:continue
        else:
            m=re.match(r'^\s*(\d{4}\.\d{2}\.\d{4})\s+(.+)',line)
            if not m:continue
            code=m[1].replace('.','')
        unit=None;unitline=None
        for j in range(i,min(i+9,len(lines))):
            if j>i and(re.match(r'^\s*\d{4}(?:\.\d{2})',lines[j])or re.match(r'^\s{8,22}\d{2}\s{2,}',lines[j])):break
            u=re.search(r'(?<!\w)(W\s+kg|kg|t|No\.)\s*(?:\.{2,}|$)',lines[j])
            if u:unit=u[1];unitline=j+1;break
        if unit:entries.append({'code':code,'unit_original':unit,'printed_code_line':i+1,'printed_unit_line':unitline,'line_literal':line.strip()})
    return entries
