#!/usr/bin/env python3
"""Manual Q1-only encrypted handoff; does not change CPU variables or schedules."""
import argparse,base64,hashlib,json,os,re,subprocess,tempfile
from pathlib import Path
from bct.v4 import private_state as private,quantitative_private as q
from bct.v4.store import Ledger,file_sha,sha

ROOT=Path('var/v4/quantitative/q1-transfer')

def gpg(home,*args,data=None):
    p=subprocess.run(['gpg','--no-options','--homedir',str(home),'--batch','--no-tty',*args],input=data,capture_output=True,timeout=25)
    if p.returncode:raise ValueError('Q1_EPHEMERAL_ENCRYPTION_FAILED')
    return p.stdout


def prepare():
    if os.environ.get('GITHUB_REF')!='refs/heads/codex/bct-v4-integration':raise ValueError('Q1_MANUAL_DEVELOPMENT_ONLY')
    from bct.v4.cpu_operations import github_guard
    github_guard()
    ROOT.mkdir(parents=True,exist_ok=False)
    with tempfile.TemporaryDirectory(prefix='bct-q1-one-use-')as home:
        os.chmod(home,0o700)
        gpg(home,'--pinentry-mode','loopback','--passphrase','','--quick-generate-key','BCT Q1 one-use transport','rsa3072','encr','1d')
        pub=gpg(home,'--export');secret=gpg(home,'--export-secret-keys')
        (ROOT/'wrapped-key.gpg').write_bytes(private._gpg(secret,os.environ.get('BCT_V4_STATE_PASSPHRASE','')))
        fingerprint=next(line.split(':')[9]for line in gpg(home,'--with-colons','--list-keys').decode().splitlines()if line.startswith('fpr:'))
        result={'public_base64':base64.b64encode(pub).decode(),'public_sha256':sha(pub),'fingerprint':fingerprint,
                'run_id':os.environ['GITHUB_RUN_ID'],'code_sha':os.environ['GITHUB_SHA'],'private_key_output':False}
        (ROOT/'public.json').write_text(json.dumps(result))
    print('BCT_Q1_TRANSPORT_PUBLIC_JSON='+json.dumps(result))


def encrypt(a):
    p=json.loads(a.public.read_text());pub=base64.b64decode(p['public_base64'],validate=True)
    if sha(pub)!=p['public_sha256']:raise ValueError('Q1_PUBLIC_TRANSPORT_HASH')
    cp=a.checkpoint;proof=json.loads((cp/'checkpoint.json').read_text())
    with tempfile.TemporaryDirectory(prefix='bct-q1-transfer-')as tmp:
        q.restore(cp,Path(tmp)/'verify')
        home=Path(tmp)/'gpg';home.mkdir(mode=0o700)
        gpg(home,'--import',data=pub)
        fingerprint=next(line.split(':')[9]for line in gpg(home,'--with-colons','--list-keys').decode().splitlines()if line.startswith('fpr:'))
        if fingerprint!=p['fingerprint']:raise ValueError('Q1_RECIPIENT_FINGERPRINT')
        archive=(cp/'checkpoint.sqlite3.gz').read_bytes()
        envelope=json.dumps({'format':q.FORMAT,'key_run':p['run_id'],'key_code_sha':p['code_sha'],
                             'proof':proof,'archive_base64':base64.b64encode(archive).decode()}).encode()
        encrypted=gpg(home,'--trust-model','always','--encrypt','--recipient',fingerprint,data=envelope)
        if len(encrypted)>private.MAX_TRANSPORT:raise ValueError('Q1_TRANSFER_SIZE_BOUND')
        a.packet.write_bytes(encrypted)
    print(json.dumps({'encrypted_bytes':len(encrypted),'encrypted_sha256':file_sha(a.packet),'key_run':p['run_id'],
                      'sqlite_sha256':proof['sqlite_sha256'],'contains_plaintext_in_public':False}))


