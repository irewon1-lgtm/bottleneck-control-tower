"""Recovery must obtain the exact preserved corpus without the expired run."""
import hashlib
import os
from pathlib import Path
import subprocess

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
HELPER_SHA = '7d9188608a66520115727ff5daa30d13190f4958'
SOURCE_SHA = '949e95d2efda7a3fd3e7a124eb0d6569b56b54dcd1a3d5fd7f053dc75b8dfb72'
RSS_SHA = '006124e204a8315e68e9a8abbd39cbca8eacc523e09d89318fbe1d830e2f403a'


def restore_steps():
    workflow = yaml.safe_load((ROOT / '.github/workflows/bct-recovery.yml').read_text())
    steps = workflow['jobs']['storage']['steps']
    restore = next(s for s in steps if s.get('name') == 'Restore original 230-source regression corpus')
    assert 'run' in restore, 'recovery still relies on the expired artifact downloader'
    return steps, restore


def test_fixed230_uses_reviewed_immutable_helpers_and_preserves_gate_contract():
    steps, restore = restore_steps()
    helper = next(s for s in steps if s.get('with', {}).get('path') == '.bct-fixed230-input')
    assert helper['with']['ref'] == HELPER_SHA
    assert helper['with']['persist-credentials'] is False
    assert helper['with']['sparse-checkout'].splitlines() == [
        '/.github/scripts/receive_cpu_sources.py', '/.github/scripts/copy_fixed230.py']
    assert steps.index(helper) < steps.index(restore)
    command = restore['run']
    assert '37790294699' not in command
    assert '--run-id 42939818925 --expected-head 28d0b8c648c0218ab2e74a1fa04ca8d63e659933' in command
    assert '--rss-run-id 42939431146' in command
    assert SOURCE_SHA in command and RSS_SHA in command
    assert 'timeout 300 python .bct-fixed230-input/.github/scripts/receive_cpu_sources.py' in command
    assert 'timeout 60 python .bct-fixed230-input/.github/scripts/copy_fixed230.py' in command
    assert '--destination "$RUNNER_TEMP/bct-recovery/fixed-precursor-qa"' in command
    required = ['Gate 0 then real GitHub storage Gate 1',
                'Gate 2 original source access on GitHub runner',
                'Gate 3 full failed-source inventory',
                'Gate 4 official original verification and evidence holds',
                'Stage 5 cost-zero real-source reading pilot',
                'Gate 5 actual readings and atomic production queue recovery',
                'Gate 6 real source E2E and required whole regressions']
    for name in required:
        assert next(s for s in steps if s.get('name') == name)['if'] == "steps.request.outputs.full_pipeline != 'true'"


@pytest.mark.parametrize('change', ['source_digest', 'source_expired', 'source_id', 'rss_digest'])
def test_unapproved_artifact_stops_real_restore_shell_before_download(tmp_path, change):
    _, restore = restore_steps()
    source = {'id': 13821760877, 'name': 'precursor-private-cache',
              'size_in_bytes': 4598165007, 'digest': 'sha256:' + SOURCE_SHA, 'expired': False}
    rss = {'id': 13820246103, 'name': 'rss-live-result',
           'size_in_bytes': 527551, 'digest': 'sha256:' + RSS_SHA, 'expired': False}
    if change == 'source_digest': source['digest'] = 'sha256:' + '0' * 64
    elif change == 'source_expired': source['expired'] = True
    elif change == 'source_id': source['id'] += 1
    else: rss['digest'] = 'sha256:' + '0' * 64
    bin_dir = tmp_path / 'bin'; bin_dir.mkdir()
    gh = bin_dir / 'gh'
    gh.write_text('#!/usr/bin/env python3\nimport json,sys\n'
                  'from pathlib import Path\n'
                  'if sys.argv[1] != "api":\n'
                  ' Path("unexpected-download").write_text("called")\n'
                  ' raise SystemExit(9)\n'
                  'source=' + repr(source) + '\nrss=' + repr(rss) + '\n'
                  'print(json.dumps({"artifacts":[source if "42939818925" in sys.argv[2] else rss]}))\n')
    gh.chmod(0o755)
    runner = tmp_path / 'runner'; runner.mkdir()
    result = subprocess.run(['bash', '-c', restore['run']], cwd=tmp_path,
                            env={**os.environ, 'RUNNER_TEMP': str(runner),
                                 'PATH': str(bin_dir) + os.pathsep + os.environ['PATH']},
                            capture_output=True, text=True, timeout=15)
    assert result.returncode != 0
    assert 'FIXED230_APPROVED_ARTIFACT_BINDING' in result.stderr
    assert not (tmp_path / 'unexpected-download').exists()


