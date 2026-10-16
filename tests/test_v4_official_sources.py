"""Synthetic format/safety regressions, not independent semantic accuracy."""
from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from bct.objective_lock import stamp_export
from bct.v4 import official_sources as f, quantitative as q, quantitative_private as private
from bct.v4.official_credentials import request, bindings
from bct.v4.store import Ledger, sha, file_sha


def meta(source, data):
    return {'source_id': source, 'url': 'https://'+sorted(f.HOSTS[source])[0]+'/synthetic',
            'sha256': sha(json.dumps(data).encode()), 'acquired_at': '2026-10-16T00:00:00Z'}


def ocds():
    return {'releases': [{'ocid': 'synthetic-ocid', 'id': 'release1', 'date': '2026-10-14T12:00:00Z',
                         'tag': ['award', 'contract'], 'buyer': {'id': 'buyer-id', 'name': 'Synthetic agency'},
                         'tender': {'id': 'tender-id', 'status': 'complete', 'title': 'Equipment framework',
                                    'lots': [{'id': 'lot1', 'status': 'cancelled'}]},
                         'awards': [{'id': 'award1', 'status': 'active', 'value': {'amount': 800000000, 'currency': 'USD'}}],
                         'contracts': [{'id': 'contract1', 'awardID': 'award1', 'status': 'active',
                                        'dateSigned': '2026-10-13', 'period': {'endDate': '2027-12-31'}}]}]}


def test_ocds_separate_contract_award_lot_and_money_not_quantity_or_delivery():
    native = ocds(); rows, nxt = f.parse_json(native, meta('find_tender', native))
    assert len(rows) == 4 and nxt is None
    assert sum(f.recheck(r, native) for r in rows) > 12
    award = next(r for r in rows if r['record_kind'] == 'PROCUREMENT_AWARD')
    contract = next(r for r in rows if r['record_kind'] == 'PROCUREMENT_CONTRACT')
    assert award['claims']['amount']['value'] == 800000000 and 'item_quantity' not in award['claims']
    assert contract['claims']['award_id']['value'] == 'award1'
    assert contract['claims']['period_end']['value'] == '2027-12-31' and 'delivery_date' not in contract['claims']
    assert any(r['claims'].get('lot_status', {}).get('value') == 'cancelled' for r in rows)
    h = f.q2_review_inputs(rows)
    assert h['signed_contract_records'] == 1 and h['Q3_eligible_targets'] == []
    assert all(r['s_stage'] == r['qualified_supply'] == 'UNKNOWN' for r in rows)


def test_native_field_mismatch_rejected_not_fuzzy_or_first_match():
    native = ocds(); rows, _ = f.parse_json(native, meta('find_tender', native))
    changed = deepcopy(native); changed['releases'][0]['buyer']['name'] = 'Other buyer'
    with pytest.raises(ValueError, match='NATIVE_MISMATCH'): f.recheck(rows[0], changed)
    bad = deepcopy(rows[0]); bad['claims']['buyer_name']['locator']['pointer'] = '/releases/9/buyer/name'
    with pytest.raises(ValueError, match='FACT_ID'): f.validate(bad)


def test_reviewed_description_requires_unique_anchor_exact_field_and_retains_conflict():
    native = ocds(); text = 'Purchase of 4 x Model4 vehicles. Not available before 2028.'
    native['releases'][0]['tender']['description'] = text
    field = {'relative_pointer': '/tender/description', 'field_sha256': sha(text.encode()),
             'anchor': 'Purchase of 4 x Model4', 'offset': 12, 'literal': '4'}
    annotation = {'notice_id': 'release1', 'fields': {'reported_item_quantity_literal': field}}
    rows = f.reviewed_item_descriptions(native, meta('find_tender', native), [annotation])
    assert f.recheck(rows[0], native) == len(rows[0]['claims'])
    assert rows[0]['claims']['reported_item_quantity_literal']['value'] == '4'
    assert rows[0]['claims']['lot_status']['value'] == 'cancelled'
    assert 'item_quantity' not in rows[0]['claims'] and rows[0]['qualified_supply'] == 'UNKNOWN'
    changed = deepcopy(native); changed['releases'][0]['tender']['description'] = text.replace('Not available', 'Available')
    with pytest.raises(ValueError, match='CHANGED'): f.reviewed_item_descriptions(changed, meta('find_tender', changed), [annotation])


