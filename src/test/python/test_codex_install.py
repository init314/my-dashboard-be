"""Offline installation checks use executable archives and preserve existing auth data."""
import io
from pathlib import Path
import tarfile
import tempfile
import types
import unittest
from unittest.mock import patch

from test_studio_remote import remote


class CodexInstallTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.home = Path(self.folder.name)
        self.binary = self.home / '.local/bin/codex'
        self.binary.parent.mkdir(parents=True)
        self.binary.write_text('#!/bin/sh\necho codex-cli 0.154.0\n')
        self.binary.chmod(0o755)
        self.auth = self.home / '.codex/auth.json'
        self.auth.parent.mkdir()
        self.auth.write_text('offline-auth-fixture')

    def tearDown(self):
        self.folder.cleanup()

    def install(self, valid=True, missing_host=False):
        archive = io.BytesIO()
        data = b'#!/bin/sh\necho codex-cli 0.157.1\n'
        with tarfile.open(fileobj=archive, mode='w:gz') as tar:
            for name in remote.CODEX_PACKAGE_FILES:
                if missing_host and name == 'bin/codex-code-mode-host': continue
                member = tarfile.TarInfo(name)
                member.size = len(data)
                member.mode = 0o755
                tar.addfile(member, io.BytesIO(data))
        archive.seek(0)
        digest = '0e211868c9fd73cb49ad35ac675b5eafdf6b9f453df8a493df980c59a590fe5f' if valid else 'invalid'
        with patch.object(remote.Path, 'home', return_value=self.home), \
             patch.object(remote.os, 'uname', return_value=types.SimpleNamespace(machine='x86_64')), \
             patch.object(remote.urllib.request, 'urlopen', return_value=archive) as download, \
             patch.object(remote.hashlib, 'sha256') as hashing:
            hashing.return_value.hexdigest.return_value = digest
            result = remote.setup(include_github=False)
            return result, download.call_count

    def test_upgrade_and_same_version_reuse_preserve_auth(self):
        result, downloads = self.install()
        self.assertEqual(result['codex'], 'codex-cli 0.157.1')
        self.assertEqual(downloads, 1)
        result, downloads = self.install()
        self.assertEqual(downloads, 0)
        self.assertEqual(self.auth.read_text(), 'offline-auth-fixture')

    def test_hash_failure_preserves_previous_binary(self):
        with self.assertRaises(remote.Failure):
            self.install(valid=False)
        self.assertIn('0.154.0', self.binary.read_text())
        self.assertEqual(self.auth.read_text(), 'offline-auth-fixture')

    def test_current_binary_without_helper_is_repaired(self):
        self.binary.write_text('#!/bin/sh\necho codex-cli 0.157.1\n')
        result, downloads = self.install()
        self.assertEqual(downloads, 1)
        self.assertTrue(self.binary.resolve().with_name('codex-code-mode-host').is_file())
        self.assertEqual(self.auth.read_text(), 'offline-auth-fixture')

    def test_incomplete_package_preserves_previous_binary(self):
        with self.assertRaises(remote.Failure):
            self.install(missing_host=True)
        self.assertIn('0.154.0', self.binary.read_text())


if __name__ == '__main__':
    unittest.main()