@pytest.mark.parametrize('changed_receipt', [False, True])
def test_real_restore_shell_orders_receive_before_copy_and_rechecks_digest(tmp_path, changed_receipt):
    _, restore = restore_steps()
    # This authored transport manifest is not the saved RSS evidence. Only the
    # workflow's expected manifest hash is replaced for this shell-only test.
    manifest = b'{"format":"bct-new-rss-delta-v1","documents":[]}'
    command = restore['run'].replace(
        '65aa1e71528bc0b2e156ba83ad4ff7d76ecf3c30536a1ffb0b72601f2abe0446',
        hashlib.sha256(manifest).hexdigest())
    source = {'id': 13821760877, 'name': 'precursor-private-cache',
              'size_in_bytes': 4598165007, 'digest': 'sha256:' + SOURCE_SHA, 'expired': False}
    rss = {'id': 13820246103, 'name': 'rss-live-result',
           'size_in_bytes': 527551, 'digest': 'sha256:' + RSS_SHA, 'expired': False}
    bin_dir = tmp_path / 'bin'; bin_dir.mkdir()
    gh = bin_dir / 'gh'
    gh.write_text('#!/usr/bin/env python3\nimport json,sys\nfrom pathlib import Path\n'
                  'source=' + repr(source) + '\nrss=' + repr(rss) + '\n'
                  'if sys.argv[1] == "api":\n'
                  ' print(json.dumps({"artifacts":[source if "42939818925" in sys.argv[2] else rss]}))\n'
                  'else:\n'
                  ' destination=Path(sys.argv[sys.argv.index("--dir")+1]); destination.mkdir()\n'
                  ' (destination/"new-document-manifest.json").write_bytes(' + repr(manifest) + ')\n')
    gh.chmod(0o755)
    helpers = tmp_path / '.bct-fixed230-input/.github/scripts'; helpers.mkdir(parents=True)
    (helpers / 'receive_cpu_sources.py').write_text(
        'import json,sys\nfrom pathlib import Path\n'
        'def argument(name): return Path(sys.argv[sys.argv.index(name)+1])\n'
        'argument("--destination").mkdir()\n'
        'argument("--receipt").write_text(json.dumps({'
        '"status":"PASS_BOUNDED_CPU_INPUT_TRANSPORT","artifact_id":13821760877,'
        '"artifact_digest":' + repr('sha256:' + ('0' * 64 if changed_receipt else SOURCE_SHA)) + '}))\n'
        'Path("receive-called").write_text("called")\n')
    (helpers / 'copy_fixed230.py').write_text(
        'import sys\nfrom pathlib import Path\n'
        'def argument(name): return Path(sys.argv[sys.argv.index(name)+1])\n'
        'assert argument("--cache").is_dir()\n'
        'argument("--destination").mkdir()\n'
        'argument("--receipt").write_text(__import__("json").dumps({'
        '"status":"PASS_EXACT_FIXED230_LITERAL_COPY","source_input_sha256":"acd344732f2f087b42767bfe32d9f16d96da6de49a766d6fc73f3c0ed298f9ec",'
        '"documents":230,"body_hashes_verified":230,"raw_hashes_verified":230,"copied_files":460,"copied_bytes":41784646,'
        '"copied_file_hash_map_sha256":"a489b7f008fa80bf3729d1563a29c7e60effd4da011ba9fa54abed010689e566"}))\n'
        'Path("copy-called").write_text("called")\n')
    runner = tmp_path / 'runner'; runner.mkdir()
    result = subprocess.run(['bash', '-c', command], cwd=tmp_path,
                            env={**os.environ, 'RUNNER_TEMP': str(runner),
                                 'PATH': str(bin_dir) + os.pathsep + os.environ['PATH']},
                            capture_output=True, text=True, timeout=15)
    assert (tmp_path / 'receive-called').exists()
    if changed_receipt:
        assert result.returncode != 0
        assert 'FIXED230_APPROVED_SOURCE_RECEIPT_BINDING' in result.stderr
        assert not (tmp_path / 'copy-called').exists()
    else:
        assert result.returncode == 0, result.stderr
        assert (tmp_path / 'copy-called').exists()
        assert (runner / 'bct-recovery/fixed-precursor-qa').is_dir()
        assert (runner / 'bct-recovery/fixed230-copy.json').is_file()


