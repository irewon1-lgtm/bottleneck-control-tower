"""Source-addressed prose scopes; never infer eligibility from an entity name.

The engineering noun grammar identifies spans, not a TARGET/issuer dictionary.
Every value and cross-statement link remains addressable in the unchanged body.
"""
from copy import deepcopy
import hashlib
import re

from . import future_body

VERSION = 'source-scope-reader-4'
FIELDS = ('product', 'specification', 'region', 'customer_group', 'supply_pool')
GENERIC = frozenset('the id company facility product market shares stock revenue cash plant factory system equipment demand supply capacity production project contract customers supplier component components fuel power'.split())
CLAUSE_WORDS = re.compile(r'\b(?:is|are|was|were|has|have|been|will|would|could|should|said|says|announced|developing|producing|receiving|watching|creates|requires|selling|last|these|those|this|that|which|while|whether|and|or|but|over)\b', re.I)
HEAD = r'(?:components?|batter(?:y|ies)|cells?|turbines?|isolators?|lasers?(?: die)?|wafer substrates?|wafers?|substrates?|cables?|fibers?|fibre|tungsten(?:\s+(?:concentrate|metal powder|powder|carbide|briquettes?))?|nickel|lithium|hydrogen|HALEU|fuel|semiconductors?|chips?|motors?|missiles?|vehicles?|trucks?|satellites?|transformers?|reactors?|burn-in|interconnection|alignment|bonding|production slots?|foundry slots?|power|electricity|seekers?|drivers?|TIA|ammonium perchlorate|engines?|interfaces?|connectors?|fiber attach|grid connections?|connection works|integrated testing)'
MODIFIERS = frozenset('precision industrial domestic military-grade high-purity high-performance high-energy-density pouch lithium-ion lithium-iron-phosphate lfp ndaa-compliant feoc-independent non-chinese driverless electric heavy-duty small modular gas steam nuclear large high-density zero-emission ballistic cruise air-launched solid-state ai data center silicon photonics photonics-soi optical external qualified production commercial-scale laser autonomous automated yard critical power photonic wafer-level garnet-based magneto-optical 300mm 200g/lane'.split())
MODIFIERS = MODIFIERS | frozenset('unobligated enriched uranium high-assay low-enriched solid rocket military defense defence datacom inp sige cpo pic-eic hybrid direct active passive co-packaged integrated optical-electrical high-energy multi-channel single-mode cw eml t-glass transmission distribution grid interconnection construction industrial-scale advanced packaging ammonium perchlorate detachable test fiber wafer concentrate metal powder carbide briquette briquettes silicon-anode density'.split())
PRODUCT = re.compile(r'(?<![\w-])(?:[A-Za-z0-9][\w/-]*\s+){0,4}'+HEAD+r'\b', re.I)
MODEL = re.compile(r'\b(?:ID\.(?:\d\s+[A-Z]{2,}|\s+[A-Z][\w-]*(?:\s+[A-Z]{2,})?)|[A-Z][A-Z0-9-]{1,20}\s+(?!20\d{2}\b)\d{1,4}[A-Za-z]?)\b')
NAMED_MODEL = re.compile(r'\b(?:[A-Z][a-z]+(?:[A-Z][A-Za-z]*)?\d{1,4}[A-Za-z]*|[A-Z]{2,6}-[A-Z]{2,6})\b')
# Filing/accounting headings and currency tags are identifiers, not models.
NONPRODUCT_IDENTIFIER = re.compile(r'^(?:FORM|ITEM|ASC|RMB|USD|EUR|GBP|ISO|MIL|ASTM)\b', re.I)
SPEC = re.compile(r'\b(?:NDAA[- ]compliant|FEOC[- ](?:compliant|independent)|non[- ]Chinese|military[- ]grade|customer[- ]qualified|unobligated|(?:\d{2,4}\s*mm)|\d{2,4}\s*G(?:bps)?(?:/lane|\s+per\s+lane)|InP|SiGe|(?:high[- ]energy[- ]density)|(?:lithium iron phosphate|LFP)|Class\s+[1-9]|grade\s+[A-Z0-9][\w/-]*|ISO[- ]\d{4,5}|MIL[- ](?:STD|DTL|PRF|SPEC)[- ]\d{2,}[A-Z0-9/-]*|ASTM[- ]?[A-Z]\d{2,}[A-Z0-9/-]*)\b', re.I)
REGION = r'(?:United States|U\.S\.|US|United Kingdom|UK|North America|South America|Europe|Canada|Japan|Germany|France|China|Mississippi|Pennsylvania|Nevada|Texas|Alaska|Tanzania|Mexico|Brazil|Chile)'
REGIONS = re.compile(r'\b'+REGION+r'(?!\w)')
NOISE = re.compile(r'^(?:Advertisement\b|Read (?:more|also):|Related (?:articles|stories|news)\b|Recommended\b|COMMODITY:|REGION:|COMPANY:|TAG:|Republish this article|Copyright\b|All rights reserved|About the author|In This Issue\b)', re.I)
HTML_NOISE = re.compile(r'(?:^|[\s_-])(?:related|recommended|advert\w*|ad-slot|menu|footer|navigation|country|region-selector|taxonomy|author-bio|copyright|disclaimer|social|share)(?:$|[\s_-])', re.I)
PARTY = r'[A-Z][A-Za-z0-9&’\'-]*(?:\s+(?:[A-Z][A-Za-z0-9&’\'-]*|of|the|and)){0,5}'
NEGATIVE_QUALIFICATION = re.compile(r'not(?:\s+yet)?\s+(?:(?:a|an|the)\s+)?(?:qualified|certified|eligible)|pending\s+(?:qualification|certification)|(?:expects?|plans?|will|target|before).{0,60}(?:qualif|certif)|qualif\w*.{0,35}(?:pending|incomplete)', re.I)


