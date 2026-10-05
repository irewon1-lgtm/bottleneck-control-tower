"""Isolated BACKFILL diagnostic: change one gate, never production globals.

Observed independence, provenance, direct-origin flags and quote identity remain
unchanged. No call to synthesize, counters, prospective, shadow.run or freeze.
"""
import ast
import copy
import difflib
import inspect
from bct import precursor_v2 as original


def retained_source_checks_failed(demand, supply):
    # _independent mixes cardinality/family checks with these other safeguards.
    return (not demand['direct_origin'] or not supply['direct_origin'] or
            demand['reference']['quote'] == supply['reference']['quote'])


def build_relaxed():
    source = inspect.getsource(original.evaluate_pair_v2)
    before = ast.parse(source)
    after = copy.deepcopy(before)
    expected = ast.dump(ast.parse("not out['independent']", mode='eval').body)
    changed = []
    for node in ast.walk(after):
        if (isinstance(node, ast.If) and ast.dump(node.test) == expected and
                len(node.body) == 1 and isinstance(node.body[0], ast.Expr) and
                ast.unparse(node.body[0]) == "out['reasons'].append('INDEPENDENT_ORIGINS_MISSING')"):
            changed.append(node)
            node.test = ast.BoolOp(op=ast.And(), values=[node.test,
                ast.Call(func=ast.Name(id='_retained_source_checks_failed', ctx=ast.Load()),
                         args=[ast.Name(id='demand', ctx=ast.Load()),
                               ast.Name(id='supply', ctx=ast.Load())], keywords=[])])
    if len(changed) != 1:
        raise ValueError('EXACT_SINGLE_INDEPENDENCE_GATE_NOT_FOUND')
    ast.fix_missing_locations(after)
    # Prove that undoing only this test expression restores the entire AST.
    proof = copy.deepcopy(after)
    restored = 0
    for node in ast.walk(proof):
        if (isinstance(node, ast.If) and isinstance(node.test, ast.BoolOp) and
                ast.dump(node.test.values[0]) == expected):
            node.test = node.test.values[0]
            restored += 1
    if restored != 1 or ast.dump(proof) != ast.dump(before):
        raise ValueError('NON_SOURCE_PREDICATE_CHANGED')
    namespace = dict(original.__dict__)
    namespace['_retained_source_checks_failed'] = retained_source_checks_failed
    exec(compile(after, '<isolated-origin-count-diagnostic>', 'exec'), namespace)
    return namespace['evaluate_pair_v2'], {
        'changed_predicate_count': 1,
        'all_other_AST_nodes_identical': True,
        'observed_independence_unchanged': True,
        'production_module_mutation': False,
        'retained_checks': ['document eligibility/provenance', 'direct_origin',
                            'distinct source quote', 'all non-origin pair gates'],
        'function_diff': ''.join(difflib.unified_diff(
            ast.unparse(before).splitlines(True), ast.unparse(after).splitlines(True),
            fromfile='A_original_function', tofile='B_diagnostic_function')),
    }


def observed_origin_details(demand, supply, documents):
    docs = {d['document_id']: d for d in documents}
    a, b = docs[demand['document_id']], docs[supply['document_id']]
    keys = ('origin_id', 'origin_url', 'origin_publisher', 'body_sha256')
    same = [k for k in keys if original.normalize(str(a[k])) == original.normalize(str(b[k]))]
    origins = {a['origin_id'], b['origin_id']}
    return {'observed_origin_id_count': len(origins), 'origin_ids': sorted(origins),
            'matching_origin_fields': same,
            'same_origin_family': bool(a.get('origin_family') and b.get('origin_family') and
                original.normalize(a['origin_family']) == original.normalize(b['origin_family'])),
            'original_independent': original._independent(demand, supply, docs),
            'direct_origin': [demand['direct_origin'], supply['direct_origin']],
            'distinct_source_quotes': demand['reference']['quote'] != supply['reference']['quote'],
            'retained_source_checks_pass': not retained_source_checks_failed(demand, supply),
            'evidence': [demand['reference'], supply['reference']]}
