"""Optional read-only official API bindings; keys never enter public receipts.

Constructing a request is not authentication or live parser verification.
No default/demo key, login, commenting endpoint, or paid fallback exists.
"""
import base64
import os
from urllib.parse import urlencode
from urllib.request import Request

ROUTES = {
    'sam_opportunities': ('BCT_SAM_API_KEY', 'https://api.sam.gov/opportunities/v2/search', 'query', 'api_key'),
    'sam_awards': ('BCT_SAM_API_KEY', 'https://api.sam.gov/contract-awards/v1/search', 'query', 'api_key'),
    'opendart': ('BCT_OPENDART_API_KEY', 'https://opendart.fss.or.kr/api/list.json', 'query', 'crtfc_key'),
    'edinet': ('BCT_EDINET_API_KEY', 'https://api.edinet-fsa.go.jp/api/v2/documents.json', 'query', 'Subscription-Key'),
    'companies_house': ('BCT_COMPANIES_HOUSE_API_KEY', 'https://api.company-information.service.gov.uk/search/companies', 'basic', ''),
    'entsoe': ('BCT_ENTSOE_API_TOKEN', 'https://web-api.tp.entsoe.eu/api', 'query', 'securityToken'),
    'estat': ('BCT_ESTAT_APP_ID', 'https://api.e-stat.go.jp/rest/3.0/app/json/getStatsData', 'query', 'appId'),
    'kosis': ('BCT_KOSIS_API_KEY', 'https://kosis.kr/openapi/Param/statisticsParameterData.do', 'query', 'apiKey'),
    'regulations': ('BCT_REGULATIONS_API_KEY', 'https://api.regulations.gov/v4/documents', 'header', 'X-Api-Key'),
    'comtrade': ('BCT_COMTRADE_API_KEY', 'https://comtradeapi.un.org/public/v1/preview/C/A/HS', 'header', 'Ocp-Apim-Subscription-Key'),
}
# data.go.kr catalogue is currently 503. Do not invent an operation from an
# obsolete endpoint; key binding can be ready while its contract stays blocked.
UNRESOLVED = {'korea_pps': 'BCT_DATA_GO_KR_SERVICE_KEY'}
PARAMS = {
    'sam_opportunities': {'postedFrom', 'postedTo', 'limit', 'offset', 'noticeid', 'ncode', 'title'},
    'sam_awards': {'modifiedDate', 'limit', 'offset', 'q', 'contractId', 'includeSections'},
    'opendart': {'bgn_de', 'end_de', 'corp_code', 'page_no', 'page_count', 'pblntf_ty'},
    'edinet': {'date', 'type'}, 'companies_house': {'q', 'items_per_page', 'start_index'},
    'entsoe': {'documentType', 'processType', 'in_Domain', 'out_Domain', 'periodStart', 'periodEnd'},
    'estat': {'statsDataId', 'lang', 'startPosition', 'limit', 'cdTime', 'cdArea', 'cdCat01'},
    'kosis': {'method', 'orgId', 'tblId', 'objL1', 'objL2', 'itmId', 'prdSe', 'startPrdDe', 'endPrdDe', 'format', 'jsonVD'},
    'regulations': {'filter[searchTerm]', 'filter[postedDate][ge]', 'page[size]', 'page[number]'},
    'comtrade': {'period', 'reporterCode', 'cmdCode', 'flowCode', 'partnerCode', 'partner2Code', 'customsCode', 'motCode', 'maxRecords'},
}


def bindings(env=None):
    env = os.environ if env is None else env
    return {source: {'secret_name': value[0], 'present': bool(env.get(value[0])),
                     'authentication': 'NOT_TESTED', 'status': 'IMPLEMENTED_UNTESTED' if env.get(value[0]) else 'NEEDS_USER_KEY'}
            for source, value in {**ROUTES, **{k: (v,) for k, v in UNRESOLVED.items()}}.items()}


def request(source, params, env=None):
    """Return an ephemeral request plus a safe identity. Caller must not log req."""
    env = os.environ if env is None else env
    if source in UNRESOLVED: raise ValueError('OFFICIAL_OPERATION_DOCUMENTATION_UNVERIFIED')
    secret, endpoint, mode, name = ROUTES[source]
    if set(params)-PARAMS[source]: raise ValueError('OFFICIAL_UNREVIEWED_REQUEST_PARAMETER')
    key = env.get(secret)
    if not key: return None, {'source_id': source, 'status': 'NEEDS_USER_KEY', 'secret_name': secret}
    safe = endpoint + ('?'+urlencode(params) if params else '')
    headers = {'Accept': 'application/json, application/xml;q=0.8', 'User-Agent': 'BCT-free-official-research/1.0'}
    query = dict(params)
    if mode == 'query': query[name] = key
    elif mode == 'basic': headers['Authorization'] = 'Basic '+base64.b64encode((key+':').encode()).decode()
    else: headers[name] = key
    req = Request(endpoint + ('?'+urlencode(query) if query else ''), headers=headers)
    return req, {'source_id': source, 'url': safe, 'status': 'IMPLEMENTED_UNTESTED', 'secret_name': secret}