def sentences(doc, lines):
    """Sentence offsets in allowed paragraphs, with abbreviations intact."""
    for line in lines:
        cuts=[0]
        for m in re.finditer(r'(?<=[.!?])\s+(?=[A-Z“"\'])',line['quote']):
            if re.search(r'(?:\bID|\bInc|\bLtd|\bCorp|\bU\.S|\bMr|\bDr|\bSt)\.$',line['quote'][:m.start()]):continue
            cuts.append(m.end())
        cuts.append(len(line['quote']))
        for a,b in zip(cuts,cuts[1:]):
            q=line['quote'][a:b].rstrip()
            if q:yield {'start':line['start']+a,'end':line['start']+a+len(q),'quote':q,'paragraph_start':line['start']}


def valid_product(value):
    v = ' '.join(value.casefold().split()).strip(' .,;:')
    model=bool(MODEL.fullmatch(value) or NAMED_MODEL.fullmatch(value))
    noun=PRODUCT.fullmatch(value)
    engineering=bool(noun and all(token in MODIFIERS or re.fullmatch(HEAD,token,re.I) for token in v.split()))
    return bool(3 <= len(v) <= 140 and v not in GENERIC and v not in ('the id', 'id')
                and not NONPRODUCT_IDENTIFIER.search(value)
                and not re.search(r'\b(?:shares|stock|revenue|cash|dollars|market)\b', v)
                and not CLAUSE_WORDS.search(value)
                and (engineering or model))


def reference(doc, start, end):
    return {'document_id': doc['document_id'], 'body_sha256': doc['body_sha256'],
            'origin_id': doc.get('origin_id'), 'locator': {'start': start, 'end': end},
            'source_quote': doc['body'][start:end], 'origin_url': doc.get('origin_url'),
            'origin_publisher': doc.get('origin_publisher'), 'published_at': doc.get('published_at'),
            'publication_precision': doc.get('publication_precision'), 'acquired_at': doc.get('acquired_at'),
            'assertion': 'DIRECT_SOURCE_FACT'}


def field(doc, start, end, *supports):
    while start < end and doc['body'][start].isspace(): start += 1
    while end > start and doc['body'][end-1] in ' ,;': end -= 1
    return {'value': doc['body'][start:end], 'locator': {'start': start, 'end': end},
            'reference': reference(doc, start, end), 'support_references': list(supports)}