def test_exact_item_quantity_requires_physical_unit_not_currency():
    native = ocds(); native['releases'][0]['awards'][0]['items'] = [{'id': 'item1', 'quantity': 12, 'unit': {'name': 'widgets'}}]
    rows, _ = f.parse_json(native, meta('find_tender', native))
    assert [r['claims']['item_quantity']['value'] for r in rows if 'item_quantity' in r['claims']] == [12]
    native['releases'][0]['awards'][0]['items'][0]['unit']['name'] = 'USD'
    with pytest.raises(ValueError, match='NOT_PHYSICAL'): f.parse_json(native, meta('find_tender', native))


def test_miso_duplicate_project_numbers_keep_native_ids_and_no_manufacturer_inference():
    native = [{'id': 1, 'projectNumber': 'J1', 'summerNetMW': 180.0, 'applicationStatus': 'Active', 'transmissionOwner': 'Grid Owner'},
              {'id': 2, 'projectNumber': 'J1', 'summerNetMW': 0.0, 'applicationStatus': 'Active'}]
    rows, _ = f.parse_json(native, meta('miso', native))
    assert len({r['logical_id'] for r in rows}) == 2 and len({r['source_lineage'] for r in rows}) == 1
    assert rows[0]['claims']['transmission_owner']['value'] == 'Grid Owner'
    assert rows[0]['published_at'] == 'UNKNOWN' and rows[0]['qualified_supply'] == 'UNKNOWN'


def test_csv_quoted_cells_and_row_reordering_preserve_project_identity():
    raw = ('Project ID,MW Effective From,Stage,Agreement Type,Customer Name,MW Connected,MW Increase / Decrease,Cumulative Total Capacity (MW)\n'
           'P1,2028-01-01,A,Direct,"Grid, Ltd",0,-20,80\nP1,2029-01-01,B,Direct,Grid Ltd,80,10,90\n').encode()
    m = meta('neso', {}); a, native = f.parse_csv(raw, m)
    assert f.recheck(a[0], native) == len(a[0]['claims']) and a[0]['claims']['capacity_change_MW']['value'] == '-20'
    lines = raw.decode().splitlines(); other = ('\n'.join([lines[0], lines[2], lines[1]])+'\n').encode()
    b, _ = f.parse_csv(other, meta('neso', {}))
    assert a[0]['logical_id'] == b[1]['logical_id'] and a[0]['logical_id'] != a[1]['logical_id']
    assert a[0]['published_at'] == 'UNKNOWN'


def test_worldbank_cancelled_award_kept_not_actual_demand():
    data = {'procnotices': [{'id': 'OP1', 'noticedate': '06-Aug-2013', 'notice_type': 'Contract Award', 'notice_status': 'Cancelled', 'project_id': 'P1'}]}
    rows, _ = f.parse_json(data, meta('world_bank', data))
    assert rows[0]['claims']['notice_status']['value'] == 'Cancelled'
    assert rows[0]['published_at'] == '2013-08-06' and f.q2_review_inputs(rows)['signed_contract_records'] == 0


def test_ercot_headers_cell_dates_and_planned_capacity_are_distinct():
    from openpyxl import Workbook
    from datetime import datetime
    w = Workbook(); w.remove(w.active)
    for sn in ['Project Details - Large Gen', 'Project Details - Small Gen', 'Commissioning Update', 'Cancellation Update']:
        s = w.create_sheet(sn); s.append(['INR', 'Project Name', 'Capacity (MW)', 'Projected COD']); s.append(['26INR001', 'Synthetic project', 10, datetime(2028, 1, 2)])
    rows, coverage = f.parse_ercot(w, meta('ercot', {}))
    assert len(rows) == 4 and f.recheck(rows[0], w) == 4
    assert rows[0]['claims']['planned_service_date']['value'] == '2028-01-02T00:00:00'
    assert all(r['qualified_supply'] == 'UNKNOWN' for r in rows)
    w.close()


@pytest.mark.parametrize('mutation', ['stage', 'host', 'hash', 'contact', 'unknown_field'])
def test_unreviewed_or_sensitive_fact_cannot_be_saved(tmp_path, mutation):
    rows, _ = f.parse_json(ocds(), meta('find_tender', ocds())); r = deepcopy(rows[0])
    if mutation == 'stage': r['s_stage'] = 'S3'
    if mutation == 'host': r['url'] = 'https://other.example/synthetic'
    if mutation == 'hash': r['source_hash'] = 'wrong'
    if mutation == 'contact': r['claims']['buyer_name']['value'] = 'synthetic@example.org'
    if mutation == 'unknown_field': r['body'] = 'source prose must not enter capsule'
    l = Ledger(tmp_path/'ledger')
    with pytest.raises(ValueError): f.save(l, [rows[0], r])
    assert l.db.execute('SELECT count(*)FROM events').fetchone()[0] == 0; l.close()