def publish():
    if os.environ.get('GITHUB_REF')!='refs/heads/codex/bct-v4-integration':raise ValueError('Q1_MANUAL_DEVELOPMENT_ONLY')
    from bct.v4.cpu_operations import github_guard
    github_guard()
    blob=os.environ.get('Q1_BLOB_SHA','');expected=os.environ.get('Q1_PACKET_SHA','');keyrun=os.environ.get('Q1_KEY_RUN','')
    if not re.fullmatch('[0-9a-f]{40}',blob)or not re.fullmatch('[0-9a-f]{64}',expected)or not re.fullmatch('[0-9]{5,20}',keyrun):raise ValueError('Q1_TRANSFER_INPUT_CONTRACT')
    # Verify the cache-key run belongs to this exact development code, not input metadata.
    run=subprocess.run(['gh','api',f'repos/{private.PUBLIC_REPO}/actions/runs/{keyrun}'],capture_output=True,text=True,timeout=25)
    if run.returncode:raise ValueError('Q1_KEY_RUN_LOOKUP_FAILED')
    run=json.loads(run.stdout)
    if run.get('head_sha')!=os.environ['GITHUB_SHA']or run.get('event')!='workflow_dispatch'or run.get('conclusion')!='success':raise ValueError('Q1_UNTRUSTED_KEY_RUN')
    response=subprocess.run(['gh','api',f'repos/{private.PUBLIC_REPO}/git/blobs/{blob}'],capture_output=True,text=True,timeout=25)
    if response.returncode:raise ValueError('Q1_CIPHERTEXT_DOWNLOAD_FAILED')
    response=json.loads(response.stdout)
    if response.get('size',private.MAX_TRANSPORT+1)>private.MAX_TRANSPORT:raise ValueError('Q1_TRANSFER_SIZE_BOUND')
    ciphertext=base64.b64decode(response['content'])
    if sha(ciphertext)!=expected:raise ValueError('Q1_CIPHERTEXT_HASH')
    secret=private._gpg((ROOT/'wrapped-key.gpg').read_bytes(),os.environ.get('BCT_V4_STATE_PASSPHRASE',''),decrypt=True)
    with tempfile.TemporaryDirectory(prefix='bct-q1-receiver-')as tmp:
        home=Path(tmp)/'gpg';home.mkdir(mode=0o700);gpg(home,'--import',data=secret)
        envelope=json.loads(gpg(home,'--max-output',str(private.MAX_TRANSPORT),'--decrypt',data=ciphertext))
        if envelope['format']!=q.FORMAT or str(envelope['key_run'])!=keyrun or envelope['key_code_sha']!=os.environ['GITHUB_SHA']:raise ValueError('Q1_ENVELOPE_IDENTITY')
        cp=Path(tmp)/'checkpoint';cp.mkdir()
        (cp/'checkpoint.json').write_text(json.dumps(envelope['proof']))
        archive=base64.b64decode(envelope['archive_base64'],validate=True)
        if len(archive)>q.LIMIT:raise ValueError('Q1_CHECKPOINT_SIZE')
        (cp/'checkpoint.sqlite3.gz').write_bytes(archive)
        verified=q.restore(cp,Path(tmp)/'before-publish')
        owner=json.loads(Path('docs/v4/cpu-automation/preflight/connection-results.json').read_text())
        if owner['actual_remote_evidence']['run_id']!=38709974717:raise ValueError('Q1_SCOPE_PROOF_NOT_PINNED')
        scope=owner['actual_remote_evidence']['receipts']['BCT_PRIVATE_SCOPE_JSON']['scope']
        # Existing dedicated PAT only; never fall back to the public GH_TOKEN.
        result=q.publish(Path(tmp)/'private-git',cp,'',os.environ.get('BCT_V4_PRIVATE_STATE_TOKEN',''),scope)
        print('BCT_Q1_PRIVATE_RESULT_JSON='+json.dumps(result))


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','encrypt','publish','checkpoint','restore'])
    p.add_argument('--checkpoint',type=Path,default=Path('var/v4/quantitative/q1/private-checkpoint'))
    p.add_argument('--root',type=Path,default=Path('var/v4/quantitative/q1/ledger'))
    p.add_argument('--public',type=Path);p.add_argument('--packet',type=Path);a=p.parse_args()
    if a.action=='prepare':prepare()
    elif a.action=='encrypt':encrypt(a)
    elif a.action=='publish':publish()
    elif a.action=='restore':print(json.dumps(q.restore(a.checkpoint,a.root)))
    else:
        l=Ledger(a.root)
        try:
            with l.worker():print(json.dumps(q.checkpoint(l,a.checkpoint)))
        finally:l.close()
if __name__=='__main__':main()