def allowed_lines(doc, raw=None):
    """Filter by DOM context and literal taxonomy labels without moving offsets.

    Tables, footnotes and exhibits are never text-pattern noise merely because
    they contain countries. Raw/context exclusions are retained as a QA record.
    """
    denied = []
    if raw:
        dom = future_body._Document(); dom.feed(raw.decode('utf-8', errors='replace')); dom.close()
        for node in future_body._nodes(dom.root):
            label = ' '.join(str(node.attrs.get(k, '')) for k in ('class', 'id', 'role'))
            if node.tag in ('nav', 'footer', 'menu') or HTML_NOISE.search(label):
                # Explicit exhibit/footnote/SEC table wrappers remain usable.
                if re.search(r'footnote|exhibit|table', label, re.I): continue
                denied.extend(future_body._blocks(node))
                text = future_body._text(node, include_script=True)
                if text: denied.append(text)
    out, excluded = [], []
    for m in re.finditer(r'[^\n]+', doc['body']):
        q = m[0]; reason = None
        if NOISE.search(q.strip()): reason = 'PAGE_CHROME_OR_TAXONOMY'
        if any(q.strip() == text.strip() or (len(q) > 10 and q in text) for text in denied): reason = 'HTML_CHROME_CONTEXT'
        if reason: excluded.append({**reference(doc, m.start(), m.end()), 'reason': reason})
        else: out.append({'start': m.start(), 'end': m.end(), 'quote': q})
    return out, excluded


def product_key(value):
    text=' '.join(value.casefold().split())
    return re.sub(r'\b(batteries|cells|turbines|isolators|lasers|wafers|substrates|cables|fibers|chips|motors|missiles|vehicles|trucks|satellites|transformers|reactors|components|engines|interfaces|connectors)\b',lambda m:'battery' if m[0]=='batteries' else m[0][:-1],text)


def _unique(values, *, product=False):
    keys = {product_key(f['value']) if product else ' '.join(f['value'].casefold().split()) for f in values}
    return values[0] if len(keys) == 1 else None


def named_anchors(quote):
    anchors=re.findall(r'\b(?:contract\s+(?:number\s+|No\.\s*)?[A-Z0-9][\w/-]*\d[\w/-]*|[A-Z][\w-]*(?:\s+[A-Z][\w-]*){0,2}\s+(?:project|Project|Plant|Facility|Mine))\b', quote)
    result=[]
    generic={'the','this','that','its','our','their','new','existing','another','first','second','third','fourth','current','proposed','a','an'}
    for token in anchors:
        if not token.lower().startswith('contract '):
            words=token.split()
            while words and words[0].casefold() in generic:words.pop(0)
            if len(words)<2:continue
            token=' '.join(words)
        result.append(token)
    return result


def _products(doc, line):
    q = line['quote']; found = []
    for m in list(PRODUCT.finditer(q)) + list(MODEL.finditer(q)) + list(NAMED_MODEL.finditer(q)):
        a, b = m.start(), m.end()
        # Trim grammar prefixes instead of calling an entire clause a product.
        raw = q[a:b]
        cut = list(re.finditer(r'\b(?:for|of|with|from|by|to|in|on|about|including|its|the|a|an|and|or|new|supply|demand|production|manufacture|manufactures|manufacturing|orders|order|additional|million|billion|using|uses|produce|produces|producing|developing|provide|provides|providing|receiving|watching|is|are|these|those|over)\s+', raw, re.I))
        if cut: a += cut[-1].end()
        raw = q[a:b]
        # Quantities are attributes, not part of the physical product identity.
        nm = re.match(r'\d+(?:,\d{3})*(?:\.\d+)?\s+', raw)
        if nm: a += nm.end(); raw = q[a:b]
        qualifier=SPEC.match(raw)
        if qualifier and qualifier.end()<len(raw) and raw[qualifier.end()].isspace():
            a+=qualifier.end();a+=len(q[a:b])-len(q[a:b].lstrip());raw=q[a:b]
        if not valid_product(raw):
            # The noun grammar must not depend on the preceding verb being in
            # a fixed cut-word list ("churn out", "commission", etc.). Keep the
            # longest engineering suffix with its literal offset.
            for token in list(re.finditer(r'\S+',raw))[1:]:
                suffix=raw[token.start():]
                if valid_product(suffix):a+=token.start();raw=suffix;break
        if NAMED_MODEL.fullmatch(raw) and not re.search(HEAD, q, re.I): continue
        if raw.upper()=='CHIPS' and re.match(r'\s+Act\b',q[b:]):continue
        if raw.casefold() in ('alignment','bonding') and not re.search(r'photonic|wafer|laser|fiber|fibre|\bdie\b|chip|semiconductor|optical|\bPIC\b',q,re.I):continue
        if valid_product(raw): found.append(field(doc, line['start']+a, line['start']+b))
    # A model and its physical noun are one identity when the source explicitly
    # says "MODEL gas turbines", not two unrelated products in the sentence.
    models=[f for f in found if NAMED_MODEL.fullmatch(f['value'])]
    for model in models:
        tail=q[model['locator']['end']-line['start']:]
        noun=re.match(r'(?:™)?\s+(?:gas\s+|industrial\s+|optical\s+)?'+HEAD+r'\b',tail,re.I)
        if not noun:
            noun=re.match(r'\s*[®™]?\s*(?:(?:multi-wafer|wafer-level|high-power|fully automated|production)\s+){0,4}burn-in\s+system\b',tail,re.I)
        if not noun:
            candidate=PRODUCT.search(tail)
            if candidate and candidate.start()<4 and valid_product(candidate[0].strip()):noun=candidate
        if noun:
            found=[f for f in found if f==model or not model['locator']['end']<=f['locator']['start']<model['locator']['end']+noun.end()]
    return found