def test_existing_private_capsule_restart_restores_new_facts_without_originals(tmp_path):
    l = Ledger(tmp_path/'ledger'); raw = tmp_path/'synthetic.json'; raw.write_bytes(b'{"value":1}')
    m = {'source_id': 'usaspending', 'url': 'https://api.usaspending.gov/api/v2/transactions/', 'sha256': file_sha(raw), 'path': str(raw), 'acquired_at': '2026-10-16'}
    r = q.observation(m, 'synthetic', 'class', 'money', 1, 'USD', 'MONEY', '2026-09', {'format': 'JSON', 'path': ['value']})
    q.commit_page(l, 'synthetic', m, [r]); records, _ = f.parse_json(ocds(), meta('find_tender', ocds()))
    assert f.save(l, records)['added'] == 4
    proof = private.checkpoint(l, tmp_path/'checkpoint'); l.close()
    subprocess.run([sys.executable, '-c', 'import sys;from bct.v4.quantitative_private import restore;restore(sys.argv[1],sys.argv[2])', str(tmp_path/'checkpoint'), str(tmp_path/'new-process')], check=True, capture_output=True, timeout=30)
    l = Ledger(tmp_path/'new-process'); before = file_sha(l.path)
    assert f.save(l, records)['added'] == 0 and file_sha(l.path) == before == proof['sqlite_sha256']
    assert l.db.execute('SELECT count(*)FROM blobs').fetchone()[0] == 0
    assert l.db.execute('SELECT count(*)FROM firsts').fetchone()[0] == 0; l.close()


def test_optional_key_routes_never_use_demo_or_leak_into_receipts():
    assert all(not r['present'] for r in bindings({}).values())
    req, receipt = request('sam_opportunities', {'limit': 10}, {})
    assert req is None and receipt['status'] == 'NEEDS_USER_KEY'
    key = 'synthetic-not-a-real-key'
    req, receipt = request('sam_opportunities', {'limit': 10}, {'BCT_SAM_API_KEY': key})
    assert key in req.full_url and key not in json.dumps(receipt) and 'api_key' not in receipt['url']
    with pytest.raises(ValueError, match='PARAMETER'): request('sam_awards', {'unrevealed': True}, {'BCT_SAM_API_KEY': key})
    with pytest.raises(ValueError, match='UNVERIFIED'): request('korea_pps', {}, {})


def _collector():
    spec = importlib.util.spec_from_file_location('official_tool', 'tools/v4_official_sources.py'); module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module


def test_failure_isolated_offline_cache_and_pending_can_resume_without_new_run_id(tmp_path):
    tool = _collector(); cache = tmp_path/'captures'; cache.mkdir()
    data = [{'id': 1, 'projectNumber': 'J1', 'summerNetMW': 1}]; u = 'https://www.misoenergy.org/synthetic'
    raw = json.dumps(data).encode(); k = sha(u.encode())
    (cache/(k+'.raw')).write_bytes(raw); (cache/(k+'.json')).write_text(json.dumps({'url': u, 'status': 200, 'raw_sha256': sha(raw), 'acquired_at': '2026-10-16'}))
    base = {'format': 'JSON', 'max_pages': 1, 'archive_facts': True, 'semantic_limits': 'synthetic'}
    reg = stamp_export({'global_sources': {'collection_jobs': [{**base, 'id': 'ready', 'source_id': 'miso', 'url': u}, {**base, 'id': 'pending', 'source_id': 'gleif', 'url': 'https://api.gleif.org/synthetic'}]}})
    l = Ledger(tmp_path/'ledger'); result = tool.collect(l, reg, tmp_path)
    assert result['record_versions_total'] == 1 and any(r['status'] == 'NOT_FETCHED_OFFLINE' for r in result['pages'])
    assert tool._state(l, 'pending', 1) is None
    again = tool.collect(l, reg, tmp_path)
    assert again['record_versions_total'] == 1 and again['HTTP_requests_this_batch'] == 0
    (cache/(k+'.raw')).write_bytes(b'corrupted')
    with pytest.raises(ValueError, match='CACHE_HASH'): tool.Capture(cache).get('miso', u)
    l.close()
