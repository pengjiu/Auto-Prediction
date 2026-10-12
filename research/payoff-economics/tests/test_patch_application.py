import importlib.util
import tempfile
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('patch',Path(__file__).resolve().parents[1]/'apply_patch.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)

class PatchTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.root=Path(self.temp.name)
        self.repo=self.root/'repo';self.repo.mkdir();self.overlay=self.root/'overlay';self.overlay.mkdir()
        (self.repo/'a.ts').write_text('before\n')
        self.manifest={'edits':[{'path':'a.ts','expected_blob':p.git_blob(b'before\n'),'replacements':[{'old':'before','new':'after'}]}]}
    def tearDown(self):self.temp.cleanup()
    def test_valid_preflight_does_not_write(self):
        changes=p.prepare(self.repo,self.manifest,self.overlay);self.assertEqual((self.repo/'a.ts').read_text(),'before\n');self.assertEqual(len(changes),1)
    def test_apply_modifies_and_adds(self):
        (self.overlay/'b.ts').write_text('new\n');p.apply(p.prepare(self.repo,self.manifest,self.overlay));self.assertEqual((self.repo/'a.ts').read_text(),'after\n');self.assertEqual((self.repo/'b.ts').read_text(),'new\n')
    def test_base_mismatch_fails_closed(self):
        (self.repo/'a.ts').write_text('user changes\n')
        with self.assertRaisesRegex(ValueError,'Base blob mismatch'):p.prepare(self.repo,self.manifest,self.overlay)
    def test_nonunique_anchor(self):
        (self.repo/'a.ts').write_text('before before');self.manifest['edits'][0]['expected_blob']=p.git_blob(b'before before')
        with self.assertRaisesRegex(ValueError,'non-unique'):p.prepare(self.repo,self.manifest,self.overlay)
    def test_existing_added_file_not_overwritten(self):
        (self.overlay/'a.ts').write_text('overwrite')
        with self.assertRaisesRegex(ValueError,'overwrite'):p.prepare(self.repo,self.manifest,self.overlay)
    def test_path_traversal(self):
        self.manifest['edits'][0]['path']='../outside'
        with self.assertRaisesRegex(ValueError,'Unsafe path'):p.prepare(self.repo,self.manifest,self.overlay)
    def test_symlink_refused(self):
        (self.repo/'a.ts').unlink();(self.repo/'a.ts').symlink_to(self.root/'outside')
        with self.assertRaisesRegex(ValueError,'Symlink'):p.prepare(self.repo,self.manifest,self.overlay)
    def test_change_after_preflight_refused(self):
        changes=p.prepare(self.repo,self.manifest,self.overlay);(self.repo/'a.ts').write_text('later edit')
        with self.assertRaisesRegex(ValueError,'after preflight'):p.apply(changes)
        self.assertEqual((self.repo/'a.ts').read_text(),'later edit')

if __name__=='__main__':unittest.main(verbosity=2)