def bound_product(line, products):
    """Resolve a grammatical purchase/output object, not every noun mentioned.

    "Order for X, configured to test Y" does not mean an order for Y. A
    coordinated "order for X and Y" still remains ambiguous.
    """
    p=_unique(products,product=True)
    if p:return p
    q=line['quote']
    for m in re.finditer(r'\b(?:orders?\s+(?:for|of)|orders?\b.{0,100}?\bcustomer\s+for|purchase\s+of|(?:production|qualified)\s+(?:capacity|output|supply)\s+(?:for|of))\s+',q,re.I):
        end=re.search(r'[,;.]|\b(?:configured to|designed to|which|that|including)\b',q[m.end():],re.I)
        limit=m.end()+end.start() if end else len(q)
        candidates=[f for f in products if line['start']+m.end()<=f['locator']['start']<line['start']+limit]
        p=_unique(candidates,product=True)
        if p:return p
    return None


def literal_fields(doc, line):
    """Recognize source facts without asserting a unique product relationship.

    In multi-product prose all candidates remain inspectable, while only
    bound_product/_attributes can supply graph fields. Recognition is never
    substituted for TARGET binding or supplier eligibility.
    """
    ps=_products(doc,line);attrs=_attributes(doc,line,None)
    out={'product':ps}
    for k,f in attrs.items():
        if k!='product' and f is not None:out[k]=[f]
    # Recognize every specification span even when their relationship is
    # ambiguous. _attributes still refuses a union of competing specs.
    out['specification']=[field(doc,line['start']+m.start(),line['start']+m.end()) for m in SPEC.finditer(line['quote'])]
    for pattern in (r'\b(?:from|for|our|its)\s+((?:a |the |its )?(?:lead|major|new|leading)(?:\s+[a-z-]+){0,5}\s+customer)\b',
                    r'\b(?:This|The) customer is\s+((?:a |the )?[^.;]{5,180}?)(?=\s+and (?:a|the)\b|[.;]|$)',
                    r'\bcustomer that is\s+((?:a |the )?[^.;]{5,180}?)(?=\s+and (?:a|the)\b|[.;]|$)'):
        for m in re.finditer(pattern,line['quote']):
            f=field(doc,line['start']+m.start(1),line['start']+m.end(1))
            f['customer_identity_status']='UNNAMED_CUSTOMER_NOT_UNIQUE_ACROSS_DOCUMENTS'
            out.setdefault('customer_group',[]).append(f)
    # Multiple contract recipients are separate unresolved literal facts.
    recipients=[]
    for m in re.finditer(r'\borders?\s+from\s+('+PARTY+r')(?=[,.;]|$)',line['quote']):
        recipients.append(field(doc,line['start']+m.start(1),line['start']+m.end(1)))
    out.setdefault('customer_group',[]).extend(recipients)
    return out


