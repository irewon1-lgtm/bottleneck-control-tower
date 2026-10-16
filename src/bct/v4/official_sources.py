"""Source-format adapters for Q1/Q2 research, never candidate promotion.

Retains field-level native pointers. A release, queue project, or trade row is
not automatically an order or available supply. Native files stay in the local
acquisition cache; the existing private capsule receives numerical facts/IDs.
"""
import csv
from datetime import datetime, timezone
from io import StringIO
import json
import re
from urllib.parse import urlsplit, parse_qsl

from .store import sha
from .quantitative import number

KIND = 'QUANTITATIVE_OFFICIAL_FACT'
VERSION = 'bct-official-formats-1'
HOSTS = {
    'find_tender': {'www.find-tender.service.gov.uk'},
    'contracts_finder': {'www.contractsfinder.service.gov.uk'},
    'gleif': {'api.gleif.org'}, 'miso': {'www.misoenergy.org'},
    'world_bank': {'search.worldbank.org'},
    'federal_register': {'www.federalregister.gov'},
    'neso': {'api.neso.energy'}, 'comtrade': {'comtradeapi.un.org'},
    'bgs': {'ogcapi.bgs.ac.uk'}, 'ercot': {'www.ercot.com'},
    'prodcom': {'ec.europa.eu'}, 'comext': {'ec.europa.eu'},
    'sam_opportunities': {'api.sam.gov'}, 'sam_awards': {'api.sam.gov'},
    'opendart': {'opendart.fss.or.kr'}, 'edinet': {'api.edinet-fsa.go.jp'},
    'companies_house': {'api.company-information.service.gov.uk'},
    'regulations': {'api.regulations.gov'}, 'estat': {'api.e-stat.go.jp'},
    'kosis': {'kosis.kr'}, 'entsoe': {'web-api.tp.entsoe.eu'},
    'korea_pps': {'apis.data.go.kr'},
    'doe_haleu': {'www.energy.gov'}, 'chips': {'www.nist.gov'},
}
FIELDS = set('source_id url source_hash acquired_at native_id logical_id id format record_kind source_lineage published_at publication_basis first_publication_verified claims unknowns research_only s_stage qualified_supply independence evidence_scope'.split())
CLAIMS = set('notice_id ocid release_tags status procurement_category classification_code classification_scheme product_label buyer_id buyer_name supplier_id supplier_name contract_id award_id award_date signed_date period_start period_end delivery_date item_quantity item_unit amount currency framework_amendment facility_id facility_type project_id project_status geography transmission_owner connection_customer summer_net_MW winter_net_MW connected_MW capacity_change_MW cumulative_MW planned_service_date application_date lei legal_name legal_jurisdiction entity_status registration_last_update publication_date publication_type project_country project_name notice_type notice_status trade_quantity trade_unit_code trade_net_weight_kg trade_value_USD trade_period commodity_code reporter_code partner_code flow_code is_estimated is_aggregate statistic_value statistic_unit statistic_period statistic_product statistic_country statistic_type generation_type dataset_update legal_form parent_lei'.split())
CLAIMS.update({'reported_project_MW', 'commissioning_status', 'approval_date', 'cancellation_date', 'statistic_flag', 'statistic_figure_notes'})
CLAIMS.add('procurement_id')
CLAIMS.update({'lot_id', 'lot_status'})
CLAIMS.add('reported_item_quantity_literal')
CLAIMS.update({'material_specification_literal', 'program_funding_literal', 'investment_literal', 'facility_region_literal', 'technology_literal', 'program_duration_literal', 'procurement_eligibility_literal', 'conditional_allocation_literal', 'counterevidence_literal', 'regulatory_condition_literal'})
KINDS = {'PROCUREMENT_TENDER', 'PROCUREMENT_AWARD', 'PROCUREMENT_CONTRACT',
         'PROCUREMENT_NOTICE', 'LEGAL_ENTITY', 'CONNECTION_PROJECT',
         'REGULATORY_DOCUMENT', 'TRADE_STATISTIC', 'PRODUCTION_STATISTIC'}
