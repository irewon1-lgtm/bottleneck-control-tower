"""Bounded direct capture of public repository URLs; no queries or LIVE writes.

Results are QA acquisition evidence only. Existing research verdicts do not
supply scope, dates, qualifications or a shortage label to the reader.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path

from bct import precursor_collection as c, precursor_scope_reader as scope, precursor_discovery as pd
from bct.objective_lock import stamp_export

SOURCES = (
    ('gas_turbine_slots','docs/verified-bottlenecks.json','https://www.sec.gov/Archives/edgar/data/1996810/000199681026000148/gev-20260630.htm'),
    ('grid_interconnection','docs/verified-bottlenecks.json','https://www.ofgem.gov.uk/press-release/ofgem-acts-free-grid-capacity-tackling-speculative-data-centre-projects'),
    ('defense_tungsten','docs/registrations/hemerdon-elmt/sources.json','https://www.sec.gov/Archives/edgar/data/2101698/000121390026102242/ea0306073-8k_elmet.htm'),
    ('suas_batteries','docs/registrations/suas-cells-20261007/sources.json','https://www.sec.gov/Archives/edgar/data/1899287/000189928726000065/ampx-20260923.htm'),
    ('cpo_els_isolators','docs/registrations/cpo-els-garnet/sources-20261006.json','https://developer.nvidia.com/blog/how-industry-collaboration-fosters-nvidia-co-packaged-optics'),
    ('siph_qualified_testing','docs/registrations/siph-cpo-20261006/sources.json','https://www.aehr.com/2026/07/aehr-receives-follow-on-production-order-from-lead-silicon-photonics-customer-for-fully-automated-fox-xp-wafer-level-burn-in-system/'),
)


def run(root):
    repository=Path(__file__).resolve().parents[1]
    for case,path,url in SOURCES:
        if url not in (repository/path).read_text():raise ValueError('URL not in preserved public source registry')
    activation={'excluded_document_ids':[],'excluded_urls':[], 'new_document_cutover':c.acquisition.now()}
    verified=[]
    def acquire(source):
        case,path,url=source
        record=c.capture(root,url,'official-qa-'+case,activation)
        # The QA root is never passed to an operational collector or LIVE store.
        # Re-read derived facts explicitly as BACKFILL_QA, not fresh discovery.
        if record.get('provenance')=='PASS':
            raw=(Path(root)/'raw'/(record['raw_sha256']+'.html')).read_bytes()
            record=c.structure(record,raw)
            scope.validate_references(record,record['retained_collection_events'])
            verified.append(record)
        result={'case':case,'registry':path,'origin_url':url,'status':record['status'],
                'provenance':record.get('provenance'),'body_acquired':bool(record.get('raw_sha256')),
                'full_body':record.get('body_status')=='FULL','blockers':record.get('provenance_blockers',[]),
                'official_blocker':record.get('official_blocker'),'error':record.get('error'),
                'published_at':record.get('published_at'),'acquired_at':record.get('acquired_at'),
                'body_sha256':record.get('body_sha256'),'raw_sha256':record.get('raw_sha256'),
                'events':len(record.get('retained_collection_events',[])),
                'complete_target_events':sum(not e['missing_scope'] for e in record.get('retained_collection_events',[])),
                'roles':sorted({e['role'] for e in record.get('precursor_events',[])})}
        print(json.dumps(result),flush=True)
        return result
    with ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(acquire,SOURCES))
    result,prepared=pd.discover(stamp_export({'mode':'BACKFILL','documents':verified,'signals':[]}),mode='BACKFILL')
    stats=c.counters(result,prepared)
    return {'mode':'BACKFILL_QA_DIRECT_PUBLIC_URLS','search_requests':0,'url_attempts':len(results),
            'bodies_acquired':sum(r['body_acquired'] for r in results),
            'provenance_verified_originals':sum(r['provenance']=='PASS' for r in results),
            'valid_independent_scope_pairs':len(stats['independent_demand_supply_pairs']),
            'backfill_early_candidates':len(result['candidates']),
            'new_live_early_candidates':0,'live_write_count':0,'results':results}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--state',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();value=run(args.state);args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(value,indent=2)+'\n')
