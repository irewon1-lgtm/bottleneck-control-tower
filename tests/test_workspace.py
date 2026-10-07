import copy, hashlib, json, sqlite3, subprocess, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bct_stocks as b

class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
        self.policy=json.loads((b.ROOT/'project.json').read_text())
        self.c=b.connect(self.root/'workspace.db',self.policy)
        self.repo=self.root/'source'; self.repo.mkdir()
        self.g('init','-b','main'); self.g('config','user.email','test@example.invalid'); self.g('config','user.name','Test')
        (self.repo/'docs').mkdir(); (self.repo/'tests').mkdir()
        doc={'targets':[{'id':'target-example','history':[{'id':'h1','status':'OBSERVE','sources':[{'url':'https://example.invalid/report','publisher':'Example supplier'}],'companies':[{'ticker':'EXAMPLE','name':'Example issuer'}]}]}]}
        (self.repo/'future-tracking.json').write_text(json.dumps(doc))
        (self.repo/'docs'/'report.md').write_text('Example source https://example.invalid/report\n')
        (self.repo/'tests'/'fixture.json').write_text('{"ticker":"FALSE"}')
        source_db=sqlite3.connect(self.repo/'canonical.sqlite3'); source_db.execute('CREATE TABLE docs(id TEXT, body TEXT)'); source_db.execute('INSERT INTO docs VALUES(?,?)',('d1','retained original')); source_db.commit(); source_db.close()
        self.g('add','.'); self.g('commit','-m','initial')
        commit=self.g('rev-parse','HEAD').decode().strip()
        for branch in ['main','data','future-bottleneck-data','bct-stocks']:
            self.g('update-ref','refs/remotes/bct/'+branch,commit)
    def g(self,*args):
        return subprocess.run(['git','-C',str(self.repo),*args],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE).stdout
    def tearDown(self): self.c.close(); self.tmp.cleanup()
    def test_01_goal_persisted(self):
        x=self.c.execute('SELECT policy_json FROM objective_versions').fetchone()[0]
        self.assertIn('2~3배',x); self.assertIn('OTC',x)
    def test_02_import_and_source_preserved(self):
        before=self.g('rev-parse','HEAD'); result=b.import_git(self.c,self.repo,self.policy)
        self.assertEqual(result['result'],'IMPORTED'); self.assertEqual(before,self.g('rev-parse','HEAD'))
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM target_histories').fetchone()[0],1)
    def test_03_idempotence(self):
        b.import_git(self.c,self.repo,self.policy); before=b.stats(self.c)
        self.assertEqual(b.import_git(self.c,self.repo,self.policy)['result'],'ALREADY_IMPORTED'); self.assertEqual(before,b.stats(self.c))
    def test_04_tests_excluded(self):
        b.import_git(self.c,self.repo,self.policy)
        self.assertFalse(self.c.execute("SELECT 1 FROM entity_mentions WHERE value='FALSE'").fetchone())
    def test_05_no_stock_verdict_from_bct(self):
        b.import_git(self.c,self.repo,self.policy)
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM candidates').fetchone()[0],0)
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM decisions').fetchone()[0],0)
        self.assertEqual(self.c.execute('SELECT DISTINCT state FROM entity_mentions').fetchone()[0],'UNRESOLVED_NOT_A_CANDIDATE')
    def test_06_append_only_policy(self):
        with self.assertRaises(sqlite3.IntegrityError): self.c.execute("UPDATE objective_versions SET policy_json='{}'")
    def test_07_hash_tampering_fails(self):
        with self.assertRaises(ValueError): b.import_blob(self.c,'0'*40,b'{}','bad.json')
    def test_08_all_blob_hashes_verified(self):
        b.import_git(self.c,self.repo,self.policy)
        self.assertEqual(b.verify(self.c)['source_hash_errors'],0)
    def test_09_sqlite_rows_copied(self):
        b.import_git(self.c,self.repo,self.policy)
        self.assertEqual(self.c.execute("SELECT COUNT(*) FROM imported_records WHERE kind='BCT_SQLITE_ROW'").fetchone()[0],1)
    def test_10_new_import_preserves_old(self):
        b.import_git(self.c,self.repo,self.policy)
        old=self.c.execute('SELECT id FROM target_histories').fetchall()
        (self.repo/'docs'/'next.json').write_text('{"name":"New source", "url":"https://example.invalid/new"}')
        self.g('add','.'); self.g('commit','-m','more'); self.g('update-ref','refs/remotes/bct/main',self.g('rev-parse','HEAD').decode().strip())
        b.import_git(self.c,self.repo,self.policy)
        self.assertEqual(old,self.c.execute('SELECT id FROM target_histories').fetchall())
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM imports').fetchone()[0],2)
    def test_11_no_freeze_without_research(self):
        b.import_git(self.c,self.repo,self.policy)
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM freezes').fetchone()[0],0)
    def test_12_export_has_no_fake_prices(self):
        b.import_git(self.c,self.repo,self.policy); b.export(self.c,self.root/'exports')
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM market_snapshots').fetchone()[0],0)
        self.assertTrue((self.root/'exports'/'entity-mentions.json').exists())
    def test_13_required_sources(self):
        self.g('update-ref','-d','refs/remotes/bct/data')
        with self.assertRaises(ValueError): b.import_git(self.c,self.repo,self.policy)
    def test_14_snapshot_deduplication(self):
        b.import_git(self.c,self.repo,self.policy)
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM source_blobs').fetchone()[0],3)
        self.assertEqual(self.c.execute("SELECT COUNT(*) FROM source_files WHERE disposition='IMPORTED'").fetchone()[0],9)
    def test_15_malformed_json_preserved(self):
        raw=b'{broken'; blob=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        with self.c: errors=b.import_blob(self.c,blob,raw,'bad.json')
        self.assertTrue(errors[0]['raw_preserved']); self.assertEqual(b.verify(self.c)['source_hash_errors'],0)

if __name__=='__main__': unittest.main()
