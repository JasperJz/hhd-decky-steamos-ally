import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from tools.package import FILES, package


class PackageTests(unittest.TestCase):
    def test_decky_archive_layout_and_extracted_runtime(self):
        with tempfile.TemporaryDirectory() as output:
            archive = package(output)
            with zipfile.ZipFile(archive) as z:
                self.assertIsNone(z.testzip())
                # Decky's development ZIP importer requires exactly one top-level plugin.json.
                manifests = [p for p in z.namelist() if p.endswith('/plugin.json') and p.count('/') == 1]
                self.assertEqual(manifests, ['hhd-decky/plugin.json'])
                self.assertEqual(set(z.namelist()), {'hhd-decky/' + p for p in FILES})
                manifest = json.loads(z.read(manifests[0]))
                self.assertEqual(manifest['name'], 'Handheld Daemon')
                self.assertIn('root', manifest['flags'])
                self.assertNotIn('api_version', manifest)
                compile(z.read('hhd-decky/main.py'), 'main.py', 'exec')
                z.extractall(Path(output) / 'unpacked')
                self.assertTrue((Path(output) / 'unpacked/hhd-decky/dist/index.js').is_file())
            digest = hashlib.sha256(archive.read_bytes()).hexdigest()
            self.assertEqual((Path(output) / 'SHA256SUMS').read_text().split()[0], digest)
            original = archive.read_bytes()
            self.assertEqual(package(output).read_bytes(), original)