@pytest.mark.parametrize('changed_map', [False, True])
@pytest.mark.parametrize('already_carried', [False, True])
def test_compact_authenticated_resume_avoids_legacy_archive_and_rechecks_exact_file_map(tmp_path, changed_map, already_carried):
    _, restore = restore_steps()
    runner = tmp_path/'runner'; corpus = runner/'bct-recovery-resume/fixed-precursor-qa'; corpus.mkdir(parents=True)
    (corpus.parent/'checkpoint.json').write_text('{"run_id":"20","code_sha":"'+ 'a'*40 +'"}')
    if already_carried:
        (runner/'bct-recovery/fixed-precursor-qa').mkdir(parents=True)
        (runner/'bct-recovery/fixed230-copy.json').write_text('{"prior":"authenticated input receipt"}')
    helpers = tmp_path/'.bct-fixed230-input/.github/scripts'; helpers.mkdir(parents=True)
    (helpers/'copy_fixed230.py').write_text(
        'import json,sys\nfrom pathlib import Path\n'
        'def argument(name): return Path(sys.argv[sys.argv.index(name)+1])\n'
        'assert argument("--cache").name=="fixed-precursor-qa"\n'
        'assert argument("--cache").parent.name=='+repr('bct-recovery' if already_carried else 'bct-recovery-resume')+'\n'
        'argument("--destination").mkdir()\n'
        'argument("--receipt").write_text(json.dumps({'
        '"status":"PASS_EXACT_FIXED230_LITERAL_COPY","source_input_sha256":"acd344732f2f087b42767bfe32d9f16d96da6de49a766d6fc73f3c0ed298f9ec",'
        '"documents":230,"body_hashes_verified":230,"raw_hashes_verified":230,"copied_files":460,"copied_bytes":41784646,'
        '"copied_file_hash_map_sha256":'+repr('0'*64 if changed_map else 'a489b7f008fa80bf3729d1563a29c7e60effd4da011ba9fa54abed010689e566')+'}))\n'
        'Path("compact-copy-called").write_text("called")\n')
    bin_dir=tmp_path/'bin'; bin_dir.mkdir(); gh=bin_dir/'gh'
    gh.write_text('#!/usr/bin/env python3\nfrom pathlib import Path\nPath("unexpected-api").write_text("called")\nraise SystemExit(99)\n'); gh.chmod(0o755)
    result = subprocess.run(['bash','-c',restore['run']],cwd=tmp_path,
        env={**os.environ,'RUNNER_TEMP':str(runner),'PATH':str(bin_dir)+os.pathsep+os.environ['PATH']},
        capture_output=True,text=True,timeout=15)
    assert (tmp_path/'compact-copy-called').exists()
    assert not (tmp_path/'unexpected-api').exists()
    if changed_map:
        assert result.returncode != 0 and 'FIXED230_COMPACT_GOLDEN_FILE_MAP_BINDING' in result.stderr
    else:
        assert result.returncode==0,result.stderr
        assert (runner/'bct-recovery/fixed230-input-transport.json').is_file()


def test_recovery_checkpoint_retains_compact_corpus_for_bounded_future_restores():
    steps, _ = restore_steps()
    upload = next(s for s in steps if s.get('uses')=='actions/upload-artifact@v4')
    assert '${{ runner.temp }}/bct-recovery/fixed-precursor-qa/documents/*.json' in upload['with']['path']
    assert '${{ runner.temp }}/bct-recovery/fixed-precursor-qa/raw/*' in upload['with']['path']