def _attributes(doc, line, product):
    q, off = line['quote'], line['start']; out = {'product': product}
    # All attribute candidates must share a clause with the product. A line
    # containing another product is unresolved, never a scope union.
    specs = [field(doc, off+m.start(), off+m.end()) for m in SPEC.finditer(q)]
    if f := _unique(specs): out['specification'] = f
    regions = []
    for m in REGIONS.finditer(q):
        before = q[max(0,m.start()-100):m.start()]
        if re.search(r'headquartered|based|publisher|office address', before, re.I): continue
        if re.search(r'\b(?:in|into|across|for|to|at)\s+(?:the\s+)?$', before, re.I):
            regions.append(field(doc, off+m.start(), off+m.end()))
    if f := _unique(regions): out['region'] = f
    customer = []
    for m in re.finditer(r'\b(?:for|to)\s+((?:military|industrial|defense|automotive|data center|AI data center)\s+(?:drones|buyers|customers|programs|operators)|(?:the\s+)?(?:U\.S\.\s+)?(?:Army|Navy|Air Force|Department of Defense)|(?:customer|buyer)\s+[A-Z][\w-]*)', q):
        customer.append(field(doc, off+m.start(1), off+m.end(1)))
    # Contract recipient is a separate relation from component/finished goods.
    for m in re.finditer(r'\b(?:contract|agreement|orders?)\s+(?:with|from)\s+([A-Z][\w-]*(?:\s+[A-Z][\w-]*){0,3})(?=\s+(?:for|to|covering)|[,.;])', q):
        customer.append(field(doc, off+m.start(1), off+m.end(1)))
    if f := _unique(customer): out['customer_group'] = f
    if not customer:
        for pattern in (
            r'\b(?:serving|for|to support|used (?:in|by))\s+((?:US |U\.S\. |American |North American )?(?:AI |hyperscale |military |industrial |defen[cs]e |automotive )?(?:data cent(?:er|re)s|drone (?:operators|programs)|defen[cs]e and other industrial customers|electric utilities))\b',
            r'\b(?:ordered|purchased|procured)\s+by\s+('+PARTY+r')(?=[,.;]|\s+(?:for|under|in|with|on)\b)',
            r'\b(?:supply|supplies|supplying|deliver|delivers|delivering)\b.{0,100}?\bto\s+('+PARTY+r')(?=[,.;]|\s+(?:for|under|in|with|on)\b)',
            r'\b('+PARTY+r')\s+(?:has |have )?(?:placed|signed|awarded)\s+(?:a |an |new |firm |binding )*(?:orders?|purchase contract)\b',
            r'\b([A-Z][A-Za-z0-9&-]*(?:\s+[A-Z][A-Za-z0-9&-]*){0,3})(?:[’\']s)\s+(?:actual |annual |minimum )?purchase (?:quantity|commitment)\b',
            r'\b('+PARTY+r')\s+(?:has |have |will )?(?:agreed to purchase|purchases|buys)\b',
        ):
            for m in re.finditer(pattern,q):customer.append(field(doc,off+m.start(1),off+m.end(1),reference(doc,off,off+len(q))))
        if f := _unique(customer):out['customer_group']=f
    if 'customer_group' not in out:
        patterns=(r'\b(?:from|for|our|its)\s+((?:a |the |its )?(?:lead|major|new|leading)(?:\s+[a-z-]+){0,5}\s+customer)\b',
                  r'\b(?:This|The) customer is\s+((?:a |the )?[^.;]{5,180}?)(?=\s+and (?:a|the)\b|[.;]|$)',
                  r'\bcustomer that is\s+((?:a |the )?[^.;]{5,180}?)(?=\s+and (?:a|the)\b|[.;]|$)')
        for pattern in patterns:
            for m in re.finditer(pattern,q):
                f=field(doc,off+m.start(1),off+m.end(1),reference(doc,off,off+len(q)))
                f['customer_identity_status']='UNNAMED_CUSTOMER_NOT_UNIQUE_ACROSS_DOCUMENTS'
                customer.append(f)
        if f := _unique(customer):out['customer_group']=f
    if 'customer_group' not in out:
        # End-use descriptions are literal facts, not named customer identity.
        for pattern in (r'\b(enterprise AI customers)\b',
                        r'\b((?:AI )?data centers)\b',
                        r'\b(defen[cs]e and aerospace programs)\b'):
            for m in re.finditer(pattern,q):customer.append(field(doc,off+m.start(1),off+m.end(1)))
        if f := _unique(customer):out['customer_group']=f
    pools = []
    for m in re.finditer(r'\b(?:supplied|manufactured|produced) by\s+([A-Z][\w-]*(?:\s+(?:[A-Z][\w-]*|Energy|Technologies|Inc\.?|Ltd\.?)){0,4})', q):
        # A maker name establishes a supplier relation, not qualification.
        # An explicit qualification statement in this same product statement
        # is required before it can define an eligible observed supply pool.
        if (re.search(r'\b(?:qualified|certified|eligible)\s+(?:(?:domestic|non-Chinese|NDAA-compliant)\s+)?(?:manufacturer|producer|supplier)\b|\b(?:customer|product|production)\s+(?:qualification|certification|approval)\b|\bqualified\s+(?:supply|capacity|output|production)\b', q, re.I)
                and not NEGATIVE_QUALIFICATION.search(q)):
            pools.append(field(doc, off+m.start(1), off+m.end(1), reference(doc, off, off+len(q))))
    for m in re.finditer(r'\b((?:qualified|certified|eligible)\s+(?:domestic|non-Chinese|NDAA-compliant)?\s*(?:producers|suppliers|manufacturers))\b', q, re.I):
        if not NEGATIVE_QUALIFICATION.search(q):pools.append(field(doc, off+m.start(1), off+m.end(1)))
    for pattern in (
        r'\b('+PARTY+r')\s+(?:has |have )?(?:completed|passed|received|achieved)\s+(?:customer |production |product )?(?:qualification|certification|approval)\b',
        r'\b('+PARTY+r')\s+(?:is|are)\s+(?:an? |the )?(?:qualified|certified|eligible)\s+(?:producer|supplier|manufacturer)\b',
    ):
        if not NEGATIVE_QUALIFICATION.search(q):
            for m in re.finditer(pattern,q):pools.append(field(doc,off+m.start(1),off+m.end(1),reference(doc,off,off+len(q))))
    if f := _unique(pools):
        f['coverage'] = 'OBSERVED_SUPPLIER_SCOPE_NOT_TOTAL_QUALIFIED_CAPACITY'
        out['supply_pool'] = f
    return out


