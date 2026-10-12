"""Archive/entrypoint unit tests; fake attacks never replace the real fixture."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import zipfile
import replay as module

FIXTURES = Path(__file__).parent / 'fixtures'


class PinnedReplay(unittest.TestCase):
    def setUp(self):
        self.index = json.loads((FIXTURES / 'index.json').read_text())
        self.archive = FIXTURES / self.index['archive_name']

    def test_original_byte_inventory(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            module.unpack_capture(self.archive, root, self.index)
            self.assertEqual(len(list((root/'capture/raw').glob('*.bin'))), 38)
            self.assertEqual(len((root/'capture/requests.jsonl').read_text().splitlines()), 80)

    def test_changed_archive_rejected(self):
        with TemporaryDirectory() as tmp:
            p=Path(tmp)/'bad.zip';p.write_bytes(self.archive.read_bytes()+b'changed')
            with self.assertRaisesRegex(ValueError, 'checksum'):
                module.unpack_capture(p,Path(tmp)/'out',self.index)

    def test_changed_file_hash_rejected_before_writes(self):
        index=deepcopy(self.index)
        index['files']['capture/config.json']['sha256']='0'*64
        with TemporaryDirectory() as tmp:
            root=Path(tmp)/'out'
            with self.assertRaisesRegex(ValueError,'byte inventory'):
                module.unpack_capture(self.archive,root,index)
            self.assertFalse(root.exists())

    def test_missing_inventory_entry(self):
        index=deepcopy(self.index);del index['files']['capture/completion.json']
        with TemporaryDirectory() as tmp, self.assertRaisesRegex(ValueError,'inventory'):
            module.unpack_capture(self.archive,Path(tmp),index)

    def _fake(self, root, bad_name, mode):
        p=root/'synthetic-attack.zip';files={}
        with zipfile.ZipFile(p,'w') as z:
            for name in ['capture/config.json','capture/completion.json',bad_name]:
                info=zipfile.ZipInfo(name);info.external_attr=mode<<16
                z.writestr(info,b'{}');files[name]={'bytes':2,'sha256':sha256(b'{}').hexdigest()}
        return p,{'schema':'s5.raw-fixture-index.v1','archive_sha256':sha256(p.read_bytes()).hexdigest(),'files':files}

    def test_path_and_symlink_defenses(self):
        for name,mode in [('../escape',0o100644),('capture/requests.jsonl',0o120777)]:
            with self.subTest(name=name,mode=mode),TemporaryDirectory() as tmp:
                root=Path(tmp);p,index=self._fake(root,name,mode)
                with self.assertRaisesRegex(ValueError,'unsafe'):
                    module.unpack_capture(p,root/'out',index)
                self.assertFalse((root/'out').exists())

    def test_duplicate_members_rejected(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp);p,index=self._fake(root,'capture/requests.jsonl',0o100644)
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter('ignore',UserWarning)
                with zipfile.ZipFile(p,'a') as z:z.writestr('capture/config.json',b'{}')
            index['archive_sha256']=sha256(p.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError,'inventory'):
                module.unpack_capture(p,root/'out',index)

    def test_existing_output_never_runs_analysis(self):
        with TemporaryDirectory() as tmp:
            p=Path(tmp)/'result.json';p.write_bytes(b'original')
            with patch.object(module,'replay') as analysis:
                with self.assertRaises(FileExistsError):module.write_report(p)
                analysis.assert_not_called()
            self.assertEqual(p.read_bytes(),b'original')


if __name__ == '__main__':unittest.main()