KINDS.add('PROGRAM_CONTEXT_NOT_QUALIFIED_SUPPLY')
SENSITIVE = re.compile(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|gh[pousr]_[A-Za-z0-9]{20,}|Bearer\s+\S+', re.I)
MW_FIELDS = {'summer_net_MW', 'winter_net_MW', 'connected_MW', 'capacity_change_MW', 'cumulative_MW', 'reported_project_MW'}
NUMERIC = MW_FIELDS | {'amount', 'item_quantity', 'trade_quantity', 'trade_net_weight_kg', 'trade_value_USD', 'statistic_value'}


def _unit(name, claims):
    if name in MW_FIELDS: return 'MW', 'NATIVE_MW_FIELD_OR_VERIFIED_MW_COLUMN_HEADER'
    if name == 'amount': return claims.get('currency', {}).get('value', 'UNKNOWN'), 'NATIVE_CURRENCY_FIELD'
    if name == 'item_quantity': return claims.get('item_unit', {}).get('value', 'UNKNOWN'), 'NATIVE_ITEM_UNIT_FIELD'
    if name == 'trade_net_weight_kg': return 'kg', 'UN_COMTRADE_NETWGT_DEFINITION'
    if name == 'trade_value_USD': return 'USD', 'UN_COMTRADE_PRIMARYVALUE_DEFINITION_NOT_QUANTITY'
    if name == 'trade_quantity':
        # This exact code8 entry was live-verified in the official reference.
        code = claims.get('trade_unit_code', {}).get('value')
        return ('kg' if code == 8 else 'UNKNOWN'), 'https://comtradeapi.un.org/files/v1/app/reference/QuantityUnits.json#qtyCode='+str(code)
    if name == 'statistic_value': return claims.get('statistic_unit', {}).get('value', 'UNKNOWN'), 'NATIVE_STATISTIC_UNIT_FIELD'
    raise ValueError('UNREVIEWED_NUMERIC_UNIT')


def safe_url(source, url):
    u = urlsplit(url)
    if (u.scheme != 'https' or u.hostname not in HOSTS.get(source, set())
            or u.username or u.password or u.fragment
            or any(re.search('token|key|auth|session|secret|password', k, re.I)
                   for k, _ in parse_qsl(u.query))):
        raise ValueError('OFFICIAL_SOURCE_URL_NOT_REVIEWED')
    return url


def pointer(data, path):
    """Exact RFC6901 traversal, never fuzzy text or first-occurrence matching."""
    if path == '': return data
    if not path.startswith('/'): raise ValueError('JSON_POINTER_REQUIRED')
    for token in path[1:].split('/'):
        token = token.replace('~1', '/').replace('~0', '~')
        data = data[int(token)] if isinstance(data, list) else data[token]
    return data


def _day(value):
    try:
        datetime.fromisoformat(value.replace('Z', '+00:00'))
        return True
    except (ValueError, TypeError): return False


def record(meta, native_id, kind, data, selectors, *, published=None,
           publication_basis='UNKNOWN', lineage=None, csv_row=None, xlsx_sheet=None):
    """Create only exact scalar claims; absent fields remain explicit UNKNOWN.

    CSV selectors use column names and logical record numbers (quoted multiline
    cells do not change record numbering). No source prose/contact is archived.
    """
    safe_url(meta['source_id'], meta['url'])
    claims = {}; unknowns = []
    for name, selector in selectors.items():
        if name not in CLAIMS: raise ValueError('UNREVIEWED_FACT_FIELD')
        try:
            if isinstance(selector, dict):
                value = data[selector['start']:selector['end']] if selector.get('raw_utf8_html') else pointer(data, selector['pointer'])[selector['start']:selector['end']]
            else: value = data[selector] if csv_row is not None or xlsx_sheet is not None else pointer(data, selector)
        except (KeyError, IndexError, TypeError): value = None
        if value is None or value == '' or isinstance(value, dict):
            unknowns.append(name); continue
        if (len(json.dumps(value)) > 700 or SENSITIVE.search(json.dumps(value))
                or (isinstance(value, list) and not all(isinstance(v, str) for v in value))):
            unknowns.append(name + ':UNSAFE_OR_UNSUPPORTED_FIELD'); continue
        loc = ({'format': 'UTF8_HTML_CHARACTER_SPAN', 'start': selector['start'], 'end': selector['end']} if isinstance(selector, dict) and selector.get('raw_utf8_html') else
               {'format': 'JSON_STRING_SPAN', **selector} if isinstance(selector, dict) else
               {'format': 'XLSX_CELL', 'sheet': xlsx_sheet, 'cell': selector, 'datetime_rule': 'EXCEL_DATETIME_ISO'} if xlsx_sheet is not None else
               {'format': 'CSV_RECORD', 'record': csv_row, 'column': selector} if csv_row is not None else {'format': 'JSON_POINTER', 'pointer': selector})
        claims[name] = {'value': value, 'locator': loc}
    for name in claims:
        if name in NUMERIC:
            claims[name]['unit'], claims[name]['unit_basis'] = _unit(name, claims)
    if published and _day(published):
        pub = published
    else: pub = 'UNKNOWN'; publication_basis = 'UNKNOWN'
    logical = sha([meta['source_id'], str(native_id), kind])
    row = dict(source_id=meta['source_id'], url=meta['url'], source_hash=meta['sha256'],
               acquired_at=meta['acquired_at'], native_id=str(native_id), logical_id=logical,
               format=VERSION, record_kind=kind, source_lineage=lineage or meta['source_id'],
               published_at=pub, publication_basis=publication_basis,
               first_publication_verified=False, claims=claims, unknowns=sorted(unknowns),
               research_only=True, s_stage='UNKNOWN', qualified_supply='UNKNOWN',
               independence='NOT_VERIFIED',
               evidence_scope='EXACT_NATIVE_FIELD_CHECKED_AT_ACQUISITION_NATIVE_NOT_IN_CAPSULE')
    row['id'] = sha([logical, meta['sha256'], claims, pub])
    validate(row)
    return row


def validate(row):
    if set(row) != FIELDS: raise ValueError('OFFICIAL_FACT_FIELDS')
    safe_url(row['source_id'], row['url'])
    if row['format'] != VERSION or row['record_kind'] not in KINDS: raise ValueError('OFFICIAL_FACT_KIND')
    if (row['research_only'] is not True or row['s_stage'] != 'UNKNOWN'
            or row['qualified_supply'] != 'UNKNOWN' or row['independence'] != 'NOT_VERIFIED'
            or row['first_publication_verified'] is not False):
        raise ValueError('OFFICIAL_FACT_UNVERIFIED_PROMOTION')
    if not re.fullmatch('[0-9a-f]{64}', row['source_hash']): raise ValueError('OFFICIAL_FACT_HASH')
    if row['published_at'] != 'UNKNOWN' and not _day(row['published_at']): raise ValueError('OFFICIAL_FACT_DATE')
    if not row['claims'] or set(row['claims']) - CLAIMS: raise ValueError('OFFICIAL_FACT_CLAIMS')
    for name, claim in row['claims'].items():
        expected = {'value', 'locator', 'unit', 'unit_basis'} if name in NUMERIC else {'value', 'locator'}
        if set(claim) != expected: raise ValueError('OFFICIAL_FACT_CLAIM_FIELDS')
        if name in NUMERIC and (claim['unit'], claim['unit_basis']) != _unit(name, row['claims']): raise ValueError('OFFICIAL_FACT_UNIT_CHANGED')
        loc = claim['locator']
        if loc.get('format') == 'JSON_POINTER':
            if set(loc) != {'format', 'pointer'} or not loc['pointer'].startswith('/'): raise ValueError('OFFICIAL_FACT_POINTER')
        elif loc.get('format') == 'JSON_STRING_SPAN':
            if set(loc) != {'format', 'pointer', 'start', 'end'} or not loc['pointer'].startswith('/') or type(loc['start']) is not int or type(loc['end']) is not int or not 0 <= loc['start'] < loc['end']: raise ValueError('OFFICIAL_FACT_STRING_SPAN')
        elif loc.get('format') == 'UTF8_HTML_CHARACTER_SPAN':
            if set(loc) != {'format', 'start', 'end'} or type(loc['start']) is not int or type(loc['end']) is not int or not 0 <= loc['start'] < loc['end']: raise ValueError('OFFICIAL_FACT_HTML_SPAN')
        elif loc.get('format') == 'CSV_RECORD':
            if set(loc) != {'format', 'record', 'column'} or type(loc['record']) is not int or loc['record'] < 1: raise ValueError('OFFICIAL_FACT_CSV_POSITION')
        elif loc.get('format') == 'XLSX_CELL':
            if set(loc) != {'format', 'sheet', 'cell', 'datetime_rule'} or not re.fullmatch('[A-Z]+[1-9][0-9]*', loc['cell']) or loc['datetime_rule'] != 'EXCEL_DATETIME_ISO': raise ValueError('OFFICIAL_FACT_CELL')
        else: raise ValueError('OFFICIAL_FACT_LOCATOR')
        if name in NUMERIC:
            if number(claim['value'])[0] is None: raise ValueError('OFFICIAL_FACT_NONNUMERIC')
    if 'item_quantity' in row['claims']:
        unit = row['claims'].get('item_unit', {}).get('value', '')
        if not unit or str(unit).upper() in {'USD', 'GBP', 'EUR', 'KRW', 'JPY', '$', '£', '€'}: raise ValueError('OFFICIAL_FACT_QUANTITY_UNIT_NOT_PHYSICAL')
    if SENSITIVE.search(json.dumps(row)): raise ValueError('OFFICIAL_FACT_SENSITIVE')
    logical = sha([row['source_id'], row['native_id'], row['record_kind']])
    if row['logical_id'] != logical or row['id'] != sha([logical, row['source_hash'], row['claims'], row['published_at']]): raise ValueError('OFFICIAL_FACT_ID')


def recheck(row, data):
    """Native source supplied explicitly; a capsule hash alone cannot do this."""
    validate(row)
    for claim in row['claims'].values():
        loc = claim['locator']
        if loc['format'] == 'CSV_RECORD': actual = data[loc['record'] - 1][loc['column']]
        elif loc['format'] == 'JSON_STRING_SPAN': actual = pointer(data, loc['pointer'])[loc['start']:loc['end']]
        elif loc['format'] == 'UTF8_HTML_CHARACTER_SPAN': actual = data[loc['start']:loc['end']]
        elif loc['format'] == 'XLSX_CELL':
            actual = data[loc['sheet']][loc['cell']].value
            if isinstance(actual, datetime): actual = actual.isoformat()
        else: actual = pointer(data, loc['pointer'])
        if type(actual) is not type(claim['value']) or actual != claim['value']: raise ValueError('OFFICIAL_FACT_NATIVE_MISMATCH')
    return len(row['claims'])


def reviewed_item_descriptions(data, meta, annotations):
    """Explicit source review, not automatic order adoption or independent truth.

    A reviewed unique field/anchor disambiguates short repeated words. The
    entire field hash and parent lot state remain checked; contradictions are
    retained. No fuzzy matching, rewriting, or unlocated quantity conversion.
    """
    out = []
    for annotation in annotations:
        indices = [i for i, rel in enumerate(data['releases']) if rel['id'] == annotation['notice_id']]
        if not indices: continue
        if len(indices) != 1: raise ValueError('REVIEW_NOTICE_AMBIGUOUS')
        i = indices[0]; rel = data['releases'][i]; base = f'/releases/{i}'
        selectors = {'notice_id': base+'/id', 'ocid': base+'/ocid', 'buyer_id': base+'/buyer/id', 'buyer_name': base+'/buyer/name', 'lot_status': base+'/tender/lots/0/status'}
        for name, review in annotation['fields'].items():
            p = base+review['relative_pointer']; text = pointer(data, p)
            if sha(text.encode()) != review['field_sha256'] or text.count(review['anchor']) != 1: raise ValueError('REVIEW_FIELD_OR_ANCHOR_CHANGED')
            start = text.index(review['anchor'])+review['offset']; end = start+len(review['literal'])
            if text[start:end] != review['literal']: raise ValueError('REVIEW_LITERAL_MISMATCH')
            selectors[name] = {'pointer': p, 'start': start, 'end': end}
        out.append(record(meta, rel['ocid']+':'+rel['id']+':reviewed-item-description', 'PROCUREMENT_NOTICE', data, selectors, published=rel.get('date'), publication_basis='RELEASE_DATE_NOT_PROVEN_FIRST_PUBLICATION', lineage='OCDS:'+rel['ocid']))
    return out


def reviewed_html(raw, meta, annotation):
    """Source-reviewed public government literals, not automatic semantic truth.

    Raw UTF8 HTML character offsets stay exact. Mutable program-page creation
    dates cannot backdate facts added years later: their publication is UNKNOWN.
    """
    from bct.target_acquisition import Metadata
    text = raw.decode('utf-8'); parser = Metadata(); parser.feed(text)
    if parser.canonical != meta['url']: raise ValueError('HTML_CANONICAL_SOURCE_IDENTITY')
    selectors = {}
    for name, review in annotation['fields'].items():
        anchor = review['anchor']
        if text.count(anchor) != 1: raise ValueError('HTML_REVIEW_ANCHOR_NOT_UNIQUE')
        start = text.index(anchor)+review['offset']; end = start+len(review['literal'])
        if text[start:end] != review['literal']: raise ValueError('HTML_REVIEW_LITERAL_MISMATCH')
        selectors[name] = {'raw_utf8_html': True, 'start': start, 'end': end}
    pub = parser.meta.get('article:published_time') if annotation.get('immutable_dated_article') else None
    row = record(meta, meta['url'], 'PROGRAM_CONTEXT_NOT_QUALIFIED_SUPPLY', text, selectors, published=pub,
                 publication_basis='DATED_NEWS_ARTICLE_NOT_PROGRAM_PAGE_CREATION_DATE', lineage=meta['url'])
    return [row], text


def parse_ocds(data, meta):
    if not isinstance(data, dict) or not isinstance(data.get('releases'), list): raise ValueError('OCDS_RELEASE_PACKAGE_REQUIRED')
    out = []
    for i, rel in enumerate(data['releases']):
        base = f'/releases/{i}'; native = rel['ocid'] + ':' + rel['id']
        common = {'ocid': base+'/ocid', 'notice_id': base+'/id', 'release_tags': base+'/tag', 'buyer_id': base+'/buyer/id', 'buyer_name': base+'/buyer/name', 'publication_date': base+'/date'}
        for section, kind in [('tender', 'PROCUREMENT_TENDER'), ('awards', 'PROCUREMENT_AWARD'), ('contracts', 'PROCUREMENT_CONTRACT')]:
            values = [rel[section]] if section == 'tender' and section in rel else rel.get(section, [])
            for j, obj in enumerate(values):
                p = base+'/'+section + ('' if section == 'tender' else '/'+str(j))
                time_key = 'period' if section == 'contracts' else 'contractPeriod'
                selectors = {**common, 'status': p+'/status', 'product_label': p+'/title', 'procurement_category': p+'/mainProcurementCategory', 'classification_code': p+'/classification/id', 'classification_scheme': p+'/classification/scheme', 'amount': p+'/value/amount', 'currency': p+'/value/currency', 'period_start': p+'/'+time_key+'/startDate', 'period_end': p+'/'+time_key+'/endDate', 'signed_date': p+'/dateSigned', 'award_date': p+'/date', 'supplier_id': p+'/suppliers/0/id', 'supplier_name': p+'/suppliers/0/name', 'contract_id' if section == 'contracts' else 'procurement_id' if section == 'tender' else 'award_id': p+'/id'}
                if section == 'contracts': selectors['award_id'] = p+'/awardID'
                out.append(record(meta, native+':'+section+':'+str(obj.get('id', j)), kind, data, selectors, published=rel.get('date'), publication_basis='RELEASE_DATE_NOT_PROVEN_FIRST_PUBLICATION', lineage='OCDS:'+rel['ocid']))
                for k, item in enumerate(obj.get('items', [])):
                    if item.get('quantity') is None or not item.get('unit', {}).get('name'): continue
                    out.append(record(meta, native+':'+section+':'+str(obj.get('id', j))+':item:'+str(item.get('id', k)), kind, data, {**common, 'item_quantity': p+f'/items/{k}/quantity', 'item_unit': p+f'/items/{k}/unit/name', 'classification_code': p+f'/items/{k}/classification/id'}, published=rel.get('date'), publication_basis='RELEASE_DATE_NOT_PROVEN_FIRST_PUBLICATION', lineage='OCDS:'+rel['ocid']))
                if section == 'tender':
                    for k, lot in enumerate(obj.get('lots', [])):
                        out.append(record(meta, native+':lot:'+str(lot['id']), 'PROCUREMENT_TENDER', data, {**common, 'lot_id': p+f'/lots/{k}/id', 'lot_status': p+f'/lots/{k}/status'}, published=rel.get('date'), publication_basis='RELEASE_DATE_NOT_PROVEN_FIRST_PUBLICATION', lineage='OCDS:'+rel['ocid']))
    return out, data.get('links', {}).get('next')


def parse_json(data, meta):
    source = meta['source_id']; out = []; next_url = None
    if source in {'find_tender', 'contracts_finder'}: return parse_ocds(data, meta)
    if source == 'miso':
        if not isinstance(data, list): raise ValueError('MISO_ARRAY_REQUIRED')
        for i, obj in enumerate(data):
            mapping = {'project_id': 'projectNumber', 'application_date': 'queueDate', 'planned_service_date': 'inService', 'transmission_owner': 'transmissionOwner', 'geography': 'state', 'summer_net_MW': 'summerNetMW', 'winter_net_MW': 'winterNetMW', 'generation_type': 'fuelType', 'facility_type': 'facilityType', 'project_status': 'applicationStatus'}
            out.append(record(meta, str(obj['id']), 'CONNECTION_PROJECT', data, {k: f'/{i}/{v}' for k, v in mapping.items()}, lineage='MISO_PROJECT:'+obj['projectNumber']))
    elif source == 'gleif':
        for i, obj in enumerate(data['data']):
            b = f'/data/{i}/attributes'
            out.append(record(meta, obj['id'], 'LEGAL_ENTITY', data, {'lei': b+'/lei', 'legal_name': b+'/entity/legalName/name', 'legal_jurisdiction': b+'/entity/jurisdiction', 'entity_status': b+'/entity/status', 'registration_last_update': b+'/registration/lastUpdateDate', 'dataset_update': '/meta/goldenCopy/publishDate'}, published=data.get('meta', {}).get('goldenCopy', {}).get('publishDate'), publication_basis='CURRENT_GOLDEN_COPY_NOT_INITIAL_REGISTRATION'))
        next_url = data.get('links', {}).get('next')
    elif source == 'world_bank':
        for i, obj in enumerate(data['procnotices']):
            pub = obj.get('noticedate', '')
            try: pub = datetime.strptime(pub, '%d-%b-%Y').date().isoformat()
            except ValueError: pub = 'UNKNOWN'
            mapping = {'notice_id': 'id', 'notice_type': 'notice_type', 'notice_status': 'notice_status', 'project_country': 'project_ctry_name', 'project_id': 'project_id', 'project_name': 'project_name', 'publication_date': 'noticedate'}
            out.append(record(meta, obj['id'], 'PROCUREMENT_NOTICE', data, {k: f'/procnotices/{i}/{v}' for k, v in mapping.items()}, published=pub, publication_basis='NOTICE_DATE_NOT_PROVEN_FIRST_VERSION', lineage='WORLD_BANK:'+obj['id']))
    elif source == 'federal_register':
        # Keep the existing collector's response/date validation.
        from bct.collectors.federal_register.collector import parse_response
        parse_response(json.dumps(data).encode(), limit=min(100, len(data.get('results', []))))
        for i, obj in enumerate(data['results']):
            out.append(record(meta, obj['document_number'], 'REGULATORY_DOCUMENT', data, {'notice_id': f'/results/{i}/document_number', 'publication_type': f'/results/{i}/type', 'publication_date': f'/results/{i}/publication_date'}, published=obj.get('publication_date'), publication_basis='FEDERAL_REGISTER_PUBLICATION'))
        next_url = data.get('next_page_url')
    elif source == 'comtrade':
        for i, obj in enumerate(data['data']):
            mapping = {'trade_quantity': 'qty', 'trade_unit_code': 'qtyUnitCode', 'trade_net_weight_kg': 'netWgt', 'trade_value_USD': 'primaryValue', 'trade_period': 'period', 'commodity_code': 'cmdCode', 'reporter_code': 'reporterCode', 'partner_code': 'partnerCode', 'flow_code': 'flowCode', 'is_estimated': 'isQtyEstimated', 'is_aggregate': 'isAggregate'}
            native = ':'.join(str(obj.get(k, 'UNKNOWN')) for k in ('period', 'reporterCode', 'partnerCode', 'flowCode', 'cmdCode', 'customsCode', 'motCode'))
            out.append(record(meta, native, 'TRADE_STATISTIC', data, {k: f'/data/{i}/{v}' for k, v in mapping.items()}, lineage='UN_COMTRADE:'+native))
    elif source == 'bgs':
        for i, obj in enumerate(data['features']):
            p = f'/features/{i}/properties/'
            mapping = {'statistic_value': 'quantity', 'statistic_unit': 'units', 'statistic_period': 'year', 'statistic_product': 'bgs_commodity_trans', 'statistic_country': 'country_iso3_code', 'statistic_type': 'bgs_statistic_type_trans', 'statistic_flag': 'sdmx_translation', 'statistic_figure_notes': 'concat_figure_notes_text'}
            out.append(record(meta, obj['id'], 'PRODUCTION_STATISTIC', data, {k: p+v for k, v in mapping.items()}, lineage='BGS:'+obj['id']))
        next_url = next((v['href'] for v in data.get('links', []) if v.get('rel') == 'next'), None)
    else: raise ValueError('SOURCE_PARSER_NOT_IMPLEMENTED')
    return out, next_url


def parse_csv(raw, meta):
    rows = list(csv.DictReader(StringIO(raw.decode('utf-8-sig'))))
    if meta['source_id'] != 'neso': raise ValueError('CSV_SOURCE_NOT_IMPLEMENTED')
    mapping = {'project_id': 'Project ID', 'product_label': 'Plant Type', 'connection_customer': 'Customer Name', 'facility_id': 'Connection Site', 'project_status': 'Project Status', 'connected_MW': 'MW Connected', 'capacity_change_MW': 'MW Increase / Decrease', 'cumulative_MW': 'Cumulative Total Capacity (MW)', 'planned_service_date': 'MW Effective From'}
    out = []
    for i, obj in enumerate(rows):
        if not obj.get('Project ID'): raise ValueError('NESO_PROJECT_ID_REQUIRED')
        native = json.dumps([obj.get(k) for k in ['Project ID', 'MW Effective From', 'Stage', 'Agreement Type']])
        out.append(record(meta, native, 'CONNECTION_PROJECT', obj, mapping, csv_row=i+1, lineage='NESO_PROJECT:'+obj['Project ID']))
    return out, rows


def parse_ercot(workbook, meta):
    """Public GIS tables, including cancellations and commissioning (not supply)."""
    out = []; coverage = {}
    for sheet in ['Project Details - Large Gen', 'Project Details - Small Gen', 'Commissioning Update', 'Cancellation Update']:
        ws = workbook[sheet]; headers = {}; count = 0
        for row in ws.iter_rows():
            values = [c.value for c in row]
            if not headers:
                if 'INR' in values and ('Capacity (MW)' in values or 'MW **' in values):
                    headers = {str(c.value).strip(): c.column for c in row if c.value is not None}
                continue
            key = row[headers['INR']-1].value
            if not isinstance(key, str) or not re.fullmatch(r'\d{2}INR\d+[a-z]?', key): continue
            names = {'project_id': 'INR', 'project_name': 'Project Name', 'generation_type': 'Fuel', 'geography': 'County', 'planned_service_date': 'Projected COD', 'reported_project_MW': 'Capacity (MW)' if 'Capacity (MW)' in headers else 'MW **', 'commissioning_status': 'Commissioning Category', 'approval_date': 'Approval Date *', 'cancellation_date': 'Cancel Date'}
            selectors = {name: row[headers[label]-1].coordinate for name, label in names.items() if label in headers}
            values = {c.coordinate: c.value.isoformat() if isinstance(c.value, datetime) else c.value for c in row}
            out.append(record(meta, sheet+':'+key, 'CONNECTION_PROJECT', values, selectors, xlsx_sheet=sheet, published=meta.get('published_at'), publication_basis='ERCOT_CATALOG_DOCUMENT_PUBLISH_DATE', lineage='ERCOT_GIS:'+key))
            count += 1
        if not headers: raise ValueError('ERCOT_GIS_TABLE_HEADER_NOT_FOUND')
        coverage[sheet] = count
    return out, coverage


def save(ledger, records):
    """Append versions in the existing event store; exact restarts are no-ops."""
    for row in records: validate(row)
    with ledger.db:
        ledger.db.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS official_fact_id ON events(json_extract(payload,'$.id')) WHERE kind='{KIND}'")
        existing = {r[0] for r in ledger.db.execute(f"SELECT json_extract(payload,'$.id') FROM events WHERE kind='{KIND}'")}
        added = 0
        for row in records:
            if row['id'] in existing: continue
            ledger.event(KIND, row); existing.add(row['id']); added += 1
    return {'added': added, 'duplicate_versions': len(records)-added, 'S2': 0, 'S3': 0}


def q2_review_inputs(records):
    """Forward evidence to Q2 review, never turn a title/contract into a TARGET.

    A signed contract may lack a physical item; parent tender labels and lots
    remain pointers for review. Power queues and trade rows cannot supply its
    missing production capacity. A repeated OCID/contract is one lineage.
    """
    latest = {}
    for r in records:
        validate(r); latest[r['logical_id']] = r
    requests = []; award_index = {}; context = {}
    def scope(r):
        return (r['source_lineage'], r['claims'].get('notice_id', {}).get('value'))
    for r in latest.values():
        context.setdefault(scope(r), []).append(r)
        if r['record_kind'] == 'PROCUREMENT_AWARD' and 'award_id' in r['claims']:
            award_index.setdefault((*scope(r), r['claims']['award_id']['value']), []).append(r)
    contracts = {}; signed_before = 0
    def published_rank(r):
        if r['published_at'] == 'UNKNOWN': return float('-inf'), r['id']
        value = datetime.fromisoformat(r['published_at'].replace('Z', '+00:00'))
        if value.tzinfo is None: value = value.replace(tzinfo=timezone.utc)
        return value.timestamp(), r['id']
    contract_rows = [r for r in latest.values() if r['record_kind'] == 'PROCUREMENT_CONTRACT']
    for r in contract_rows:
        c = r['claims']; signed_before += 'signed_date' in c
        identity = (r['source_lineage'], c.get('contract_id', {}).get('value', r['native_id']))
        if identity not in contracts or published_rank(r) > published_rank(contracts[identity]): contracts[identity] = r
    for r in contracts.values():
        c = r['claims']
        if r['record_kind'] != 'PROCUREMENT_CONTRACT' or 'signed_date' not in c: continue
        matches = award_index.get((*scope(r), c.get('award_id', {}).get('value')), [])
        supplier = matches[0]['claims'].get('supplier_id', {}).get('value') if len(matches) == 1 else None
        siblings = context[scope(r)]
        titles = [x['id'] for x in siblings if x['record_kind'] == 'PROCUREMENT_TENDER' and 'product_label' in x['claims']]
        conflicts = [x['id'] for x in siblings if x['claims'].get('lot_status', {}).get('value') in {'cancelled', 'unsuccessful'}]
        requests.append({'evidence_id': r['id'], 'procurement_lineage': r['source_lineage'],
                         'contract_id': c.get('contract_id', {}).get('value'),
                         'review_state': 'SIGNED_CONTRACT_RECORD_PHYSICAL_OBJECT_UNVERIFIED',
                         'buyer_id': c.get('buyer_id', {}).get('value'),
                         'supplier_id_via_exact_award_id': supplier,
                         'award_evidence_ids': [m['id'] for m in matches],
                         'procurement_title_evidence_ids_not_product_identity': titles,
                         'parent_lot_conflicts_not_resolved_contract_cancellation': conflicts,
                         'signed_date': c['signed_date']['value'],
                         'contract_period_not_firm_delivery': {k: c[k]['value'] for k in ['period_start', 'period_end'] if k in c},
                         'missing': ['physical_product_and_specification', 'item_quantity_and_unit',
                                     'customer_need_date_not_contract_end', 'qualified_supplier_pool',
                                     'allocable_capacity_and_ready_date', 'independent_counterpart_evidence'],
                         'Q3_eligible': False, 's_stage': 'UNKNOWN'})
    return {'review_inputs': requests, 'signed_contract_records': len(requests),
            'signed_release_records_before_contract_dedup': signed_before,
            'contract_groups_all': len(contracts),
            'duplicate_contract_release_records': len(contract_rows)-len(contracts),
            'exact_unique_contract_award_links': sum(len(r['award_evidence_ids']) == 1 for r in requests),
            'supplier_ids_via_exact_award_link': sum(r['supplier_id_via_exact_award_id'] is not None for r in requests),
            'parent_lot_conflict_review_inputs': sum(bool(r['parent_lot_conflicts_not_resolved_contract_cancellation']) for r in requests),
            'source_reviewed_item_descriptions_not_confirmed_orders': [r['id'] for r in latest.values() if 'reported_item_quantity_literal' in r['claims']],
            'independent_pairs': 0, 'Q3_eligible_targets': [], 'S2': 0, 'S3': 0}