def read_scopes(doc, events, labels, raw=None):
    if hashlib.sha256(doc['body'].encode()).hexdigest() != doc['body_sha256']:
        raise ValueError('BODY_VERSION_MISMATCH')
    lines, excluded = allowed_lines(doc, raw); records = []
    for line in sentences(doc, lines):
        products = _products(doc, line)
        p = bound_product(line,products)
        attrs = _attributes(doc, line, p)
        if re.match(r'^(?:This|The) customer is\b',line['quote']):
            attrs={k:f for k,f in attrs.items() if k=='customer_group'};products=[];p=None
        if p is None:attrs.pop('product',None)
        records.append({**line, 'products': products, 'fields': attrs})
    # Index the actual event statements too, so a multi-sentence paragraph is
    # not itself treated as one product definition.
    for e in events:
        if any(x['start']<=e['locator']['start'] and e['locator']['end']<=x['end'] for x in lines):
            if not any((x['start'],x['end'])==(e['locator']['start'],e['locator']['end']) for x in records):
                line={'start':e['locator']['start'],'end':e['locator']['end'],'quote':e['source_quote']}
                ps=_products(doc,line);p=bound_product(line,ps)
                records.append({**line,'products':ps,'fields':_attributes(doc,line,p) if p else {}})
    # Labels are a complete explicit document definition only when unique and
    # in allowed text. A region metadata menu cannot populate this definition.
    definition = labels('\n'.join(x['quote'] for x in lines))
    global_fields = {}
    for k, f in definition.items():
        candidates = []
        for line in lines:
            for local_key, local in labels(line['quote']).items():
                if local_key == k and local['value'] == f['value']:
                    candidates.append(field(doc, line['start']+local['locator']['start'], line['start']+local['locator']['end']))
        if candidates and (k != 'product' or valid_product(f['value'])): global_fields[k] = candidates[0]
    result = []
    for old in events:
        parent = next((x for x in records if x['start'] <= old['locator']['start'] and old['locator']['end'] <= x['end']), None)
        rec = parent
        if rec is None: continue
        if (rec['start'],rec['end']) != (old['locator']['start'],old['locator']['end']):
            rec={'start':old['locator']['start'],'end':old['locator']['end'],'quote':old['source_quote']}
            rec['products']=_products(doc,rec)
            p=bound_product(rec,rec['products']);rec['fields']=_attributes(doc,rec,p) if p else {}
        e = deepcopy(old); scope = deepcopy(global_fields)
        scope.update(deepcopy(rec['fields']))
        for k, f in labels(rec['quote']).items():
            if k != 'product' or valid_product(f['value']): scope[k] = field(doc, rec['start']+f['locator']['start'], rec['start']+f['locator']['end'])
        # Multi-product prose cannot inherit another line's definition.
        if len({product_key(x['value']) for x in rec['products']}) > 1 and not rec['fields'].get('product'):
            scope = {}; e['scope_unknown_reason'] = 'MULTIPLE_PRODUCTS_NO_EXPLICIT_EVENT_BINDING'
        product = scope.get('product')
        anchors=named_anchors(rec['quote'])
        linked=[x for x in records if any(re.search(r'(?<!\w)'+re.escape(a)+r'(?!\w)',x['quote']) for a in anchors)]
        if not product and anchors:
            sources=[x for x in linked if x['fields'].get('product')]
            f=_unique([x['fields']['product'] for x in sources],product=True)
            if f:
                product=scope['product']=deepcopy(f)
                product['link_kind']='EXACT_NAMED_CONTRACT_OR_PROJECT'
                product['support_references'] += [reference(doc,rec['start'],rec['end'])]+[reference(doc,x['start'],x['end']) for x in sources]
        if product:
            key = product_key(product['value'])
            related = [x for x in records if product_key(x['fields'].get('product',{}).get('value','')) == key
                       and (not named_anchors(x['quote']) or not anchors or set(anchors)&set(named_anchors(x['quote'])))]
            all_anchors={a for x in records if product_key(x['fields'].get('product',{}).get('value',''))==key for a in named_anchors(x['quote'])}
            if not anchors and len(all_anchors)>1:
                related=[rec]  # commodity repetition cannot join distinct projects
            # A named contract/project is an explicit relationship even when
            # the next statement only describes its customer or certification.
            related += [x for x in linked if x not in related and not x['products']]
            order_products={product_key(x['fields']['product']['value']) for x in records if x['fields'].get('product') and re.search(r'\borders?\b',x['quote'],re.I)}
            if len(order_products)==1 and key in order_products and re.search(r'\borders?\b',rec['quote'],re.I):
                # Explicit singular customer anaphor for the sole observed
                # purchase object in this document; no cross-document identity.
                related += [x for x in records if re.match(r'^(?:This|The) customer is\b',x['quote']) and not x['products']]
            for i,x in enumerate(records):
                if x['start']!=rec['start'] or i+1>=len(records):continue
                nxt=records[i+1]
                # Resolve only an explicit physical noun anaphor in the same
                # paragraph with one antecedent. "Its" or an issuer name is
                # never a product link.
                if (nxt.get('paragraph_start')==x.get('paragraph_start') and len({p['value'].casefold() for p in x['products']})==1
                    and re.match(r'^(?:These|Those|This|The)\s+(?:cells|turbines|wafers|lasers|isolators|substrates|product)\b',nxt['quote'])):
                    related.append(nxt)
            # Exact repeated product is a link. Company, geography and pronouns
            # alone never extend a scope. Conflicting specs/customers stay local.
            for k in FIELDS[1:]:
                if k in scope: continue
                candidates = [x['fields'][k] for x in related if k in x['fields']]
                unique = _unique(candidates)
                conflict = any(len({x['fields'][dimension]['value'].casefold() for x in related if dimension in x['fields']}) > 1 for dimension in ('specification','customer_group'))
                if unique and not conflict:
                    scope[k] = deepcopy(unique)
                    scope[k]['support_references'].append(reference(doc, rec['start'], rec['end']))
                    scope[k]['link_kind'] = 'EXACT_REPEATED_PRODUCT'
        # Keep the original generic CHANGE_TARGET grammar only as a lead when
        # its value passed source-bound quality checks in the collection layer.
        e['scope'] = scope
        if 'product' not in scope and not anchors:
            # A generic supplier class in an unrelated paragraph is not an
            # eligible pool for any physical TARGET.
            e['scope'].pop('supply_pool',None)
        e['scope_reader_version'] = VERSION
        e['scope_unknowns'] = {k: e.get('scope_unknown_reason','NO_UNAMBIGUOUS_SOURCE_BOUND_'+k.upper()) for k in FIELDS if k not in scope}
        result.append(e)
    return result, excluded


def validate_references(doc, events):
    for e in events:
        refs = [reference(doc, **e['locator'])]
        for f in e['scope'].values():
            if doc['body'][f['locator']['start']:f['locator']['end']] != f['value']: raise ValueError('SCOPE_LOCATOR_MISMATCH')
            refs += [f['reference']] + f.get('support_references', [])
        for ref in refs:
            loc = ref['locator']
            if (ref['document_id'] != doc['document_id'] or ref['body_sha256'] != doc['body_sha256']
                    or ref['source_quote'] != doc['body'][loc['start']:loc['end']]): raise ValueError('SOURCE_REFERENCE_MISMATCH')
    return True
